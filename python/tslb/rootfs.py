from tslb.CommonExceptions import *
from tslb import database as db
from tslb import settings
from tslb import tclm
from tslb.tclm import lock_X, lock_Splus, lock_S
from tslb.filesystem.FileOperations import mkdir_p
from tslb.VersionNumber import VersionNumber
from tslb import Architecture
import tslb.database.rootfs
import errno
import os
import re
import subprocess


class Image(object):
    """
    This object represents a rootfs image stored on a ceph rbd. It has methods
    for mounting it and properties to query parameters. An image is always read
    only to allow mounting it concurrently even though the used filesystem
    (ext4) does not have cluster features.

    While you have such an Image object the image is locked and therefore you
    can be sure it won't be deleted while you perform operations on it. But
    keep in mind that, once you dismissed it, everything may happen. Even if
    it's mounted (will result in cruel errors ...). I know this is c-style, but
    I don't want to make it more complicated (yet), and after all time is
    limited. So please bear with me.
    """

    def __init__(self, id, acquired_X=False, db_object=None):
        """
        Constructs an Image object if such an image exists in the database.

        :param id: The image's id
        :param acquire_X: Set to true if the image's lock is held in X mode by
            the caller. Mainly used by functions that create images.

        :param db_object: The db object representing this package. Use only of
            you ABSOLUTELY known what you are doing.

        :raises rootfs.NoSuchImage: If such an image does not exist.
        """
        self.id = id
        self.acquired_X = acquired_X
        self._packages = None

        # Acquire corresponding lock
        self.db_lock = tclm.define_lock('tslb.rootfs.images.{:d}'.format(self.id))

        if not self.acquired_X:
            self.db_lock.acquire_S()

        # Find corresponding DB object
        if db_object is None:
            with db.session_scope() as s:
                i = s.query(db.rootfs.Image)\
                    .filter(db.rootfs.Image.id == self.id).one_or_none()

                if i is None:
                    raise NoSuchImage(self.id)

                s.expunge(i)
                self.db_object = i

        else:
            self.db_object = db_object


    def __del__(self):
        if self.acquired_X:
            self.db_lock.release_X()
        else:
            self.db_lock.release_S()


    @property
    def in_available_list(self):
        """
        Look if the image is at the moment in the list of available images.
        Since other processes may alter the list, this needs to be done
        everytime one accesses this property.

        :rtype: bool
        """
        lk = tclm.define_lock('tslb.rootfs.available')

        with lock_S(lk):
            with db.session_scope() as s:
                cnt = s.query(db.rootfs.AvailableImage).filter(
                    db.rootfs.AvailableImage.id == self.id).count()

                return cnt > 0


    @property
    def packages(self):
        """
        Returns a list of packages in this image, order by name, arch, version.
        This property is essentially a shortcut for self.query_packages().

        :returns: A list of tuples like (name, arch integer, version number)
        :rtype: List(Tuple(str, int, VersionNumber))
        """
        return self.query_packages()


    def contains_package(self, name, arch=None, version=None):
        """
        Test if the image contains the specified package. The test my include
        an architecture or version filter.

        :param name: The package's name
        :param arch: The package's arch int/str or None (default)
        :param version: The package's version number or None (default)

        :type name: str
        :type arch: int or str or NoneType
        :type version: Anything accepted by VersionNumber's constructor or
            NoneType

        :rtype: bool
        """
        if arch is not None:
            arch = Architecture.to_int(arch)

        if version is not None:
            version = VersionNumber(version)

        with db.session_scope() as s:
            q = s.query(db.rootfs.ImageContent)\
                .filter(db.rootfs.ImageContent.id == self.id,
                    db.rootfs.ImageContent.package == name)

            if arch is not None:
                q = q.filter(db.rootfs.ImageContent.arch == arch)

            if version is not None:
                q = q.filter(db.rootfs.ImageContent.version == version)

            return q.count() > 0


    def query_packages(self, name=None, arch=None, version=None):
        """
        Query the packages which this image contains. Any of name, arch and
        version may be None. The liste returned is ordered by name, arch and
        version.

        :param name: The package's name or None (default)
        :param arch: The package's architecture or None (default)
        :param version: The package's version or None (default)

        :type name: str
        :type arch: int or str or NoneType
        :type version: Anything accepted by VersionNumber's constructor or
            NoneType

        :returns: A list of tuples like (name, arch integer, version number)
        :rtype: List(Tuple(str, int, VersionNumber))
        """
        with db.session_scope() as s:
            q = s.query(
                db.rootfs.ImageContent.package,
                db.rootfs.ImageContent.arch,
                db.rootfs.ImageContent.version)\
                .filter(db.rootfs.ImageContent.id == self.id)

            if name is not None:
                q = q.filter(db.rootfs.ImageContent.package == name)

            if arch is not None:
                arch = Architecture.to_int(arch)
                q = q.filter(db.rootfs.ImageContent.arch == arch)

            if version is not None:
                version = VersionNumber(version)
                q = q.filter(db.rootfs.ImageContent.version == version)

            q = q.order_by(db.rootfs.ImageContent.package,
                db.rootfs.ImageContent.arch,
                db.rootfs.ImageContent.version)

            return [ (p,a,v) for p,a,v in q ]


    # Actions
    def mount(self, namespace):
        """
        Maps and mounts the image in the specified `namespace', that is
        <temp_location>/rootfs/namespace/<image id>. Note that the image is
        mapped again for the mount if it is mapped already. Then simply two or
        more block devices are bound to the same image. Likewise it can be
        mounted multiple times in different namespaces; with a different block
        device each time.

        If the image has an @ro_base snapshot, the snapshot is mapped and
        mounted read only. If not, the image itself is mapped and mounted read-
        and writable if the lock is held in X mode, otherwise the image itself
        is mounted read only.

        :param namespace: The namespace in which the image shall be mounted.

        :raises ImageAlreadyMounted: If the image is mounted in the given
            namespace already. Note we don't differ between mounted already and
            in the process of being mounted already.

        :raises BaseException: If something goes wrong, should not happen
            during normal business, hence this can be used to cause program
            termination or similar.
        """
        namespace = str(namespace)

        # See if the image has an @ro_base snapshot
        has_ro_base = bool('ro_base' in _list_rbd_image_snapshots(self.id))

        # Create mountpoint (this will fail if the image is mounted already)
        base = os.path.join(settings.get_temp_location(), 'rootfs', namespace)
        mkdir_p(base)

        mountpoint = os.path.join(base, str(self.id))

        try:
            os.mkdir(mountpoint, 0o755)
        except FileExistsError:
            raise ImageAlreadyMounted(namespace, self.id)

        try:
            # Map
            block_device = _map_rbd_image(
                (str(self.id) + "@ro_base") if has_ro_base else self.id)

            try:
                # Mount
                if has_ro_base or not self.acquired_X:
                    cmd = ['mount', block_device, mountpoint, '-oro']
                else:
                    cmd = ['mount', block_device, mountpoint, '-orw']

                r = subprocess.call(cmd)
                if r != 0:
                    raise CommandFailed(cmd, r)

            except:
                _unmap_rbd_image(block_device, False)

        except:
            os.rmdir(mountpoint)
            raise


    def unmount(self, namespace):
        """
        Unmount and unmap the image in the given namespace. Be sure to not
        simultaniously run this function on the same namespace! Mountpoints are
        not locked ...

        :param namespace: The namespace
        :raises ImageNotMounted: If the image is not mounted in the given
            namespace.

        :raises BaseException: If something goes wrong.
        """
        mountpoint = os.path.join(settings.get_temp_location(), 'rootfs',
            namespace, str(self.id))

        if not os.path.isdir(mountpoint):
            raise ImageNotMounted(namespace, self.id)

        # Find the block device where the image is mapped.
        cmd = ['findmnt', mountpoint]

        r = subprocess.run(cmd, stdout=subprocess.PIPE)

        if r.returncode != 0:
            raise os.CommandFailed(cmd, r.returncode)

        lines = r.stdout.decode().split('\n')

        if len(lines) != 3:
            raise Exception(
                f"Failed to find block device for mounted image {self.id} in" +
                f" namespace {namespace}: returned lines {len(lines)} != 3")

        line = lines[1]
        m = re.match(r'^\S+\s+(\S+)', line)

        if not m:
            raise Exception(
                f"Failed to find block device for mounted image {self.id} in" +
                f" namespace {namespace}: no regex match in {line}")

        block_device = m.group(1)

        # Unmount
        cmd = ['umount', mountpoint]
        
        r = subprocess.call(cmd)

        if r != 0:
            raise CommandFailed(cmd, r)

        # Unmap
        _unmap_rbd_image(block_device)

        # Delete mountpoint
        os.rmdir(mountpoint)


    def publish(self):
        """
        Create the `ro_base` snapshot if it does not exist yet and add the
        image to the list of available images, if it is not listed there
        already. The image's lock must be acquired in X mode (for creating the
        snapshot).

        :raises RuntimeError: If the lock is not held in X mode.
        :raises BaseException: If an operation fails.
        """
        if not self.acquired_X:
            raise RuntimeError(
                "Cannot publish an Image will it is not locked exclusively.")

        # Create protected snapshot
        if 'ro_base' not in _list_rbd_image_snapshots(self.id):
            cmd = ['rbd', 'snap', 'create',
                *settings.get_ceph_cmd_conn_params(),
                settings.get_ceph_rootfs_rbd_pool() + '/' + str(self.id) +
                '@ro_base']

            r = subprocess.call(cmd)
            if r != 0:
                raise CommandFailed(cmd, r)

            cmd = ['rbd', 'snap', 'protect',
                *settings.get_ceph_cmd_conn_params(),
                settings.get_ceph_rootfs_rbd_pool() + '/' + str(self.id) +
                '@ro_base']

            r = subprocess.call(cmd)
            if r != 0:
                raise CommandFailed(cmd, r)

        # Add this image's id to the list of available images
        lk = tclm.define_lock('tslb.rootfs.available')
        with lock_X(lk):
            with db.session_scope() as s:
                cnt = s.query(db.rootfs.AvailableImage)\
                    .filter(db.rootfs.AvailableImage.id == self.id).count()

                if cnt  == 0:
                    ai = db.rootfs.AvailableImage()
                    ai.id = self.id
                    s.add(ai)


    def unpublish(self):
        """
        Remove the image from the list of available images if it is listed
        there. Otherwise do nothing.
        """
        lk = tclm.define_lock('tslb.rootfs.available')
        with lock_X(lk):
            with db.session_scope() as s:
                ai = s.query(db.rootfs.AvailableImage)\
                    .filter(db.rootfs.AvailableImage.id == self.id)\
                    .one_or_none()

                if ai is not None:
                    s.delete(ai)


    def add_packages_to_list(self, pkgs):
        """
        Add packages to the list of installed packages. This requires an X lock
        on the image.

        :param pkgs: A list of packages to append.
        :type pkgs: List(Tuple(str, int/atr, <convertible to VersionNumber>))

        :raises RuntimeError: If the lock is not acquired in X mode.
        """
        if not self.acquired_X:
            raise RuntimeError(
                "Cannot alter an Image that is not locked exclusively.")

        with db.session_scope() as s:
            for name, arch, version in pkgs:
                arch = Architecture.to_int(arch)
                version = VersionNumber(version)
                s.add(db.rootfs.ImageContent(self.id, name, arch, version))


    def remove_packages_from_list(self, pkgs):
        """
        Remove packages from the list of installed packages. This requires an X
        lock on the image.

        :param pkgs: A list of packages to remove.
        :type pkgs: List(Tuple(str, int/atr, <convertible to VersionNumber>))

        :raises RuntimeError: If the lock is not acquired in X mode.
        """
        if not self.acquired_X:
            raise RuntimeError(
                "Cannot alter an Image that is not locked exclusively.")

        with db.session_scope() as s:
            for name, arch, version in pkgs:
                arch = Architecture.to_int(arch)
                version = VersionNumber(version)

                # OK, this is worse than only delete statements but I'm too
                # lazy right now.
                ac = s.query(db.rootfs.ImageContent).filter(
                    db.rootfs.ImageContent.id == self.id,
                    db.rootfs.ImageContent.package == name,
                    db.rootfs.ImageContent.arch == arch,
                    db.rootfs.ImageContent.version == version).one_or_none()

                if ac is not None:
                    s.delete(ac)


    def __repr__(self):
        return "tslb.rootfs.Image(%d)" % self.id


