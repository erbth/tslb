"""
The rootfs module of the package builder.
"""

from tslb import Architecture
from tslb.VersionNumber import VersionNumber
from tslb import SourcePackage
from tslb.build_pipeline import BuildPipeline
from tslb.Console import Color
import signal
import sys


def signal_handler(signum, stack_frame):
    """
    OK, this is bad, but it's better than the default actio anyway ...
    """
    if signum == signal.SIGTERM:
        exit(240)


def rootfs_module_entry(name, arch, version):
    """
    This function shall catch all exceptions and transform them into a return
    value to get a somewhat safe interface to the rootfs module.
    """
    try:
        sp = SourcePackage.SourcePackage(name, arch, write_intent=True)
        spv = sp.get_version(version)
        bp = BuildPipeline()

        r = bp.build_source_package_version(spv)

    except BaseException as e:
        print(Color.red("ERROR: %s" % e))
        r = False

    return 0 if r else 2


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, signal_handler)

    print(Color.magenta("Entered the rootfs module"))

    if len(sys.argv) != 4:
        print("Invalid API usage.")
        exit(1)

    try:
        name = sys.argv[1]
        arch = Architecture.to_int(sys.argv[2])
        version = VersionNumber(sys.argv[3])

    except BaseException as e:
        print("Invalid API usage: %s" % e)
        exit(1)

    r = rootfs_module_entry(name, arch, version)

    print(Color.magenta("Leaving the rootfs module"))
    exit(r)
