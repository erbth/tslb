#!/usr/bin/python3
"""
List reverse dependencies of a binary package version
"""
import argparse
import re
from sqlalchemy.orm import aliased
from tslb import Architecture
from tslb.Constraint import DependencyList
from tslb.SourcePackage import SourcePackage
from tslb.VersionNumber import VersionNumber
import tslb.database as db
import tslb.database.BinaryPackage as dbbp


def main():
    parser = argparse.ArgumentParser("List reverse dependencies of a binary package version")
    parser.add_argument(metavar="pkg@arch[:version]", dest="pkg", help="Binary package version")

    args = parser.parse_args()

    # Interpret binary package version
    m = re.fullmatch(r"(.*)@([^:@]+)(?::([^:@]+))?", args.pkg)
    if not m:
        print("Invalid binary package format.")
        exit(1)

    bp_name = m[1]
    bp_arch = Architecture.to_int(m[2])
    bp_version = VersionNumber(m[3]) if m[3] else None

    with db.session_scope() as s:
        # If bp_version is None, find the latest version number
        if bp_version is None:
            b = aliased(dbbp.BinaryPackage)
            b2 = aliased(dbbp.BinaryPackage)
            v = s.query(b.version_number)\
                    .filter(b.architecture == bp_arch,
                            b.name == bp_name,
                            ~s.query(b2)\
                                .filter(b2.architecture == b.architecture,
                                        b2.name == b.name,
                                        b2.version_number > b.version_number)\
                                .exists())\
                    .first()

            if not v:
                print("Could not find latest version number - does the binary package exist?")
                exit(1)

            bp_version = v[0]

        # Find the requested binary package
        sn, sv = dbbp.find_source_package_version_for_binary_package(
                s, bp_name, bp_version, bp_arch)

        requested_bp = SourcePackage(sn, bp_arch).get_version(sv)\
                .get_binary_package(bp_name, bp_version)


        # Find latest version of each binary package
        b = aliased(dbbp.BinaryPackage)
        b2 = aliased(dbbp.BinaryPackage)

        bps = s.query(b.source_package, b.architecture, b.source_package_version_number,
                    b.name, b.version_number)\
                .filter(~s.query(b2)\
                            .filter(b2.architecture == b.architecture,
                                    b2.name == b.name,
                                    b2.version_number > b.version_number)\
                            .exists())\
                .all()

        bps = list(bps) + [requested_bp]


        # Build the reverse dependency graph
        R = {}
        for e in bps:
            if e is requested_bp:
                bp = requested_bp
            else:
                sn, a, sv, bn, v = e
                bp = SourcePackage(sn, a).get_version(sv).get_binary_package(bn, v)

            id_ = (bp.name, bp.architecture)
            if id_ not in R:
                R[id_] = []

            # Add edges
            deps = bp.get_attribute_or_default('rdeps', DependencyList()).get_required() + \
                    bp.get_attribute_or_default('rpredeps', DependencyList()).get_required()

            for dep in deps:
                id2 = (dep, bp.architecture)
                if id2 not in R:
                    R[id2] = []

                R[id2].append(id_)

            del bp

        # Find reverse dependencies
        rev_deps = set(R[(bp_name, bp_arch)])

        # Print reverse dependencies
        for name, arch in sorted(rev_deps, key=lambda x: (x[1], x[0])):
            print("%s@%s" % (name, Architecture.to_str(arch)))



if __name__ == '__main__':
    main()
    exit(0)
