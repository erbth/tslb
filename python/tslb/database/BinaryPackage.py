from .SourcePackage import SourcePackageVersion
from tslb.VersionNumber import VersionNumberColumn
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


def find_binary_packages_with_file(session, arch, path, is_absolute=False, only_latest=False):
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
    :param bool only_latest: If True, only the latest version of a package is
        returned in case more versions match, otherwise all are returned
    :returns list(tuple(str, VersionNumber)): A list of binary package versions
        found
    """
    arch = Architecture.to_int(arch)
    bpf = aliased(BinaryPackageFile)

    bpq = session.query(bpf.binary_package, bpf.version_number)
    if is_absolute:
        bpq = bpq.filter(bpf.architecture == arch, bpf.path == path)
    else:
        bpq = bpq.filter(bpf.architecture == arch, bpf.path.like('%' +
            path.replace('%', '\%').replace('_', '\_')))

    if only_latest:
        bpf2 = aliased(BinaryPackageFile)

        bpq = bpq.filter(~session.query(bpf2)
                .filter(bpf2.binary_package == bpf.binary_package,
                    bpf2.architecture == bpf.architecture,
                    bpf2.path == bpf.path,
                    bpf2.version_number > bpf.version_number).exists())

    return list(bpq.distinct().all())