def _delete_rbd_image(name, raises=True):
    """
    For internal use in this module only; deletes a rbd image using the rbd
    command.

    :param raises: If False, errors are suppressed (useful if used to clean up
        in case something went wrong. Then it's usually not beneficial to know
        that cleanup failed, too.).

    :raises CommonExceptions.CommandFailed: If the command failed to run and
        raises is True.
    """
    cmd = ['rbd', 'rm', *settings.get_ceph_cmd_conn_params(),
        settings.get_ceph_rootfs_rbd_pool() + '/' + str(name)]

    r = subprocess.call(cmd)
    if r != 0 and raises:
        raise CommandFailed(cmd, r)


def _map_rbd_image(name):
    """
    For internal use only. Maps the specified rbd image to a block device.

    :param name: Name of the rbd image
    :returns: The path to the block device
    :rtype: str
    :raises CommonExceptions.CommandFailed: If the underlying rbd command
        failed.
    """
    cmd = ['rbd', 'map', *settings.get_ceph_cmd_conn_params(),
        settings.get_ceph_rootfs_rbd_pool() + '/' + str(name)]

    r = subprocess.run(cmd, stdout=subprocess.PIPE)
    if r.returncode != 0:
        raise CommandFailed(cmd, r.returncode)

    return r.stdout.decode().replace('\n','')

