#!/bin/bash
"""
Find enabled development versions of packages using the .90-99 heuristic.
"""
from tslb.SourcePackage import SourcePackageList, SourcePackage
from tslb import parse_utils
from tslb.VersionNumber import VersionNumber

ARCH = 'amd64'

# (<pkg name>, <pkg source version>)
whitelist = set((n,VersionNumber(v)) for n,v in [
    ('nmap', '7.91'),
    ('tcpdump', '4.99.1')
])


def main():
    spl = SourcePackageList(ARCH)
    for n in spl.list_source_packages():
        sp = SourcePackage(n, ARCH)

        for v in sp.list_version_numbers():
            if (n, v) in whitelist:
                continue

            spv = sp.get_version(v)

            if not parse_utils.is_yes(spv.get_attribute_or_default('enabled', 'false')):
                continue

            is_dev = False
            for comp in v.components:
                for l,h in [(90,99), (900, 999), (9000, 9999)]:
                    if comp >= l and comp <= h:
                        is_dev = True
                        break

            if is_dev:
                print(spv)


if __name__ == '__main__':
    main()
    exit(0)
