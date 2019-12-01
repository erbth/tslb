from .SourcePackage import SourcePackageVersion
from tslb.VersionNumber import VersionNumberColumn
from sqlalchemy import types, Column, ForeignKey, ForeignKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
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
