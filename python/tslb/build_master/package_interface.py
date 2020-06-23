"""
An interface to the packages.
"""
from tslb import Architecture
from tslb.Constraints import DependencyList, VersionConstraint
from tslb.VersionNumber import VersionNumber

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

    def get_packages(self):
        """
        :returns list(tuple(str, VersionNumber)):
        """
        raise NotImplementedError

    def get_cdeps(self, package):
        """
        :param tuple(str, VersionNumber) package:
        :returns DependencyList:
        """
        raise NotImplementedError

    def get_next_stage(self, package):
        """
        Get the next stage that the package must flow through.

        :param tuple(str, VersionNumber) package:
        :returns str:
        """
        raise NotImplementedError

    def outdate_package(self, package, stage):
        """
        :param tuple(str, VersionNumber) package:
        :param str stage:
        :returns str:
        """
        raise NotImplementedError

    def compute_child_outdate(self, stage):
        """
        Determine which stage of children shall be outdated given a package is
        rebuilt in stage :param stage:.

        :param str stage:
        :returns str:
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

    def get_packages(self):
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


# Real implementation