def _unmap_rbd_image(path, raises=True):
    """
    For internal use only. Unmaps the specified rbd block device.

    :param path: The path to the block device
    :param raises: If False, errors are suppressed (useful if used to clean up
        in case something went wrong. Then it's usually not beneficial to know
        that cleanup failed, too.).

    :raises CommonExceptions.CommandFailed: If the command failed to run and
        raises is True.
    """
    cmd = ['rbd', 'unmap', *settings.get_ceph_cmd_conn_params(), str(path)]

    r =  subprocess.call(cmd)
    if r != 0 and raises:
        raise CommandFailed(cmd, r)


def _list_rbd_image_snapshots(name):
    """
    For internal use only. List the snapshots of a rbd image. I am sorry but if
    the image does not exist, all you get is a CommandFailed and nothing like
    ENOENT or whatever.
    
    :param name: The name of the image.
    :raises CommonExceptions.CommandFailed: If an unerlying rbd command failed.
    """
    cmd = ['rbd', 'snap', 'ls', *settings.get_ceph_cmd_conn_params(),
        settings.get_ceph_rootfs_rbd_pool() + '/' + str(name)]

    r = subprocess.run(cmd, stdout=subprocess.PIPE)
    if r.returncode != 0:
        raise CommandFailed(cmd, r.returncode)

    lines = r.stdout.decode().split('\n')[1:-1]
    return [re.match(r'\s*\S+\s+(\S+)', line).group(1) for line in lines]


