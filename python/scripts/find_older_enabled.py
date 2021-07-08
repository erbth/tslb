"""
Find source packages of which the newest enabled version is not the newest
configured version.
"""
from tslb.SourcePackage import SourcePackageList, SourcePackage
from tslb.parse_utils import is_yes

arch = "amd64"

pkgs = SourcePackageList(arch).list_source_packages()
for pkg in pkgs:
    sp = SourcePackage(pkg, arch)
    versions = sp.list_version_numbers()
    if not versions:
        continue

    newest = max(versions)
    newest_enabled = None

    for v in versions:
        spv = sp.get_version(v)

        if is_yes(sp.get_version(v).get_attribute_or_default('enabled', None)):
            if newest_enabled is not None:
                newest_enabled = max(newest_enabled, v)
            else:
                newest_enabled = v

    if newest_enabled is not None and newest_enabled != newest:
        print("%s: newest enabled: %s, newest configured: %s" %
                (sp.short_str(), newest_enabled, newest))
