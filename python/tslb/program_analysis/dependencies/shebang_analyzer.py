import os
import stat
import tslb.database as db
import tslb.database.BinaryPackage
from tslb.Constraint import VersionConstraint
from tslb.VersionNumber import VersionNumber
from .dependency_analyzer import *


class ShebangAnalyzer(BaseDependencyAnalyzer):
    """
    Find dependencies based on 'shebang'-requested interpreters.
    """
    display_name = "shebang"

    def analyze_root(dirname, out):
        out.write("\nAdding runtime dependencies based on 'shebang'-requested interpreters...\n")

        # TODO: stopped here.
        for file_, sha512 in bp.get_files():
            full_path = simplify_path_static(base + '/' + file_)

            if not cls._add_file_dependencies_shebang(
                    bp, rdeps, full_path, session, out):
                return False

        return True


    def analyze_file(filename, out):
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

        return analyze_buffer(bp, rdeps, '#!' + line, db_session, out)


    def analyze_buffer(buf, out):
        """
        Add dependencies based on shebang given at least the first line of the
        file to test in the buffer.

        :type buf: bytes (interpreted as ascii text) | str
        :returns: Set(Dependency)
        :raises AnalyzeError: If an error has been encountered
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
        for i, interpreter in enumerate(interpreters):
            deps = db.BinaryPackage.find_binary_packages_with_file(
                    db_session,
                    bp.architecture,
                    interpreter,
                    True,
                    only_newest=True)

            # Try the best to find the interpreter /usr/bin/env would choose
            # among multiple choices.
            if len(deps) == 0 and i > 0:
                continue

            if len(deps) != 1:
                raise AnalyzeError("Did not find a binary package containing interpreter `%s'." %
                    interpreter)

            name, version = deps[0]

            # Add depencency
            rdeps.add(BinaryPackageDependency(name, [VersionConstraint('>=', version)]))

        return rdeps
