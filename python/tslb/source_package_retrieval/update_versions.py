#!/usr/bin/python3
"""
Update source package versions if newer versions are available.
"""
from sqlalchemy.orm import aliased
from tslb import Architecture
from tslb import SourcePackage as spkg
from tslb.parse_utils import is_yes
import sys
import tslb.database as db
import tslb.database.upstream_versions


def update_versions(arch):
    """
    Ask if outdated enabled packages shall be updated and eventually perform
    the update.
    """
    for name in spkg.SourcePackageList(arch).list_source_packages():
        sp = spkg.SourcePackage(name, arch)
        enabled = False
        vs = sp.list_version_numbers()

        for v in vs:
            if is_yes(sp.get_version(v).get_attribute_or_default('enabled', None)):
                enabled = True

        if not enabled:
            continue

        newest_configured = max(vs)

        with db.session_scope() as s:
            uvs = aliased(db.upstream_versions.UpstreamVersion)
            uvs2 = aliased(db.upstream_versions.UpstreamVersion)

            newest_available = s.query(uvs.version_number)\
                    .filter(
                        uvs.name == sp.name,
                        ~s.query(uvs2)
                            .filter(
                                uvs2.name == sp.name,
                                uvs2.version_number > uvs.version_number)
                            .exists()
                    ).first()

            if not newest_available:
                continue

            newest_available = newest_available[0]

        if newest_available > newest_configured:
            print("Newever version (%s) for `%s' available (is %s):" %
                    (newest_available, sp.name, newest_configured))

            update = None
            while update is None:
                i = input('  update [yN]? ').lower()
                if i == 'y':
                    update = True
                elif i == 'n' or i == '':
                    update = False


# Update versions
def main():
    if len(sys.argv) != 2:
        print("Usage: %s <architecture>" % sys.argv[0])
        exit(1)

    try:
        arch = Architecture.to_int(sys.argv[1])
    except ValueError as e:
        print(str(e))
        exit(1)

    update_versions(arch)

if __name__ == '__main__':
    main()
    exit(0)