def list_images():
    """
    List all (published and unpublished) rootfs images.

    :rtype: List(int)
    """
    with db.session_scope() as s:
        q = s.query(db.rootfs.Image.id)
        return [t[0] for t in q]


def find_image(requirements):
    """
    Find a published rootfs image that fulfills certain criteria. Basically one
    alway wants to find an image with certain installed packages. The question
    is only how, since such an image may not exist, or if it exists, may have
    many unneeded packages, whereas a different one could miss a package but
    not have any extra one. Moreover one may want to have exact version
    matches, just bigger equal- or maybe no version requirements at all.

    For now, this function tries to fulfill all given package constraints. If
    this is not possible it selects an image with least missing and disruptiv
    packages. A package is disruptive if it violates a constraint and hence
    needs to be removed. Missing and disruptive packages are weighted equally.
    From the remaining, feasible package set one with least extra packages is
    choosen.

    :param requirements: Required packages and versions
    :type requirements: tslb.Constraint.DependencyList of (str:name, int:arch)
        tuples

    :returns: The image
    :rtype: tslb.rootfs.Image
    """
    with lock_S(tclm.define_lock('tslb.rootfs.available')):
        # Calculating an error function for each image
        with db.session_scope() as s:
            available_imgs =\
                    [e[0] for e in s.query(db.rootfs.AvailableImage.id)]

            # List of tuples (error, image id)
            error_function = []

            required_packages = set(requirements.get_required())

            for img_id in available_imgs:
                # Compute the error
                e = 0

                # How many packages are missing or need to be updated?
                for n,a in required_packages:
                    if s.query(db.rootfs.ImageContent).filter(
                        db.rootfs.ImageContent.id == img_id,
                        db.rootfs.ImageContent.package == n,
                        db.rootfs.ImageContent.arch == a).count() == 0:

                        e += 1

                # How many packages are disruptiv i.e. conflict with the
                # requirements?
                content = s.query(
                    db.rootfs.ImageContent.package,
                    db.rootfs.ImageContent.arch,
                    db.rootfs.ImageContent.version)\
                        .filter(db.rootfs.ImageContent.id == img_id)

                for p,a,v in content:
                    if ((p,a),v) not in requirements:
                        e += 1

                # Last, compute the number of extra packages. Make sure that
                # having one of the above deviations is alway worse. Therefore,
                # the maximum cost that can be added by the extra packages must
                # be lower than 1.
                extra = 0

                content = s.query(
                    db.rootfs.ImageContent.package,
                    db.rootfs.ImageContent.arch)\
                        .filter(db.rootfs.ImageContent.id == img_id).distinct()

                for p,a in content:
                    if (p,a) not in required_packages:
                        extra += 1

                e += (1 - 1 / (extra + 1))

                error_function.append((e, img_id))

        # Find the best one
        return Image(min(error_function)[1])


