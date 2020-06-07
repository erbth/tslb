"""
This module houses functions that are used by multiple stages.
"""
import os
from tslb.filesystem import FileOperations as fops


def update_binary_package_files(bp):
    """
    Update a binary package's files from its destdir.

    :param BinaryPackag bp: The binary package
    """
    files = []

    def file_function(p):
        nonlocal files
        files.append((os.path.join('/', p), ''))

    fops.traverse_directory_tree(os.path.join(bp.scratch_space_base, 'destdir'), file_function)

    bp.set_files(files)
