from tslb import Graph
from tslb.SourcePackage import SourcePackageList, SourcePackage, SourcePackageVersion
from tslb.tclm import lock_S

"""
Build graph containing all packages with edges that show compiletime
dependencies.
"""

class CdepGraph(object):
    def __init__(self, arch):
        """
        self.nodes containt, if built, the graph.

        :param arch: The architecture for which to build the graph.
        """
        self.arch = arch
        self.nodes = {}

    def build(self):
        """
        Populates self.nodes according to the current package database.
        """
        l = SourcePackageList(self.arch)

        # Make sure nothing moves while we look at it
        with lock_S(l.db_root_lock):
            # Clear the current graph
            self.nodes = {}

            pkgs = l.list_source_packages()

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
