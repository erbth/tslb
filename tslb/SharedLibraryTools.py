import re
import os
from tslb.VersionNumber import VersionNumber
from tslb import CommonExceptions as ces
import subprocess
from tslb.database import SourcePackage as dbspkg

def file_is_shared_object (filename):
    return True if re.match ('^.*\.so(\.\d+)*$', filename) else False

def guess_library_name (filename):
    match = re.match ('^(.*)\.so(\.\d+)*$', filename)

    if match:
        return match.group(1)
    else:
        return None

class SharedLibrary(object):
    def __init__(self, *args):
        """
        Usage: (name, [file [,file [,...]]]) or
        (database.SourcePackage.SourcePackageSharedLibrary, list(files))
        """
        if len(args == 2) and\
                isinstance(args[0], dbspkg.SourcePackageSharedLibrary) and\
                isinstance(args[1], list):
            db = args[0]
            files = args[1]

            self.name = db.name
            self.files = files
            self.version_number = db.version_number
            self.abi_version_number = db.abi_version_number
            self.soname = db.soname

        elif len(args >= 2):
            name = args[0]
            files = args[1:]

            self.name = name
            self.files = set(files)
            self.version_number = None
            self.abi_version_number = None
            self.soname = None

            self.guess_version_number ()
            self.guess_abi_version_number()

        else:
            raise ValueError("Invalid arguements")

    def get_name(self):
        return self.name

    def get_files(self):
        return self.files

    def get_abi_versioned_files(self):
        abi_files = []

        for f in self.files:
            if re.match('^.*\.%s(\..*)?$' % self.abi_version_number, f):
                abi_files.append(f)

        return abi_files

    def get_dev_symlinks (self):
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
                target = os.path.join (os.path.dirname(f), os.readlink(f)) if os.path.islink(f) else f

                if target in self.files and target not in link_chain:
                    diff = True
                    link_chain.add(target)

        # Everything else is a development symlink.
        return self.files - link_chain

    def get_version_number(self):
        return self.version_number

    def get_abi_version_number(self):
        return self.abi_version_number


    def add_file(self, f):
        self.files.add(f)
        self.guess_version_number()
        self.guess_abi_version_number()


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

        if self.files:
            cmd = ['objdump', '-p', next(iter(self.files))]

            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            out, err = p.communicate()

            if p.returncode != 0:
                raise ces.CommandFailed(' '.join(cmd))

            match = re.search(r'SONAME\s+(' + self.name + '\.so(\.(\d+(\.\d+)*))?)', str(out))

            if not match:
                raise ces.AnalyzeError("'%s' has no SONAME" % self.name)

            self.soname = match.group(1)
            self.abi_version_number = VersionNumber(match.group(3)) if match.group(3) != '' else None

        else:
            self.abi_version_number = None


    def __str__(self):
        return self.name
