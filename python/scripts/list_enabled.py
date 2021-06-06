from tslb.SourcePackage import SourcePackageList, SourcePackage
from tslb.parse_utils import is_yes
from tslb import Architecture

import argparse

parser = argparse.ArgumentParser("List enabled source packages")
parser.add_argument("-v", "--versions", action="store_true", help="Include versions in output")
args = parser.parse_args()


for arch in Architecture.architectures:
    print("Architecture: %s" % Architecture.to_str(arch))

    for pkg in SourcePackageList(arch).list_source_packages():
        sp = SourcePackage(pkg, arch)

        enabled_vs = []

        for v in sp.list_version_numbers():
            spv = sp.get_version(v)
            if spv.has_attribute('enabled') and is_yes(spv.get_attribute('enabled')):
                enabled_vs.append(v)

        if enabled_vs:
            print("  %s" % pkg)

            if args.versions:
                for v in enabled_vs:
                    print("    %s" % v)
