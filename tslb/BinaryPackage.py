from Architecture import architectures
from CommonExceptions import NoSuchAttribute, MissingWriteIntent, AttributeManuallyHeld
from VersionNumber import VersionNumber
from datetime import datetime
from datetime import time as dttime
from sqlalchemy.orm import aliased
from tclm import lock_S, lock_Splus, lock_X
import base64
import database as db
import database.BinaryPackage as dbbpkg
import database.SourcePackage as dbspkg
import os
import pickle
import pytz
import tclm
import timezone

def generate_version_number(time = None):
    """
    :param time: If not None, it will be used to generate the micro-version.
    :type time: datetime.datetime or None
    """
    if time is None:
        time = datetime.utcnow()
    else:
        time = time.astimezone(pytz.utc).replace(tzinfo=None)

    tdiff = time - datetime.combine(time.date(), dttime())
    msec = tdiff.seconds * 1000 + round(tdiff.microseconds / 1000)
    return VersionNumber(time.year, time.timetuple().tm_yday, msec)

class BinaryPackage(object):
    def __init__(self, source_package_version, name, version_number, create_locks=False, db_session=None):
        """
        :param source_package_version: The source package version to which this
            binary package belongs to.
        :type source_package_version: SourcePackage.SourcePackageVersion
        :param name: The binary package's name (must - together with the version
            number and the architecture - be unique among all binary packages).
        :type name: str
        :param version_number: The binary package's version number.
        :param create_locks: If true, the required locks are created.
        :param db_session: If not None, the given session will be used for db
            operations (i.e. for transactionality).
        """
        self.source_package_version = source_package_version
        self.name = name
        version_number = VersionNumber(version_number)
        self.version_number = version_number

        # For convenience
        self.architecture = self.source_package_version.architecture

        # Create locks if requested
        self.fsrlp = source_package_version.fsrlp + ".binary_packages.%s.%s" %\
                (self.name, str(self.version_number).replace('.', '_'))
        self.dbrlp = source_package_version.dbrlp + ".binary_packages.%s.%s" %\
                (self.name, str(self.version_number).replace('.', '_'))

        self.fs_root_lock = tclm.define_lock(self.fsrlp)
        self.db_root_lock = tclm.define_lock(self.dbrlp)

        if create_locks:
            self.ensure_write_intent()

            self.fs_root_lock.create(False)
            self.db_root_lock.create(False)

        # Bind to the corresponding db tuple
        self.read_from_db(db_session)

        # Fs location
        self.fs_base = os.path.join(self.source_package_version.fs_binary_packages,
                self.name, str(self.version_number))

    # Peripheral methods
    def read_from_db(self, db_session = None):
        s = db.get_session() if db_session is None else db_session

        try:
            bp = aliased(dbbpkg.BinaryPackage)
            dbo = s.query(bp)\
                    .filter(bp.name == self.name,
                            bp.architecture == self.architecture,
                            bp.version_number == self.version_number)\
                    .first()

            if dbo is None:
                raise NoSuchBinaryPackage(self.name, self.architecture, self.version_number)

            s.expunge(dbo)
            self.dbo = dbo

            if not db_session:
                s.commit()

        except:
            if not db_session:
                s.rollback()
            raise

        finally:
            if not db_session:
                s.close()

    def ensure_write_intent(self):
        """
        A convenience method calling self.source_package_version.ensure_write_intent()
        """
        self.source_package_version.ensure_write_intent()


    # Attributes
    # General
    def get_creation_time(self):
        return self.dbo.creation_time

    # Files
    def set_files(self, files, time=None):
        """
        :param files: list(tuple(path, sha512sum)), where path is relative to the
            install location but written as absolute path.
        :type files: list(tuple(str, str))
        """
        self.ensure_write_intent()

        if time is None:
            time = timezone.now()

        files = sorted(files)

        with lock_X(self.db_root_lock):
            with db.session_scope() as s:
                # Check for differences
                fs = aliased(dbbpkg.BinaryPackageFile)
                dbfiles = s.query(fs.path, fs.sha512sum)\
                        .filter(fs.binary_package == self.name,
                                fs.architecture == self.architecture,
                                fs.version_number == self.version_number)\
                        .order_by(fs.path, fs.sha512sum)\
                        .all()

                different = len(files) != len(dbfiles)

                if not different:
                    for i in range(len(files)):
                        if files[i] != dbfiles[i]:
                            different = True
                            break

                # Eventually update files
                if different:
                    t = dbbpkg.BinaryPackageFile.__table__
                    s.execute(t.delete()\
                            .where(t.c.binary_package == self.name)\
                            .where(t.c.architecture == self.architecture)\
                            .where(t.c.version_number == self.version_number))

                    s.flush()

                    s.execute(t.insert(
                        [
                            {
                                'binary_package': self.name,
                                'architecture': self.architecture,
                                'version_number': self.version_number,
                                'path': p,
                                'sha512sum': sha512
                            } for p, sha512 in files
                        ]))

                # Update the reassured time
                self.dbo.files_reassured_time = time

                if different:
                    self.dbo.files_modified_time = time

                s.add(self.dbo)

            self.read_from_db()

    def get_files(self):
        """
        :returns: ordered list(tuple(path, sha512sum))
        :rtype: list(tuple(str, str))
        """
        with db.session_scope() as s:
            fs = aliased(dbbpkg.BinaryPackageFile)
            l = s.query(fs.path, fs.sha512sum)\
                    .filter(fs.binary_package == self.name,
                            fs.architecture == self.architecture,
                            fs.version_number == self.version_number)\
                    .order_by(fs.path)\
                    .all()

            return l

    def get_files_meta(self):
        """
        :returns: tuple(modified_time, reassured_time)
        :rtype: tuple(datetime, datetime)
        """
        return (self.dbo.files_modified_time, self.dbo.files_reassured_time)

    # Key-Value-Store like attributes
    def list_attributes(self):
        """
        :returns: A list of all keys
        """
        with db.session_scope() as s:
            pa = aliased(dbbpkg.BinaryPackageAttribute)
            l = s.query(pa.key)\
                    .filter(pa.binary_package == self.name,
                            pa.architecture == self.architecture,
                            pa.version_number == self.version_number)\
                    .all()

            return [ e[0] for e in l]

    def has_attribute(self, key):
        """
        :returns: True or False
        :rtype: bool
        """
        with db.session_scope() as s:
            pa = aliased(dbbpkg.BinaryPackageAttribute)
            return len(s.query(pa.key)\
                    .filter(pa.binary_package == self.name,
                            pa.architecture == self.architecture,
                            pa.version_number == self.version_number,
                            pa.key == key)\
                    .all()) != 0

    def get_attribute(self, key):
        """
        :param key: The attribute's key
        :type key: str
        :returns: The stored string or object in its appropriate type
        :rtype: str or virtually anything else
        """
        with db.session_scope() as s:
            pa = aliased(dbbpkg.BinaryPackageAttribute)
            v = s.query(pa.value)\
                    .filter(pa.binary_package == self.name,
                            pa.architecture == self.architecture,
                            pa.version_number == self.version_number,
                            pa.key == key)\
                    .all()

            if len(v) == 0:
                raise NoSuchAttribute("Binary package `%s@%s:%s'" %
                        (self.name, self.architecture,
                            self.version_number), key)

            v = v[0][0]

            if v is None or len(v) == 0:
                return None
            elif v[0] == 's':
                return v[1:]
            elif v[0] == 'p':
                return pickle.loads(base64.b64decode(v[1:].encode('ascii')))
            else:
                return None

    def get_attribute_meta(self, key):
        """
        :param key: The attribute's key
        :type key: str
        :returns: tuple(modified_time, reassured_time, manual_hold_time or None)
        :rtype: tuple(datetime, datetime, datetime or None)
        """
        with db.session_scope() as s:
            pa = aliased(dbbpkg.BinaryPackageAttribute)
            v = s.query(pa.modified_time, pa.reassured_time, pa.manual_hold_time)\
                    .filter(pa.binary_package == self.name,
                            pa.architecture == self.architecture,
                            pa.version_number == self.version_number,
                            pa.key == key)\
                    .all()

            if len(v) == 0:
                raise NoSuchAttribute("Binary package `%s@%s:%s'" %
                        (self.name, self.architecture,
                            self.version_number), key)

            return v[0]

    def manually_hold_attribute(self, key, remove=False, time=None):
        self.ensure_write_intent()

        with lock_X(self.db_root_lock):
            with db.session_scope() as s:
                pa = aliased(dbbpkg.BinaryPackageAttribute)
                v = s.query(pa)\
                        .filter(pa.binary_package == self.name,
                                pa.architecture == self.architecture,
                                pa.version_number == self.version_number,
                                pa.key == key)\
                        .all()

                if len(v) == 0:
                    raise NoSuchAttribute("Binary package `%s@%s:%s'" %
                            (self.name, self.architecture,
                                self.version_number), key)

                v = v[0]

                if not time:
                    time = timezone.now()

                if remove:
                    v.manual_hold_time = None
                else:
                    v.manual_hold_time = time

    def attribute_manually_held(self, key):
        """
        :returns: The time the attribute was manually held or None
        :rtype: datetime or None
        """
        with db.session_scope() as s:
            pa = aliased(dbbpkg.BinaryPackageAttribute)
            v = s.query(pa.manual_hold_time)\
                    .filter(pa.binary_package == self.name,
                            pa.architecture == self.architecture,
                            pa.version_number == self.version_number,
                            pa.key == key)\
                    .all()

            if len(v) == 0:
                raise NoSuchAttribute("Binary package `%s@%s:%s'" %
                        (self.name, self.architecture,
                            self.version_number), key)

            return v[0][0]

    def set_attribute(self, key, value, time = None):
        """
        :param key: The attribute's key
        :type key: str
        :param value: The string or object to be assigned as value
        :type value: str or virtually any type
        :param time: If not None, this will be used for the timestamps
        :type time: datetime or None
        """
        self.ensure_write_intent()

        if not time:
            time = timezone.now()

        # Serialize object
        if value.__class__ == str:
            o = "s" + value
        else:
            o = "p" + base64.b64encode(pickle.dumps(value)).decode('ascii')

        # Eventually update the attribute
        with lock_X(self.db_root_lock):
            with db.session_scope() as s:
                pa = aliased(dbbpkg.BinaryPackageAttribute)
                a = s.query(pa)\
                        .filter(pa.binary_package == self.name,
                                pa.architecture == self.architecture,
                                pa.version_number == self.version_number,
                                pa.key == key)\
                        .all()

                if len(a) == 0:
                    # Create a new attribute tuple
                    s.add(dbbpkg.BinaryPackageAttribute(
                            self.name,
                            self.architecture,
                            self.version_number,
                            key, o, time))
                else:
                    a = a[0]

                    # This attribute manually locked?
                    if a.manual_hold_time is not None:
                        raise AttributeManuallyHeld(key)

                    if a.value != o:
                        a.value = o;
                        a.modified_time = time

                    a.reassured_time = time

    def unset_attribute(self, key):
        self.ensure_write_intent()

        with lock_X(self.db_root_lock):
            with db.session_scope() as s:
                pa = aliased(dbbpkg.BinaryPackageAttribute)
                a = s.query(pa)\
                        .filter(pa.binary_package == self.name,
                                pa.architecture == self.architecture,
                                pa.version_number == self.version_number,
                                pa.key == key)\
                        .all()

                if len(a) == 0:
                    raise NoSuchAttribute("Binary package `%s@%s:%s'" %
                            (self.name, self.architecture,
                                self.version_number), key)

                a = a[0]

                # Manually held?
                if a.manual_hold_time is not None:
                    raise AttributeManuallyHeld(key)

                s.delete(a)

# Some exceptions for our pleasure
class NoSuchBinaryPackage(Exception):
    def __init__(self, name, architecture, version_number=None):
        architecture = architectures[architecture]
        if version_number is not None:
            super().__init__("No such binary package: `%s@%s:%s'." % (name, architecture, version_number))
        else:
            super().__init__("No such binary package: `%s@%s'." % (name, architecture))
