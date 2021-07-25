import argparse
import re
from tslb import database as db
from tslb.database import BinaryPackage
from tslb import Architecture


def main():
    arch = 'amd64'

    parser = argparse.ArgumentParser("Search in files")
    parser.add_argument(metavar="<pattern>", dest="pattern")
    parser.add_argument("--only-latest", action="store_true",
            help="Only consider the latest version of each binary package.")

    args = parser.parse_args()
    with db.session_scope() as session:
        res = BinaryPackage.find_binary_packages_with_file_pattern(
                session, arch, args.pattern, only_latest=args.only_latest)

        for name, version, path in res:
            print("%s:%s@%s: %s" % (name, version, Architecture.to_str(arch), path))


if __name__ == '__main__':
    main()
    exit(0)
