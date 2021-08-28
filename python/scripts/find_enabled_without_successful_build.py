#!/usr/bin/python3
"""
Find enabled packages the last build of which did either fail or is not
finished yet.
"""
from tslb import Architecture
from tslb import buildpipeline
from tslb.SourcePackage import SourcePackage, SourcePackageList
from tslb.parse_utils import is_yes


def main():
    last_stage = buildpipeline.all_stages[-1]

    for arch in Architectures.architecture:
        print("Checking architecture %s:" % Architectures.to_str(arch))
        for name in SourcePackageList(arch).list_version_numbers():
            sp = SourcePackage(name, arch)

            for v in sp.list_version_numbers():
                spv = sp.get_version(v)
                if not is_yes(spv.get_attribute_or_default('enabled', 'false')):
                    continue

                # Get last build pipeline event
                # kj

                # Is it a success event? If yes, is it for the last stage?

                # Is it an error?

                # Otherwise the package's build did not complete yet.


if __name__ == '__main__':
    main()
