import datetime
import dateutil
import locale
import subprocess
import tempfile
import tslb.database as db
import tslb.database.BuildPipeline
from sqlalchemy.orm import aliased
from tslb.Console import Color
from tslb import Architecture
from tslb import CommonExceptions as ces
from tslb import SourcePackage as spkg
from tslb.management_shell import *
from tslb.VersionNumber import VersionNumber
from tslb.timezone import localtime
from tslb.build_state import outdate_package_stage, outdate_enabled_versions_in_arch
import tslb.build_pipeline as bpp


class RootDirectory(Directory):
    def __init__(self):
        super().__init__()
        self.name = "source_packages"

    def listdir(self):
        return [ArchDirectory(a) for a in Architecture.architectures.keys()]


class ArchDirectory(Directory):
    """
    A directory for a specific architecture.
    """
    def __init__(self, arch):
        super().__init__()

        self.arch = Architecture.to_int(arch)
        self.name = Architecture.to_str(self.arch)


    def listdir(self):
        content = [SourcePackageDirectory(name, self.arch)
                for name in spkg.SourcePackageList(self.arch).list_source_packages()]

        content.append(SourcePackageActionOutdateEnabledVersionsArch(self.arch))
        content.append(SourcePackageActionCreate(self.arch))
        content.append(SourcePackageActionDestroy(self.arch))

        return content


class SourcePackageActionOutdateEnabledVersionsArch(Action):
    """
    Outdate all enabled versions in the architecture
    """
    def __init__(self, arch):
        super().__init__(writes=True)

        self.arch = arch
        self.name = "outdate_enabled_versions"


    def run(self, *args):
        if len(args) != 2:
            print("Usage: %s <stage>" % args[0])
            return

        try:
            outdate_enabled_versions_in_arch(self.arch, args[1])
            print(Color.GREEN + "finished." + Color.NORMAL)

        except ValueError as e:
            print(str(e))

        except BaseException as e:
            print(e)
            print(Color.RED + "FAILED." + Color.NORMAL)


class SourcePackageActionCreate(Action):
    """
    Create a new source package
    """
    def __init__(self, arch):
        super().__init__(writes=True)

        self.arch = arch
        self.name = "create"


    def run(self, *args):
        if len(args) != 2:
            print("Usage: %s <name>" % args[0])
            return

        name = args[1]

        print("This will create source package `%s'." % name)

        while True:
            i = input("Are you sure? [y/n] ")
            if i in ('y', 'Y'):
                break

            if i in ('n', 'N'):
                return

        try:
            spkg.SourcePackageList(self.arch).create_source_package(name)

        except spkg.SourcePackageExists:
            print("A source package with name `%s' exists already." % name)
            return

        print("Created `%s'." % name)


class SourcePackageActionDestroy(Action):
    """
    Destroy a source package
    """
    def __init__(self, arch):
        super().__init__(writes=True)

        self.arch = arch
        self.name = "delete"


    def run(self, *args):
        if len(args) != 2:
            print("Usage: %s <name>" % args[0])
            return

        name = args[1]

        print("This will destroy source package `%s'." % name)

        while True:
            i = input_no_history("Are you sure? [y/n] ")
            if i in ('y', 'Y'):
                break

            if i in ('n', 'N'):
                return

        spl = spkg.SourcePackageList(self.arch)
        exists = name in spl.list_source_packages()

        if not exists:
            print("WARNING: Source package `%s' does not exist in the database." % name)

        try:
            spl.destroy_source_package(name)
        except Exception as e:
            print(Color.RED + "ERROR: " + str(e) + Color.NORMAL)
            return

        if exists:
            print("Destroyed `%s'." % name)
        else:
            print("finished.")


class SourcePackageDirectory(Directory):
    """
    One directory per source package.
    """
    def __init__(self, name, arch):
        super().__init__()

        self.arch = arch
        self.name = name


    def listdir(self):
        return [
            SourcePackageVersionsDirectory(self.arch, self.name),
            SourcePackageGenericAction(self.name, self.arch, 'get_creation_time')
        ]


class SourcePackageBaseAction(Action):
    """
    A base class for actions on source packages that contains a factory that
    creates locked `SourcePackage` objects.
    """
    def __init__(self, name, arch, writes=False):
        super().__init__(writes=writes)

        self.pkg_name = name
        self.arch = arch


    def create_spkg(self, write_intent=False):
        return spkg.SourcePackage(self.pkg_name, self.arch, write_intent)


