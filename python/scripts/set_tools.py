from tslb.SourcePackage import SourcePackage, SourcePackageList, SourcePackageVersion
from tslb.Constraint import DependencyList, VersionConstraint
from tslb.parse_utils import is_yes

spl = SourcePackageList("amd64")
pkgs = spl.list_source_packages()

for pkg in pkgs:
    sp = SourcePackage(pkg, "amd64", write_intent=True)
    for v in sp.list_version_numbers():
        spv = sp.get_version(v)
        if spv.has_attribute('enabled') and is_yes(spv.get_attribute('enabled')):
            if spv.has_attribute('tools'):
                continue

            print(spv)

            dl = DependencyList()
            dl.add_constraint(VersionConstraint('', '0'), "glibc")
            dl.add_constraint(VersionConstraint('', '0'), "zlib")

            spv.set_tools(dl)
