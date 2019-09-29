from sqlalchemy import Column, types, ForeignKey, ForeignKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
import timezone
from VersionNumber import VersionNumberColumn
from . import Attribute

Base = declarative_base()

class SourcePackage(Base):
    __tablename__ = 'source_packages'

    name = Column(types.String, primary_key = True)

    # Attributes
    # General
    creation_time = Column(types.DateTime(timezone=True), nullable = False)

    # List of versions in an attribute-like style.
    versions_modified_time = Column(types.DateTime(timezone=True), nullable = False)
    versions_reassured_time = Column(types.DateTime(timezone=True), nullable = False)
    versions_manual_hold_time = Column(types.DateTime(timezone=True), nullable = True)

    # Inititalize a brand new package before storing it in the db.
    def initialize_fields(self, name, time = None):
        if not time:
            time = timezone.now()

        self.name = name
        self.creation_time = time
        self.versions_modified_time = time
        self.versions_reassured_time = time
        self.versions_manual_hold_time = None

class SourcePackageVersion(Base):
    __tablename__ = 'source_package_versions'

    source_package = Column(types.String,
            ForeignKey(SourcePackage.name, ondelete = 'CASCADE', onupdate = 'CASCADE'),
            primary_key = True)
    version_number = Column(VersionNumberColumn, primary_key = True)

    # Attributes
    # General
    creation_time = Column(types.DateTime(timezone=True), nullable = False)

    # Files
    files_modified_time = Column(types.DateTime(timezone=True), nullable = False)
    files_reassured_time = Column(types.DateTime(timezone=True), nullable = False)

    def initialize_fields(self, source_package, version_number, time = None):
        """
        Initialize a new object before storing it in the db.
        """
        if not time:
            time = timezone.now()

        self.source_package = source_package
        self.version_number = version_number
        self.creation_time = time

        self.files_modified_time = time
        self.files_reassured_time = time

class SourcePackageVersionFile(Base):
    __tablename__ = 'source_package_version_files'

    source_package = Column(types.String, primary_key = True)
    source_package_version_number = Column(VersionNumberColumn, primary_key = True)
    path = Column(types.String, primary_key = True)
    sha512sum = Column(types.String, primary_key = True)

    __table_args__ = (ForeignKeyConstraint(
        (source_package, source_package_version_number),
        (SourcePackageVersion.source_package, SourcePackageVersion.version_number)), )

    def __init__(self, source_package, version_number, path, sha512sum):
        self.source_package = source_package
        self.source_package_version_number = version_number
        self.path = path
        self.sha512sum = sha512sum
