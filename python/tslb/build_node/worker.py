from .BuildNode import FAIL_REASON_NODE_TRY_AGAIN
from .BuildNode import FAIL_REASON_PACKAGE, FAIL_REASON_NODE_ABORT
from tslb import Architecture
from tslb.VersionNumber import VersionNumber
from tslb.package_builder import PackageBuilder, PkgBuildFailed
import subprocess
import sys
import time


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
    print("Building Source Package %s:%s@%s" % (name, version_number, Architecture.to_str(arch)))

    print("\033[32mStarting an interactive bash shell ...\033[0m")
    subprocess.run(['bash'])

    print("done.")
    return 255

    pb = PackageBuilder(identity)

    try:
        pb.build_package(name, arch, version_number)
        print(Color.GREEN + "Completed successfully." + Color.NORMAL)
        return 255

    except PkgBuildFailed:
        print(Color.RED + "FAILED." + Color.NORMAL)
        return FAIL_REASON_PACKAGE

    except:
        print(Color.RED + "FAILED." + Color.NORMAL)
        return FAIL_REASON_NODE_ABORT


    # Catch all ...
    return FAIL_REASON_NODE_ABORT


if __name__ == "__main__":
    try:
        name = sys.argv[1]
        arch = Architecture.to_int(sys.argv[2])
        version_number = VersionNumber(sys.argv[3])
        identity = sys.argv[4]

    except BaseException as e:
        print("ERROR: %s" % e)
        exit(FAIL_REASON_NODE_ABORT)

    exit(worker(name, arch, version_number, identity))
