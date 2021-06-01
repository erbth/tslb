"""
Build graph containing all packages with edges that show compiletime
dependencies.
"""
from tslb import Graph
from tslb import utils
from tslb.SourcePackage import SourcePackageList, SourcePackage, SourcePackageVersion
from tslb.tclm import lock_S


class CdepGraph(object):
    def __init__(self, arch):
        """
        self.nodes containt, if built, the graph.

        :param arch: The architecture for which to build the graph.
        """
        self.arch = arch
        self.nodes = {}

    def build(self, only_enabled=False):
        """
        Populates self.nodes according to the current package database.

        :param bool only_enabled: Include only packages with at least one
            enabled version. If cdeps of enabled packages are not enabled, an
            error will be thrown.
        """
        spl = SourcePackageList(self.arch)

        # Make sure nothing moves while we look at it
        with lock_S(spl.db_root_lock):
            # Clear the current graph
            self.nodes = {}

            pkgs = utils.list_enabled_source_packages(spl)

            # Add each package to the graph.
            for pkg in pkgs:
                # Data is a tuple (name, version, set([cdep names]))
                sp = SourcePackage(pkg, self.arch)
                spv = sp.get_latest_version()

                cdl = spv.get_cdeps().get_required()

                self.nodes[sp.name] = Graph.Node((sp.name, spv.version_number, cdl))

            # Build edges or throw
            for node in self.nodes.values():
                sp_name, sp_version_number, cdl = node.data

                for cdep in cdl:
                    if cdep not in self.nodes:
                        raise MissingCdep(sp_name, cdep)

                    node.add_child(self.nodes[cdep])


# Exceptions to make us happy
class MissingCdep(Exception):
    def __init__(self, pkg, cdep):
        super().__init__("Missing cdep `%s' required by `%s'" % (cdep, pkg))
