from sqlalchemy import types
from tslb.VersionNumber import VersionNumber

class VersionNumberColumn(types.TypeDecorator):
    """
    Represents VersionNumbers in object relational databases
    """
    impl = types.ARRAY(types.Integer)

    # This could probably be set to `True`, however I'm not sure of the actual
    # implications and disabling the cache is always save.
    cache_ok = False

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        return value.components

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        v = VersionNumber(0)
        v.components = value
        return v
