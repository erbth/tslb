#!/usr/bin/python3
from tslb.SourcePackage import SourcePackageList, SourcePackage
from tslb import Constraint
from tslb.VersionNumber import VersionNumber
import sys


# Find cdeps of basic_build_tools
bbt = 'basic_build_tools'
bbt_cdeps = set(SourcePackage(bbt, 'amd64').get_latest_version()
        .get_attribute('cdeps').get_required())

# Add bbt to cdeps of each package that has it in tools and is not in the set
for name in SourcePackageList('amd64').list_source_packages():
    if name in bbt_cdeps:
        print("Skipping '%s'." % name)
        continue

    spv = SourcePackage(name, 'amd64', write_intent=True).get_latest_version()
    if spv.has_attribute('tools') and bbt in spv.get_attribute('tools').get_required():
        print("Adding to '%s'." % name)
        cdeps = spv.get_attribute('cdeps')
        cdeps.add_constraint(
                Constraint.VersionConstraint(Constraint.CONSTRAINT_TYPE_NONE, VersionNumber(0)),
                bbt)

        if 'gcc' in cdeps.get_required():
            cdeps.remove_dependency('gcc')
            print("  Removing dependency on gcc.")

        spv.set_attribute('cdeps', cdeps)

    else:
        print("Not required for '%s'." % name)