def create_empty_image():
    """
    Creates an empty rootfs image, including the rbd image and an empty ext4
    filesystem therein.

    The lock of the new image is left in X state. This function aims to be
    transactional in case of failing single operations.

    :returns: The newly created image.
    :rtype: rootfs.Image
    :raises BaseException: If something goes wrong, but not on purpose of
        communicating business-as-usual errors.
    """
    # Create a database tuple
    s = db.get_session()

    try:
        di = db.rootfs.Image()
        s.add(di)
        s.flush()

        img_id = di.id

        # Create and aquire a lock for the image
        lk = tclm.define_lock('tslb.rootfs.images.{:d}'.format(img_id))

        with lock_Splus(tclm.define_lock('tslb.rootfs.images')):
            lk.create(True)

    except:
        s.rollback()
        s.close()
        raise

    new_image = None

    try:
        # Create a ceph rbd image
        cmd = ['rbd', 'create', *settings.get_ceph_cmd_conn_params(),
            '--size', '102400',
            settings.get_ceph_rootfs_rbd_pool() + '/' + str(img_id)]

        r = subprocess.call(cmd)
        if r != 0:
            raise CommandFailed(cmd, r)

        try:
            # Map and format the image
            block_device = _map_rbd_image(img_id)

            try:
                cmd = ['mke2fs', '-t', 'ext4', block_device]

                r = subprocess.call(cmd)
                if r != 0:
                    raise CommandFailed(cmd, r)

            except:
                _unmap_rbd_image(img_id, False)
                raise

            # Unmap the image
            _unmap_rbd_image(block_device)

            # Commit to DB and return a new rootfs.Image object
            s.expunge(di)
            new_image = Image(img_id, acquired_X=True, db_object = di)
            s.commit()
            return new_image

        except:
            _delete_rbd_image(img_id, False)
            raise

    except:
        if new_image is None:
            lk.release_X()

        s.rollback()
        raise

    finally:
        s.close()


