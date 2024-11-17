#!/bin/bash
"""
Find enabled development versions of packages using the .90-99 heuristic and
the uneven-version-component heuristic.
"""
from tslb.SourcePackage import SourcePackageList, SourcePackage
from tslb import parse_utils
from tslb.VersionNumber import VersionNumber

ARCH = 'amd64'
UNEVEN_VERSION_COMPONENT = True

# (<pkg name>, <pkg source version>)
whitelist = set((n,VersionNumber(v)) for n,v in [
    ('nmap', '7.91'),
    ('tcpdump', '4.99.1')
])


def main():
    spl = SourcePackageList(ARCH)
    for n in spl.list_source_packages():
        sp = SourcePackage(n, ARCH)
        upstream_source_url = sp.get_attribute_or_default('upstream_source_url', None)

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

            if UNEVEN_VERSION_COMPONENT:
                if upstream_source_url and ('gnome' in upstream_source_url or 'cpan.org' in upstream_source_url):
                    for comp in v.components[1:3]:
                        if comp % 2 != 0:
                            is_dev = True

            if is_dev:
                print("%s (from %s)" % (spv, upstream_source_url))


if __name__ == '__main__':
    main()
    exit(0)