class SourcePackageGenericAction(SourcePackageBaseAction):
    """
    Simply calls the method of the given name without arguments on a
    `SourcePackage` instance.
    """
    def __init__(self, name, arch, method):
        super().__init__(name, arch)

        self.name = method
        self.method = method


    def run(self, *args):
        ret = getattr(self.create_spkg(), self.method)()

        def print_element(elem):
            if isinstance(elem, datetime.datetime):
                print(localtime(elem).strftime(locale.nl_langinfo(locale.D_T_FMT)))
            else:
                print(str(elem))

        if isinstance(ret, list) or isinstance(ret, tuple):
            for e in ret:
                print_element(e)

        else:
            print_element(ret)


#********************* Presenting SourcePackageVersions ***********************
class SourcePackageVersionsDirectory(Directory):
    """
    A directory that houses all versions of a source package.
    """
    def __init__(self, arch, name):
        super().__init__()

        self.arch = arch
        self.pkg_name = name

        self.name = "versions"


    def listdir(self):
        content = [SourcePackageVersionDirectory(self.pkg_name, self.arch, v)
                for v in spkg.SourcePackage(self.pkg_name, self.arch).list_version_numbers()]

        content.append(SourcePackageVersionsGetMeta(self.pkg_name, self.arch))
        content.append(SourcePackageVersionsManuallyHold(self.pkg_name, self.arch, True))
        content.append(SourcePackageVersionsManuallyHold(self.pkg_name, self.arch, False))
        content.append(SourcePackageVersionsAdd(self.pkg_name, self.arch))
        content.append(SourcePackageVersionsDelete(self.pkg_name, self.arch))
        content.append(SourcePackageVersionsCopyShallow(self.pkg_name, self.arch))

        return content


class SourcePackageVersionsGetMeta(SourcePackageBaseAction):
    """
    Print the versions' meta data.
    """
    def __init__(self, name, arch):
        super().__init__(name, arch)
        self.name = "get_meta"


    def run(self, *args):
        modified, reassured, manually_held = self.create_spkg().get_versions_meta()

        modified = localtime(modified).strftime(locale.nl_langinfo(locale.D_T_FMT))
        reassured = localtime(reassured).strftime(locale.nl_langinfo(locale.D_T_FMT))

        if manually_held is None:
            manually_held = "---"
        else:
            manually_held = localtime(manually_held).strftime(locale.nl_langinfo(locale.D_T_FMT))

        print("modified:      %s" % modified)
        print("reassured:     %s" % reassured)
        print("manually held: %s" % manually_held)


class SourcePackageVersionsManuallyHold(SourcePackageBaseAction):
    """
    Manually hold- or unhold a package's versions.

    :param hold: If set to true, hold the versions, otherwise unhold.
    """
    def __init__(self, name, arch, hold):
        super().__init__(name, arch, writes=True)

        self.hold = hold
        self.name = 'hold' if self.hold else 'unhold'


    def run(self, *args):
        sp = self.create_spkg(True)

        if self.hold != bool(sp.versions_manually_held()):
            if self.hold:
                sp.manually_hold_versions(False)
                print("Held versions manually.")
            else:
                sp.manually_hold_versions(True)
                print("Unheld versions manually.")


class SourcePackageVersionsAdd(SourcePackageBaseAction):
    """
    Add a new source package version
    """
    def __init__(self, name, arch):
        super().__init__(name, arch, writes=True)

        self.name = "add"


    def run(self, *args):
        if len(args) != 2:
            print("Usage: %s <version>" % args[0])
            return

        try:
            version = VersionNumber(args[1])

        except (TypeError, ValueError) as e:
            print("Invalid version number: %s" % e)
            return

        try:
            self.create_spkg(True).add_version(version)

        except spkg.SourcePackageVersionExists:
            print("Version exists already")
            return

        except ces.AttributeManuallyHeld:
            print("Versions are manually held.")
            return

        print("Created `%s'." % version)


