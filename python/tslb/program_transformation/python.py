"""
Transformations on python (byte-) code
"""
from tslb.Console import Color
from tslb.filesystem.FileOperations import simplify_path_static
import json
import os
import subprocess

def compile_base_in_chroot(rootfs_mountpoint, destdir, out, concurrent_workers=1):
    """
    Compile a python3-base in a chroot environment. Only the directories within
    the sys.path of the installed python3 version are considered.

    :param str rootfs_mountpoint: The mountpoint at which the
        chroot-environment is mounted.

    :param str destdir: The base directory within the chroot environment, at
        which the python installation is located. Must be an absolute path with
        respect to the chroot environment.

    :param out: sys.stdout-like object to print to.

    :param int concurrent_workers: Number of worker threads to use

    :returns: True in case of success, otherwise False.
    """
    from tslb.package_builder import execute_in_chroot

    def _work():
        try:
            # Get sys.path
            ret = subprocess.run(
                ['python3', '-c', 'import sys, json; print(json.dumps(sys.path))'],
                stdout=subprocess.PIPE,
                stderr=out
            )

            if ret.returncode != 0:
                raise RuntimeError("python3 command failed: %s" % ret.returncode)

            path = json.loads(ret.stdout.decode('ascii'))

            # Process each directory recursively if it exists and is a
            # directory
            for d in path:
                if not d:
                    continue

                sd = simplify_path_static(destdir + d)
                if not os.path.isdir(sd):
                    continue

                ret = subprocess.run(
                    ['python3', '-m', 'compileall',
                        '-r', '10',
                        '-j', str(concurrent_workers),
                        '-x', '^.*/usr/lib/python.*/tests?/.*$',
                        sd
                    ],
                    cwd=destdir,
                    stdout=out,
                    stderr=out
                )

                if ret.returncode != 0:
                    raise RuntimeError("compileall failed: %s" % ret.returncode)

        except Exception as e:
            print(Color.RED + "ERROR: " + Color.NORMAL + str(e), file=out)
            return -1

        return 0

    ret = execute_in_chroot(
        rootfs_mountpoint,
        _work)

    return ret == 0
