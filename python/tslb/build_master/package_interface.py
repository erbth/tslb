"""
An interface to the packages.
"""
import asyncio
import contextlib
from tslb import Architecture
from tslb import build_pipeline
from tslb import build_state
from tslb.Constraint import DependencyList, VersionConstraint
from tslb.SourcePackage import NoSuchSourcePackage, NoSuchSourcePackageVersion, NoSuchAttribute
from tslb.SourcePackage import SourcePackageList, SourcePackage
from tslb.VersionNumber import VersionNumber
from tslb.tclm import lock_S

def create_package_interface(arch):
    """
    A factory (though it is only a function) to create either a real or a stub
    package interface.

    :param str/int arch: The architecture for which to create a package
        interface.
    :returns PackageInterface:
    """
    return StubPackageInterface(arch)


# Abstract interface class
class PackageInterface:
    """
    Abstract interface class
    """
    def __init__(self, arch):
        # Rather ugly way to disallow creating objects of this class.
        raise NotImplementedError

    async def get_packages(self):
        """
        :returns list(tuple(str, VersionNumber)):
        :raises InvalidConfiguration:
        """
        raise NotImplementedError

    def get_cdeps(self, package):
        """
        :param tuple(str, VersionNumber) package:
        :returns DependencyList:
        :raises InvalidConfiguration:
        """
        raise NotImplementedError

    def get_next_stage(self, package):
        """
        Get the next stage that the package must flow through or None if the
        package's build finished.

        :param tuple(str, VersionNumber) package:
        :returns str|NoneType:
        """
        raise NotImplementedError

    def outdate_package(self, package, stage):
        """
        :param tuple(str, VersionNumber) package:
        :param str stage:
        """
        raise NotImplementedError

    def compute_child_outdate(self, stage):
        """
        Determine which stage of children shall be outdated given a package is
        rebuilt in stage :param stage:. If :param stage: is None (to indicate
        that the package's build finished), this will return None.

        :param str|NoneType stage:
        :returns str:
        """
        raise NotImplementedError

    @contextlib.contextmanager
    def lock(self):
        """
        A context manager that represents a lock on the package base. While it
        is aquired, the package base cannot be changed by other processes.
        """
        raise NotImplementedError


# Stub implementation
class StubPackageInterface(PackageInterface):
    def __init__(self, arch):
        self._arch = Architecture.to_int(arch)
        self._pkgs = {
            ("glibc", VersionNumber("1.0")):        ([],                                    'configure'),
            ("tinfo", VersionNumber("1.1")):        (['glibc'],                             'configure'),
            ("ncurses", VersionNumber("3.0")):      (['glibc'],                             'configure'),
            ("readline", VersionNumber("1.7")):     (['glibc', 'tinfo'],                    'configure'),
            ("bash", VersionNumber("1.0")):         (['glibc', 'ncurses', 'readline'],      'configure'),
            ("eudev", VersionNumber("2.0")):        (['glibc', 'util-linux'],               'configure'),
            ("util-linux", VersionNumber("1.0")):   (['glibc', 'eudev', 'libmount'],        'configure'),
            ("libmount", VersionNumber("1.0")):     (['util-linux', 'glibc'],               'build'),
            ("snmpd", VersionNumber("1.0")):        (['glibc', 'libmount'],                 'finished')
        }

    async def get_packages(self):
        return list(self._pkgs.keys())

    def get_cdeps(self, package):
        dl = DependencyList()
        for name in self._pkgs[package][0]:
            dl.add_constraint(VersionConstraint('', '0'), name)

        return dl

    def get_next_stage(self, package):
        stage = self._pkgs[package][1]

        if stage == 'finished':
            return None

        return stage

    def outdate_package(self, package, stage):
        cdeps, old_stage = self._pkgs[package]

        if stage == 'configure' and old_stage in ('build', 'finished'):
            self._pkgs[package] = (cdeps, stage)

        elif stage == 'build' and old_stage in ('finished',):
            self._pkgs[package] = (cdeps, stage)


    def compute_child_outdate(self, stage):
        if stage in ('configure, build'):
            return 'configure'

        return None


    @contextlib.contextmanager
    def lock(self):
        yield None


# Real implementation
class RealPackageInterface(PackageInterface):
    def __init__(self, arch):
        self._arch = Architecture.to_int(arch)


    async def get_packages(self):
        spl = SourcePackageList(self._arch)

        all_pkg_names = spl.list_source_packages()
        enabled_pkg_versions = []

        for name in all_pkg_names:
            # 'yield' cpu for communication...
            await asyncio.sleep(0.0001)
            pkg = SourcePackage(name, self._arch)

            enabled_version = None

            for version in pkg.list_version_numbers():
                spv = pkg.get_version(version)

                if spv.has_attribute('enabled'):
                    val = spv.get_attribute('enabled')

                    if (isinstance(val, bool) and val) or \
                            (isinstance(val, str) and val.lower() == "true"):

                        if enabled_version is not None:
                            raise InvalidConfiguration(
                                    "Source package `%s' has multiple enabled versions." %
                                    name)

                        enabled_version = version

            if enabled_version is not None:
                enabled_pkg_versions.append((name, enabled_version))

        return enabled_pkg_versions


    def get_cdeps(self, pkg):
        name, version = pkg

        try:
            return SourcePackage(name, self._arch).get_version(version).get_attribute('cdeps')

        except (NoSuchSourcePackage, NoSuchSourcePackageVersion, NoSuchAttribute) as e:
            raise InvalidState(str(e))


    def get_next_stage(self, pkg):
        spv = SourcePackage(pkg[0], self._arch).get_version(pkg[1])
        return build_state.get_next_stage(build_state.get_build_state(spv))


    def outdate_package(self, pkg, stage):
        build_state.outdate_package_stage(pkg[0], self._arch, pkg[1], stage)


    def compute_child_outdate(self, stage):
        if not stage:
            return None

        return build_pipeline.outdates_child[stage].name


    @contextlib.contextmanager
    def lock(self):
        with lock_S(SourcePackageList(self._arch).db_root_lock):
            yield None


#******************************** Exceptions **********************************
class InvalidConfiguration(Exception):
    def __init__(self, msg):
        super().__init__("Invalid configuration: " + msg)
