"""A simple wrapper around the unshare() syscall"""
import ctypes
import os


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
