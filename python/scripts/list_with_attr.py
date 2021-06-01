#!/usr/bin/env python3
from tslb.SourcePackage import SourcePackageList, SourcePackage

# ATTR = "adapt_command"
ATTR = "additional_rdeps"
arch = "amd64"

for pkg in SourcePackageList(arch).list_source_packages():
    sp = SourcePackage(pkg, arch)
    for v in sp.list_version_numbers():
        spv = sp.get_version(v)
        if spv.has_attribute(ATTR):
            print(spv)
