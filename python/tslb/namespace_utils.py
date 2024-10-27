"""A simple wrapper around Linux namespace related syscalls like unshare()"""
import ctypes
import os
import select
import termios
import tty


_libc = ctypes.CDLL('libc.so.6', use_errno=True)


# Arguments to unshare()
CLONE_FILES     = 0x00000400
CLONE_FS        = 0x00000200
CLONE_NEWCGROUP = 0x02000000
CLONE_NEWIPC    = 0x08000000
CLONE_NEWNET    = 0x40000000
CLONE_NEWNS     = 0x00020000
CLONE_NEWPID    = 0x20000000
CLONE_NEWTIME   = 0x00000080
CLONE_NEWUSER   = 0x10000000
CLONE_NEWUTS    = 0x04000000
CLONE_SYSVSEM   = 0x00040000

def unshare(flags):
    ret = _libc.unshare(flags)
    if ret != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))


MS_RDONLY       = 1
MS_NOSUID       = 2
MS_NODEV        = 4
MS_NOEXEC       = 8
MS_SYNCHRONOUS  = 16
MS_REMOUNT      = 32
MS_MANDLOCK     = 64
MS_DIRSYNC      = 128
MS_NOSYMFOLLOW  = 256
MS_NOATIME      = 1024
MS_NODIRATIME   = 2048
MS_BIND         = 4096
MS_MOVE         = 8192
MS_REC          = 16384
MS_SILENT       = 32768
MS_POSIXACL     = (1<<16)
MS_UNBINDABLE   = (1<<17)
MS_PRIVATE      = (1<<18)
MS_SLAVE        = (1<<19)
MS_SHARED       = (1<<20)
MS_RELATIME     = (1<<21)
MS_KERNMOUNT    = (1<<22)
MS_I_VERSION    = (1<<23)
MS_STRICTATIME  = (1<<24)
MS_LAZYTIME     = (1<<25)

def mount(source, target, filesystemtype, mountflags, data):
    ret = _libc.mount(source, target, filesystemtype, mountflags, data)
    if ret != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))


MOUNT_ATTR_RDONLY        = 0x00000001
MOUNT_ATTR_NOSUID        = 0x00000002
MOUNT_ATTR_NODEV         = 0x00000004
MOUNT_ATTR_NOEXEC        = 0x00000008
MOUNT_ATTR__ATIME        = 0x00000070
MOUNT_ATTR_RELATIME      = 0x00000000
MOUNT_ATTR_NOATIME       = 0x00000010
MOUNT_ATTR_STRICTATIME   = 0x00000020
MOUNT_ATTR_NODIRATIME    = 0x00000080
MOUNT_ATTR_IDMAP         = 0x00100000
MOUNT_ATTR_NOSYMFOLLOW   = 0x00200000

AT_EMPTY_PATH            = 0x1000
AT_RECURSIVE             = 0x8000

OPEN_TREE_CLONE          = 1
OPEN_TREE_CLOEXEC        = os.O_CLOEXEC

MOVE_MOUNT_F_SYMLINKS    = 0x00000001
MOVE_MOUNT_F_AUTOMOUNTS  = 0x00000002
MOVE_MOUNT_F_EMPTY_PATH  = 0x00000004
MOVE_MOUNT_T_SYMLINKS    = 0x00000010
MOVE_MOUNT_T_AUTOMOUNTS  = 0x00000020
MOVE_MOUNT_T_EMPTY_PATH  = 0x00000040
MOVE_MOUNT_SET_GROUP     = 0x00000100


SYS_open_tree = 428
SYS_move_mount = 429
SYS_mount_setattr = 442


class MountAttr(ctypes.Structure):
    _fields_ = [
        ("attr_set", ctypes.c_uint64),
        ("attr_clr", ctypes.c_uint64),
        ("propagation", ctypes.c_uint64),
        ("userns_fd", ctypes.c_uint64),
    ]


_open_tree = ctypes.CDLL('libc.so.6', use_errno=True).syscall
_open_tree.restype = ctypes.c_int
_open_tree.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]

_move_mount = ctypes.CDLL('libc.so.6', use_errno=True).syscall
_move_mount.restype = ctypes.c_int
_move_mount.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_char_p,
                        ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]

_mount_setattr = ctypes.CDLL('libc.so.6', use_errno=True).syscall
_mount_setattr.restype = ctypes.c_int
_mount_setattr.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_char_p,
                           ctypes.c_uint, ctypes.POINTER(MountAttr), ctypes.c_size_t]


def open_tree(dirfd, filename, flags):
    ret = _open_tree(SYS_open_tree, dirfd, filename, flags)
    if ret < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, "open_tree: " + os.strerror(errno))

    return ret


def move_mount(from_dirfd, from_pathname, to_dirfd, to_pathname, flags):
    ret = _move_mount(SYS_move_mount, from_dirfd, from_pathname,
                      to_dirfd, to_pathname, flags)
    if ret < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, "open_tree: " + os.strerror(errno))


