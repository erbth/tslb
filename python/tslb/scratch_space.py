"""
A module that provides persistent scratch space in form of named images that
contain ext4 filesystems. The images support snapshot that can be rolled back.
They are placed on a ceph RBD pool.

Such a scratch space image is called 'scratch space'.
"""
import re
import os
import subprocess
import rados
import rbd
from contextlib import contextmanager
from tslb import basic_utils
from tslb import settings
from tslb import tclm
from tslb.filesystem.FileOperations import mkdir_p
from tslb.tclm import lock_X, lock_Splus, lock_S
from tslb.CommonExceptions import CommandFailed


def create_locks(rbd_pool=None):
    """
    To be called before any operation after the TCLM was restarted, this
    creates all necessary locks for the scratch space list and all existing
    scratch spaces.

    :param str rbd_pool: Specifies the RBD pool to use. If it is set to None
        (default), the pool is read from the system.ini config file.
    """
    if rbd_pool == None:
        rbd_pool = settings.get_ceph_scratch_space_rbd_pool()

    list_lock = tclm.define_lock('tslb.scratch_space.%s.space_list' % rbd_pool)
    spaces_lock_path = 'tslb.scratch_space.%s.spaces' % rbd_pool
    spaces_lock = tclm.define_lock(spaces_lock_path)

    list_lock.create(True)
    list_lock.release_X()

    spaces_lock.create(True)

    try:
        pool = ScratchSpacePool(rbd_pool)
        for name in pool.list_scratch_spaces():
            lk = tclm.define_lock(spaces_lock_path + '.' + name.replace('.', '_'))
            lk.create(False)

    finally:
        spaces_lock.release_X()


class ScratchSpacePool:
    """
    A pool of scratch space that represents a RADOS pool on which the RBD
    images are stored. It is used to create, delete and find scratch spaces.

    This class is only thread safe if called from a single flow of execution.
    I.e. it does not protect the connection to RADOS with a mutex.

    :param str rbd_pool: Specifies the RBD pool to use. If it is set to None
        (default), the pool is read from the system.ini config file.
    """
    def __init__(self, rbd_pool=None):
        if rbd_pool == None:
            rbd_pool = settings.get_ceph_scratch_space_rbd_pool()

        self._rados = rados.Rados(name=settings.get_ceph_name())
        self._rados.conf_parse_argv(settings.get_ceph_cmd_conn_params())
        self._rados.connect()

        try:
            self._rbd_pool = rbd_pool
            self._ioctx = None

            # RW locks
            self._list_lock = tclm.define_lock(
                'tslb.scratch_space.%s.space_list' % rbd_pool)

            self._space_lock_base = 'tslb.scratch_space.%s.spaces.' % rbd_pool

        except:
            self._rados.shutdown()
            raise


    def __del__(self):
        self._rados.shutdown()


    # Properties
    @property
    def space_lock_base(self):
        return self._space_lock_base


    @contextmanager
    def get_ioctx(self):
        if self._ioctx is not None:
            yield self._ioctx
        else:
            with self._rados.open_ioctx(self._rbd_pool) as ioctx:
                self._ioctx = ioctx
                try:
                    yield ioctx
                finally:
                    self._ioctx = None


    def get_scratch_space(self, name, rw, size):
        """
        Find an existing scratch space or create a new one.

        :param str name: The scratch space's name
        :param bool rw: True means that the scratch space will be mounted
            read-writable and be locked exclusively, False means it will be
            mounted read-only and locked shared.
        :param int size: The size of the scratch space in bytes if a new one
            has to be created.
        :raises BaseException: if something fails.
        """
        with self.get_ioctx() as ioctx:
            rbd_inst = rbd.RBD()

            with lock_X(self._list_lock):
                # Determine if the requested image exists already.
                exists_already = False

                for img_name in rbd_inst.list(ioctx):
                    if img_name == name:
                        exists_already = True
                        break

                if exists_already:
                    return ScratchSpace(self, name, rw)

                # Create a new image and format it.
                rbd_inst.create(ioctx, name, size)

                try:
                    dev = _map_rbd_image(name)

                    try:
                        r = subprocess.run(['mke2fs', '-t', 'ext4', dev])

                        if r.returncode != 0:
                            raise Exception("Mount failed with exit-code %d." % r.returncode)

                        _unmap_rbd_image(dev)
                        return ScratchSpace(self, name, rw, create_lock=True)

                    except:
                        _unmap_rbd_image(dev, raises=False)
                        raise

                except:
                    rbd_inst.remove(ioctx, name)
                    raise


    def delete_scratch_space(self, name):
        """
        Deletes the given scratch space if it exists.

        :param str name: The scratch space's name
        :returns: True if the scratch space has been deleted, False if no such
            scratch space existed.
        :raises BaseException: if something fails.
        """
        with self.get_ioctx() as ioctx:
            rbd_inst = rbd.RBD()

            with lock_X(self._list_lock):
                # Determine if the requested image exists
                exists = False

                for img_name in rbd_inst.list(ioctx):
                    if img_name == name:
                        exists = True
                        break

                if not exists:
                    return False

                # Delete the image and its snapshots
                with lock_X(tclm.define_lock(self.space_lock_base + name.replace('.', '_'))):
                    img = rbd.Image(ioctx, name)
                    snaps = [snap['name'] for snap in img.list_snaps()]

                    for snap in snaps:
                        img.remove_snap(snap)

                    del img

                    rbd_inst.remove(ioctx, name)

        return True


    def list_scratch_spaces(self):
        """
        List all scratch spaces in the pool

        :returns List(str): A list of scratch space names.
        :raises BaseException: if something fails.
        """
        with self.get_ioctx() as ioctx:
            rbd_inst = rbd.RBD()

            with lock_X(self._list_lock):
                return rbd_inst.list(ioctx)


