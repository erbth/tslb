#!/usr/bin/python3
"""
Create or update xorg libraries
"""
import argparse
import itertools
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
URL = "https://x.org/archive/individual/lib/"

META_PKG_NAME = "xorg-libraries"
META_PKG_VERSION = VersionNumber("1.0.0")

PKGS = [
    ("xtrans", "1.4.0"),
    ("libX11", "1.7.2"),
    ("libXext", "1.3.4"),
    ("libFS", "1.0.8"),
    ("libICE", "1.0.10"),
    ("libSM", "1.2.3"),
    ("libXScrnSaver", "1.2.3"),
    ("libXt", "1.2.1"),
    ("libXmu", "1.1.3"),
    ("libXpm", "3.5.13"),
    ("libXaw", "1.0.14"),
    ("libXfixes", "6.0.0"),
    ("libXcomposite", "0.4.5"),
    ("libXrender", "0.9.10"),
    ("libXcursor", "1.2.0"),
    ("libXdamage", "1.1.5"),
    ("libfontenc", "1.1.4"),
    ("libXfont2", "2.0.5"),
    ("libXft", "2.3.4"),
    ("libXi", "1.7.99.2"),
    ("libXinerama", "1.1.4"),
    ("libXrandr", "1.5.2"),
    ("libXres", "1.2.1"),
    ("libXtst", "1.2.3"),
    ("libXv", "1.0.11"),
    ("libXvMC", "1.0.12"),
    ("libXxf86dga", "1.1.5"),
    ("libXxf86vm", "1.1.4"),
    ("libdmx", "1.1.4"),
    ("libpciaccess", "0.16"),
    ("libxkbfile", "1.1.0"),
    ("libxshmfence", "1.3"),
]

# These additional pkgs will be added as dependencies to the meta package
ADDITIONAL_PKGS = [
    'libXau',
    'libXdmcp',
    'libxcb',
    'xcb-util',
    'xcb-util-image',
    'xcb-util-keysyms',
    'xcb-util-renderutil',
    'xcb-util-wm',
    'xcb-util-cursor'
]