class SourcePackageVersionsDelete(SourcePackageBaseAction):
    """
    Delete a source package version
    """
    def __init__(self, name, arch):
        super().__init__(name, arch, writes=True)

        self.name = "delete"


    def run(self, *args):
        if len(args) != 2:
            print("Usage: %s <version>" % args[0])
            return

        try:
            version = VersionNumber(args[1])

        except (TypeError, ValueError) as e:
            print("Invalid version number: %s" % e)
            return

        sp = self.create_spkg(True)

        if version not in sp.list_version_numbers():
            print("WARNING: This version does not exist in the database.")

        try:
            sp.delete_version(version)

        except ces.AttributeManuallyHeld:
            print("Versions are manually held.")
            return

        print("finished.")


class SourcePackageVersionsCopyShallow(SourcePackageBaseAction):
    """
    Copy a source package version and its attributes. Occurences of the old
    version number in str attributes are replaced with the new version number.
    """
    def __init__(self, name, arch):
        super().__init__(name, arch, writes=True)

        self.name = "copy_shallow"


    def run(self, *args):
        if len(args) != 3:
            print("Usage: %s <src> <dst>" % args[0])
            return

        try:
            src = VersionNumber(args[1])
            dst = VersionNumber(args[2])

        except (TypeError, ValueError) as e:
            print("Invalid version number: %s" % e)
            return

        sp = self.create_spkg(True)

        versions = sp.list_version_numbers()
        src_found = False

        for v in versions:
            if src == v:
                src_found = True

            if dst == v:
                print("Destination version number exists already.")
                return

        if not src_found:
            print("No such source version number")
            return

        src = sp.get_version(src)

        try:
            dst = sp.add_version(dst)

        except ces.AttributeManuallyHeld:
            print("Versions are manually held.")
            return

        old_version_string = str(src.version_number)
        new_version_string = str(dst.version_number)

        for attr in src.list_attributes():
            value = src.get_attribute(attr)

            # Replace the old version number
            if isinstance(value, str) and old_version_string in value:
                print("Attribute `%s': replacing version string `%s' with `%s'." %
                    (attr, old_version_string, new_version_string))

                value = value.replace(old_version_string, new_version_string)

            dst.set_attribute(attr, value)


#*************** Presenting a single source package version *******************
class SourcePackageVersionDirectory(Directory):
    """
    One directory per source package version.
    """
    def __init__(self, name, arch, version):
        super().__init__()

        self.pkg_name = name
        self.arch = Architecture.to_int(arch)
        self.version = VersionNumber(version)

        self.name = str(self.version)


    def listdir(self):
        return [
            SourcePackageVersionAttributesDirectory(self.pkg_name, self.arch, self.version),
            SourcePackageVersionBinaryPackagesDirectory(self.pkg_name, self.arch, self.version, False),
            SourcePackageVersionBinaryPackagesDirectory(self.pkg_name, self.arch, self.version, True),
            SourcePackageVersionBuildStateDirectory(self.pkg_name, self.arch, self.version),
            SourcePackageVersionGenericAction(self.pkg_name, self.arch, self.version, "get_creation_time"),
            SourcePackageVersionListAttributesAction(self.pkg_name, self.arch, self.version),
            SourcePackageVersionListSharedLibrariesAction(self.pkg_name, self.arch, self.version),
            SourcePackageVersionShowMostRecentInternalRDepsAction(self.pkg_name, self.arch, self.version),
            SourcePackageVersionInspectScratchSpaceAction(self.pkg_name, self.arch, self.version),
            SourcePackageVersionCleanBinaryPackagesAction(self.pkg_name, self.arch, self.version)
        ]


class SourcePackageVersionFactoryBase:
    """
    A base class that contains a factory for creating (and therefore locking)
    SourcePackageVersions and the corresponding SourcePackages.
    """
    def create_spv(self, write_intent=False):
        return spkg.SourcePackage(self.pkg_name, self.arch, write_intent)\
                .get_version(self.version)


class SourcePackageVersionGenericAction(Action, SourcePackageVersionFactoryBase):
    """
    Simply call the method with the given name without arguments on a
    `SourcePackageVersion` instance.
    """
    def __init__(self, name, arch, version, method):
        super().__init__()

        self.pkg_name = name
        self.arch = arch
        self.version = version

        self.name = method
        self.method = method


    def run(self, *args):
        ret  = getattr(self.create_spv(), self.method)()

        def print_element(elem):
            if isinstance(elem, datetime.datetime):
                print(localtime(elem).strftime(locale.nl_langinfo(locale.D_T_FMT)))
            else:
                print(str(elem))

        if isinstance(ret, list) or isinstance(ret, tuple):
            for e in ret:
                print_element(e)

        else:
            print_element(ret)


