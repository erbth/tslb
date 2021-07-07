from sqlalchemy import Column, types, ForeignKey, ForeignKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import FetchedValue
from tslb import timezone
from tslb.VersionNumber import VersionNumberColumn
from . import Attribute

Base = declarative_base()

class SourcePackage(Base):
    __tablename__ = 'source_packages'

    name = Column(types.String, primary_key = True)
    architecture = Column(types.Integer, primary_key = True)

    # Attributes
    # General
    creation_time = Column(types.DateTime(timezone=True), nullable = False)

    # List of versions in an attribute-like style.
    versions_modified_time = Column(types.DateTime(timezone=True), nullable = False)
    versions_reassured_time = Column(types.DateTime(timezone=True), nullable = False)
    versions_manual_hold_time = Column(types.DateTime(timezone=True), nullable = True)

    # Inititalize a brand new package before storing it in the db.
    def initialize_fields(self, name, architecture, time = None):
        if not time:
            time = timezone.now()

        self.name = name
        self.architecture = architecture

        self.creation_time = time
        self.versions_modified_time = time
        self.versions_reassured_time = time
        self.versions_manual_hold_time = None

class SourcePackageVersion(Base):
    __tablename__ = 'source_package_versions'

    source_package = Column(types.String, primary_key = True)
    architecture = Column(types.Integer, primary_key=True)
    __table_args__ = (ForeignKeyConstraint(
        (source_package, architecture),
        (SourcePackage.name, SourcePackage.architecture),
        onupdate='CASCADE', ondelete='CASCADE'),)

    version_number = Column(VersionNumberColumn, primary_key = True)

    # Attributes
    # General
    creation_time = Column(types.DateTime(timezone=True), nullable = False)

    # Installed files
    installed_files_modified_time = Column(types.DateTime(timezone=True), nullable = False)
    installed_files_reassured_time = Column(types.DateTime(timezone=True), nullable = False)

    # Current binary packages
    current_binary_packages_modified_time = Column(types.DateTime(timezone=True), nullable=False)
    current_binary_packages_reassured_time = Column(types.DateTime(timezone=True), nullable=False)

    def initialize_fields(self, source_package, architecture, version_number, time = None):
        """
        Initialize a new object before storing it in the db.
        """
        if not time:
            time = timezone.now()

        self.source_package = source_package
        self.architecture = architecture
        self.version_number = version_number
        self.creation_time = time

        self.installed_files_modified_time = time
        self.installed_files_reassured_time = time

        self.current_binary_packages_modified_time = time
        self.current_binary_packages_reassured_time = time

class SourcePackageVersionInstalledFile(Base):
    __tablename__ = 'source_package_version_installed_files'

    source_package = Column(types.String, primary_key = True)
    architecture = Column(types.Integer, primary_key = True)
    version_number = Column(VersionNumberColumn, primary_key = True)
    path = Column(types.String, primary_key = True)
    sha512sum = Column(types.String)

    __table_args__ = (ForeignKeyConstraint(
        (source_package, architecture, version_number),
        (SourcePackageVersion.source_package, SourcePackageVersion.architecture,
            SourcePackageVersion.version_number),
        onupdate='CASCADE', ondelete = 'CASCADE'), )

    def __init__(self, source_package, architecture, version_number, path, sha512sum):
        self.source_package = source_package
        self.architecture = architecture
        self.version_number = version_number
        self.path = path
        self.sha512sum = sha512sum

# Shared libraries
class SourcePackageSharedLibrary(Base):
    __tablename__ = 'source_package_shared_libraries'

    source_package = Column(types.String, primary_key = True)
    architecture = Column(types.Integer, primary_key = True)
    source_package_version_number = Column(VersionNumberColumn, primary_key = True)

    name = Column(types.String, primary_key = True)
    version_number = Column(VersionNumberColumn, nullable=True)
    abi_version_number = Column(VersionNumberColumn, nullable=True)
    soname = Column(types.String, primary_key=True)

    # I don't want too large foreign keys ...
    id = Column(types.BigInteger, unique=True, nullable=False, server_default=FetchedValue())


    __table_args__ = (ForeignKeyConstraint(
        (source_package, architecture, source_package_version_number),
        (SourcePackageVersion.source_package, SourcePackageVersion.architecture,
            SourcePackageVersion.version_number),
        onupdate='CASCADE', ondelete='CASCADE'),)

    __mapper_args__ = {'eager_defaults': True}


    def __init__(self, source_package, architecture, source_package_version_number, sl):
        """
        :param sl: The shared library to store
        :type sl: SharedLibraryTools.SharedLibrary
        """
        self.source_package = source_package
        self.architecture = architecture
        self.source_package_version_number = source_package_version_number
        self.name = sl.name
        self.version_number = sl.version_number
        self.abi_version_number = sl.abi_version_number
        self.soname = sl.soname


