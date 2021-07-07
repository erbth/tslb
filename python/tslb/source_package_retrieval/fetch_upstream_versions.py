#!/usr/bin/python3
"""
Download lists of available upstream package version numbers and store them in
the database. This module does also provide a __main__.
"""
from tslb import Architecture
from tslb import Console
from tslb import SourcePackage as spkg
from tslb import timezone
from tslb.Console import Color
from tslb.parse_utils import is_yes
from tslb.source_package_retrieval import find_version_numbers as fvn
import sys
import tslb.database as db
import tslb.database.upstream_versions


def fetch_versions_for_package(sp, out=sys.stdout):
    """
    :param SourcePackage sp: Source Package
    :returns: True on success, otherwise False.
    """
    if not sp.has_attribute('upstream_source_url'):
        print(Color.YELLOW + "WARNING: Source package `%s' has no attribute `upstream_source_url'." %
                sp.short_str() + Color.NORMAL, file=out)
        return False

    # Find upstream version numbers
    Console.print_status_box("Finding versions of `%s'" % sp.short_str(), file=out)
    try:
        versions = fvn.find_versions_at_url(sp.name, sp.get_attribute('upstream_source_url'))
        Console.update_status_box(True, file=out)
    except fvn.FindException as e:
        Console.update_status_box(False, file=out)
        print(Color.RED + "ERROR: " + Color.NORMAL + str(e), file=out)
        return False

    # Store version numbers in database
    now = timezone.now()

    with db.session_scope() as s:
        t = db.upstream_versions.UpstreamVersion.__table__
        s.execute(t.delete().where(t.c.name == sp.name))
        s.flush()

        s.execute(t.insert([
            {
                'name': sp.name,
                'version_number': v,
                'download_url': urls[0],
                'signature_download_url': urls[1],
                'retrieval_time': now
            }
            for v, urls in versions
        ]))

    return True


def fetch_versions_for_enabled_packages(arch, out=sys.stdout):
    """
    Fetch versions for all packages that have at least one version enabled.
    """
    for name in spkg.SourcePackageList(arch).list_source_packages():
        sp = spkg.SourcePackage(name, arch)
        enabled = False
        for v in sp.list_version_numbers():
            if is_yes(sp.get_version(v).get_attribute_or_default('enabled', None)):
                enabled = True

        if enabled:
            fetch_versions_for_package(sp, out)

        del sp


# Download lists of version numbers
def main():
    if len(sys.argv) != 2:
        print("Usage: %s <architecture>" % sys.argv[0])
        exit(1)

    try:
        arch = Architecture.to_int(sys.argv[1])
    except ValueError as e:
        print(str(e))
        exit(1)

    fetch_versions_for_enabled_packages(arch)

if __name__ == '__main__':
    main()
    exit(0)
