"""
Some utility functions that are useful in various conditions or special states
of the system, and do not properly fit into exactly one Python module/package.
"""
import tclm
from tclm import lock_X
from SourcePackage import SourcePackage, SourcePackageList, SourcePackageVersion

def initially_create_all_locks():
    """
    Creates all locks at the tclm. Useful to populate them when starting the
    system.
    """
    spl = SourcePackageList(create_locks = True)

    sps = spl.list_source_packages()

    with lock_X(spl.fs_root_lock):
        with lock_X(spl.db_root_lock):
            for n in sps:
                p = SourcePackage(n, create_locks=True, write_intent=True)

                for v in p.list_version_numbers():
                    SourcePackageVersion(p, v, create_locks=True)