class SourcePackageVersionListAttributesAction(Action, SourcePackageVersionFactoryBase):
    """
    List a source package version's attributes and values.
    """
    def __init__(self, name, arch, version):
        super().__init__()

        self.pkg_name = name
        self.arch = arch
        self.version = version

        self.name = "list_attributes"


    def run(self, *args):
        spv = self.create_spv()
        attrs = spv.list_attributes()

        for attr in attrs:
            val = spv.get_attribute(attr)

            if isinstance(val, datetime.datetime):
                val = localtime(elem).strftime(locale.nl_langinfo(locale.D_T_FMT))
            elif isinstance(val, str):
                pass
            else:
                val = str(val)

            print("%s: %s" % (attr, val))


class SourcePackageVersionInspectScratchSpaceAction(Action, SourcePackageVersionFactoryBase):
    """
    Run a tools-system bash shell rooted in the package's scratch space. The
    scratch space is mounted read- and writable and thus the source package
    version locked in S+ mode.
    """
    def __init__(self, name, arch, version):
        super().__init__(writes=True)

        self.pkg_name = name
        self.arch = arch
        self.version = version

        self.name = 'inspect_scratch_space'


    def run(self, *args):
        try:
            spv = self.create_spv(True)
            spv.mount_scratch_space()

            subprocess.run(['bash'], cwd=spv.scratch_space.mount_path)

        except BaseException as e:
            print(Color.RED + "FAILED: " + Color.NORMAL + str(e) + "\n")


class SourcePackageVersionCleanBinaryPackagesAction(Action, SourcePackageVersionFactoryBase):
    """
    Remove old binary packages (those which are not built from the source
    package anymore and all but the most recent version of those which are
    built).
    """
    def __init__(self, name, arch, version):
        super().__init__(writes=True)

        self.pkg_name = name
        self.arch = arch
        self.version = version

        self.name = 'clean_binary_packages'


    def run(self, *args):
        print(
"This removes binary packages that are not currently built and all but the most\n"
"recent versions of those which are.\n")

        while True:
            try:
                r = input("Do you really want to proceed? [y/N] ")
                if r == 'y' or r == 'Y':
                    break
                if r == 'n' or r == 'N' or r == '':
                    return

            except KeyboardInterrupt:
                print()
                return

        spv = self.create_spv(True)
        spv.remove_old_binary_packages()


#************** Presenting a source package version's attributes **************
class SourcePackageVersionAttributesDirectory(Directory, SourcePackageVersionFactoryBase):
    """
    A directory that represents a source package version's attributes.
    """
    def __init__(self, name, arch, version):
        super().__init__()

        self.pkg_name = name
        self.arch = arch
        self.version = version

        self.name = 'attributes'


    def listdir(self):
        children = []

        for attr in self.create_spv().list_attributes():
            children.append(SourcePackageVersionAttributeProperty(
                self.pkg_name, self.arch, self.version, attr))

        children.append(SourcePackageVersionAddAttributeAction(self.pkg_name, self.arch, self.version))
        children.append(SourcePackageVersionUnsetAttributeAction(self.pkg_name, self.arch, self.version))

        return children


class SourcePackageVersionAttributeProperty(Property, SourcePackageVersionFactoryBase):
    """
    Objects of this class represent a propery of a source package version.
    """
    def __init__(self, name, arch, version, property_key):
        super().__init__(writable=True)

        self.pkg_name = name
        self.arch = arch
        self.version = version

        self.name = property_key


    def read_raw(self):
        return self.create_spv().get_attribute(self.name)


    def read(self):
        val = self.read_raw()

        if isinstance(val, str):
            return 'str: "%s"' % val
        elif isinstance(val, int):
            return 'int: "%d"' % val
        elif val is None:
            return 'None'
        else:
            return str(val)


    def write(self, value):
        self.create_spv(True).set_attribute(self.name, value)


class SourcePackageVersionAddAttributeAction(Action, SourcePackageVersionFactoryBase):
    """
    Add an attribute to a source package version.
    """
    def __init__(self, name, arch, version):
        super().__init__(writes=True)

        self.pkg_name = name
        self.arch = arch
        self.version = version

        self.name = 'add'


    def run(self, *args):
        if len(args) < 2 or len(args) > 3:
            print("Usage: %s <attr. name> [<attr. value>]" % (args[0]))
            return

        key = args[1]
        val = str(args[2]) if len(args) > 2 else None

        spv = self.create_spv(True)
        if spv.has_attribute(key):
            print("This attribute exists already.")
            return

        spv.set_attribute(key, val)


