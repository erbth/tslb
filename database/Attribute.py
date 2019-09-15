from sqlalchemy import Column, types, ForeignKey
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class AttributeMeta(object):
    """
    A class to hold an attribute's meta information for i.e. returning or
    supplying it.
    """

    def __init__(self, modified_time, reassured_time, manual_hold_time):
        self.modified_time = modified_time
        self.reassured_time = reassured_time
        self.manual_hold_time = manual_hold_time

    def is_on_manual_hold (self):
        return self.manual_hold_time is not None


# Attributes of different types
class Attribute(Base):
    __abstract__ = True

    modified_time =    Column(types.DateTime, nullable=False)
    reassured_time =   Column(types.DateTime, nullable=False)
    manual_hold_time = Column(types.DateTime, nullable=True)

    def get_meta(self):
        return AttributeMeta (self.modified_time, self.reassured_time, self.manual_hold_time)

class StringAttribute(Attribute):
    __abstract__ = True
    value = Column(types.VARCHAR, nullable=True)

class BlobAttribute(Attribute):
    __abstract__ = True
    value = Column(types.BLOB, nullable=True)


# Useful exceptions for Attribute concerns
def NoSuchAttribute(Exception):
    def __init__(self):
        super('No such attribute')
