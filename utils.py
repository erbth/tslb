"""
Some utility functions that are useful in various conditions or special states
of the system, and do not properly fit into exactly one Python module/package.
"""
import tclm
import SourcePackage

def initially_create_all_locks():
    """
    Creates all locks at the tclm. Useful to populate them when starting the
    system.
    """
    spl = SourcePackage.SourcePackageList(create_locks = True)