class SourcePackageVersionUnsetAttributeAction(Action, SourcePackageVersionFactoryBase):
    """
    Unset an attribute of a source package version.
    """
    def __init__(self, name, arch, version):
        super().__init__(writes=True)

        self.pkg_name = name
        self.arch = arch
        self.version = version

        self.name = 'unset'


    def run(self, *args):
        if len(args) != 2:
            print("Usage: %s <attr. name>" % (args[0]))
            return

        try:
            self.create_spv(True).unset_attribute(args[1])
        except ces.NoSuchAttribute:
            print("No such attribute.")


#*********** Presenting a source package version's binary packages ************
class BinaryPackageVersionFactoryBase:
    """
    An abstract base class that contains a factory for creating and locking
    binary packages among with their required source packages and source
    package versions.
    """
    def create_bp(self, write_intent=False):
        sp = spkg.SourcePackage(self.sp_name, self.sp_arch, write_intent=write_intent)
        spv = sp.get_version(self.sp_version)
        bp = spv.get_binary_package(self.bp_name, self.bp_version)

        return bp


class SourcePackageVersionBinaryPackagesDirectory(Directory, SourcePackageVersionFactoryBase):
    """
    Present all binary packages that where built out of a source package to the
    user.

    :param str name: The source package's name
    :param int arch: The source package's architecture
    :param VersionNumber version: The source package's version
    :param bool only_current: True means that only the current binary packages
        are added to the directory, False adds all.
    """
    def __init__(self, name, arch, version, only_current):
        super().__init__()

        self.pkg_name = name
        self.arch = arch
        self.version = version
        self.only_current = only_current

        self.name = 'current_binary_packages' if only_current else 'all_binary_packages'


    def listdir(self):
        bp_names = self.create_spv().list_current_binary_packages() \
            if self.only_current else \
            self.create_spv().list_all_binary_packages()

        children = []

        for bp_name in sorted(bp_names):
            children.append(BinaryPackageNameDirectory(
                    self.pkg_name, self.arch, self.version, bp_name))

        return children


class BinaryPackageNameDirectory(Directory, SourcePackageVersionFactoryBase):
    """
    Presents a binary package identified by a name. This is an abstraction that
    does not exist in the database as binary packages do always have a specific
    version. Two binary packages with the same name but a different version are
    considered different in TSLB's ecosystem, however there is an upgrade path
    between them.

    :param str sp_name: The source package's name
    :param int sp_arch: The source package's architecture
    :param VersionNumber sp_version: The source package's version
    :param str bp_name: The binary package's name
    """
    def __init__(self, sp_name, sp_arch, sp_version, bp_name):
        super().__init__()

        self.pkg_name = sp_name
        self.arch = sp_arch
        self.version = sp_version
        self.bp_name = bp_name

        self.name = bp_name


    def listdir(self):
        versions = self.create_spv().list_binary_package_version_numbers(self.bp_name)
        versions.sort()

        children = []

        for version in versions:
            children.append(BinaryPackageVersionDirectory(
                self.pkg_name, self.arch, self.version, self.bp_name, version))

        return children


class BinaryPackageVersionDirectory(Directory, BinaryPackageVersionFactoryBase):
    """
    Present a specific version of a binary package to the user. This presents
    what is refered to as `BinaryPackage` in the tslb ecosystem.

    :param str sp_name: The source package's name
    :param int sp_arch: The source package's architecture
    :param VersionNumber sp_version: The source package's version
    :param str bp_name: The binary package's name
    :param VersionNumber bp_version: The binary package's version
    """
    def __init__(self, sp_name, sp_arch, sp_version, bp_name, bp_version):
        super().__init__()

        self.sp_name = sp_name
        self.sp_arch = sp_arch
        self.sp_version = sp_version
        self.bp_name = bp_name
        self.bp_version = bp_version

        self.name = str(bp_version)


    def listdir(self):
        return [
            BinaryPackageVersionAttributesDirectory(self),
            BinaryPackageVersionGenericAction(self, 'get_creation_time'),
            BinaryPackageVersionGenericAction(self, 'get_files')
        ]


