from tslb.SourcePackage import SourcePackageList, SourcePackage
from tslb.parse_utils import is_yes
from tslb import Architecture

import argparse

parser = argparse.ArgumentParser("List enabled source packages (were the latest version is enabled)")
parser.add_argument("-v", "--versions", action="store_true", help="Include enabled versions in output")
parser.add_argument("-d", "--disabled", action="store_true", help="List disabled instead of enabled packages")
args = parser.parse_args()


for arch in Architecture.architectures:
    print("Architecture: %s" % Architecture.to_str(arch))

    for pkg in SourcePackageList(arch).list_source_packages():
        sp = SourcePackage(pkg, arch)

        enabled_vs = []
        enabled = False

        vs = sp.list_version_numbers()
        latest = max(vs)

        for v in vs:
            spv = sp.get_version(v)
            if spv.has_attribute('enabled') and is_yes(spv.get_attribute('enabled')):
                enabled_vs.append(v)

                if v == latest:
                    enabled = True


        if (enabled and not args.disabled) or (not enabled and args.disabled):
            print("  %s" % pkg)

            if args.versions:
                for v in enabled_vs:
                    print("    %s%s" % ('but: ' if args.disabled else '', v))
