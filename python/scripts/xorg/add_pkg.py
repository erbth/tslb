#!/usr/bin/python3
"""
Create or update an existing package with desired attributes.
"""
import argparse
from tslb import Architecture
from tslb.SourcePackage import SourcePackageList, SourcePackage
from tslb.VersionNumber import VersionNumber
from tslb import higher_order_tools as hot
from tslb.Console import Color
from tslb import Constraint
from tslb import parse_utils
import tslb.higher_order_tools.source_package
from tslb_source_package_retrieval import fetch_upstream_versions

ARCH = Architecture.amd64


def read_args():
    parser = argparse.ArgumentParser("Create or update a Xorg source package")
    parser.add_argument(metavar="<name>", dest="name", help="Source package name")
    parser.add_argument(metavar="<version>", dest="version", help="Source package version")
    parser.add_argument("--url", help="Upstream source url")
    parser.add_argument("--fetch", action='store_true', help="Fetch upstream versions")

    args = parser.parse_args()

    d = {
        'name': args.name,
        'version': VersionNumber(args.version),
        'url': args.url,
        'fetch': args.fetch,
    }
    return d


def cond_update(obj, attr, value):
    update = False
    if not obj.has_attribute(attr):
        update = True

    elif obj.get_attribute(attr) != value:
        if parse_utils.query_user_input("'%s' differs. Update?" % attr, 'yn') == 'y':
            update = True

    if update:
        print("Setting '%s'" % attr)
        obj.set_attribute(attr, value)


def main():
    # Read command line arguments
    args = read_args()

    # If the source package does not exist, create it
    spl = SourcePackageList(ARCH)
    if args['name'] in spl.list_source_packages():
        sp = SourcePackage(args['name'], ARCH, write_intent=True)
    else:
        print("Creating source package `%s'." % args['name'])
        sp = spl.create_source_package(args['name'])

    # Set the upstream source URL
    if args['url']:
        cond_update(sp, 'upstream_source_url', args['url'])

    # If the source package version does not exist, create it
    vs = sp.list_version_numbers()
    if args['version'] in vs:
        spv = sp.get_version(args['version'])

    else:
        # If there is another version, shallow-clone it
        if vs:
            v_to_clone = max(vs)
            print("Shallow-copying version `%s'." % v_to_clone)
            spv = hot.source_package.shallow_version_copy(
                sp.get_version(v_to_clone), args['version'])

        else:
            print("Creating version `%s'." % args['version'])
            spv = sp.add_version(args['version'])


    # Set build parameters
    # enabled
    spv.set_attribute('enabled', 'true')

    # tools
    tools = Constraint.DependencyList()
    tools.add_constraint(
            Constraint.VersionConstraint(Constraint.CONSTRAINT_TYPE_NONE, VersionNumber(0)),
            'basic_build_tools')

    cond_update(spv, 'tools', tools)

    # Add cdeps if missing
    if not spv.has_attribute('cdeps'):
        print("Adding empty cdeps.")
        spv.set_attribute(Constraint.DependencyList())

    # Source archive name
    if not spv.has_attribute('source_archive'):
        source_archive = '%s-%s.tar.bz2' % (args['name'], args['version'])
        print("Setting source_archive to `%s'." % source_archive)
        spv.set_attribute('source_archive', source_archive)

    # Configure command
    configure_command = "./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var"
    cond_update(spv, 'configure_command', configure_command)


    # Fetch upstream versions
    if args['fetch']:
        fetch_upstream_versions.fetch_versions_for_package(sp)


    print("\n" + Color.BRIGHT_YELLOW +
            "Remember to adapt cdeps and maybe configure_command!" + Color.NORMAL)


if __name__ == '__main__':
    main()
    exit(0)
