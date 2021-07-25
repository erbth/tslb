from .SourcePackage import SourcePackageVersion
from tslb.VersionNumber import VersionNumber, VersionNumberColumn
from sqlalchemy import types, Column, ForeignKey, ForeignKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import aliased
from tslb import Architecture
from tslb import timezone

Base = declarative_base()

class BinaryPackage(Base):
    __tablename__ = 'binary_packages'

    source_package = Column(types.String)
    architecture = Column(types.Integer, primary_key=True)
    source_package_version_number = Column(VersionNumberColumn)

    name = Column(types.String, primary_key = True)
    version_number = Column(VersionNumberColumn, primary_key = True)

    creation_time = Column(types.DateTime(timezone=True), nullable=False)

    # Files
    files_modified_time = Column(types.DateTime(timezone=True), nullable = False)
    files_reassured_time = Column(types.DateTime(timezone=True), nullable = False)

    __table_args__ = (ForeignKeyConstraint(
        (source_package, architecture, source_package_version_number),
        (SourcePackageVersion.source_package, SourcePackageVersion.architecture,
            SourcePackageVersion.version_number),
        onupdate='CASCADE', ondelete='CASCADE'),)

    def initialize_fields(self, source_package, architecture, source_package_version_number,
            name, version_number, time=None):

        if time is None:
            time = timezone.now()

        self.source_package = source_package
        self.architecture = architecture
        self.source_package_version_number = source_package_version_number
        self.name = name
        self.version_number = version_number
        self.creation_time = time
        self.files_modified_time = time
        self.files_reassured_time = time

# Files
class BinaryPackageFile(Base):
    __tablename__ = 'binary_package_files'

    binary_package = Column(types.String, primary_key = True)
    architecture = Column(types.Integer, primary_key = True)
    version_number = Column(VersionNumberColumn, primary_key = True)
    path = Column(types.String, primary_key = True)
    sha512sum = Column(types.String)

    __table_args__ = (ForeignKeyConstraint(
        (binary_package, architecture, version_number),
        (BinaryPackage.name, BinaryPackage.architecture, BinaryPackage.version_number),
        onupdate='CASCADE', ondelete = 'CASCADE'), )

    def __init__(self, binary_package, architecture, version_number, path, sha512sum):
        self.binary_package = binary_package
        self.architecture = architecture
        self.version_number = version_number
        self.path = path
        self.sha512sum = sha512sum

# KV-like attributes
class BinaryPackageAttribute(Base):
    __tablename__ = 'binary_package_attributes'

    binary_package = Column(types.String, primary_key = True)
    architecture = Column(types.Integer, primary_key = True)
    version_number = Column(VersionNumberColumn, primary_key = True)

    modified_time = Column(types.DateTime(timezone=True), nullable = False)
    reassured_time = Column(types.DateTime(timezone=True), nullable = False)
    manual_hold_time = Column(types.DateTime(timezone=True))

    key = Column(types.String, primary_key = True)
    value = Column(types.String)

    __table_args__ = (ForeignKeyConstraint(
        (binary_package, architecture, version_number),
        (BinaryPackage.name, BinaryPackage.architecture, BinaryPackage.version_number),
        onupdate='CASCADE', ondelete='CASCADE'), )

    def __init__(self, binary_package, architecture, version_number, key, value, time=None):
        if time is None:
            time = timezone.now()

        self.binary_package = binary_package
        self.architecture = architecture
        self.version_number = version_number

        self.modified_time = time
        self.reassured_time = time
        self.manual_hold_time = None

        self.key = key
        self.value = value


#****************** Low-level functions for searching etc. ********************
def find_binary_packages(session, name, arch):
    """
    This function searches for binary packages with the specified name and
    architecture. All version number of binary packages that match them (the
    version number is the degree of freedom here) are returned.

    :param session: A SQLAlchemy database session
    :param str name: The name of binary packages that should be found
    :param str|int arch: The architecture for which packages should be
        searched
    :returns list(VersionNumber): The found binary package versions
    """
    arch = Architecture.to_int(arch)
    bp = aliased(BinaryPackage)

    q = session.query(bp.version_number)\
            .filter(bp.architecture == arch, bp.name == name)\
            .all()

    return [t[0] for t in q]


