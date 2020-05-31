import os
import re
import subprocess
import sys
from tslb import CommonExceptions as ces
from tslb.VersionNumber import VersionNumber
from tslb.database import SourcePackage as dbspkg
from tslb.filesystem.FileOperations import simplify_path_static


def file_belongs_to_shared_library(filename, out=sys.stdout):
    """
    ELF shared objects are considered only as such if they have a SONAME
    attribute. All other types of files that end in .so[.version] are
    considered shared libraries on the other hand, because they could be linker
    scripts linking to shared libraries and parts of static libraries.
    """
    if re.match ('^.*\.so(\.\d+)*$', filename):
        with open(filename, 'rb') as f:
            magic = f.read(4)

        if magic == b'\x7fELF':
            # Check if a SONAME attribute exists
            cmd = ['objdump', '-p', filename]

            ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=sys.stdout)
            if ret.returncode != 0:
                raise ces.CommandFailed(' '.join(cmd))

            match = re.search(r'SONAME\s+(.+)\.so(\.\d+)*', ret.stdout.decode('UTF-8'))
            if match:
                return True

            return False

        else:
            return True

    else:
        return False


def guess_library_name(filename, out=sys.stdout):
    # If the filename points to an ELF file, try to determine the library's
    # name by looking at the SONAME header attribute.
    with open(filename, 'rb') as f:
        magic = f.read(4)

    if magic == b'\x7fELF':
        cmd = ['objdump', '-p', filename]

        ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=out)
        if ret.returncode != 0:
            raise ces.CommandFailed(' '.join(cmd))

        match = re.search(r'SONAME\s+(.+)\.so(\.\d+)*', ret.stdout.decode('UTF-8'))
        if match:
            return match.group(1)


    # Fall back to name-based library name guessing
    match = re.match ('^((.*)/)*([^/]+)\.so(\.\d+)*$', filename)
    if match:
        return match.group(3)
    else:
        return None


class SharedLibrary(object):
    def __init__(self, *args, fs_base='/'):
        """
        Usage: (name, [file [,file [,...]]], [fs_base=...]) or
        (database.SourcePackage.SourcePackageSharedLibrary,
            list(tuple(filename, is_dev_symlink)))
        """
        if len(args) == 2 and\
                isinstance(args[0], dbspkg.SourcePackageSharedLibrary) and\
                isinstance(args[1], list):
            db = args[0]
            files = args[1]

            self.name = db.name
            self.version_number = db.version_number
            self.abi_version_number = db.abi_version_number
            self.soname = db.soname

            self.files = set()
            self._dev_symlinks = set()

            for f, is_dev in files:
                self.files.add(f)

                if is_dev:
                    self._dev_symlinks.add(f)


        elif len(args) >= 1:
            name = args[0]
            files = args[1:]

            self.name = name
            self.files = set(files)
            self.version_number = None
            self.abi_version_number = None
            self.soname = None
            self._dev_symlinks = None
            self._fs_base = fs_base

            self.guess_version_number ()
            self.guess_abi_version_number()
            self.guess_dev_symlinks()

        else:
            raise ValueError("Invalid arguements")

    def get_name(self):
        return self.name

    def get_files(self):
        return self.files

    def get_abi_versioned_files(self):
        abi_files = []

        for f in self.files:
            if re.match(r'^.*\.%s(\..*)?$' % self.abi_version_number, f):
                abi_files.append(f)

        return abi_files

    def get_dev_symlinks (self):
        """
        :returns Set(str): A set of dev symlinks, which is a subset of the
            library's files.
        """
        return self._dev_symlinks


    def get_version_number(self):
        return self.version_number

    def get_abi_version_number(self):
        return self.abi_version_number


    def add_file(self, f):
        self.files.add(f)
        self.guess_version_number()
        self.guess_abi_version_number()
        self.guess_dev_symlinks()


    def guess_version_number(self):
        # Take the highest version number. This will also yield the most
        # specific one.
        self.version_number = None

        for f in self.files:
            match = re.match('^.*\.so\.(\d+(\.\d+)*)$', f)

            if match:
                v = VersionNumber(match.group(1))

                if self.version_number:
                    if v > self.version_number:
                        self.version_number = v
                else:
                    self.version_number = v

    def guess_abi_version_number(self):
        """
        This will not only populate the abi_version_number attribute but also
        self.soname.
        """
        self.abi_version_number = None

        for _file in self.files:
            full_file = simplify_path_static(self._fs_base + '/' + _file)

            # Only search for SONAME in ELF files.
            with open(full_file, 'rb') as f:
                if f.read(4) != b'\x7fELF':
                    continue

            cmd = ['objdump', '-p', full_file]

            ret = subprocess.run(cmd, stdout=subprocess.PIPE)
            if ret.returncode != 0:
                raise ces.CommandFailed(' '.join(cmd))

            match = re.search(r'SONAME\s+(' + self.name + r'\.so(\.(\d+(\.\d+)*))?)', ret.stdout.decode('UTF-8'))
            if not match:
                raise ces.AnalyzeError("'%s' has no SONAME" % self.name)

            self.soname = match.group(1)
            self.abi_version_number = VersionNumber(match.group(3)) if match.group(3) else None

            break

    def guess_dev_symlinks(self):
        """
        Determines all symlinks that are not the libraries SONAME and are not
        part of a 'link chain' from the SONAME symlink to a regular file. These
        are only needed during compiletime.
        """
        # TODO: What about more specific symlinks ? For now I think that no one
        # should link against them as it breaks the concept of major / minor
        # version and therefore updates.

        # SONAME'd file
        so_named_file = None
        r = re.compile('.+/%s$' % self.soname)

        for f in self.files:
            if re.match (r, f):
                so_named_file = f
                break

        if not so_named_file:
            raise ces.AnalyzeError ("Shared library %s seems to have no SONAME'd file." % self.name)

        # Link chain from SONAME'd file to a regular file
        link_chain = set()
        link_chain.add(so_named_file)

        diff = True

        while diff:
            diff = False

            for f in set(link_chain):
                full_f = simplify_path_static(self._fs_base + '/' + f)

                if os.path.islink(full_f):
                    target = os.path.join(os.path.dirname(f), os.readlink(full_f))
                else:
                    target = f

                if target in self.files and target not in link_chain:
                    diff = True
                    link_chain.add(target)

        # Everything else is probably a development symlink.
        self._dev_symlinks = self.files - link_chain

        # However things like the dynamic linker are not. Usually, development
        # symlinks are located under /usr and not plainly in /lib or /lib64.
        # For now we use this as a heuristic and see how far we'll come with
        # that.
        to_remove = set()
        for symlink in self._dev_symlinks:
            if not symlink.startswith('/usr'):
                to_remove.add(symlink)

        self._dev_symlinks -= to_remove


    def __str__(self):
        return self.name
