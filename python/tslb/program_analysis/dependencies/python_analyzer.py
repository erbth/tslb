import os
import re
import stat
import tslb.database as db
import tslb.database.BinaryPackage
from tslb import SourcePackage as spkg
from tslb.Console import Color
from tslb.filesystem.FileOperations import simplify_path_static
from .dependency_analyzer import *
from .. import PythonTools


mod_re = re.compile('^.*/destdir/usr/lib/python[0-9.]*/site-packages/.*')


class PythonAnalyzer(BaseDependencyAnalyzer):
    """
    Find dependencies between python packages by examining import-statements.
    """
    name = "python"


    @classmethod
    def analyze_root(cls, dirname, arch, out, spv=None):
        deps = set()

        # Process python packages
        def _work(p):
            st_buf = os.lstat(p)
            if stat.S_ISREG(st_buf.st_mode):
                if mod_re.match(p):
                    return p

            elif stat.S_ISDIR(st_buf.st_mode):
                for c in os.listdir(p):
                    r = _work(os.path.join(p, c))
                    if r:
                        return r

            return None

        file_in_home = _work(dirname)
        if file_in_home:
            # Analyze dependencies of packages
            modules = PythonTools.find_required_modules_in_path(
                    dirname,
                    printer=lambda msg: out.write("  %s\n" % msg.replace(dirname, '')),
                    ignore_decode_errors=True)

            deps |= cls._dependencies_from_modules(modules, arch, out, file_in_home=file_in_home)


        # Analyze scripts outside of python packages
        def _work(p):
            if mod_re.match(p):
                return set()

            st_buf = os.lstat(p)
            if stat.S_ISREG(st_buf.st_mode):
                cls.analyze_file(p, arch, out)

            elif stat.S_ISDIR(st_buf.st_mode):
                ret = set()
                for c in os.listdir(p):
                    ret |= _work(os.path.join(p, c))

                return ret

            return set()

        deps |= _work(dirname)

        return deps


    @classmethod
    def analyze_file(cls, filename, arch, out, spv=None):
        interpreter = None
        file_in_home = None

        if filename.endswith('py'):
            if mod_re.match(filename):
                file_in_home = filename
            else:
                interpreter = cls._get_interpreter(filename)

        else:
            interpreter = cls._get_interpreter(filename)

        if not interpreter and not file_in_home:
            return set()

        print("  Analyzing script '%s'..." % re.sub(r'.*/destdir/', '', filename), file=out)

        modules = PythonTools.find_required_modules_in_module(filename, ignore_decode_errors=True)
        return cls._dependencies_from_modules(modules, arch, out,
                interpreter=interpreter, file_in_home=file_in_home)


    @classmethod
    def analyze_buffer(cls, buf, arch, out, spv=None):
        if not buf:
            return set()

        try:
            if isinstance(buf, bytes):
                buf = buf.decode('utf8')

        except UnicodeDecodeError:
            return set()

        if buf[:2] != '#!':
            return set()

        # Guess if this could be a python source module
        m = re.match(r'^\s*(/usr/bin/python[0-9.]*)(\s+.*)?$', buf.split('\n')[0])
        if not m:
            return set()

        modules = PythonTools.find_required_modules_in_module_buffer(buf)
        return cls._dependencies_from_modules(modules, arch, out, interpreter=m[1])


    def _dependencies_from_modules(modules, arch, out, interpreter=None, file_in_home=None):
        """
        Given an iterable of modules guess Dependency-objects.

        :type modules:       List(str)
        :param interpreter:  Interpreter used by the module
        :param file_in_home: An arbitrary file in the python home to use.
        :rtype:              Set(Dependency)
        """
        # Find python home
        if not interpreter and not file_in_home:
            raise ValueError("At least one of `interpreter` of `file_in_home` must be specified.")

        # Reduce filenames to the start of the root fs
        def _reduce(f):
            if f:
                m = re.match('^.*/destdir(/usr/.*)$', f)
                if m:
                    return m[1]

            return f

        interpreter = _reduce(interpreter)
        file_in_home = _reduce(file_in_home)
        python_home = None

        print(Color.MAGENTA + "    interpreter:  %s" % interpreter + Color.NORMAL, file=out)
        print(Color.MAGENTA + "    file in home: %s" % file_in_home + Color.NORMAL, file=out)

        home_regex = re.compile('^(/usr/lib/python[0-9.]*)/site-packages/')
        if file_in_home:
            m = home_regex.match(file_in_home)
            if m:
                python_home = m[1]

        elif interpreter:
            # Try to find the latest package containing the interpreter and
            # search for the most specific python home in it.
            with db.session_scope() as s:
                pkg = db.BinaryPackage.find_binary_packages_with_file(
                        s, arch, interpreter, True, only_newest=True)

                if pkg:
                    # Get binary package
                    ret = db.BinaryPackage.find_source_package_version_for_binary_package(
                            s, *pkg[0], arch)
                    if ret:
                        try:
                            bp = spkg.SourcePackage(ret[0], arch).get_version(ret[1])\
                                    .get_binary_package(*pkg[0])

                            for f,_ in bp.get_files():
                                m = home_regex.match(f)
                                if m:
                                    python_home = m[1]
                                    break

                            del bp

                        except (spkg.NoSuchSourcePackage, spkg.NoSuchSourcePackageVersion):
                            pass

        if not python_home:
            raise AnalyzerError("Could not find python home.")

        print(Color.MAGENTA + "    python home:  %s" % python_home + Color.NORMAL, file=out)

        # Generate possible paths to modules
        deps = set()
        for module in modules:
            deps.add(Or([
                FileDependency(simplify_path_static(python_home + '/' + module + '/__init__.py')),
                FileDependency(simplify_path_static(python_home + '/' + module + '.py')),
                FileDependency(simplify_path_static(python_home + '/' + module + '.pyi')),
                FileDependency(simplify_path_static(python_home + '/' + module + '.so')),
                FileDependency(simplify_path_static(python_home + '/site-packages/' + module + '/__init__.py')),
                FileDependency(simplify_path_static(python_home + '/site-packages/' + module + '.py')),
                FileDependency(simplify_path_static(python_home + '/site-packages/' + module + '.pyi')),
                FileDependency(simplify_path_static(python_home + '/site-packages/' + module + '.so')),

                # Try namespace-packages last
                FileDependency(simplify_path_static(python_home + '/' + module)),
                FileDependency(simplify_path_static(python_home + '/site-packages/' + module)),
            ]))

        return deps


    def _get_interpreter(filename):
        with open(filename, 'rb') as f:
            if f.read(2) == b'#!':
                try:
                    line = f.readline().decode('ascii').strip()
                    m = re.match(r'^\s*(/usr/bin/python[0-9.]*)(\s+.*)?$', line)
                    if m:
                        return m[1]

                    m = re.match(r'^\s*/usr/bin/env\s+(python[0-9.]*)(\s+.*)?$', line)
                    if m:
                        return '/usr/bin/' + m[1]

                except UnicodeDecodeError:
                    return None

        return None
