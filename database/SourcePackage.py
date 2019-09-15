from sqlalchemy import Column, types, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
import timezone
from VersionNumber import VersionNumberColumn
import Attribute

Base = declarative_base()

class SourcePackage(Base):
    __tablename__ = 'source_packages'

    name = Column(types.String, primary_key = True)

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
    version = Column(VersionNUmberColumn,
            ForeignKey('SourcePackage.version', ondelete = 'CASCADE', onupdate = 'CASCADE'),
            primary_key = True)