class BinaryPackageVersionAttributesDirectory(Directory):
    """
    A directory that presents a binary package's attributes.

    :param bpvd: the corresponding binary package version's directory
    :type bpvd: BinaryPackageVersionDirectory
    """
    def __init__(self, bpvd):
        super().__init__()

        self.bpvd = bpvd
        self.name = 'attributes'


    def listdir(self):
        children = [BinaryPackageVersionIsCurrentProperty(self.bpvd)]

        for prop_name in self.bpvd.create_bp().list_attributes():
            children.append(BinaryPackageVersionAttributeProperty(self.bpvd, prop_name))

        children.append(BinaryPackageVersionAddAttributeAction(self.bpvd))
        children.append(BinaryPackageVersionUnsetAttributeAction(self.bpvd))

        return children


class BinaryPackageVersionGenericAction(Action):
    """
    A generic action that calls the supplied method on a binary package without
    arguments.

    :param bpvd: the corresponding binary package version's directory
    :type bpvd: BinaryPackageVersionDirectory
    :param str method: The method to call.
    """
    def __init__(self, bpvd, method):
        super().__init__()

        self.bpvd = bpvd
        self.method = method

        self.name = method


    def run(self, *args):
        ret = getattr(self.bpvd.create_bp(), self.method)()

        def print_element(elem):
            if isinstance(elem, datetime.datetime):
                print(localtime(elem).strftime(locale.nl_langinfo(locale.D_T_FMT)))
            else:
                print(str(elem))

        if isinstance(ret, list) or isinstance(ret, tuple):
            for e in ret:
                print_element(e)

        else:
            print_element(ret)


class BinaryPackageVersionIsCurrentProperty(Property):
    """
    A read-only property that shows if a binary package is currently built out
    of the source package version.

    :param bpvd: the corresponding binary package version's directory
    :type bpvd: BinaryPackageVersionDirectory
    """
    def __init__(self, bpvd):
        super().__init__(writable=False)

        self.bpvd = bpvd
        self.name = 'currently_built'


    def read_raw(self):
        bp = self.bpvd.create_bp()
        return bp.name in bp.source_package_version.list_current_binary_packages()


    def read(self):
        built = self.read_raw
        return "Yes" if built else "No"


class BinaryPackageVersionAttributeProperty(Property):
    """
    A property that represents a binary package's attribute.

    :param bpvd: the corresponding binary package version's directory
    :type bpvd: BinaryPackageVersionDirectory
    :param str name: The propertie's name (key).
    """
    def __init__(self, bpvd, name):
        super().__init__(writable=True)

        self.bpvd = bpvd
        self.name = name


    def read_raw(self):
        return self.bpvd.create_bp().get_attribute(self.name)


    def read(self):
        val = self.read_raw()

        if isinstance(val, str):
            return 'str: "%s"' % val
        elif isinstance(val, int):
            return 'int: "%d"' % val
        elif val is None:
            return 'None'
        else:
            return str(val)


    def write(self, value):
        self.bpvd.create_bp(True).set_attribute(self.name, value)


class BinaryPackageVersionAddAttributeAction(Action):
    """
    Add an attribute to the binary package.

    :param bpvd: the corresponding binary package version's directory
    :type bpvd: BinaryPackageVersionDirectory
    """
    def __init__(self, bpvd):
        super().__init__(writes=True)

        self.bpvd = bpvd
        self.name = 'add'


    def run(self, *args):
        if len(args) < 2 or len(args) > 3:
            print("Usage: %s <attr. name> [<attr. value>]" % (args[0]))
            return

        key = args[1]
        value = str(args[2]) if len(args) > 2 else None

        self.bpvd.create_bp(True).set_attribute(key, value)


class BinaryPackageVersionUnsetAttributeAction(Action):
    """
    Unset an attribute of a binary package.

    :param bpvd: the corresponding binary package version's directory
    :type bpvd: BinaryPackageVersionDirectory
    """
    def __init__(self, bpvd):
        super().__init__(writes=True)

        self.bpvd = bpvd
        self.name = 'unset'


    def run(self, *args):
        if len(args) != 2:
            print("Usage: %s <attr. name>" % (args[0]))
            return

        try:
            self.bpvd.create_bp(True).unset_attribute(args[1])
        except ces.NoSuchAttribute:
            print("No such attribute.")


