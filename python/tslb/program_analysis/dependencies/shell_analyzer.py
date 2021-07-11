import os
import re
import stat
from tslb.Console import Color
from tslb.filesystem.FileOperations import simplify_path_static
from tslb.basic_utils import read_file
from .dependency_analyzer import *
from .. import bash_tools


class ShellAnalyzer(BaseDependencyAnalyzer):
    """
    This analyzer employs a best-effort approach to finding external programs
    required by bash-like shells.
    """
    name = "shell"

    @classmethod
    def analyze_root(cls, dirname, arch, out):
        deps = set()
        def analyze(d):
            nonlocal deps

            for c in os.listdir(d):
                full_path = simplify_path_static(d + '/' + c)
                st_buf = os.lstat(full_path)

                if stat.S_ISDIR(st_buf.st_mode):
                    analyze(full_path)
                elif stat.S_ISREG(st_buf.st_mode):
                    deps |= cls._analyze_file(dirname, full_path, arch, out)

        analyze(dirname)
        return deps

    @classmethod
    def analyze_file(cls, filename, arch, out):
        st_buf = os.lstat(filename)
        if not stat.S_ISREG(st_buf.st_mode):
            return set()

        return cls._analyze_file(None, full_path, arch, out)

    @classmethod
    def analyze_buffer(cls, buf, arch, out):
        return cls._analyze_buffer(None, buf, arch, out)


    @classmethod
    def _analyze_file(cls, root, full_path, arch, out):
        """
        :param root: Path to the root directory of the system, in which the
            file to analyze resides. This is used for loading additional
            'library'-scripts. May be None.
        """
        # Check by shebang if this is a shell script this analyzer can
        # interpret - ignore scripts without shebang for now.
        can_interpret = False

        with open(full_path, 'rb') as f:
            if f.read(2) == b'#!':
                line = f.readline().decode('ascii').strip()
                comp = [comp for comp in line.split() if comp]

                if comp[0] in ('/bin/sh', '/bin/bash', '/usr/bin/bash'):
                    can_interpret = True
                elif comp[0] == '/usr/bin/env' and len(comp) > 1 and comp[1] == 'bash':
                    can_interpret = True

        if can_interpret:
            path = full_path.replace(root, '') if root else full_path
            out.write("  Analyzing shell script '%s'...\n" % path)
            return cls._analyze_buffer(root, read_file(full_path, 'utf8'), arch, out)

        return set()


    def _analyze_buffer(root, text, arch, out):
        def inc_loader(path):
            if not root:
                return None

            if not re.match(r'^/[0-9a-zA-Z_./-]+$', path):
                out.write(Color.MAGENTA +
                        "    Load request for included file '%s' denied (probably parser inaccuracy)." %
                        path + Color.NORMAL + "\n")
                return None

            full_path = simplify_path_static(root + '/' + path)
            try:
                st_buf = os.stat(full_path)
                if not st_buf.st_mode & stat.S_IFREG:
                    out.write(Color.MAGENTA +
                            "    Included file '%s' is not a regular file." % path +
                            Color.NORMAL + "\n")
                    return None

                out.write(Color.MAGENTA + "    Loading included file '%s'..." % path +
                        Color.NORMAL + "\n")

                return read_file(full_path, 'utf8')

            except FileNotFoundError:
                out.write(Color.MAGENTA + "    Included file '%s' not found." % path +
                    Color.NORMAL + "\n")
                return None

        programs = bash_tools.determine_required_programs(text, inc_loader)

        # Constract file-dependencies based on programs
        deps = set()
        for p in programs:
            if p.startswith('/'):
                deps.add(FileDependency(simplify_path_static(p)))
            else:
                deps.add(Or([
                    FileDependency(simplify_path_static('/bin/' + p)),
                    FileDependency(simplify_path_static('/usr/bin/' + p)),
                    FileDependency(simplify_path_static('/sbin/' + p)),
                    FileDependency(simplify_path_static('/usr/sbin/' + p))
                ]))

        return deps