def find_binary_packages_with_file(session, arch, path, is_absolute=False, only_newest=False):
    """
    This function searches in all known files of binary packages for binary
    packages of the specified architecture that contain the specified path.

    If the path is specified to be absolute (see :param is_absolute:), the
    whole file paths are matched agains the specified path. Otherwise the
    functions searches for packages with files that end with the specified
    path.

    :param session: A SQLAlchemy database session
    :param str path: The path to search for
    :param str|int arch: The architecture in which should be searched
    :param bool is_absolute: True if the path should be treated as absolute
        path, otherwise false.
    :param bool only_newest: If True, only the binary package with the newest
        version number is returned, even if multiple different packages contain
        the file.
    :returns list(tuple(str, VersionNumber)): A list of binary package versions
        found
    """
    arch = Architecture.to_int(arch)
    bpf = aliased(BinaryPackageFile)

    cte = session.query(bpf)
    if is_absolute:
        cte = cte.filter(bpf.architecture == arch, bpf.path == path)
    else:
        cte = cte.filter(bpf.architecture == arch, bpf.path.like('%' +
            path.replace('\\', '\\\\').replace('%', r'\%').replace('_', r'\_'), escape='\\'))

    cte = cte.cte('candidates')
    cand1 = aliased(cte)

    bpq = session.query(cand1.c['binary_package'], cand1.c['version_number'])

    if only_newest:
        cand2 = aliased(cte)
        bpq = bpq.filter(~session.query(cand2)
                .filter(cand2.c['version_number'] > cand1.c['version_number']).exists())

    return list(bpq.distinct().all())


def find_binary_packages_with_file_pattern(session, arch, pattern, only_latest=False):
    """
    This function searches in all known files of binary packages for binary
    packages of the specified architecture that contain a file matching the
    specified pattern. The pattern my include the wildcard characters '*' and
    '?', where '?' can be any single character (like with globbing).

    The pattern can contain '/' as well or may start with a '/'.

    :param session: A SQLAlchemy database session
    :param str pattern: The pattern to search for
    :param str|int arch: The architecture in which should be searched
    :param bool only_latest: If true, only the files of the latest version of
        each binary package are searched for the pattern.
    :returns list(tuple(str, VersionNumber, path)): A list of binary package
        versions found, along with the matched paths. The list is sorted
        alphabetically and by increasing version number.
    """
    pattern = pattern.replace('\\', '\\\\').replace('%', r'\%').replace('_', r'\_')
    pattern = pattern.replace('*', '%').replace('?', '_')

    arch = Architecture.to_int(arch)
    bpf = aliased(BinaryPackageFile)

    q = session.query(bpf.binary_package, bpf.version_number, bpf.path)\
            .filter(bpf.architecture == arch,
                    bpf.path.like(pattern, escape='\\'))

    if only_latest:
        # Filter out matches from binary package versions that are not the
        # latest version of the binary package.
        bp = aliased(BinaryPackage)
        q = q.filter(~session.query(bp)\
                .filter(bp.name == bpf.binary_package,
                        bp.architecture == bpf.architecture,
                        bp.version_number > bpf.version_number)\
                .exists())

    q = q.order_by(bpf.binary_package, bpf.version_number, bpf.path)\
            .distinct()

    return list(q.all())


def find_source_package_version_for_binary_package(session, bp_name, bp_version, arch):
    """
    Given a binary package name, version and architecture find the
    corresponding source package's name and version.

    :param session: A SQLAlchemy database session
    :param str bp_name: The binary package's name
    :param VersionNumber|constructable bp_version: The binary package's version
    :param arch: The binary package's architecture
    :returns Tuple(str, VersionNumber)|NoneType: The corresponding source
        package version's name and version number
    """
    bp = aliased(BinaryPackage)
    return session.query(bp.source_package, bp.source_package_version_number)\
            .filter(bp.architecture == Architecture.to_int(arch),
                    bp.name == bp_name,
                    bp.version_number == VersionNumber(bp_version))\
            .first()