class SourcePackageSharedLibraryFile(Base):
    __tablename__ = 'source_package_shared_library_files'

    source_package_id = Column(types.BigInteger,
        ForeignKey(SourcePackageSharedLibrary.id, onupdate='CASCADE', ondelete='CASCADE'),
        primary_key = True)

    path = Column(types.String, primary_key=True)
    is_dev_symlink = Column(types.Boolean, nullable=False)

    def __init__(self, source_package_id, path, is_dev_symlink):
        self.source_package_id = source_package_id
        self.path = path
        self.is_dev_symlink = is_dev_symlink

# Current binary packages
class SourcePackageVersionCurrentBinaryPackage(Base):
    __tablename__ = 'source_package_version_current_binary_packages'

    source_package = Column(types.String, primary_key = True)
    architecture = Column(types.Integer, primary_key = True)
    version_number = Column(VersionNumberColumn, primary_key = True)

    name = Column(types.String, primary_key = True)

    __table_args__ = (ForeignKeyConstraint(
        (source_package, architecture, version_number),
        (SourcePackageVersion.source_package, SourcePackageVersion.architecture,
            SourcePackageVersion.version_number),
        onupdate='CASCADE', ondelete='CASCADE'), )

    def __init__(self, source_package, architecture, version_number, name):
        self.source_package = source_package
        self.architecture = architecture
        self.version_number = version_number
        self.name = name

# KV-like attributes
class SourcePackageAttribute(Base):
    __tablename__ = 'source_package_attributes'

    source_package = Column(types.String, primary_key = True)
    architecture = Column(types.Integer, primary_key = True)

    modified_time = Column(types.DateTime(timezone=True), nullable = False)
    reassured_time = Column(types.DateTime(timezone=True), nullable = False)
    manual_hold_time = Column(types.DateTime(timezone=True))

    key = Column(types.String, primary_key = True)
    value = Column(types.String)

    __table_args__ = (ForeignKeyConstraint(
        (source_package, architecture),
        (SourcePackage.name, SourcePackage.architecture),
        onupdate='CASCADE', ondelete='CASCADE'), )

    def __init__(self, source_package, architecture, key, value, time=None):
        if time is None:
            time = timezone.now()

        self.source_package = source_package
        self.architecture = architecture

        self.modified_time = time
        self.reassured_time = time
        self.manual_hold_time = None

        self.key = key
        self.value = value

class SourcePackageVersionAttribute(Base):
    __tablename__ = 'source_package_version_attributes'

    source_package = Column(types.String, primary_key = True)
    architecture = Column(types.Integer, primary_key = True)
    version_number = Column(VersionNumberColumn, primary_key = True)

    modified_time = Column(types.DateTime(timezone=True), nullable = False)
    reassured_time = Column(types.DateTime(timezone=True), nullable = False)
    manual_hold_time = Column(types.DateTime(timezone=True))

    key = Column(types.String, primary_key = True)
    value = Column(types.String)

    __table_args__ = (ForeignKeyConstraint(
        (source_package, architecture, version_number),
        (SourcePackageVersion.source_package, SourcePackageVersion.architecture,
            SourcePackageVersion.version_number),
        onupdate='CASCADE', ondelete='CASCADE'), )

    def __init__(self, source_package, architecture, version_number, key, value, time=None):
        if time is None:
            time = timezone.now()

        self.source_package = source_package
        self.architecture = architecture
        self.version_number = version_number

        self.modified_time = time
        self.reassured_time = time
        self.manual_hold_time = None

        self.key = key
        self.value = value
