#!/usr/bin/python3
"""
Fetch specific (instead of all enabled) packages from upstream.
"""
import sys
from tslb_source_package_retrieval import fetch_upstream_versions
from tslb.SourcePackage import SourcePackage


def main():
    if len(sys.argv) < 3:
        print("Usage: %s <arch> <pkg1> [<pkg2> ...]")
        exit(1)

    arch = sys.argv[1]
    for pkg in sys.argv[2:]:
        fetch_upstream_versions.fetch_versions_for_package(SourcePackage(pkg, arch))


if __name__ == '__main__':
    main()
    exit(0)
