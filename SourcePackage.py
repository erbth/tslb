from VersionNumber import VersionNumber
from sqlalchemy.orm import aliased
from tclm import lock_S, lock_Splus, lock_X
from time import sleep
import base64
import database
import database.SourcePackage
import database.SourcePackage as dbspkg
import pickle
import tclm
import timezone

class SourcePackageList(object):
    def __init__(self, create_locks = False):
        # Define a few required locks
        self.dbrlp = 'tslb_db.source_packages'
        self.fsrlp = 'tslb_fs.packaging'

        self.db_root_lock = tclm.define_lock(self.dbrlp)
        self.fs_root_lock = tclm.define_lock(self.fsrlp)

        # Create locks if desired
        if create_locks:
            self.fs_root_lock.create(True)
            self.db_root_lock.create(True)

            self.db_root_lock.release_X()
            self.fs_root_lock.release_X()

    def list_source_packages(self):
        """
        Returns an ordered list of the source packages' names.
        """
        with lock_S(self.db_root_lock):
            sps = database.conn.get_session().query(database.SourcePackage.SourcePackage.name)\
                        .order_by(database.SourcePackage.SourcePackage.name).all()

            names = [ sp[0] for sp in sps ]
            return names


    def create_source_package(self, name):
        # Lock the source package list and the fs
        with lock_X(self.fs_root_lock):
            with lock_X(self.db_root_lock):
                # Create the db tuple
                s = database.conn.get_session()

                p = aliased(dbspkg.SourcePackage)
                if s.query(p).filter(p.name == name).first():
                    raise SourcePackageExists(name)

                spkg = database.SourcePackage.SourcePackage()
                spkg.initialize_fields(name)

                s.add(spkg)
                s.commit()
                del spkg

                # Create fs location

                # Create locks
                spkg = SourcePackage(name, write_intent = True, create_locks = True)
                return spkg

    def destroy_source_package(self, name):
        # Lock the source package list and the fs
        with lock_X(self.fs_root_lock):
            with lock_X(self.db_root_lock):
                # Remove the db tuple(s)
                s = database.conn.get_session()
                spkg = s.query(database.SourcePackage.SourcePackage).filter_by(name=name).first()

                if spkg:
                    s.delete(spkg)
                    s.commit()

                # Remove the fs location(s)

