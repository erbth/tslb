import os
import re
import subprocess
import FileOperations as FOps
import Exceptions as es

"""
Utilities for working with compiled code.
"""

def strip_symbols(base_directory):
    """
    Strip unneeded symbols from objects in well known locations in the given
    directory. The assumed to be a root directory of a lsb compatible directory
    tree.
    This procedure was adapted from LFS 8.2.
    """

    # /usr/lib and /usr/local/lib
    for directory in [ 'usr/lib', 'usr/local/lib' ]:
        directory = os.path.join(base_directory, directory)

        if os.path.isdir (directory):
            # find usr/lib -type f -name \*.a -exec strip -v --strip-debug {} ';'
            def action(n):
                if n.endswith('.a'):
                    cmd = [ 'strip', '-v', '--strip-debug', os.path.join(directory, n) ]

                    if subprocess.call(cmd) != 0:
                        raise es.CommandFailed(' '.join(cmd))

            FOps.traverse_directory_tree(directory, action)

            # find usr/lib -type f -name \*.so* -exec strip -v --strip-unneeded {} ';'
            r = re.compile ('.*\.so.*')

            def action(n):
                if re.match(r, n):
                    cmd = [ 'strip', '-v', '--strip-unneeded', os.path.join(directory, n) ]

                    if subprocess.call(cmd) != 0:
                        raise es.CommandFailed(' '.join(cmd))

            FOps.traverse_directory_tree(directory, action)

            # find usr/lib -name \*.la -delete
            def action(n):
                if n.endswith('.la'):
                    os.remove (os.path.join(directory, n))

            FOps.traverse_directory_tree(directory, action)

    # /lib
    directory = os.path.join(base_directory, 'lib')

    if os.path.isdir (directory):
        # find lib -type f -name \*.so* -exec strip -v --strip-unneeded {} ';'
        r = re.compile ('.*\.so.*')

        def action(n):
            if re.match(r, n):
                cmd = [ 'strip', '-v', '--strip-unneeded', os.path.join(directory, n) ]

                if subprocess.call(cmd) != 0:
                    raise es.CommandFailed(' '.join(cmd))

        FOps.traverse_directory_tree(directory, action)

    # Executables
    dirs = [ 'bin', 'sbin', 'usr/bin', 'usr/sbin', 'usr/libexec' ]

    for directory in dirs:
        directory = os.path.join (base_directory, directory)

        if os.path.isdir (directory):
            # find $DIR -type f -exec strip -v --strip-all {} ';'
            def action(n):
                cmd = [ 'strip', '-v', '--strip-all', os.path.join(directory, n) ]

                if subprocess.call(cmd) != 0:
                    raise es.CommandFailed(' '.join(cmd))

            FOps.traverse_directory_tree(directory, action)