#******************************* Shared libraries *****************************
class SourcePackageVersionListSharedLibrariesAction(Action, SourcePackageVersionFactoryBase):
    """
    List a source package version's shared libraries.
    """
    def __init__(self, name, arch, version):
        super().__init__()

        self.pkg_name = name
        self.arch = arch
        self.version = version

        self.name = "list_shared_libraries"


    def run(self, *args):
        spv = self.create_spv()

        for lib in sorted(spv.get_shared_libraries(), key=lambda lib: lib.soname):
            print("%s (ABI-version: %s / Version: %s):" % (
                lib.get_name(),
                lib.get_abi_version_number(),
                lib.get_version_number()))

            print("  files:")
            for _file in lib.get_files():
                print("    `%s'" % _file)

            print("  dev symlinks:")
            for _dev_symlink in lib.get_dev_symlinks():
                print("    `%s'" % _dev_symlink)


#****************************** Show rdep graph *******************************
class SourcePackageVersionShowMostRecentInternalRDepsAction(Action, SourcePackageVersionFactoryBase):
    """
    Print or display (using a dot viewer) a graph of current (from last build)
    binary package's internal (only between binary packages of this source
    package version) runtime dependencies.

    Arguments: [-g, --graph] to display a graph using a dot viewer.
    """
    def __init__(self, name, arch, version):
        super().__init__()

        self.pkg_name = name
        self.arch = arch
        self.version = version

        self.name = 'show_most_recent_internal_rdeps'


    def run(self, *args):
        display = False

        if len(args) > 1:
            if len(args) == 2 and args[1] in ('-g', '--graph'):
                display = True

            else:
                print("Invalid arguments. Use [-g, --graph].")
                return

        rdeps = []

        spv = self.create_spv()

        all_bp_names = spv.list_all_binary_packages()
        current_bp_names = set(spv.list_current_binary_packages())

        for bp_name in all_bp_names:
            if bp_name not in current_bp_names:
                continue

            version = max(spv.list_binary_package_version_numbers(bp_name))
            bp = spv.get_binary_package(bp_name, version)

            if not bp.has_attribute('rdeps'):
                continue

            rdeps.append((bp_name, (version, bp.get_attribute('rdeps'))))

            # Remove references to spv
            del bp

        # Free locks
        del spv

        # Format a graph in dot
        dot = 'digraph "internal dependencies" {\n'

        node_labels = {}
        bp_versions = {}
        label = 1

        for name, v in rdeps:
            version, _ = v

            node_labels[name] = label
            bp_versions[name] = version

            dot += '    %d [label="%s:%s"];\n' % (label, name, version)

            label += 1

        dot += '\n'

        # Add edges to graph
        for name, v in rdeps:
            _, deps = v

            for dep in deps.get_required():
                if dep in node_labels and (dep, bp_versions[dep]) in deps:
                    dot += '    %d -> %d [label="%s"];\n' % (
                            node_labels[name],
                            node_labels[dep],
                            deps.get_constraint_list(dep))

        dot += '}'

        if display:
            cmd = ['xdot', '-']
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            p.communicate(dot.encode('UTF-8'))

        else:
            print(dot)


#******************************** Build events ********************************
class SourcePackageVersionBuildStateDirectory(Directory, SourcePackageVersionFactoryBase):
    """
    A directory that interfaces with the build pipeline and events that it
    generates.
    """
    def __init__(self, name, arch, version):
        super().__init__()

        self.pkg_name = name
        self.arch = arch
        self.version = version

        self.name = 'build_state'


    def listdir(self):
        return [
            SourcePackageVersionBuildStateListAction(self),
            SourcePackageVersionBuildStateShowEventDetailsAction(self),
            SourcePackageVersionBuildStateOutdateAction(self),
            SourcePackageVersionBuildStateListStagesAction()
        ]


class SourcePackageVersionBuildStateListAction(Action):
    """
    List a source package version's last build events
    """
    def __init__(self, build_state_directory):
        super().__init__()

        self.build_state_directory = build_state_directory
        self.name = 'list'


    def run(self, *args):
        events = []

        with db.session_scope() as s:
            se = aliased(db.BuildPipeline.BuildPipelineStageEvent)
            events = s.query(se)\
                .filter(se.source_package == self.build_state_directory.pkg_name,
                        se.architecture == self.build_state_directory.arch,
                        se.version_number == self.build_state_directory.version)\
                .order_by(se.time)


        for event in events[-60:]:
            print("[%s] %-10s %-30s (%s)" % (
                event.time.strftime(locale.nl_langinfo(locale.D_T_FMT)),
                db.BuildPipeline.BuildPipelineStageEvent.status_values.str_map[event.status],
                event.stage,
                event.snapshot_name))