def mount_setattr(dirfd, pathname, flags, attr):
    ret = _mount_setattr(SYS_mount_setattr, dirfd, pathname, flags, attr, 8*4)
    if ret != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))


# Common tools that use the syscalls wrapped above
def make_private_mount(path):
    attr = MountAttr()

    attr.attr_set = 0
    attr.attr_clr = 0
    attr.propagation = MS_PRIVATE
    attr.userns_fd = 0

    mount_setattr(-1, path.encode('utf8'), 0, attr)

def bind_mount(src, dst, recursive=False):
    mount(src.encode('utf8'), dst.encode('utf8'), None,
          MS_BIND | (MS_REC if recursive else 0),
          None)

def make_id_mapped_mount(src, dst, userns_pid, copy_recursive=False, map_recursive=False):
    fd_userns = os.open('/proc/%d/ns/user' % userns_pid,
                        os.O_RDONLY | os.O_CLOEXEC)

    try:
        fd_tree = open_tree(
                -1, src.encode('utf8'), OPEN_TREE_CLONE | OPEN_TREE_CLOEXEC |
                    (AT_RECURSIVE if copy_recursive else 0))
    except:
        os.close(fd_userns)
        raise

    try:
        attr = MountAttr()

        attr.attr_set = MOUNT_ATTR_IDMAP
        attr.attr_clr = 0
        attr.propagation = 0
        attr.userns_fd = fd_userns

        mount_setattr(
                fd_tree, b"",
                AT_EMPTY_PATH | (AT_RECURSIVE if map_recursive else 0),
                attr)

        move_mount(fd_tree, b"", -1, dst.encode('utf8'), MOVE_MOUNT_F_EMPTY_PATH)

    finally:
        os.close(fd_tree)
        os.close(fd_userns)


PR_CAP_AMBIENT              = 47
PR_CAP_AMBIENT_IS_SET       = 1
PR_CAP_AMBIENT_RAISE        = 2
PR_CAP_AMBIENT_LOWER        = 3
PR_CAP_AMBIENT_CLEAR_ALL    = 4

CAP_CHOWN               = 0
CAP_DAC_OVERRIDE        = 1
CAP_DAC_READ_SEARCH     = 2
CAP_FOWNER              = 3
CAP_FSETID              = 4
CAP_KILL                = 5
CAP_SETGID              = 6
CAP_SETUID              = 7
CAP_SETPCAP             = 8
CAP_LINUX_IMMUTABLE     = 9
CAP_NET_BIND_SERVICE    = 10
CAP_NET_BROADCAST       = 11
CAP_NET_ADMIN           = 12
CAP_NET_RAW             = 13
CAP_IPC_LOCK            = 14
CAP_IPC_OWNER           = 15
CAP_SYS_MODULE          = 16
CAP_SYS_RAWIO           = 17
CAP_SYS_CHROOT          = 18
CAP_SYS_PTRACE          = 19
CAP_SYS_PACCT           = 20
CAP_SYS_ADMIN           = 21
CAP_SYS_BOOT            = 22
CAP_SYS_NICE            = 23
CAP_SYS_RESOURCE        = 24
CAP_SYS_TIME            = 25
CAP_SYS_TTY_CONFIG      = 26
CAP_MKNOD               = 27
CAP_LEASE               = 28
CAP_AUDIT_WRITE         = 29
CAP_AUDIT_CONTROL       = 30
CAP_SETFCAP             = 31
CAP_MAC_OVERRIDE        = 32
CAP_MAC_ADMIN           = 33
CAP_SYSLOG              = 34
CAP_WAKE_ALARM          = 35
CAP_BLOCK_SUSPEND       = 36
CAP_AUDIT_READ          = 37
CAP_PERFMON             = 38

def prctl(option, arg2=0, arg3=0, arg4=0, arg5=0):
    ret = _libc.prctl(option, arg2, arg3, arg4, arg5)
    if ret < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))

    return ret


# Working with pseudo-terminals
def posix_openpt(flags):
    """
    possible flags: os.O_RDWR, os.O_NOCTTY

    :returns: fd to pty master device
    """
    ret = _libc.posix_openpt(flags)
    if ret < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))

    return ret

def grantpt(fd):
    if _libc.grantpt(fd) < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))

def unlockpt(fd):
    if _libc.unlockpt(fd) < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))

def ptsname(fd):
    buf = ctypes.create_string_buffer(1024)
    if _libc.ptsname_r(fd, buf, 1024) < 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno))

    return buf.value.decode('utf8')


def proxy_pty(own, ctrl):
    """
    :param own: Own pty
    :param ctrl: The master fd to control
    """
    before = termios.tcgetattr(own)

    try:
        tty.setraw(own)

        while True:
            rd, wr, ex = select.select([ctrl, own], [], [])

            if ctrl in rd:
                try:
                    buf = os.read(ctrl, 65536)
                except OSError as exc:
                    if exc.errno == 5:
                        break
                    raise

                os.write(1, buf)

            if own in rd:
                buf = os.read(own, 65536)
                os.write(ctrl, buf)

    finally:
        termios.tcsetattr(own, termios.TCSAFLUSH, before)