class SourcePackage(object):
    def __init__(self, name, write_intent = False, create_locks = False):
        """
        Initially, create_locks must be true for the first time the package was
        used. If write_intent is True, S+ locks are acquired initially.
        """
        self.name = name
        self.write_intent = write_intent

        # Define a few required locks
        self.dbrlp = 'tslb_db.source_packages.%s' % self.name
        self.fsrlp = 'tslb_fs.packaging.%s' % self.name

        self.db_root_lock = tclm.define_lock(self.dbrlp)

        self.fs_root_lock = tclm.define_lock(self.fsrlp)

        # Create locks if desired
        if create_locks:
            self.fs_root_lock.create(False)
            self.db_root_lock.create(False)

        # Acquire locks in the requested mode
        if write_intent:
            # Deadlock free locking protocol: First fs, then db.
            self.fs_root_lock.acquire_Splus()
            self.db_root_lock.acquire_Splus()
        else:
            self.fs_root_lock.acquire_S()
            self.db_root_lock.acquire_S()

        # Download information from the DB. This is like an opaque class, hence
        # I can implement the db information by linking this pure-memory object,
        # which is more like a control class accumulating all functionality
        # spread across different modules (DB, locking, fs) into one interface,
        # to a db object.
        try:
            self.read_from_db()

        except:
            # Release locks
            if write_intent:
                self.db_root_lock.release_Splus()
                self.fs_root_lock.release_Splus()
            else:
                self.db_root_lock.release_S()
                self.fs_root_lock.release_S()

            raise

    def __del__(self):
        if self.write_intent:
            self.db_root_lock.release_Splus()
            self.fs_root_lock.release_Splus()
        else:
            self.db_root_lock.release_S()
            self.fs_root_lock.release_S()


    # Peripheral methods and functions ...
    def ensure_write_intent(self):
        if not self.write_intent:
            # Abort to avoid deadlocks
            raise MissingWriteIntent('create client version')
            # self.write_intent = True

            # self.fs_root_lock.acquire_Splus()
            # self.fs_root_lock.release_S()

            # self.db_root_lock.acquire_Splus()
            # self.db_root_lock.release_S()

    def read_from_db(self):
        s = database.conn.get_session()
        dbo = s.query(database.SourcePackage.SourcePackage)\
                .filter_by(name=self.name)\
                .first()

        if dbo is None:
            raise NoSuchSourcePackage(self.name)

        s.expunge(dbo)
        self.dbo = dbo


    # Attributes
    # General
    def get_creation_time(self):
        return self.dbo.creation_time

    # Versions
    def list_version_numbers(self):
        s = database.conn.get_session()
        vns = s.query(dbspkg.SourcePackageVersion.version_number)\
                .filter(dbspkg.SourcePackageVersion.source_package == self.name)\
                .all()

        return [ vn[0] for vn in vns ]

    def get_version(self, version_number):
        return SourcePackageVersion(self, version_number)

    def get_latest_version(self):
        """
        Get the latest version.
        """
        pv1 = aliased(dbspkg.SourcePackageVersion)
        pv2 = aliased(dbspkg.SourcePackageVersion)

        s = database.get_session()
        v = s.query(pv1.version_number)\
                .filter(pv1.source_package == self.name,
                        ~s.query(pv2)\
                                .filter(pv2.source_package == pv1.source_package,
                                    pv2.version_number > pv1.version_number)\
                                .exists())\
                .first()

        if not v:
            raise NoSuchSourcePackageVersion(self.name, "latest")

        return SourcePackageVersion(self.name, v[0])

    def manually_hold_versions(self, remove=False, time=None):
        """
        :param remove: If True, the manual hold flag will be removed.
        :type remove: bool
        :param time: The timestamp to assign during the operation, or None to
                     use timezone.now().
        :type time: datetime
        """
        self.ensure_write_intent()

        if not time:
            time = timezone.now()

        with lock_X(self.db_root_lock):
            if remove != (not bool(self.dbo.versions_manual_hold_time)):
                if remove:
                    self.dbo.versions_manual_hold_time = None
                else:
                    self.dbo.versions_manual_hold_time = time

                s = database.get_session()
                s.add(self.dbo)
                s.commit()

                self.read_from_db()

    def versions_manually_held(self):
        """
        :returns: The date and time when the versions were manually held, or
                  None if they are not held.
        :rtype: datetime
        """
        return self.dbo.versions_manual_hold_time

    def add_version(self, version_number, time = None):
        """
        Add a new version. This may raise an AttributeManuallyHeld.

        :returns: The newly created version
        :rtype: SourcePackageVersion (throws hence does not return None)
        """
        if self.dbo.versions_manual_hold_time:
            raise AttributeManuallyHeld("versions")

        version_number = VersionNumber(version_number)
        self.ensure_write_intent()

        if not time:
            time = timezone.now()

        with lock_X(self.fs_root_lock):
            with lock_X(self.db_root_lock):
                s = database.get_session()

                pvs = aliased(dbspkg.SourcePackageVersion)
                if s.query(pvs)\
                        .filter(pvs.source_package == self.name,
                                pvs.version_number == version_number)\
                        .first():
                    raise SourcePackageVersionExists(self.name, version_number)

                # Create the fs locations

                # Add the db tuple
                pv = dbspkg.SourcePackageVersion()
                pv.initialize_fields(self.name, version_number)
                s.add(pv)

                # Create a version object to create locks
                SourcePackageVersion(
                        self, version_number, create_locks=True, db_session=s)

                self.dbo.versions_modified_time = time
                self.dbo.versions_reassured_time = time
                s.add(self.dbo)

                # Transactionality
                s.commit()

                self.read_from_db()

                # Create a new version object because the former one was bound
                # to the former session (for transactionality).
                return SourcePackageVersion(self, version_number)

    def delete_version(self, version_number, time = None):
        """
        Delete a version. This may raise (among others) an AttributeManuallyHeld.
        """
        if self.dbo.versions_manual_hold_time:
            raise AttributeManuallyHeld("versions")

        version_number = VersionNumber(version_number)
        self.ensure_write_intent()

        if not time:
            time = timezone.now()

        with lock_X(self.fs_root_lock):
            with lock_X(self.db_root_lock):
                # Delete fs locations

                # Delete the db tuple
                s = database.get_session()

                pv = aliased(dbspkg.SourcePackageVersion)
                v = s.query(pv)\
                        .filter(pv.source_package == self.name,
                                pv.version_number == version_number)\
                        .first()

                # Could be that something went wrong when creating this package.
                # We'd tolerate that.
                if v is not None:
                    s.delete(v)

                    self.dbo.versions_modified_time = time
                    self.dbo.versions_reassured_time = time
                    s.add(self.dbo)

                    s.commit()

                    self.read_from_db()

    def get_versions_meta(self):
        """
        :returns: tuple(modified_time, reassured_time, manual_hold_time or None)
        :rtype: tuple(datetime, datetime, datetime or None)
        """
        return (self.dbo.versions_modified_time, self.dbo.versions_reassured_time,
                self.dbo.versions_manual_hold_time)


