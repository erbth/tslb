#!/usr/bin/env python3
import argparse
import sys
from tslb import Architecture
from tslb.SourcePackage import SourcePackageList, SourcePackage

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--arch", metavar="<architecture>", type=str,
                        required=True)

    parser.add_argument("-w", "--without", action="store_true",
                        help="List packages without the given attribute")

    parser.add_argument("attr", metavar="<attribute>", type=str)

    args = parser.parse_args()
    args.arch = Architecture.to_str(args.arch)

    return args


def main():
    args = parse_args()

    for pkg in SourcePackageList(args.arch).list_source_packages():
        sp = SourcePackage(pkg, args.arch)
        for v in sp.list_version_numbers():
            spv = sp.get_version(v)

            sel = spv.has_attribute(args.attr)
            if args.without:
                sel = not sel

            if sel:
                print(spv)


if __name__ == '__main__':
    main()
    sys.exit(0)