class SourcePackageVersionBuildStateShowEventDetailsAction(Action):
    """
    Show details of a build event.
    """
    def __init__(self, build_state_directory):
        super().__init__()

        self.build_state_directory = build_state_directory
        self.name = 'show_event_details'


    def run(self, *args):
        if len(args) < 2:
            print("Usage: %s <timestamp as shown by `list'>" % args[0])
            return

        try:
            ts = datetime.datetime.strptime(
                    ' '.join(args[1:]),
                    locale.nl_langinfo(locale.D_T_FMT).replace('%e', '%d'))\
                            .replace(tzinfo=dateutil.tz.tzlocal())

        except ValueError as e:
            print("Invalid timestamp format: %s" % e)
            return

        # Find all events that match the queried timestamp (it has only second
        # precision) and present a list to select from.
        with db.session_scope() as s:
            se = aliased(db.BuildPipeline.BuildPipelineStageEvent)
            events = list(s.query(se)\
                .filter(se.source_package == self.build_state_directory.pkg_name,
                        se.architecture == self.build_state_directory.arch,
                        se.version_number == self.build_state_directory.version,
                        se.time >= ts,
                        se.time < ts + datetime.timedelta(seconds=1))\
                .order_by(se.time))

            if len(events) > 1:
                print("Multiple events match the given timestamp:")

                for i, event in enumerate(events):
                    print("%-5d: %-10s %-30s (%s)" % (
                        i,
                        db.BuildPipeline.BuildPipelineStageEvent.status_values.str_map[event.status],
                        event.stage,
                        event.snapshot_name))

                event = None

                while not event:
                    j = input("Please chose one [0..%d]: " % (len(events) - 1))
                    try:
                        j = int(j)
                    except ValueError:
                        print("Must be a number.")
                        continue

                    if j < 0 or j >= len(events):
                        print("Out of range.")
                        continue

                    event = events[j]

            elif len(events) == 1:
                event = events[0]

            else:
                print("No event at the givent timestamp.")
                return

            # Display information about the chosen event and the associated
            # console output.
            with tempfile.NamedTemporaryFile('w', encoding='utf8') as f:
                f.write("Package: %s@%s:%s\n\n" % (
                    event.source_package,
                    Architecture.to_str(event.architecture),
                    event.version_number))

                f.write("Time:          %s\n" % event.time.strftime('%a %b %e %H:%M:%S.%f %Y %z'))
                f.write("Stage:         %s\n" % event.stage)
                f.write("Status:        %s\n" % db.BuildPipeline.BuildPipelineStageEvent
                        .status_values.str_map[event.status])

                f.write("Snapshot name: %s\n\n" % event.snapshot_name)

                if event.output:
                    f.write("Console output:\n")
                    f.write(event.output)

                else:
                    f.write("No console output.\n")

                f.flush()

                subprocess.run(['pager', '-r', f.name])


class SourcePackageVersionBuildStateOutdateAction(Action):
    """
    Outdate a specific stage of the source package version.
    """
    def __init__(self, build_state_directory):
        super().__init__()

        self.build_state_directory = build_state_directory
        self.name = 'outdate'


    def run(self, *args):
        if len(args) != 2:
            print("Usage: %s <stage name>" % args[0])
            return

        try:
            outdate_package_stage(
                self.build_state_directory.pkg_name,
                self.build_state_directory.arch,
                self.build_state_directory.version,
                args[1])

            print(Color.GREEN + "finished." + Color.NORMAL)

        except ValueError as e:
            print(str(e))

        except BaseException as e:
            print(e)
            print(Color.RED + "FAILED." + Color.NORMAL)


class SourcePackageVersionBuildStateListStagesAction(Action):
    """
    List the stages of which the build pipeline is composed. It is convenient
    to have such an action in the source package version's build events
    directory, because it makes manually outdating the source package version
    easier.
    """
    def __init__(self):
        super().__init__()
        self.name = 'list_buildpipeline_stages'


    def run(self, *args):
        for stage in bpp.all_stages:
            print(stage.name)