class SourcePackageVersion(object):
    def __init__(self, source_package, version_number, create_locks=False, db_session=None):
        """
        Must be called with the source package be X locked.

        :param source_package:
        :type source_package: SourcePackage
        :param db_session: Optionally specify a db session for i.e.
                           transactionality
        """
        self.source_package = source_package
        version_number = VersionNumber(version_number)
        self.version_number = version_number

        # Create locks if requested
        vs = str(self.version_number).replace('.', '_')
        self.fsrlp = source_package.fsrlp + "." + vs
        self.dbrlp = source_package.dbrlp + "." + vs

        self.fs_root_lock = tclm.define_lock(self.fsrlp)
        self.fs_source_location_lock = tclm.define_lock(self.fsrlp + '.source_location')
        self.fs_build_location_lock = tclm.define_lock(self.fsrlp + '.build_location')
        self.fs_install_location_lock = tclm.define_lock(self.fsrlp + '.install_location')
        self.fs_packaging_location_lock = tclm.define_lock(self.fsrlp + '.packaging_location')

        self.db_root_lock = tclm.define_lock(self.dbrlp)

        if create_locks:
            self.source_package.ensure_write_intent()

            for l in [
                    self.fs_source_location_lock,
                    self.fs_build_location_lock,
                    self.fs_install_location_lock,
                    self.fs_packaging_location_lock,
                    self.db_root_lock ]:
                l.create(False)

        # Bind a DB object
        try:
            self.read_from_db(db_session)

        except:
            raise


    # Peripheral methods
    def read_from_db(self, db_session = None):
        s = database.conn.get_session() if not db_session else db_session
        dbos = s.query(database.SourcePackage.SourcePackageVersion)\
                .filter_by(source_package = self.source_package.name,
                        version_number = self.version_number).all()

        if len(dbos) != 1:
            raise NoSuchSourcePackageVersion(self.source_package.name, self.version_number)

        dbo = dbos[0]

        if not db_session:
            s.expunge(dbo)

        self.dbo = dbo


    # Attributes
    # General
    def get_creation_time(self):
        return self.dbo.creation_time

    # Installed files
    def set_installed_files(self, files, time=None):
        """
        :param files: list(tuple(path, sha512sum)), where path is relative to the
            install location but written as absolute path.
        :type files: list(tuple(str, str))
        """
        self.source_package.ensure_write_intent()

        if time is None:
            time = timezone.now()

        files = sorted(files)

        with lock_X(self.db_root_lock):
            s = database.get_session()

            # Check for differences
            fs = aliased(dbspkg.SourcePackageVersionFile)
            dbfiles = s.query(fs.path, fs.sha512sum)\
                    .filter(fs.source_package == self.source_package.name,
                            fs.source_package_version_number == self.version_number)\
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
                s.query(dbspkg.SourcePackageVersionFile)\
                        .filter(dbspkg.SourcePackageVersionFile.source_package == self.source_package.name,
                                dbspkg.SourcePackageVersionFile.source_package_version_number ==
                                    self.version_number)\
                        .delete()


                for (p, sha512) in files:
                    s.add(dbspkg.SourcePackageVersionFile(
                        self.source_package.name,
                        self.version_number,
                        p,
                        sha512))

            # Update the reassured time
            self.dbo.files_reassured_time = time

            if different:
                self.dbo.files_modified_time = time

            s.add(self.dbo)
            s.commit()

            self.read_from_db()

    def get_installed_files(self):
        """
        :returns: list(tuple(path, sha512sum))
        :rtype: list(tuple(str, str))
        """
        s = database.get_session()

        fs = aliased(dbspkg.SourcePackageVersionFile)
        l = s.query(fs.path, fs.sha512sum)\
                .filter(fs.source_package == self.source_package.name,
                        fs.source_package_version_number == self.version_number)\
                .all()

        return l

    def get_installed_files_meta(self):
        """
        :returns: tuple(modified_time, reassured_time)
        :rtype: tuple(datetime, datetime)
        """
        return (self.dbo.files_modified_time, self.dbo.files_reassured_time)

    # Shared libraries

    # Binary packages
    def list_binary_packages(self):
        pass

    def get_binary_package(self):
        pass

    def add_binary_package(self):
        pass

    def remove_binary_package(self):
        pass

    # Key-Value-Store like attributes
    def list_attributes(self):
        """
        :returns: A list of all keys
        """
        s = database.get_session()
        
        pa = aliased(dbspkg.SourcePackageVersionAttribute)
        l = s.query(pa.key)\
                .filter(pa.source_package == self.source_package.name,
                        pa.version_number == self.version_number)\
                .all()

        return [ e[0] for e in l]

    def has_attribute(self, key):
        """
        :returns: True or False
        :rtype: bool
        """
        s = database.get_session()

        pa = aliased(dbspkg.SourcePackageVersionAttribute)
        return len(s.query(pa.key)\
                .filter(pa.source_package == self.source_package.name,
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
        s = database.get_session()

        pa = aliased(dbspkg.SourcePackageVersionAttribute)
        v = s.query(pa.value)\
                .filter(pa.source_package == self.source_package.name,
                        pa.version_number == self.version_number,
                        pa.key == key)\
                .all()

        if len(v) == 0:
            raise NoSuchAttribute("Source package version `%s@%s'" %
                    (self.source_package.name, self.version_number), key)

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
        s = database.get_session()

        pa = aliased(dbspkg.SourcePackageVersionAttribute)
        v = s.query(pa.modified_time, pa.reassured_time, pa.manual_hold_time)\
                .filter(pa.source_package == self.source_package.name,
                        pa.version_number == self.version_number,
                        pa.key == key)\
                .all()

        if len(v) == 0:
            raise NoSuchAttribute("Source package version `%s@%s'" %
                    (self.source_package.name, self.version_number), key)

        return v[0]

    def manually_hold_attribute(self, key, remove=False, time=None):
        self.source_package.ensure_write_intent()

        with lock_X(self.db_root_lock):
            s = database.get_session()

            pa = aliased(dbspkg.SourcePackageVersionAttribute)
            v = s.query(pa)\
                    .filter(pa.source_package == self.source_package.name,
                            pa.version_number == self.version_number,
                            pa.key == key)\
                    .all()

            if len(v) == 0:
                raise NoSuchAttribute("Source package version `%s@%s'" %
                        (self.source_package.name, self.version_number), key)

            v = v[0]

            if not time:
                time = timezone.now()

            if remove:
                v.manual_hold_time = None
            else:
                v.manual_hold_time = time

            s.commit()

    def attribute_manually_held(self, key):
        """
        :returns: The time the attribute was manually held or None
        :rtype: datetime or None
        """
        s = database.get_session()

        pa = aliased(dbspkg.SourcePackageVersionAttribute)
        v = s.query(pa.manual_hold_time)\
                .filter(pa.source_package == self.source_package.name,
                        pa.version_number == self.version_number,
                        pa.key == key)\
                .all()

        if len(v) == 0:
            raise NoSuchAttribute("Source package version `%s@%s'" %
                    (self.source_package.name, self.version_number), key)

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
        self.source_package.ensure_write_intent()

        if not time:
            time = timezone.now()

        # Serialize object
        if value.__class__ == str:
            o = "s" + value
        else:
            o = "p" + base64.b64encode(pickle.dumps(value)).decode('ascii')

        # Eventually update the attribute
        with lock_X(self.db_root_lock):
            s = database.get_session()

            pa = aliased(dbspkg.SourcePackageVersionAttribute)
            a = s.query(pa)\
                    .filter(pa.source_package == self.source_package.name,
                            pa.version_number == self.version_number,
                            pa.key == key)\
                    .all()

            if len(a) == 0:
                # Create a new attribute tuple
                s.add(dbspkg.SourcePackageVersionAttribute(
                        self.source_package.name,
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

            s.commit()

    def unset_attribute(self, key):
        self.source_package.ensure_write_intent()

        with lock_X(self.db_root_lock):
            s = database.get_session()

            pa = aliased(dbspkg.SourcePackageVersionAttribute)
            a = s.query(pa)\
                    .filter(pa.source_package == self.source_package.name,
                            pa.version_number == self.version_number,
                            pa.key == key)\
                    .all()

            if len(a) == 0:
                raise NoSuchAttribute("Source package version `%s@%s'" %
                        (self.source_package.name, self.version_number), key)

            a = a[0]

            # Manually held?
            if a.manual_hold_time is not None:
                raise AttributeManuallyHeld(key)

            s.delete(a)
            s.commit()


# Some exceptions for our pleasure.
class NoSuchSourcePackage(Exception):
    def __init__(self, name):
        super().__init__("No such source package: `%s'" % name)

class NoSuchSourcePackageVersion(Exception):
    def __init__(self, name, version_number):
        super().__init__("No such source package version: `%s@%s'" % (name, version_number))

class MissingWriteIntent(Exception):
    def __init__(self, reference):
        super().__init__("A write was requested but no write intent specified before. I abort to avoid deadlocks.")

class AttributeManuallyHeld(Exception):
    def __init__(self, attr_name):
        super().__init__("Attribute %s was manually held." % attr_name)

class SourcePackageExists(Exception):
    def __init__(self, name):
        super().__init__("Source package `%s' exists already." % name)

class SourcePackageVersionExists(Exception):
    def __init__(self, name, version_number):
        super().__init__("Source package version: `%s@%s'" % (name, version_number))

class NoSuchAttribute(Exception):
    def __init__(self, obj, key):
        super().__init__("%s has no attribute `%s'." % (obj, key))
