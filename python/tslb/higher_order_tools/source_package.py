"""
Higher-order tools that operate on source packages
"""
from tslb import CommonExceptions as ces
from tslb.VersionNumber import VersionNumber
import sys
import time


def shallow_version_copy(src, dst, out=sys.stdout):
    """
    Copy a source package version in a "shallow manner"

    :param SourcePackageVersion src:
    :param VersionNumber dst:
    :returns SourcePackageVersion: The new source package version
    :raises ces.VersionExists: If the destination version number exists already
    :raises ces.AttributeManuallyHeld: If the versions of the SourcePackage are
        manually held.
    """
    dst = VersionNumber(dst)

    sp = src.source_package
    if dst in sp.list_version_numbers():
        raise ces.VersionExists(dst)

    dst_spv = sp.add_version(dst)

    # Copy attributes replacing occurances of the version number in them.
    old_version_string = str(src.version_number)
    new_version_string = str(dst)

    for attr in src.list_attributes():
        value = src.get_attribute(attr)

        if isinstance(value, str) and old_version_string in value:
            print("Attribute `%s': replacing version string `%s' with `%s'." %
                    (attr, old_version_string, new_version_string), file=out)

            value = value.replace(old_version_string, new_version_string)

        dst_spv.set_attribute(attr, value)

    return dst_spv
