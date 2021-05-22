"""
Some utility functions that are useful in various conditions or special states
of the system, and do not properly fit into exactly one Python module/package.
"""
from tslb import rootfs
from tslb import rootfs
from tslb import scratch_space
from tslb import tclm
from tslb import tclm
from tslb.Architecture import architectures
from tslb.BinaryPackage import BinaryPackage
from tslb.SourcePackage import SourcePackage, SourcePackageList, SourcePackageVersion
from tslb.tclm import lock_X
import contextlib
import errno
import multiprocessing
import os
import pty
import select
import sys
import threading
import traceback


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


class FDWrapper:
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


def is_mounted(path):
    """
    Returns true if the specified path exists and something is mounted there
    i.e. it is a mountpoint.
    """
    with open('/proc/mounts', 'r', encoding='UTF-8') as f:
        for mountpoint in f:
            if mountpoint.split()[1] == path:
                return True

    return False


class LogTransformer:
    """
    A context manager that provides the writer-end of a pty in from of an
    sys.stdout-like object and starts a background thread which reads from it,
    transforms log lines accordingly and writes the output to the given
    stdout-like object.

    It can optionally aquire a given lock while writing to protect the output
    FD.

    :param str pattern: Pattern used when writing to the output. %(line)s is
                        substituted by a line read from the input.
    :param out:         Output sys.stdout-like object
    :param lock:        Optional lock to acquire while writing, defaults to
                        None.
    """
    def __init__(self, pattern, out, lock=None):
        self._pattern = pattern
        self._out = out
        self._lock = lock
        self._master = None
        self._slave = None
        self._worker = None

        self._pipe_r = None
        self._pipe_w = None

    def _worker_fun(self):
        while True:
            rfds,_,_ = select.select([self._master, self._pipe_r], [], [])
            if self._master in rfds:
                lines = os.read(self._master, 65535)
            elif self._pipe_r in rfds:
                break

            # read() returning zero indicates EOF
            if not lines:
                return

            lines = lines.decode('utf8').replace('\r', '').rstrip('\n').split('\n')
            text = ''.join((self._pattern % {'line': line}) + '\n' for line in lines)

            if self._lock is not None:
                with self._lock:
                    self._out.write(text)
            else:
                self._out.write(text)

    def __enter__(self):
        self._master, self._slave = pty.openpty()
        self._pipe_r, self._pipe_w = os.pipe()
        self._worker = threading.Thread(target=self._worker_fun)
        self._worker.start()
        return FDWrapper(self._slave)

    def __exit__(self, exc_type, exc_value, traceback):
        # Request exit
        os.write(self._pipe_w, b'1')
        self._worker.join()

        os.close(self._slave)
        os.close(self._master)
        os.close(self._pipe_r)
        os.close(self._pipe_w)

        self._master = None
        self._slave = None
        self._pipe_r = None
        self._pipe_w = None
        self._worker = None


@contextlib.contextmanager
def thread_inspector(stop=True):
    """
    Start a thread inspecing all threads to e.g. find deadlocks.

    :param bool stop: Stop the monitor after exiting the with-statement
        (defaults to True, may interfer with other things if kept running...)
    """
    ev = threading.Event()

    def debug_fcnt():
        while True:
            if ev.wait(1):
                break

            # Print all threads
            print("Threads: (PID: %s)" % os.getpid())
            frames = sys._current_frames()
            for t in threading.enumerate():
                frame = frames.get(t.ident)
                if not frame:
                    continue

                c = frame.f_code
                pos = c.co_filename + ":" + str(frame.f_lineno)
                print("  %s (%s): %s" % (t.ident, t.name, pos))
                print(traceback.print_stack(frame))

    thdbg = threading.Thread(target=debug_fcnt)
    thdbg.start()

    yield

    if stop:
        ev.set()
        thdbg.join()
