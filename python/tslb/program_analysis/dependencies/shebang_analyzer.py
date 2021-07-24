import os
import stat
import tslb.database as db
import tslb.database.BinaryPackage
from tslb import Architecture
from tslb.Constraint import VersionConstraint
from tslb.VersionNumber import VersionNumber
from tslb.filesystem.FileOperations import simplify_path_static
from .dependency_analyzer import *


class ShebangAnalyzer(BaseDependencyAnalyzer):
    """
    Find dependencies based on 'shebang'-requested interpreters.
    """
    name = "shebang"

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
                    deps |= cls.analyze_file(full_path, arch, out)

        analyze(dirname)
        return deps


    @classmethod
    def analyze_file(cls, filename, arch, out):
        # Only consider executable files
        st_buf = os.lstat(filename)
        if not stat.S_ISREG(st_buf.st_mode) or not \
                st_buf.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            return set()

        # Read the file and process it if it starts with a 'shebang'
        with open(filename, 'rb') as f:
            if f.read(2) == b'#!':
                line = f.readline().decode('ascii').strip()
            else:
                line = None

        if not line:
            return set()

        return cls.analyze_buffer('#!' + line, arch, out)


    def analyze_buffer(buf, arch, out):
        """
        Add dependencies based on shebang given at least the first line of the
        file to test in the buffer.

        :type buf: bytes (interpreted as ascii text) | str
        :param arch: The architecture in which dependencies shall be searched.
        :returns: Set(Dependency)
        :raises AnalyzerError: If an error has been encountered
        """
        rdeps = set()

        if isinstance(buf, bytes):
            buf = buf.decode('ascii')

        if buf[:2] != '#!':
            return rdeps

        line = buf.split('\n')[0][2:].strip().split(' ')
        interpreters = [line[0]]

        # Handle #!/usr/bin/env specially
        if interpreters[0] == '/usr/bin/env':
            for arg in line[1:]:
                if arg and not arg.startswith('-'):
                    if arg.startswith('/'):
                        interpreters.append(arg)
                    else:
                        interpreters += [
                            '/usr/bin/' + arg,
                            '/bin/' + arg,
                        ]

        # Find the package containing the interpreter
        with db.session_scope() as session:
            for i, interpreter in enumerate(interpreters):
                deps = db.BinaryPackage.find_binary_packages_with_file(
                        session,
                        Architecture.to_int(arch),
                        interpreter,
                        True,
                        only_newest=True)

                # Try the best to find the interpreter /usr/bin/env would choose
                # among multiple choices.
                if len(deps) == 0 and i > 0:
                    continue

                if len(deps) != 1:
                    raise AnalyzerError("Did not find a binary package containing interpreter `%s'." %
                        interpreter)

                name, version = deps[0]

                # Add depencency
                rdeps.add(BinaryPackageDependency(name, [VersionConstraint('>=', version)]))

            return rdeps
