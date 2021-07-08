#!/usr/bin/python3
"""
List enabled source packages without upstream url
"""
import argparse
from tslb import Architecture
from tslb import SourcePackage as spkg
from tslb.parse_utils import is_yes
from tslb.Console import Color


parser = argparse.ArgumentParser("List enabled source packages without upstream url")
parser.add_argument("-i", "--include-with-url", action="store_true",
        help="Also print source packages with enabled urls")

parser.add_argument(metavar="<arch>", dest="arch", help="Architecture")

args = parser.parse_args()


arch = Architecture.to_int(args.arch)

for name in spkg.SourcePackageList(arch).list_source_packages():
    sp = spkg.SourcePackage(name, arch)
    enabled = bool([True for v in sp.list_version_numbers()
        if is_yes(sp.get_version(v).get_attribute_or_default('enabled', None))])

    if enabled:
        if sp.has_attribute('upstream_source_url'):
            if args.include_with_url:
                print(Color.GREEN + "`%s' has upstream_source_url" % sp.short_str() + Color.NORMAL)
        else:
            print(Color.RED + "`%s' has no upstream_source_url" % sp.short_str() + Color.NORMAL)
