#!/usr/bin/env python3
"""
Determine if all required packages have an enabled version.
"""
from tslb.SourcePackage import SourcePackageList, SourcePackageVersion, SourcePackage
from tslb.parse_utils import is_yes
import sys

arch = "amd64"

ordered_lfs_packages = [
    "man-pages",
    "iana-etc",
    "glibc",
    "zlib",
    "bzip2",
    "xz",
    "zstd",
    "file",
    "readline",
    "m4",
    "bc",
    "flex",
    "tcl-core",
    "expect",
    "dejagnu",
    "binutils",
    "gmp",
    "mpfr",
    "mpc",
    "attr",
    "acl",
    "libcap",
    "shadow",
    "gcc",
    "pkg-config",
    "ncurses",
    "sed",
    "psmisc",
    "gettext",
    "bison",
    "grep",
    "bash",
    "libtool",
    "gdbm",
    "gperf",
    "expat",
    "inetutils",
    "perl",
    "xml-parser",
    "intltool",
    "autoconf",
    "automake",
    "kmod",
    "elfutils",
    "libffi",
    "openssl",
    "python3",
    "ninja",
    "meson",
    "coreutils",
    "check",
    "diffutils",
    "gawk",
    "findutils",
    "groff",
    "grub",
    "less",
    "gzip",
    "iproute2",
    "kbd",
    "libpipeline",
    "make",
    "patch",
    "man-db",
    "tar",
    "texinfo",
    "vim",
    "systemd",
    "dbus",
    "procps-ng",
    "util-linux",
    "e2fsprogs",
]

excluded_packages = [
    "groff",
    "man-db",
    "libpipeline",
    "zstd"
]


# Cmdline parsing
GUIDE = '-g' in sys.argv
PRINT_MISSING = not GUIDE


lfs_packages = set(ordered_lfs_packages)
excluded_packages = set(excluded_packages)
required_packages = lfs_packages - excluded_packages

# Find enabled packages
all_packages = set(SourcePackageList(arch).list_source_packages())
enabled_packages = set()

for pkg in all_packages:
    sp = SourcePackage(pkg, arch)
    enabled = False

    for v in sp.list_version_numbers():
        spv = sp.get_version(v)
        if spv.has_attribute('enabled') and is_yes(spv.get_attribute('enabled')):
            enabled = True
            break

        del spv

    if enabled:
        enabled_packages.add(pkg)

    del sp


missing_packages = required_packages - all_packages
not_enabled_packages = required_packages - enabled_packages - missing_packages


if PRINT_MISSING:
    print("Not enabled packages (%d):" % len(not_enabled_packages))
    for pkg in sorted(not_enabled_packages):
        print("  %s" % pkg)

    print("\nMissing packages (%d):" % len(missing_packages))
    for pkg in sorted(missing_packages):
        print("  %s" % pkg)

    print()


if GUIDE:
    n = 1
    next_n = 10

    print("Next actions:")
    for pkg in ordered_lfs_packages:
        if pkg not in required_packages:
            continue

        if pkg in enabled_packages:
            continue

        action = ""
        if pkg in missing_packages:
            action = "add"
        elif pkg in not_enabled_packages:
            action = "enable"
        else:
            action = "?"

        print(" %2d.: %s %s" % (n, action, pkg))
        n += 1
        if n > next_n:
            break
