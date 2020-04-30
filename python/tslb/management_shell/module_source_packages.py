import datetime
import locale
from tslb.management_shell import *
from tslb import SourcePackage as spkg
from tslb import Architecture
from tslb.VersionNumber import VersionNumber
from tslb.timezone import localtime


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
        return [SourcePackageDirectory(name, self.arch)
                for name in spkg.SourcePackageList(self.arch).list_source_packages()]


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


# Presenting a single source package version
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
            SourcePackageVersionGenericAction(self.pkg_name, self.arch, self.version, "get_creation_time"),
            SourcePackageListAttributesAction(self.pkg_name, self.arch, self.version),
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


class SourcePackageListAttributesAction(Action, SourcePackageVersionFactoryBase):
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

        children.append(SourcePackageVersionAttributeAddAction(self.pkg_name, self.arch, self.version))
        children.append(SourcePackageVersionAttributeUnsetAction(self.pkg_name, self.arch, self.version))

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


    def read(self):
        val = self.create_spv().get_attribute(self.name)

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


class SourcePackageVersionAttributeAddAction(Action, SourcePackageVersionFactoryBase):
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

        self.create_spv(True).set_attribute(key, val)


class SourcePackageVersionAttributeUnsetAction(Action, SourcePackageVersionFactoryBase):
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

        self.create_spv(True).unset_attribute(args[1])
