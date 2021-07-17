import re
import sys
from tslb import database as db
from tslb.database import BinaryPackage
from tslb import Architecture

arch = 'amd64'

if len(sys.argv) < 2:
    print("Usage: %s <pattern>" % sys.argv[0])
    exit(1)

with db.session_scope() as session:
    pattern = ' '.join(sys.argv[1:])
    res = BinaryPackage.find_binary_packages_with_file_pattern(session, arch, pattern)

    for name, version, path in res:
        print("%s:%s@%s: %s" % (name, version, Architecture.to_str(arch), path))
