from .BuildNode import FAIL_REASON_NODE_TRY_AGAIN
from .BuildNode import FAIL_REASON_PACKAGE, FAIL_REASON_NODE_ABORT
from tslb import Architecture
from tslb.Console import Color
from tslb.VersionNumber import VersionNumber
from tslb.package_builder import PackageBuilder, PkgBuildFailed
import signal
import subprocess
import sys
import time
import traceback


# Globals (for signal handling)
package_builder = None


def signal_handler(signum, stack_frame):
    if package_builder:
        package_builder.stop_build()


def worker(name, arch, version_number, identity):
    """
    This function is to be run in an extra process. It builds a package and
    reports the result as return value.

    :param name: The package's name
    :type name: str
    :param arch: The package's architecture
    :type arch: int
    :param version_number: The package's version number
    :type version_number: VersionNumber.VersionNumber
    :param identity: This build node's identity
    :type identity: str
    :returns: Error code from FAIL_REASON_* or 255 on success.
    """
    global package_builder

    print("Building Source Package %s:%s@%s" % (name, version_number, Architecture.to_str(arch)))

    pb = PackageBuilder(identity)

    try:
        package_builder = pb
        pb.build_package(name, arch, version_number)
        package_bulder = None

        print(Color.GREEN + "Completed successfully." + Color.NORMAL)
        return 255

    except PkgBuildFailed as e:
        print(Color.RED + "FAILED: " + Color.NORMAL + str(e) + ".")
        traceback.print_exc()
        return FAIL_REASON_PACKAGE

    except BaseException as e:
        print(Color.RED + "FAILED: " + Color.NORMAL + str(e) + ".")
        traceback.print_exc()
        return FAIL_REASON_NODE_ABORT


    # Catch all ...
    return FAIL_REASON_NODE_ABORT


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        name = sys.argv[1]
        arch = Architecture.to_int(sys.argv[2])
        version_number = VersionNumber(sys.argv[3])
        identity = sys.argv[4]

    except BaseException as e:
        print("ERROR: %s" % e)
        exit(FAIL_REASON_NODE_ABORT)

    exit(worker(name, arch, version_number, identity))
