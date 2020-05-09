"""
Some utility functions that are useful in various conditions or special states
of the system, and do not properly fit into exactly one Python module/package.
"""
from tslb.Architecture import architectures
from tslb.BinaryPackage import BinaryPackage
from tslb.SourcePackage import SourcePackage, SourcePackageList, SourcePackageVersion
from tslb import rootfs
from tslb import tclm
from tslb.tclm import lock_X
from tslb import tclm
from tslb import rootfs
from tslb import scratch_space
import multiprocessing
import os


def initially_create_all_locks():
    """
    Creates all locks at the tclm. Useful to populate them when starting the
    system.
    """
    # Create locks for scratch spaces
    scratch_space.create_locks()

    # Create locks for packages
    for arch in architectures.keys():
        spl = SourcePackageList(arch, create_locks = True)

        sps = spl.list_source_packages()

        with lock_X(spl.db_root_lock):
            for n in sps:
                p = SourcePackage(n, arch, create_locks=True, write_intent=True)

                for v in p.list_version_numbers():
                    spv = SourcePackageVersion(p, v, create_locks=True)

                    for bn in spv.list_all_binary_packages():
                        for bv in spv.list_binary_package_version_numbers(bn):
                            BinaryPackage(spv, bn, bv, create_locks=True)


    # Create locks for rootfs images
    lk = tclm.define_lock('tslb.rootfs.available')
    lk.create(True)
    lk.release_X()

    rlk = tclm.define_lock('tslb.rootfs.images')
    rlk.create(True)

    try:
        for i in rootfs.list_images():
            tclm.define_lock('tslb.rootfs.images.' + str(i)).create(False)

    finally:
        rlk.release_X()


def run_bash_in_rootfs_image(img_id):
    """
    Start an interactive bash shell in an isolated (not sharing environment)
    chroot environment rooted at the given image.

    :param img_id: The rootfs image's id
    :returns: The shell's return code
    :raises rootfs.NoSuchImage: If the id does not match an image
    """
    img_id = int(img_id)
    image = rootfs.Image(img_id)

    if not image.in_available_list:
        # Upgrade to an X lock
        lk = tclm.define_lock('tslb.rootfs.images.%d' % img_id)
        lk.acquire_Splus()

        del image
        lk.acquire_X()
        lk.release_Splus()

        image = rootfs.Image(img_id, acquired_X=True)

    mount_namespace = 'manual'

    image.mount(mount_namespace)
    mountpoint = image.get_mountpoint(mount_namespace)

    # Avoid a cyclic import dependency
    from tslb import package_builder as pb

    try:
        pb.mount_pseudo_filesystems(mountpoint)

        def f():
            return os.execlp('bash', 'bash', '--login', '+h')

        return pb.execute_in_chroot(mountpoint, f)

    finally:
        pb.unmount_pseudo_filesystems(mountpoint, raises=True)
        image.unmount(mount_namespace)


class FDWrapper(object):
    """
    Wraps an fd into something that behaves like sys.stdout etc.
    This does NOT close the fd on deletion!

    :param int fd: The fd to wrap
    """
    def __init__(self, fd):
        self._fd = fd

    def fileno(self):
        return self._fd

    def close(self):
        os.close(self._fd)


    def write(self, data):
        """
        :type data: str or bytes
        """
        if isinstance(data, str):
            data = data.encode('utf8')

        os.write(self._fd, data)