def read_args():
    parser = argparse.ArgumentParser("Create or update Xorg libraries")
    parser.add_argument("--set-pkgs", action='store_true', help="Create- or update package versions")
    parser.add_argument("--set-meta", action='store_true', help="Create- or update meta package")
    parser.add_argument("--fetch", action='store_true', help="Fetch upstream versions")

    args = parser.parse_args()

    d = {
        'set_pkgs': args.set_pkgs,
        'set_meta': args.set_meta,
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


def create_pkg(name, version):
    print("Updating %s:%s" % (name, version))
    version = VersionNumber(version)

    # If the source package does not exist, create it
    spl = SourcePackageList(ARCH)
    if name in spl.list_source_packages():
        sp = SourcePackage(name, ARCH, write_intent=True)
    else:
        print("Creating source package `%s'." % name)
        sp = spl.create_source_package(name)

    # Set the upstream source URL
    cond_update(sp, 'upstream_source_url', URL)

    # If the source package version does not exist, create it
    vs = sp.list_version_numbers()
    if version in vs:
        spv = sp.get_version(version)

    else:
        # If there is another version, shallow-clone it
        if vs:
            v_to_clone = max(vs)
            print("Shallow-copying version `%s'." % v_to_clone)
            spv = hot.source_package.shallow_version_copy(
                sp.get_version(v_to_clone), version)

        else:
            print("Creating version `%s'." % version)
            spv = sp.add_version(version)


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
        source_archive = '%s-%s.tar.bz2' % (name, version)
        print("Setting source_archive to `%s'." % source_archive)
        spv.set_attribute('source_archive', source_archive)

    # Configure command
    configure_command = """#!/bin/bash -e

# The build and configure procedures were adapted from the book `Beyond Linux®
# From Scratch (systemd Edition)', `Version 10.1' by 'The BLFS Development
# Team'. At the time I initially wrote this file, the book was available from
# www.linuxfromscratch.org/blfs.
"""

    configure_command += "./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var"

    if name == "libXt":
        configure_command += " --with-appdefaultdir=/etc/X11/app-defaults"

    cond_update(spv, 'configure_command', configure_command + "\n")


    # Adapt cdeps
    cdeps = spv.get_attribute('cdeps')
    new_cdeps = Constraint.DependencyList()

    for pkg in cdeps.get_required():
        if pkg in ('glib', 'gcc', 'glibc'):
            continue

        for vc in cdeps.l[pkg]:
            new_cdeps.add_constraint(vc, pkg)

    for pkg in ['xorgproto', 'xcb-proto']:
        new_cdeps.add_constraint(
                Constraint.VersionConstraint(Constraint.CONSTRAINT_TYPE_NONE, VersionNumber(0)),
                pkg)

    spv.set_attribute('cdeps', new_cdeps)


    spv.set_attribute('dev_dependencies', 'cdeps_headers')


def create_meta_package():
    print("Updating meta-package '%s:%s'" % (META_PKG_NAME, META_PKG_VERSION))

    # If the source package does not exist, create it
    spl = SourcePackageList(ARCH)
    if META_PKG_NAME in spl.list_source_packages():
        sp = SourcePackage(META_PKG_NAME, ARCH, write_intent=True)
    else:
        print("  Creating source package `%s'." % META_PKG_NAME)
        sp = spl.create_source_package(META_PKG_NAME)

    # If the source package version does not exist, create it
    vs = sp.list_version_numbers()
    if META_PKG_VERSION in vs:
        spv = sp.get_version(META_PKG_VERSION)

    else:
        # If there is another version, shallow-clone it
        if vs:
            v_to_clone = max(vs)
            print("  Shallow-copying version `%s'." % v_to_clone)
            spv = hot.source_package.shallow_version_copy(
                sp.get_version(v_to_clone), META_PKG_VERSION)

        else:
            print("  Creating version `%s'." % META_PKG_VERSION)
            spv = sp.add_version(META_PKG_VERSION)


    # Set build parameters
    spv.set_attribute('enabled', 'true')
    spv.set_attribute('source_archive', None)
    spv.set_attribute('unpack_command', None)
    spv.set_attribute('configure_command', None)
    spv.set_attribute('build_command', None)
    spv.set_attribute('install_to_destdir_command', None)

    # Tools
    tools = Constraint.DependencyList()
    tools.add_constraint(
            Constraint.VersionConstraint(Constraint.CONSTRAINT_TYPE_NONE, VersionNumber(0)),
            'basic_build_tools')

    spv.set_attribute('tools', tools)

    # cdeps and rdeps
    cdeps = Constraint.DependencyList()
    additional_rdeps = []

    for pkg in itertools.chain((t[0] for t in PKGS), ADDITIONAL_PKGS):
        cdeps.add_constraint(
                Constraint.VersionConstraint(Constraint.CONSTRAINT_TYPE_NONE, VersionNumber(0)),
                pkg)

        dl = Constraint.DependencyList()
        dl.add_constraint(Constraint.VersionConstraint(">=", "current"), pkg + '-all')
        additional_rdeps.append((META_PKG_NAME + '-all', dl))

    spv.set_attribute('cdeps', cdeps)
    spv.set_attribute('additional_rdeps', additional_rdeps)


def main():
    # Read command line arguments
    args = read_args()

    if args['set_pkgs']:
        for pkg_name, pkg_version in PKGS:
            create_pkg(pkg_name, pkg_version)

    # Create or update meta package
    if args['set_meta']:
        create_meta_package()

    # Fetch upstream versions
    if args['fetch']:
        for pkg_name, pkg_version in PKGS:
            fetch_upstream_versions.fetch_versions_for_package(SourcePackage(pkg_name, ARCH))


    if args['set_pkgs']:
        print("\n" + Color.BRIGHT_YELLOW +
                "Remember to adapt cdeps!" + Color.NORMAL)


if __name__ == '__main__':
    main()
    exit(0)
