"""
This module is a collection of functions to strip symbols from executable
files.

The strip procedures were inspired by the Book "Linux From Scratch" version
"9.1-systemd" published on March 1st, 2020 by Gerard Beekmans, Managing Editor
Bruce Dubbs, Editor R. Reno and Editor DJ Lucas. Specifically the authors'
approach is described on page 224 ff. in chapter "6.79. Stripping Again".

As the time of this writing the book was available from
http://www.linuxfromscratch.org/lfs/download.html.
"""

from concurrent import futures
import concurrent.futures.thread
import os
import re
import stat
import subprocess
import sys


def strip_and_create_debug_links_in_root(root_path, out=sys.stdout, parallel=None):
    """
    This function finds and strips ELF files in a given system root. It handles
    the library and executable directories different. In library directories
    the maximum strip level is --remove-unneeded, whereas all symbols are
    stripped from files in executable directories, provided they do not end
    with .a or .so*.

    :param str root_path: The path to a system's filsystem-root
    :param out: An output stream to which this function shall report shat it
        does
    :param parallel: The number of stripping tasks to perform in parallel, or
        None if no parallel execution shall be done.
    :raises: an exception on error.
    """
    lib_dirs = ['lib', 'usr/lib', 'usr/local/lib', 'lib64', 'opt']
    exec_dirs = ['bin', 'sbin', 'usr/bin', 'usr/sbin', 'usr/local/bin', 'usr/local/sbin']

    exe = None
    try:
        if parallel:
            if parallel < 1:
                raise ValueError("Number of parallel threads must be >= 1.")

            exe = futures.ThreadPoolExecutor(parallel)

        inode_set = set()
        fs = []

        for d in lib_dirs:
            target = os.path.join(root_path, d)
            if not os.path.isdir(target):
                continue

            fs += strip_and_create_debug_links_in_directory(
                    target,
                    max_level='unneeded',
                    out=out,
                    exe=exe,
                    inode_set=inode_set)

        for d in exec_dirs:
            target = os.path.join(root_path, d)
            if not os.path.isdir(target):
                continue

            fs += strip_and_create_debug_links_in_directory(
                    target,
                    max_level='all',
                    out=out,
                    exe=exe,
                    inode_set=inode_set)

        # Wait for futures in case of parallel execution
        if exe:
            # Fetch result to raise pending exceptions
            for res in futures.wait(fs, return_when=futures.ALL_COMPLETED).done:
                res.result()

    finally:
        if exe:
            exe.shutdown(wait=True)


def strip_and_create_debug_links_in_directory(path, max_level='all',
        out=sys.stdout, exe=None, inode_set=None):
    """
    This function finds and strips all ELF files in a given directory. The
    directory must not cross multiple filesystems because inode numbers must be
    from the same namespace.

    :param str path: The path which should be searched for ELF files
    :param str max_level: The maximum level of symbols to strip, can be 'debug'
        < 'unneeded' < 'all'.
    :param out: An output stream to which this function shall report what it
        does.
    :param exe: An executor for performing (potentially concurrent) stripping
    :param set() inode_set: A set to pass to all calls for identifying hard
        links and not processing the corresponding file multiple times. Leave
        None when calling this function. An empty set will be created
        automatically and passed to recursive calls. However it may be set to
        an empty set() for multiple calls to this function.

    :returns: A list of futures if :param exe: is given, else an empty list.

    :raises: an exception on error.
    """
    stbuf = os.lstat(path)

    if max_level != 'all' and max_level != 'unneeded' and max_level != 'debug':
        raise ValueError("Invalid max_level: `%s'" % max_level)

    # Don't strip a file with multiple hard links multiple times.
    if inode_set is None:
        inode_set = set()

    if stbuf.st_ino in inode_set:
        return []

    inode_set.add(stbuf.st_ino)

    if stat.S_ISDIR(stbuf.st_mode):
        # Recursively process directory
        ret = []
        for elem in os.listdir(path):
            ret += strip_and_create_debug_links_in_directory(
                    os.path.join(path, elem),
                    max_level,
                    out,
                    exe,
                    inode_set)

        return ret

    elif stat.S_ISREG(stbuf.st_mode):
        with open(path, 'rb') as f:
            magic = f.read(4)

        if magic != b'\x7fELF':
            return []

        # Use a filename ending based heuristics to find an appropriate strip
        # level.
        if path.endswith('.a'):
            strip_type = 'debug'
        elif re.match(r'.*\.so.*$', path):
            strip_type = 'unneeded'
        else:
            strip_type = 'all'

        # Limit the maximum strip level
        if max_level == 'unneeded':
            if strip_type == 'all':
                strip_type = 'unneeded'

        elif max_level == 'debug':
            strip_type = 'debug'

        def work():
            strip_and_create_debug_links_for_elf_file(
                    path=path,
                    strip_type=strip_type,
                    out=out)

        if exe:
            return [exe.submit(work)]
        else:
            work()

    return []


def strip_and_create_debug_links_for_elf_file(path, strip_type, out=sys.stdout):
    """
    Strip debug information from the given ELF file and move it to a separate
    file which is linked by a GNU debug link.

    :param str path: The path to the ELF file.
    :param str strip_type: One out of 'debug', 'unneeded' or 'all'. Remember
        that only debug information is copied to an extra file.
    :param out: An output stream to which this function shall report what it
        does.

    :raises: an exception on error.
    """
    if strip_type == 'debug':
        action = '--strip-debug'
    elif strip_type == 'unneeded':
        action = '--strip-unneeded'
    elif strip_type == 'all':
        action = '--strip-all'
    else:
        raise ValueError("Invalid strip_type: `%s'" % strip_type)

    out.write("Processing `%s' (%s) ...\n" % (path, action))

    save_cmd = ['objcopy', '--only-keep-debug', path, path + '.dbg']
    add_debug_link_cmd = ['objcopy', '--add-gnu-debuglink=%s.dbg' % path, path]
    strip_cmd = ['strip', action, path]

    if subprocess.run(save_cmd, stdout=out, stderr=out).returncode != 0:
        raise RuntimeError("Failed to save debug symbols.")

    if subprocess.run(add_debug_link_cmd, stdout=out, stderr=out).returncode != 0:
        raise RuntimeError("Failed to add GNU debug link.")

    if subprocess.run(strip_cmd, stdout=out, stderr=out).returncode != 0:
        raise RuntimeError("Failed to strip symbols.")