class ScratchSpace:
    """
    This class represents a single scratch space. Instances of this
    `ScratchSpace` class must only be created by `ScratchSpacePool`.

    This class is only thread safe if called from a single flow of execution.
    I.e. it does not protect the connection to RADOS with a mutex.

    The initializer has to lock the image, and mount or map it appropriately.
    If :param create_lock: is true, it should moreover create a lock for the
    image at TCLM.
    """
    def __init__(self, scratch_space_pool, name, rw, create_lock=False):
        self._pool = scratch_space_pool
        self._name = name
        self._rw = rw
        self._lk = tclm.define_lock(self._pool.space_lock_base + self._name.replace('.', '_'))
        self._mountpoint = os.path.join(
            settings.get_temp_location(), 'scratch_space', self._name)

        if create_lock:
            self._lk.create(True)

            if not self._rw:
                self._lk.acquire_Splus()
                self._lk.release_X()
                self._lk.acquire_S()
                self._lk.release_Splus()

        else:
            if self._rw:
                self._lk.acquire_X()
            else:
                self._lk.acquire_S()


    def __del__(self):
        self.unmount()

        if self._rw:
            self._lk.release_X()
        else:
            self._lk.release_S()


    # Basic properties
    @property
    def name(self):
        return self._name


    @property
    def mounted(self):
        cmd = ['findmnt', self._mountpoint]

        r = subprocess.run(cmd, stdout=subprocess.DEVNULL)
        return r.returncode == 0


    @property
    def mount_path(self):
        return self._mountpoint


    @property
    def rw(self):
        return self._rw


    # Mounting and unmounting
    def mount(self):
        """
        Mount the image if it is not mounted already.

        :raises RuntimeError: If the operation fails.
        """
        if self.mounted:
            return

        # Map
        dev = _map_rbd_image(self.name, ro=not self._rw)

        try:

            # Mount
            if not os.path.isdir(self._mountpoint):
                mkdir_p(self._mountpoint)

            _mount(dev, self._mountpoint, ro=not self._rw)

        except:
            _unmap_rbd_image(dev, raises=False)
            raise


    def unmount(self):
        """
        Unmount the image if it is currently mounted.

        :raises RuntimeError: If the operation fails.
        """
        # Find the device, if any.
        dev = None

        with open('/proc/mounts', 'r', encoding='UTF-8') as f:
            for line in f:
                m = re.match(r'^(\S+)\s+(\S+)\s+.*', line)
                if m and m.group(2) == self._mountpoint:
                    dev = m.group(1)
                    break

        if dev is None:
            return

        # Unmount
        _umount(self._mountpoint)

        # Unmap
        _unmap_rbd_image(dev)

        # Delete mountpoint
        os.rmdir(self._mountpoint)


    # Snapshots
    def create_snapshot(self, name):
        """
        Create a snapshot of the image. This can only be done if the image is
        acquired read- and writable.

        :param str name: The name of the snapshot to be created.
        :raises SnapshotExists: if the snapshot exists already.
        :raises NotWritable: if the image is acquired read-only.
        """
        if not self.rw:
            raise NotWritable

        with self._pool.get_ioctx() as ioctx:
            if self.has_snapshot(name):
                raise SnapshotExists

            img = rbd.Image(ioctx, self._name)
            freeze = self.mounted and self._rw

            # Freeze the fs if it is mounted read- and writable
            if freeze:
                if subprocess.run(['fsfreeze', '-f', self._mountpoint]).returncode != 0:
                    raise RuntimeError(
                        "Failed to freeze the filesystem in scratch space %s." %
                        self._name)

            try:
                img.create_snap(name)

            finally:
                if freeze:
                    if subprocess.run(['fsfreeze', '-u', self._mountpoint]).returncode != 0:
                        raise RuntimeError(
                            "Failed to thaw the filesystem in scratch space %s." %
                            self._name)


    def delete_snapshot(self, name):
        """
        Delete the snapshot with the given name. This can only be done if the
        image is locked for writing.

        :param str name: The snapshot's name.
        :raises NoSuchSnapshot: if the snapshot does not exist.
        :raises NotWritable: if the image is not locked for writing.
        """
        if not self.rw:
            raise NotWritable

        with self._pool.get_ioctx() as ioctx:
            if not self.has_snapshot(name):
                raise NoSuchSnapshot

            img = rbd.Image(ioctx, self._name)
            img.remove_snap(name)


    def revert_snapshot(self, name):
        """
        Revert the scratch space to the state of the snapshot with the given
        name. The snapshot is not deleted by this operation. This operation
        requires that the image is locked for writing.

        Note that this will temporarily unmount the scratch space.

        :param str name: The snapshot's name
        :raises NoSuchSnapshot: if the snapshot does not exist.
        :raises NotWritable: if the image is not locked for writing.
        """
        if not self.rw:
            raise NotWritable


        was_mounted = self.mounted

        with self._pool.get_ioctx() as ioctx:
            if not self.has_snapshot(name):
                raise NoSuchSnapshot

            if was_mounted:
                self.unmount()

            try:
                img = rbd.Image(ioctx, self._name)
                img.rollback_to_snap(name)

            except BaseException as e:
                raise RuntimeError("Failed to rollback snapshot: %s" % e)

            finally:
                if was_mounted:
                    self.mount()



    def has_snapshot(self, name):
        """
        Check if a snapshot with the given name exists.

        :param str name: The snapshot's name.
        :returns bool: True such a snapshot exists, False otherwise.
        """
        return name in self.list_snapshots()


    def list_snapshots(self):
        """
        List the scratch space's snapshots.

        :returns List(str): A list of all snapshots of the scratch space.
        """
        snaps = []

        with self._pool.get_ioctx() as ioctx:
            img = rbd.Image(ioctx, self._name)

            snaps = [snap['name'] for snap in img.list_snaps()]

        return snaps


    # Mounting a snapshot
    def is_snapshot_mounted(self, snap_name):
        return basic_utils.is_mounted(self.get_snapshot_mount_path(snap_name))


    def get_snapshot_mount_path(self, snap_name):
        escaped_name = re.sub('[^a-zA-Z0-9.:+-]', '_', snap_name)
        return self._mountpoint + '-' + escaped_name


    def mount_snapshot(self, snap_name):
        """
        Mount a snapshot if it is not mounted already. The mountpoint will be
        the normal mountpoint's name appended by the snapshot's name.
        Characters that should not be used on a filesystem are replaced with
        underscores. Snapshots are always mounted read-only.

        :param str snap_name:
        :raises NoSuchSnapshot:
        :raises RuntimeError: If the operation fails.
        """
        if snap_name not in self.list_snapshots():
            raise NoSuchSnapshot

        if self.is_snapshot_mounted(snap_name):
            return

        # Map
        dev = _map_rbd_image(self.name + "@" + snap_name, ro=True)

        try:
            # Mount
            mp = self.get_snapshot_mount_path(snap_name)

            if not os.path.isdir(mp):
                mkdir_p(mp)

            _mount(dev, mp, ro=True)

        except:
            _unmap_rbd_image(dev, raises=False)
            raise


    def unmount_snapshot(self, snap_name):
        """
        Unmount a snapshot it if is currently mounted.

        :param str snap_name:
        :raises RuntimeError: If the oepration fails.
        """
        # Find the device, if any.
        dev = None
        mp = self.get_snapshot_mount_path(snap_name)

        with open('/proc/mounts', 'r', encoding='UTF-8') as f:
            for line in f:
                m = re.match(r'^(\S+)\s+(\S+)\s.*', line)
                if m and m[2] == mp:
                    dev = m[1]
                    break

        if dev is None:
            return

        # Unmount
        _umount(mp)

        # Unmap
        _unmap_rbd_image(dev)

        # Delete mountpoint
        os.rmdir(mp)


