#!/usr/bin/python3
"""
Update source package versions if newer versions are available.
"""
from sqlalchemy.orm import aliased
from tslb import Architecture
from tslb import SourcePackage as spkg
from tslb import higher_order_tools as hot
from tslb.Console import Color
from tslb.parse_utils import is_yes, query_user_input
import sys
import tslb.database as db
import tslb.database.upstream_versions
import tslb.higher_order_tools.source_package


def update_versions(arch):
    """
    Ask if outdated enabled packages shall be updated and eventually perform
    the update.
    """
    for name in spkg.SourcePackageList(arch).list_source_packages():
        sp = spkg.SourcePackage(name, arch)
        newest_enabled = None
        vs = sp.list_version_numbers()

        for v in vs:
            if is_yes(sp.get_version(v).get_attribute_or_default('enabled', None)):
                if newest_enabled is None:
                    newest_enabled = v
                else:
                    newest_enabled = max(newest_enabled, v)

        if newest_enabled is None:
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
                print(Color.YELLOW +
                        "No upstream source package for `%s'." % sp.name + Color.NORMAL)
                continue

            newest_available = newest_available[0]

        if newest_available > newest_configured:
            print("Newever version (%s) for `%s' available (is %s):" %
                    (newest_available, sp.name, newest_configured))

            u = query_user_input('  update (a: abort)?', 'yNa')
            if u == 'a':
                print("User aborted.")
                exit(0)
            elif u != 'y':
                continue

            # Copy newest enabled or configured version shallowly and disable
            # the new copy.
            if newest_enabled != newest_configured:
                print("  The newest enabled version is not the newest configured version.")
                u = query_user_input('  Copy from the newest enabled (e) or configured (c) version?', 'ec')
                if u == 'e':
                    src_version = newest_enabled
                else:
                    src_version = newest_configured

            else:
                src_version = newest_configured

            # Upgrade lock on source package
            sp2 = spkg.SourcePackage(sp.name, sp.architecture, write_intent=True)
            sp = sp2

            spv = sp.get_version(src_version)
            new_spv = hot.source_package.shallow_version_copy(spv, newest_available)
            del spv

            new_spv.set_attribute('enabled', 'false')
            print("  Disabled new version.")

            # Disable old version and enable new version
            u = query_user_input(
                    '  Should the old version now be disabled and the new versionen be enabled?',
                    'yn')

            if u == 'y':
                sp.get_version(newest_enabled).set_attribute('enabled', 'false')
                new_spv.set_attribute('enabled', 'true')

            del new_spv

        else:
            print(Color.GREEN + "`%s' already up-to-date." % sp.name + Color.NORMAL)


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

    print("Checking for available newer versions...")
    update_versions(arch)

if __name__ == '__main__':
    main()
    exit(0)
