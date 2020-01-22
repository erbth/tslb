"""
Some utility functions that are useful in various conditions or special states
of the system, and do not properly fit into exactly one Python module/package.
"""
from tslb.Architecture import architectures
from tslb.BinaryPackage import BinaryPackage
from tslb.SourcePackage import SourcePackage, SourcePackageList, SourcePackageVersion
from tslb.tclm import lock_X
from tslb import tclm

def initially_create_all_locks():
    """
    Creates all locks at the tclm. Useful to populate them when starting the
    system.
    """
    for arch in architectures.keys():
        spl = SourcePackageList(arch, create_locks = True)

        sps = [ e[0] for e in spl.list_source_packages(arch) ]

        with lock_X(spl.fs_root_lock):
            with lock_X(spl.db_root_lock):
                for n in sps:
                    p = SourcePackage(n, arch, create_locks=True, write_intent=True)

                    for v in p.list_version_numbers():
                        spv = SourcePackageVersion(p, v, create_locks=True)

                        for bn in spv.list_all_binary_packages():
                            for bv in spv.list_binary_package_version_numbers(bn):
                                BinaryPackage(spv, bn, bv, create_locks=True)
