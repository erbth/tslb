#!/usr/bin/python3
"""
Copy the latest version of each enabled package from the collecting repo to the
destination directory.
"""
import argparse
import os
import shutil
import sys
from tslb import Architecture
from tslb import settings
from tslb.SourcePackage import SoucePackage, SourcePackageList
from tslb.parse_utils import is_yes


def process_arch(args, arch):
    arch_str = Architecture.to_str(arch)
    verbose = args['verbose']
    only_enabled = args['only_enabled']

    src = os.path.join(settings.get_collectin_repo_location(), arch_str)
    dst = os.path.join(args['dst'], arch_str)

    print("Processing architecture '%s'." % arch_str)

    os.mkdir(dst)

    # Copy the transport forms of the latest versions of all current binary
    # packages in the given architecture.
    for sp_name in SourcePackageList(arch).list_source_packages():
        sp = SourcePackage(sp_name, arch)
        for v in sp.list_version_numbers():
            spv = sp.get_version(v)

            if only_enabled and not is_yes(spv.get_attribute_or_default('enabled', 'true')):
                if verbose:
                    print("  Skipping `%s'..." % spv)
                continue

            for bpn in spv.list_current_binary_packages:
                bpv = max(spv.list_binary_package_version_numbers(bpn))

                transport_form = '%s-%s_%s.tpm2' % (bpn, bpv, arch_str)
                print("  Copying '%s'..." % transport_form)
                shutil.copy(src, dst)

    print()


def read_args():
    parser = argparse.ArgumentParser("Create a repo with latest package versions")
    parser.add_argument('dst', metavar='<destination>', help="Destination directory (must not exist yet)")
    parser.add_argument('-e', '--only-enabled', action='store_true', help="Copy only enabled versions")
    parser.add_argument('-v', '--verbose', action='store_true')

    parsed = parser.parse_args()

    args = {
        'dst': parsed.dst,
        'verbose': parsed.verbose,
        'only_enabled': parsed.only_enabled
    }
    return args

def main():
    args = read_args()

    dst = args['dst']
    if os.path.exists(dst):
        print("Destination `%s' exists already." % dst)
        exit(1)

    # Ensure that the collecting repo is mounted
    if not os.path.isdir(settings.get_collecting_repo_location()):
        print("Cannot access the collecting repo.")
        exit(1)

    # Create target directory
    os.mkdir(dst)

    # Determine architectures to process
    archs = []
    for arch in Architecture.architectures:
        arch_str = Architecture.to_str(arch)
        if os.path.exists(os.path.join(settings.get_collecting_repo_location(), arch_str)):
            archs.append(arch)

    # Process architectures
    for arch in archs:
        process_arch(args, arch)

    print("\nFinished.")
    print("""If you intend to distribute this snapshot, remember to create an index
with a unique name (e.g. date or source package version of a meta package""")


if __name__ == '__main__':
    main()
    exit(0)