def _map_rbd_image(name, ro=False):
    """
    For internal use only. Maps the specified rbd image to a block device.

    :param name: Name of the rbd image
    :param bool ro: Set to true if the image is to be mapped read only.
    :returns: The path to the block device
    :rtype: str
    :raises CommonExceptions.CommandFailed: If the underlying rbd command
        failed.
    """
    cmd = ['rbd', 'map', *settings.get_ceph_cmd_conn_params(),
        settings.get_ceph_scratch_space_rbd_pool() + '/' + str(name)]

    if ro:
        cmd.append('--read-only')

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

    r = subprocess.run(cmd).returncode
    if r != 0 and raises:
        raise CommandFailed(cmd, r)


def _list_mapped_rbd_images():
    """
    For internal user only. Shows which rbd images are mapped to which block
    devices.

    :returns List(str, str): A list of tuples (image name, block device) that
        contains all images mapped on the system.
    """
    dev_dir = '/sys/bus/rbd/devices'

    if not os.path.isdir(dev_dir):
        return []

    imgs = []

    for m_id in os.path.listdir(dev_dir):
        name = ""

        with open(os.path.join(dev_dir, m_id, 'name'), 'r', encoding='UTF-8') as f:
            name = f.read().split()

        imgs.append((name, '/dev/rbd' + m_id))


    return imgs


