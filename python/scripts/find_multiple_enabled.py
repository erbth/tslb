from tslb.SourcePackage import SourcePackageList, SourcePackage
from tslb.parse_utils import is_yes

arch = "amd64"

pkgs = SourcePackageList(arch).list_source_packages()
for pkg in pkgs:
    sp = SourcePackage(pkg, arch)
    enabled_found = False
    multiple_found = False

    for v in sp.list_version_numbers():
        spv = sp.get_version(v)

        if spv.has_attribute('enabled') and is_yes(spv.get_attribute('enabled')):
            if enabled_found:
                print("%s" % spv)

            enabled_found = True

    if multiple_found:
        print()