def cow_clone_image(src):
    """
    Creates a new rootfs image as cow clone from another image. The other
    image, specified in src, must be published (be in the list of available
    images). Otherwise a ValueError is thrown.

    The lock of the new image is left in X state. This function aims to be
    transactional in case of failing single operations.

    :param src: The source image
    :type src: tslb.rootfs.Image
    :returns: The newly created image
    :rtype tslb.rootfs.Image

    :raises ValueError: If src is not published.
    :raises BaseException: If an underlying operation fails.
    """
    # src must be published
    if not src.in_available_list:
        raise ValueError(f"The source image ({src.id}) is not published.")

    # Create a database tuple
    s = db.get_session()

    try:
        di = db.rootfs.Image()
        s.add(di)
        s.flush()

        img_id = di.id

        # Create and aquire a lock for the image
        lk = tclm.define_lock('tslb.rootfs.images.{:d}'.format(img_id))

        with lock_Splus(tclm.define_lock('tslb.rootfs.images')):
            lk.create(True)

    except:
        s.rollback()
        s.close()
        raise

    new_image = None

    try:
        # Copy content list
        q = s.query(
            db.rootfs.ImageContent.package,
            db.rootfs.ImageContent.arch,
            db.rootfs.ImageContent.version)\
                .filter(db.rootfs.ImageContent.id == src.id)

        for p, a, v in q:
            s.add(db.rootfs.ImageContent(img_id, p, a, v))

        # Clone the source image
        cmd = ['rbd', 'clone', *settings.get_ceph_cmd_conn_params(),
            settings.get_ceph_rootfs_rbd_pool() + '/' + str(src.id) +
            '@ro_base',
            settings.get_ceph_rootfs_rbd_pool() + '/' + str(img_id)]

        r = subprocess.call(cmd)

        if r != 0:
            raise CommandFailed(cmd, r)

        try:
            # Commit to DB and return a new rootfs.Image object
            s.expunge(di)
            new_image = Image(img_id, acquired_X=True, db_object=di)
            s.commit()
            return new_image

        except:
            _delete_rbd_image(img_id, False)
            raise

    except:
        if new_image is None:
            lk.release_X()

        s.rollback()
        raise

    finally:
        s.close()


def delete_image(img_id):
    """
    Deletes an image. If the image is still published, it is unpublished first.
    If no such image exists, the function does nothing.

    Concurrently calling this function on the same image is perfectly fine.
    It's just that only the first one will delete the image, the other callers
    simply do nothing.

    :param img_id: The image's id.
    :type img_id: int
    """
    # Unpublish first if required.
    lk = tclm.define_lock('tslb.rootfs.available')

    with lock_X(lk):
        with db.session_scope() as s:
            ai = s.query(db.rootfs.AvailableImage)\
                .filter(db.rootfs.AvailableImage.id == img_id).one_or_none()

            if ai is not None:
                s.delete(ai)

    # Delete the image (requires an X lock on the image to ensure all
    # operations completed.
    lk = tclm.define_lock('tslb.rootfs.images.' + str(img_id))

    try:
        with lock_X(lk):
            # Delete from db
            with db.session_scope() as s:
                di = s.query(db.rootfs.Image)\
                        .filter(db.rootfs.Image.id == img_id).one_or_none()

                if di is not None:
                    s.delete(di)

            # Unprotect and purge rbd snapshots
            try:
                snapshots = _list_rbd_image_snapshots(img_id)

            except CommandFailed as e:
                if e.returncode == errno.ENOENT:
                    snapshots = []
                else:
                    raise

            if 'ro_base' in snapshots:
                cmd = ['rbd', 'snap', 'unprotect',
                        *settings.get_ceph_cmd_conn_params(),
                        settings.get_ceph_rootfs_rbd_pool() + '/' + str(img_id)
                        + '@ro_base']

                r = subprocess.call(cmd)
                if r != 0 and r != errno.ENOENT:
                    raise CommandFailed(cmd, r)

            cmd = ['rbd', 'snap', 'purge',
                    *settings.get_ceph_cmd_conn_params(),
                    settings.get_ceph_rootfs_rbd_pool() + '/' + str(img_id)]

            r = subprocess.call(cmd)
            if r != 0 and r != errno.ENOENT:
                raise CommandFailed(cmd, r)

            # Delete rbd image
            cmd = ['rbd', 'rm',
                    *settings.get_ceph_cmd_conn_params(),
                    settings.get_ceph_rootfs_rbd_pool() + '/' + str(img_id)]

            r = subprocess.call(cmd)
            if r != 0 and r != errno.ENOENT:
                raise CommandFailed(cmd, r)


    except RuntimeError as e:
        if str(e) == 'No such lock.':
            pass
        else:
            raise


# *************************** Exceptions **************************************
class RootFSException(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class NoSuchImage(RootFSException):
    def __init__(self, img_id):
        super().__init__(f"No such image: {img_id}.")


class ImageAlreadyMounted(RootFSException):
    def __init__(self, namespace, img_id):
        super().__init__(
            f"Image {img_id} mounted already in namespace {namespace}.")


class ImageNotMounted(RootFSException):
    def __init__(self, namespace, img_id):
        super().__init__(
                f"Image {img_id} is not mounted in namespace {namespace}.")
