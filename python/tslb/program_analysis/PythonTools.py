"""
This module contains functions for analysing python code, i.e. to compute its
dependencies.
"""

from typing import Set
import re
import os, stat

def find_required_modules_in_module(m: str) -> Set[str]:
    """
    Parses a python module (.py file) and detects all packages/moduels that
    it imports.

    :param m: The path to the module
    :returns: A set of modules required by the given source file.
    """
    ms: Set[str]
    ms = set()

    def add_import_word(w):
        m = re.match(r'^([^.]+)', w)
        if m:
            ms.add(m.group(1))

    with open(m) as f:
        for line in f:
            # import xxx [as yyy]
            m = re.match(
                    r'^\s*import\s+(([^\s,]+(\s+as\s+[^\s]+)?)(\s*,\s*([^\s]+)(\s+as\s+[^\s]+)?)*)\s*$',
                    line)

            if m:
                pms = re.findall(r'[^,]+', m.group(1))

                for pm in pms:
                    m2 = re.match(r'\s*([^ ]+)', pm)

                    if m2:
                        add_import_word(m2.group(1))

            # from xxx import yyy [as zzz]
            m = re.match(r'^\s*from\s+([^\s]+)\s+import', line)
            if m:
                add_import_word(m.group(1))

    return ms


def find_required_modules_in_path(p: str, ignore_domestic=True, printer=None) -> Set[str]:
    """
    Parses all python source files in the given directory, if p is a directory,
    or the given source file recursively and returns a set of required modules.

    In case a given file is not recognized as python source file, it is skipped.
    This function does not follow symlinks.

    Modules that are in the current directory are not returned if
    ignore_domestic is True.

    :param p: Path to a directory (package) or single source file (module).
    :param ignore_domestic: Ignore modules and packages in this directory.
    :param printer: A function to print status updates, or None.
    :returns: A set of modules required by source files in the given directory.
    """
    if printer is None:
        printer = lambda x: None

    ms: Set[str]
    ms = set()

    domestic_modules = set()
    domestic_packages = set()

    def work(p):
        nonlocal ms

        s = os.stat(p, follow_symlinks=False)

        if stat.S_ISREG(s.st_mode):
            m = re.match(r'(.*[/\\])*([^/\.]+).py$', p)
            if m:
                domestic_modules.add(m.group(2))

            is_python = bool(m)

            # Maybe it's a script?
            if not is_python:
                if s.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
                    with open(p) as f:
                        if re.match(r'^#!\S*python', f.readline()):
                            is_python = True

            if is_python:
                printer('Processing file %s ...' % p)
                ms |= find_required_modules_in_module(p)

        elif stat.S_ISDIR(s.st_mode):
            m = re.match(r'([^/\\.])$', p)
            if m:
                domestic_packages.add(m.group(1))

            for e in os.listdir(p):
                work(os.path.join(p, e))

    work(p)

    if ignore_domestic:
        for m in domestic_modules:
            if m in ms:
                ms.remove(m)

        for m in domestic_packages:
            if m in ms:
                ms.remove(m)

    return ms
