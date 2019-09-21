from sqlalchemy import Column, types, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
import timezone
from VersionNumber import VersionNumberColumn
from . import Attribute

Base = declarative_base()

class SourcePackage(Base):
    __tablename__ = 'source_packages'

    name = Column(types.String, primary_key = True)

    # List of versions in an attribute-like style.
    versions_modified_time = Column(types.DateTime(timezone=True), nullable = False)
    versions_reassured_time = Column(types.DateTime(timezone=True), nullable = False)
    versions_manual_hold_time = Column(types.DateTime(timezone=True), nullable = True)

    def hold_versions_manually(self, time = None):
        if not time:
            time = timezone.now()

        self.versions_manual_hold_time = time

    def versions_manually_held(self):
        return bool(versions_manual_hold_time)

    def set_versions_modified(self, time = None):
        if not time:
            time = timezone.now()

        self.versions_modified_time = time
        self.versions_reassured_time = time

    def set_versions_reassured(self, time = None):
        if not time:
            time = timezone.now()

        self.versions_reassured_time = time

    # Inititalize a brand dnew package before storing it in the db.
    def initialize_fields(self, name, time = None):
        if not time:
            time = timezone.now()

        self.name = name
        self.versions_modified_time = time
        self.versions_reassured_time = time
        self.versions_manual_hold_time = None

class SourcePackageVersion(Base):
    __tablename__ = 'source_package_versions'

    source_package = Column(types.String,
            ForeignKey('SourcePackage.name', ondelete = 'CASCADE', onupdate = 'CASCADE'),
            primary_key = True)
    version = Column(VersionNumberColumn, primary_key = True)

    # Lists of attributes of different types
    def get_attribute (self, name):
        """
        :returns: The attribute's value.
        :except:  A Attribute.NoSuchAttribute if no such attribute exists
                  (required since the value can be None)
        """
        pass

    def get_attribute_meta (self, name):
        """
        :returns: An instance of Attribute.AttributeMeta.
        :except:  A Attribute.NoSuchAttribute if no such attribute exists
                  (required since the value can be None)
        """
        pass

    def set_attribute (self, value, change_time=None):
        """
        Updates or initially sets an attribute.
        """
        if change_time is None:
            change_time = timezone.now()

        pass

class SourcePackackage_StringAttributes(Attribute.StringAttribute):
    __tablename__ = 'source_package__string_attribute'

    source_package = Column(types.String,
            ForeignKey('SourcePackage.name', ondelete = 'CASCADE', onupdate = 'CASCADE'),
            primary_key = True)
    version = Column(VersionNumberColumn,
            ForeignKey('SourcePackage.version', ondelete = 'CASCADE', onupdate = 'CASCADE'),
            primary_key = True)