def _mount(dev, mountpoint, ro=False):
    """
    Mount a device's filesystem at a mountpoint.

    :param str dev: The device with the filesystem to mount
    :param str mountpoint: The mountpoint
    :param bool ro: Set to true if the fs should be mounted read only.

    :raises RuntimeError: if the operation fails.
    """
    cmd = ['mount', dev, mountpoint]
    if ro:
        cmd.append('-oro')

    returncode = subprocess.run(cmd).returncode

    if returncode != 0:
        raise RuntimeError('Failed to mount "%s" at "%s": %d.' %
                (dev, mountpoint, returncode))


def _umount(fs):
    """
    Unmount a mounted filesystem.

    :param str fs: The mountpoint or device to unmount.

    :raises RuntimeError: if the operation fails.
    """
    returncode = subprocess.run(['umount', fs]).returncode

    if returncode != 0:
        raise RuntimeError('Failed to unmount "%s": %d.' % (fs, returncode))


#********************************* Exceptions *********************************
class ScratchSpaceException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


class SnapshotExists(ScratchSpaceException):
    def __init__(self):
        super().__init__("A snapshot with that name exists already.")


class NoSuchSnapshot(ScratchSpaceException):
    def __init__(self):
        super().__init__("A snapshot with that name does not exist.")


class NotWritable(ScratchSpaceException):
    def __init__(self):
        super().__init__("The scratch space is not locked for writing.")
