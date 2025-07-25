from tslb import Architecture
from tslb import settings
from tslb.Architecture import architectures
from tslb.BinaryPackage import BinaryPackage, NoSuchBinaryPackage
from tslb.CommonExceptions import NoSuchAttribute, MissingWriteIntent, AttributeManuallyHeld
from tslb.filesystem import FileOperations as fops
from tslb.program_analysis.shared_library_tools import SharedLibrary
from tslb.VersionNumber import VersionNumber
from sqlalchemy.orm import aliased
from tslb.tclm import lock_S, lock_Splus, lock_X
from time import sleep
from tslb import BinaryPackage as bp
import base64
from tslb import database
from tslb.database import BinaryPackage as dbbpkg
from tslb.database import SourcePackage as dbspkg
import os
import pickle
from tslb import tclm
from tslb import timezone
from tslb.scratch_space import ScratchSpacePool

# For convenience methods
from tslb.Constraint import VersionConstraint, DependencyList

class SourcePackageList:
    def __init__(self, architecture, create_locks = False):
        architecture = Architecture.to_int(architecture)

        if architecture not in architectures.keys():
            raise ValueError('Invalid architecture')

        self.architecture = architecture

        # Define a few required locks
        self.dbrlp = 'tslb.db.%s.source_packages' % architectures[architecture]

        self.db_root_lock = tclm.define_lock(self.dbrlp)

        # Create locks if desired
        if create_locks:
            self.db_root_lock.create(True)
            self.db_root_lock.release_X()

    def list_source_packages(self):
        """
        Returns an ordered list of the source packages' names.

        :returns: list(name)
        :rtype: list(str)
        """
        with lock_S(self.db_root_lock):
            with database.session_scope() as s:
                sp = aliased(dbspkg.SourcePackage)

                q = s.query(sp.name)\
                        .filter(sp.architecture == self.architecture)\
                        .order_by(sp.name).all()

                return [ e[0] for e in q ]

    def create_source_package(self, name):
        """
        :returns: A source package with write intent
        """
        # Lock the source package list and the fs
        with lock_X(self.db_root_lock):
            s = database.get_session()

            try:
                # Create the db tuple
                p = aliased(dbspkg.SourcePackage)
                if s.query(p).filter(p.name == name, p.architecture == self.architecture).first():
                    raise SourcePackageExists(name, self.architecture)

                spkg = dbspkg.SourcePackage()
                spkg.initialize_fields(name, self.architecture)

                s.add(spkg)
                del spkg

                # Create locks
                SourcePackage(name, self.architecture, write_intent = True,
                        create_locks = True, db_session = s)

                s.commit()

                return SourcePackage(name, self.architecture, write_intent = True)

            except:
                s.rollback()
                raise
            finally:
                s.close()

    def destroy_source_package(self, name):
        # First try to delete all versions of the package s.t. scratch spaces
        # are deleted.
        sp = None
        try:
            sp = SourcePackage(name, self.architecture, write_intent=True)

            for v in sp.list_version_numbers():
                sp.delete_version(v)

        except NoSuchSourcePackage:
            pass
        except AttributeManuallyHeld:
            raise
        except RuntimeError as e:
            if str(e) == "No such lock.":
                pass
            else:
                raise

        # Lock the source package list
        with lock_X(self.db_root_lock):
            # Release Source package
            del sp

            # Remove the db tuple(s)
            with database.session_scope() as s:
                spkg = s.query(dbspkg.SourcePackage).\
                        filter_by(name=name, architecture=self.architecture).first()

                if spkg:
                    s.delete(spkg)


class SourcePackage:
    def __init__(self, name, architecture,
        write_intent = False, create_locks = False, db_session=None):

        """
        Initially, create_locks must be True for the first time the package was
        used. If write_intent is True, S+ locks are acquired during
        initialization.
        """
        architecture = Architecture.to_int(architecture)

        self.name = name
        self.architecture = architecture
        self.write_intent = write_intent

        # Define a few required locks
        self.dbrlp = 'tslb.db.%s.source_packages.%s' % (architectures[self.architecture], self.name)
        self.db_root_lock = tclm.define_lock(self.dbrlp)

        # Create locks if desired
        if create_locks:
            self.db_root_lock.create(False)

        # Acquire locks in the requested mode
        if write_intent:
            self.db_root_lock.acquire_Splus()
        else:
            self.db_root_lock.acquire_S()

        # Download information from the DB. This is like an opaque class, hence
        # I can implement the db information by linking this pure-memory
        # object, which is more like a control class accumulating all
        # functionality spread across different modules (DB, locking, fs) into
        # one interface, to a db object.
        try:
            self.read_from_db(db_session)

        except:
            # Release locks
            if write_intent:
                self.db_root_lock.release_Splus()
            else:
                self.db_root_lock.release_S()

            raise

    def __del__(self):
        try:
            if self.write_intent:
                self.db_root_lock.release_Splus()
            else:
                self.db_root_lock.release_S()

        except Exception as e:
            print("Failed to __del__ %s: %s." % (repr(self), e))

        except:
            print("Failed to __del__ %s." % repr(self))



#******************* Peripheral methods and functions *************************
    def ensure_write_intent(self):
        if not self.write_intent:
            # Abort to avoid deadlocks
            raise MissingWriteIntent


    def read_from_db(self, db_session=None):
        s = db_session if db_session else database.conn.get_session()

        try:
            dbo = s.query(dbspkg.SourcePackage)\
                    .filter_by(name=self.name, architecture=self.architecture)\
                    .first()

            if dbo is None:
                raise NoSuchSourcePackage(self.name, self.architecture)

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


    # Attributes
    # General
    def get_creation_time(self):
        return self.dbo.creation_time

    # Versions
    def list_version_numbers(self):
        with database.session_scope() as s:
            vns = s.query(dbspkg.SourcePackageVersion.version_number)\
                    .filter(dbspkg.SourcePackageVersion.source_package == self.name,
                            dbspkg.SourcePackageVersion.architecture == self.architecture)\
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

        with database.session_scope() as s:
            v = s.query(pv1.version_number)\
                    .filter(pv1.source_package == self.name,
                            pv1.architecture == self.architecture,
                            ~s.query(pv2)\
                                    .filter(pv2.source_package == pv1.source_package,
                                        pv2.architecture == pv1.architecture,
                                        pv2.version_number > pv1.version_number)\
                                    .exists())\
                    .first()

            if not v:
                raise NoSuchSourcePackageVersion(self.name, self.architecture, "latest")

            return SourcePackageVersion(self, v[0])

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

                with database.session_scope() as s:
                    s.add(self.dbo)

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

        with lock_X(self.db_root_lock):
            s = database.get_session()

            try:
                pvs = aliased(dbspkg.SourcePackageVersion)
                if s.query(pvs)\
                        .filter(pvs.source_package == self.name,
                                pvs.architecture == self.architecture,
                                pvs.version_number == version_number)\
                        .first():
                    raise SourcePackageVersionExists(self.name, self.architecture, version_number)

                # Add the db tuple
                pv = dbspkg.SourcePackageVersion()
                pv.initialize_fields(self.name, self.architecture, version_number)
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

            except:
                s.rollback()
                raise
            finally:
                s.close()


    def delete_version(self, version_number, time = None):
        """
        Delete a version. This may raise (among others) an
        AttributeManuallyHeld.
        """
        if self.dbo.versions_manual_hold_time:
            raise AttributeManuallyHeld("versions")

        version_number = VersionNumber(version_number)
        self.ensure_write_intent()

        if not time:
            time = timezone.now()

        with lock_X(self.db_root_lock):
            # Delete scratch space
            ScratchSpacePool().delete_scratch_space("%s_%s_%s" % (
                self.name,
                Architecture.to_str(self.architecture),
                version_number))

            # Delete the db tuple
            s = database.get_session()

            try:
                pv = aliased(dbspkg.SourcePackageVersion)
                v = s.query(pv)\
                        .filter(pv.source_package == self.name,
                                pv.architecture == self.architecture,
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
                    s.close()

                    self.read_from_db()

                else:
                    s.rollback()

            except:
                s.rollback()
                raise

            finally:
                s.close()


    def get_versions_meta(self):
        """
        :returns: tuple(modified_time, reassured_time, manual_hold_time or None)
        :rtype: tuple(datetime, datetime, datetime or None)
        """
        return (self.dbo.versions_modified_time, self.dbo.versions_reassured_time,
                self.dbo.versions_manual_hold_time)


    # Key-Value-Store like attributes
    def list_attributes(self, pattern=None):
        """
        :param str pattern: A pattern that the attributes must match. May contain
            '*' as wildcard-character.
        :returns: A list of all keys
        """
        with database.session_scope() as s:
            pa = aliased(dbspkg.SourcePackageAttribute)
            q = s.query(pa.key)\
                    .filter(pa.source_package == self.name,
                            pa.architecture == self.architecture)

            if pattern is not None:
                pattern = pattern.replace('\\', '\\\\').replace('%', r'\%').replace('_', r'\_')\
                        .replace('*', '%')

                q = q.filter(pa.key.like(pattern, escape='\\'))

            return [e[0] for e in q.all()]


    def has_attribute(self, key):
        """
        :returns: True or False
        :rtype: bool
        """
        with database.session_scope() as s:
            pa = aliased(dbspkg.SourcePackageAttribute)
            return len(s.query(pa.key)\
                    .filter(pa.source_package == self.name,
                            pa.architecture == self.architecture,
                            pa.key == key)\
                    .all()) != 0


    def get_attribute(self, key):
        """
        :param key: The attribute's key
        :type key: str
        :returns: The stored string or object in its appropriate type
        :rtype: str or virtually anything else
        """
        with database.session_scope() as s:
            pa = aliased(dbspkg.SourcePackageAttribute)
            v = s.query(pa.value)\
                    .filter(pa.source_package == self.name,
                            pa.architecture == self.architecture,
                            pa.key == key)\
                    .all()

            if len(v) == 0:
                raise NoSuchAttribute("Source package `%s@%s'" %
                        (self.name, architectures[self.architecture]), key)

            v = v[0][0]

            if v is None or len(v) == 0:
                return None
            elif v[0] == 's':
                return v[1:]
            elif v[0] == 'p':
                return pickle.loads(base64.b64decode(v[1:].encode('ascii')))
            else:
                return None

    def get_attribute_or_default(self, key, default):
        """
        Like `get_attribute`, but return a default value instead of raising a
        `NoSuchAttribute` if the attribute does not exist.
        """
        if not self.has_attribute(key):
            return default

        return self.get_attribute(key)


    def get_attribute_meta(self, key):
        """
        :param key: The attribute's key
        :type key: str
        :returns: tuple(modified_time, reassured_time, manual_hold_time or None)
        :rtype: tuple(datetime, datetime, datetime or None)
        """
        with database.session_scope() as s:
            pa = aliased(dbspkg.SourcePackageAttribute)
            v = s.query(pa.modified_time, pa.reassured_time, pa.manual_hold_time)\
                    .filter(pa.source_package == self.name,
                            pa.architecture == self.architecture,
                            pa.key == key)\
                    .all()

            if len(v) == 0:
                raise NoSuchAttribute("Source package `%s@%s'" %
                        (self.name, architectures[self.architecture]), key)

            return v[0]


    def manually_hold_attribute(self, key, remove=False, time=None):
        self.ensure_write_intent()

        with lock_X(self.db_root_lock):
            with database.session_scope() as s:
                pa = aliased(dbspkg.SourcePackageAttribute)
                v = s.query(pa)\
                        .filter(pa.source_package == self.name,
                                pa.architecture == self.architecture,
                                pa.key == key)\
                        .all()

                if len(v) == 0:
                    raise NoSuchAttribute("Source package `%s@%s'" %
                            (self.name, architectures[self.architecture]), key)

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
        with database.session_scope() as s:
            pa = aliased(dbspkg.SourcePackageAttribute)
            v = s.query(pa.manual_hold_time)\
                    .filter(pa.source_package == self.name,
                            pa.architecture == self.architecture,
                            pa.key == key)\
                    .all()

            if len(v) == 0:
                raise NoSuchAttribute("Source package `%s@%s'" %
                        (self.name, architectures[self.architecture]), key)

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
            with database.session_scope() as s:
                pa = aliased(dbspkg.SourcePackageAttribute)
                a = s.query(pa)\
                        .filter(pa.source_package == self.name,
                                pa.architecture == self.architecture,
                                pa.key == key)\
                        .all()

                if len(a) == 0:
                    # Create a new attribute tuple
                    s.add(dbspkg.SourcePackageAttribute(
                            self.name,
                            self.architecture,
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
            with database.session_scope() as s:
                pa = aliased(dbspkg.SourcePackageAttribute)
                a = s.query(pa)\
                        .filter(pa.source_package == self.name,
                                pa.architecture == self.architecture,
                                pa.key == key)\
                        .all()

                if len(a) == 0:
                    raise NoSuchAttribute("Source package `%s@%s'" %
                            (self.name, architectures[self.architecture]), key)

                a = a[0]

                # Manually held?
                if a.manual_hold_time is not None:
                    raise AttributeManuallyHeld(key)

                s.delete(a)


    def __str__(self):
        return "SourcePackage(%s@%s)" % (self.name,
            Architecture.to_str(self.architecture))

    def short_str(self):
        """
        :returns: A string of the form %s@%s
        """
        return "%s@%s" % (self.name, Architecture.to_str(self.architecture))


    def __repr__(self):
        return "tslb.SourcePackage.SourcePackage(%s@%s)" % (self.name,
            Architecture.to_str(self.architecture))


class SourcePackageVersion:
    def __init__(self, source_package, version_number, create_locks=False, db_session=None):
        """
        A source package version.

        :param source_package:
        :type source_package: SourcePackage
        :param create_locks: Create the locks. Must be called with the
            SourcePackage X locked.
        :param db_session: Optionally specify a db session for i.e.
                           transactionality
        """
        self.source_package = source_package
        version_number = VersionNumber(version_number)
        self.version_number = version_number

        # For convenience:
        self.name = self.source_package.name
        self.architecture = self.source_package.architecture

        # Create locks if requested
        vs = str(self.version_number).replace('.', '_')
        self.dbrlp = source_package.dbrlp + "." + vs

        self.db_root_lock = tclm.define_lock(self.dbrlp)
        self.db_binary_packages_lock = tclm.define_lock(self.dbrlp + '.binary_packages')

        if create_locks:
            self.ensure_write_intent()
            self.db_binary_packages_lock.create(False)

        # Bind a DB object
        self.read_from_db(db_session)

        # A scratch space and caches for directories in it
        self.scratch_space = None


    # Peripheral methods
    def read_from_db(self, db_session = None):
        s = database.conn.get_session() if db_session is None else db_session

        try:
            dbos = s.query(dbspkg.SourcePackageVersion)\
                    .filter_by(source_package = self.source_package.name,
                            architecture = self.architecture,
                            version_number = self.version_number).all()

            if len(dbos) != 1:
                raise NoSuchSourcePackageVersion(self.source_package.name,
                        self.architecture, self.version_number)

            dbo = dbos[0]

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
        A convenience method that calls self.source_package.ensure_write_intent.
        """
        self.source_package.ensure_write_intent()


    def mount_scratch_space(self):
        """This method ensures that the scratch space exists and mounts it."""
        if not self.scratch_space:
            self.scratch_space = ScratchSpacePool().get_scratch_space(
                "%s_%s_%s" % (self.name, Architecture.to_str(self.architecture), self.version_number),
                self.source_package.write_intent,
                100 * 1024 * 1024 * 1024)

        self.scratch_space.mount()


    def clean_scratch_space(self):
        """
        Delete all content from the build- and install locations on the tslb fs.
        The binary packages are not removed because they'll get new version
        numbers and may still be needed for inspection.
        """
        self.ensure_write_intent()
        self.mount_scratch_space()
        fops.clean_directory(self.scratch_space.mount_path)


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
        self.ensure_write_intent()

        if time is None:
            time = timezone.now()

        files = sorted(files)

        with lock_X(self.db_root_lock):
            with database.session_scope() as s:
                # Check for differences
                fs = aliased(dbspkg.SourcePackageVersionInstalledFile)
                dbfiles = s.query(fs.path, fs.sha512sum)\
                        .filter(fs.source_package == self.source_package.name,
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
                    s.query(dbspkg.SourcePackageVersionInstalledFile)\
                            .filter(dbspkg.SourcePackageVersionInstalledFile.source_package ==
                                        self.source_package.name,
                                    dbspkg.SourcePackageVersionInstalledFile.architecture ==
                                        self.architecture,
                                    dbspkg.SourcePackageVersionInstalledFile.version_number ==
                                        self.version_number)\
                            .delete()


                    for (p, sha512) in files:
                        s.add(dbspkg.SourcePackageVersionInstalledFile(
                            self.source_package.name,
                            self.architecture,
                            self.version_number,
                            p,
                            sha512))

                # Update the reassured time
                self.dbo.installed_files_reassured_time = time

                if different:
                    self.dbo.installed_files_modified_time = time

                s.add(self.dbo)

            self.read_from_db()


    def get_installed_files(self):
        """
        :returns: list(tuple(path, sha512sum))
        :rtype: list(tuple(str, str))
        """
        with database.session_scope() as s:
            fs = aliased(dbspkg.SourcePackageVersionInstalledFile)
            l = s.query(fs.path, fs.sha512sum)\
                    .filter(fs.source_package == self.source_package.name,
                            fs.architecture == self.architecture,
                            fs.version_number == self.version_number)\
                    .all()

            return l


    def get_installed_files_meta(self):
        """
        :returns: tuple(modified_time, reassured_time)
        :rtype: tuple(datetime, datetime)
        """
        return (self.dbo.installed_files_modified_time, self.dbo.installed_files_reassured_time)


    # Shared libraries
    def get_shared_libraries(self):
        """
        :returns: list(shared libraries)
        :rtype: list(shared_library_tools.SharedLibrary)
        """
        libs = []

        with database.session_scope() as s:
            ls = aliased(dbspkg.SourcePackageSharedLibrary)
            dblibs = s.query(ls)\
                    .filter(ls.source_package == self.source_package.name,
                            ls.architecture == self.architecture,
                            ls.source_package_version_number == self.version_number)\
                    .all()

            for dblib in dblibs:
                fs = aliased(dbspkg.SourcePackageSharedLibraryFile)
                files = s.query(fs.path, fs.is_dev_symlink)\
                        .filter(fs.source_package_id == dblib.id)\
                        .all()

                files = [ (e[0], e[1]) for e in files ]

                libs.append(SharedLibrary(dblib, files))

            return libs


    def set_shared_libraries(self, libs):
        """
        :param libs: list(shared libraries)
        :rtype: list(shared_library_tools.SharedLibrary)
        """
        with lock_X(self.db_root_lock):
            with database.session_scope() as s:
                # Delete all currently stored shared libraries
                s.query(dbspkg.SourcePackageSharedLibrary)\
                        .filter(dbspkg.SourcePackageSharedLibrary.source_package == self.source_package.name,
                                dbspkg.SourcePackageSharedLibrary.architecture == self.architecture,
                                dbspkg.SourcePackageSharedLibrary.source_package_version_number == self.version_number)\
                        .delete()

                # Store the new ones
                for l in libs:
                    lib = dbspkg.SourcePackageSharedLibrary(
                        self.source_package.name,
                        self.architecture,
                        self.version_number,
                        l)

                    s.add(lib)

                    # Make sure we have an id
                    s.flush()
                    _id = lib.id

                    # Insert files
                    s.execute(dbspkg.SourcePackageSharedLibraryFile.__table__.insert(
                        [
                            {
                                'source_package_id': _id,
                                'path': f,
                                'is_dev_symlink': f in l.get_dev_symlinks()
                            } for f in l.get_files()
                        ]))


    # Binary packages
    def list_current_binary_packages(self):
        """
        List only the binary packages that are currently built from this source
        package version. That is, only the packages that would be built when
        a full rebuild was done with the source package version's state before
        the last split-into-binary-packages was done.

        :returns: list(names)
        :rtype: list(str)
        """
        with database.session_scope() as s:
            cp = aliased(dbspkg.SourcePackageVersionCurrentBinaryPackage)
            cbps = s.query(cp.name)\
                    .filter(cp.source_package == self.source_package.name,
                            cp.architecture == self.architecture,
                            cp.version_number == self.version_number)\
                    .all()

            return [ e[0] for e in cbps ]


    def get_current_binary_packages_meta(self):
        """
        No manual hold time is returned because it does not make sense to hold
        something that is purely functional dependent on the current state.

        :returns: tuple(modified time, reassured time)
        :rtype: typle(datetime.datetime, datetime.datetime)
        """
        return (self.dbo.current_binary_packages_modified_time,
                self.dbo.current_binary_packages_reassured_time)


    def set_current_binary_packages(self, names, time = None):
        """
        Set the list of binary packages that is to be created during the next
        split-into-binary-packages.

        :param names: list(binary packages' names)
        :type names: list(str)
        """
        self.ensure_write_intent()

        if time is None:
            time = timezone.now()

        with lock_X(self.db_root_lock):
            with database.session_scope() as s:
                modified = False

                # Detect changes
                cp = aliased(dbspkg.SourcePackageVersionCurrentBinaryPackage)
                dbnames = s.query(cp.name)\
                        .filter(cp.source_package == self.source_package.name,
                                cp.architecture == self.architecture,
                                cp.version_number == self.version_number)\
                        .order_by(cp.name)\
                        .all()

                dbnames = [ e[0] for e in dbnames ]

                if len(dbnames) != len(names):
                    modified = True
                else:
                    for i in range(len(names)):
                        if dbnames[i] != names[i]:
                            modified = True
                            break

                # Eventually update package list
                if modified:
                    t = dbspkg.SourcePackageVersionCurrentBinaryPackage.__table__
                    s.execute(t.delete()\
                            .where(t.c.source_package == self.source_package.name)\
                            .where(t.c.architecture == self.architecture)\
                            .where(t.c.version_number == self.version_number))

                    s.flush()
                    s.execute(cp.__table__.insert(
                        [
                            {
                                'source_package': self.source_package.name,
                                'architecture': self.architecture,
                                'version_number': self.version_number,
                                'name': n
                            } for n in names
                        ]))

                # Update timestamps
                self.dbo.current_binary_packages_reassured_time = time

                if modified:
                    self.dbo.current_binary_packages_modified_time = time

                s.add(self.dbo)

            self.read_from_db()


    def list_all_binary_packages(self):
        """
        List all binary packages that were built from this source package,
        whether they would still be built or not.

        :returns: list(names)
        :rtype: list(str)
        """
        with database.session_scope() as s:
            bp = aliased(dbbpkg.BinaryPackage)
            names = s.query(bp.name)\
                    .filter(bp.source_package == self.source_package.name,
                            bp.architecture == self.architecture,
                            bp.source_package_version_number == self.version_number)\
                    .distinct()\
                    .all()

            return [n[0] for n in names]


    def list_binary_package_version_numbers(self, name):
        """
        List the version numbers of the given binary package.

        :param name: The binary package's name
        :type name: str
        :returns: ordered list(version numbers)
        :rtype: list(VersionNumber) (may be empty if no such binary package exists)
        """
        with database.session_scope() as s:
            bp = aliased(dbbpkg.BinaryPackage)
            vs = s.query(bp.version_number)\
                    .filter(bp.source_package == self.source_package.name,
                            bp.architecture == self.architecture,
                            bp.source_package_version_number == self.version_number,
                            bp.name == name)\
                    .order_by(bp.version_number)\
                    .all()

            return [v[0] for v in vs]


    def get_binary_package(self, name, version_number):
        """
        :param name: The binary package's name
        :type name: str
        :param version_number: The binary package's version number
        :returns: The binary package
        :rtype: BinaryPackage.BinaryPackage
        """
        version_number = VersionNumber(version_number)

        return BinaryPackage(self, name, version_number)


    def add_binary_package(self, name, version_number):
        """
        Creates a new binary package for this source package version.

        :param name: The binary package's name
        :type name: str
        :param version_number: The binary package's version numver
        :returns: The binary package
        :rtype: BinaryPackage.BinaryPackage
        """
        self.ensure_write_intent()
        version_number = VersionNumber(version_number)

        with lock_X(self.db_root_lock):
            with database.session_scope() as s:
                # Create db tuple
                bp = dbbpkg.BinaryPackage()
                bp.initialize_fields(
                        self.source_package.name,
                        self.architecture,
                        self.version_number,
                        name,
                        version_number)

                s.add(bp)

                # Create a binary package object to create locks
                BinaryPackage(self, name, version_number, create_locks=True, db_session=s)

                # Commit
                s.commit()

                # Create a new binary package object that is not bound to the
                # former session and can therefore be returned.
                return BinaryPackage(self, name, version_number)


    def delete_binary_package(self, name, version_number):
        """
        Remove the given binary package

        :param name: The binary package's name
        :type name: str
        :param version_number: The binary package's version number
        """
        self.ensure_write_intent()
        self.mount_scratch_space()

        version_number = VersionNumber(version_number)

        with lock_X(self.db_root_lock):
            with database.session_scope() as s:
                # Delete db tuple
                s.query(dbbpkg.BinaryPackage)\
                        .filter_by(source_package = self.source_package.name,
                                architecture = self.architecture,
                                source_package_version_number = self.version_number,
                                name = name,
                                version_number = version_number)\
                        .delete()

                # Delete the binary package's files in the scratch space
                fops.rm_rf(os.path.join('/binary_packages', name, str(version_number)))


    def remove_old_binary_packages(self):
        """
        This method removes all binary packages that are not currently built
        out of the source package version. Moreover it removes all but the
        latest version of binary packages that are built.

        This operation requires that the source package version has write
        intent announced.
        """
        self.ensure_write_intent()

        # Delete packages that are not built anymore
        all_bp_names = self.list_all_binary_packages()
        current_bps = set(self.list_current_binary_packages())

        to_delete = []

        for bp_name in all_bp_names:
            if bp_name not in current_bps:
                for v in self.list_binary_package_version_numbers(bp_name):
                    to_delete.append((bp_name, v))

        for name, version in to_delete:
            self.delete_binary_package(name, version)

        # Delete old versions of packages that are built
        all_bp_names = self.list_all_binary_packages()

        for bp_name in all_bp_names:
            versions = self.list_binary_package_version_numbers(bp_name)
            newest = max(versions)

            for v in versions:
                if v != newest:
                    self.delete_binary_package(bp_name, v)


    # Key-Value-Store like attributes
    def list_attributes(self, pattern=None):
        """
        :param str pattern: A pattern that the attributes must match. May contain
            '*' as wildcard-character.
        :returns: A list of all keys
        """
        with database.session_scope() as s:
            pa = aliased(dbspkg.SourcePackageVersionAttribute)
            q = s.query(pa.key)\
                    .filter(pa.source_package == self.source_package.name,
                            pa.architecture == self.architecture,
                            pa.version_number == self.version_number)

            if pattern is not None:
                pattern = pattern.replace('\\', '\\\\').replace('%', r'\%').replace('_', r'\_')\
                        .replace('*', '%')

                q = q.filter(pa.key.like(pattern, escape='\\'))

            return [e[0] for e in q.all()]


    def has_attribute(self, key):
        """
        :returns: True or False
        :rtype: bool
        """
        with database.session_scope() as s:
            pa = aliased(dbspkg.SourcePackageVersionAttribute)
            return len(s.query(pa.key)\
                    .filter(pa.source_package == self.source_package.name,
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
        with database.session_scope() as s:
            pa = aliased(dbspkg.SourcePackageVersionAttribute)
            v = s.query(pa.value)\
                    .filter(pa.source_package == self.source_package.name,
                            pa.architecture == self.architecture,
                            pa.version_number == self.version_number,
                            pa.key == key)\
                    .all()

            if len(v) == 0:
                raise NoSuchAttribute("Source package version `%s@%s:%s'" %
                        (self.source_package.name, architectures[self.architecture],
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

    def get_attribute_or_default(self, key, default):
        """
        Like `get_attribute`, but return a default value instead of raising a
        `NoSuchAttribute` if the attribute does not exist.
        """
        if not self.has_attribute(key):
            return default

        return self.get_attribute(key)


    def get_attribute_meta(self, key):
        """
        :param key: The attribute's key
        :type key: str
        :returns: tuple(modified_time, reassured_time, manual_hold_time or None)
        :rtype: tuple(datetime, datetime, datetime or None)
        """
        with database.session_scope() as s:
            pa = aliased(dbspkg.SourcePackageVersionAttribute)
            v = s.query(pa.modified_time, pa.reassured_time, pa.manual_hold_time)\
                    .filter(pa.source_package == self.source_package.name,
                            pa.architecture == self.architecture,
                            pa.version_number == self.version_number,
                            pa.key == key)\
                    .all()

            if len(v) == 0:
                raise NoSuchAttribute("Source package version `%s@%s:%s'" %
                        (self.source_package.name, architectures[self.architecture],
                            self.version_number), key)

            return v[0]


    def manually_hold_attribute(self, key, remove=False, time=None):
        self.ensure_write_intent()

        with lock_X(self.db_root_lock):
            with database.session_scope() as s:
                pa = aliased(dbspkg.SourcePackageVersionAttribute)
                v = s.query(pa)\
                        .filter(pa.source_package == self.source_package.name,
                                pa.architecture == self.architecture,
                                pa.version_number == self.version_number,
                                pa.key == key)\
                        .all()

                if len(v) == 0:
                    raise NoSuchAttribute("Source package version `%s@%s:%s'" %
                            (self.source_package.name, architectures[self.architecture],
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
        with database.session_scope() as s:
            pa = aliased(dbspkg.SourcePackageVersionAttribute)
            v = s.query(pa.manual_hold_time)\
                    .filter(pa.source_package == self.source_package.name,
                            pa.architecture == self.architecture,
                            pa.version_number == self.version_number,
                            pa.key == key)\
                    .all()

            if len(v) == 0:
                raise NoSuchAttribute("Source package version `%s@%s:%s'" %
                        (self.source_package.name, architectures[self.architecture],
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
            with database.session_scope() as s:
                pa = aliased(dbspkg.SourcePackageVersionAttribute)
                a = s.query(pa)\
                        .filter(pa.source_package == self.source_package.name,
                                pa.architecture == self.architecture,
                                pa.version_number == self.version_number,
                                pa.key == key)\
                        .all()

                if len(a) == 0:
                    # Create a new attribute tuple
                    s.add(dbspkg.SourcePackageVersionAttribute(
                            self.source_package.name,
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
            with database.session_scope() as s:
                pa = aliased(dbspkg.SourcePackageVersionAttribute)
                a = s.query(pa)\
                        .filter(pa.source_package == self.source_package.name,
                                pa.architecture == self.architecture,
                                pa.version_number == self.version_number,
                                pa.key == key)\
                        .all()

                if len(a) == 0:
                    raise NoSuchAttribute("Source package version `%s@%s:%s'" %
                            (self.source_package.name, architectures[self.architecture],
                                self.version_number), key)

                a = a[0]

                # Manually held?
                if a.manual_hold_time is not None:
                    raise AttributeManuallyHeld(key)

                s.delete(a)


    # Some convenience methods for accessing frequently used attributes
    def get_cdeps(self):
        """
        :rtype: DependencyList or None
        """
        if self.has_attribute('cdeps'):
            return self.get_attribute('cdeps')
        else:
            return None


    def set_cdeps(self, dl):
        if not isinstance(dl, DependencyList):
            raise TypeError
        else:
            self.set_attribute('cdeps', dl)


    def add_cdep(self, pkg_name, c='', vn='0'):
        """
        e.g. add_cdep('basic_fhs', '>=', '3.0')
        """
        if self.has_attribute('cdeps'):
            dl = self.get_attribute('cdeps')
            dl.add_constraint(pkg_name, VersionConstraint(c, vn))
            self.set_attribute('cdeps', dl)

        else:
            dl = DependencyList()
            dl.add_constraint(pkg_name, VersionConstraint(c, vn))
            self.set_attribute('cdeps', dl)


    def remove_cdep(self, pkg_name):
        if self.has_attribute('cdeps'):
            dl = self.get_attribute('cdeps')
            ndl = DependencyList()

            for pn, cs in dl.l.items():
                if pn != pkg_name:
                    for c in cs:
                        ndl.add_constraint(pn, c)

            self.set_attribute('cdeps', ndl)

    def get_tools(self):
        """
        :rtype: DependencyList or None
        """
        if self.has_attribute('tools'):
            return self.get_attribute('tools')
        else:
            return None


    def set_tools(self, dl):
        if not isinstance(dl, DependencyList):
            raise TypeError
        else:
            self.set_attribute('tools', dl)


    def add_tool(self, pkg_name, c='', vn='0'):
        """
        e.g. add_tool('tpm2', '>=', '1.0')
        """
        if self.has_attribute('tools'):
            dl = self.get_attribute('tools')
            dl.add_constraint(pkg_name, VersionConstraint(c, vn))
            self.set_attribute('tools', dl)

        else:
            dl = DependencyList()
            dl.add_constraint(pkg_name, VersionConstraint(c, vn))
            self.set_attribute('tools', dl)


    def remove_tool(self, pkg_name):
        if self.has_attribute('tools'):
            dl = self.get_attribute('tools')
            ndl = DependencyList()

            for pn, cs in dl.l.items():
                if pn != pkg_name:
                    for c in cs:
                        ndl.add_constraint(pn, c)

            self.set_attribute('tools', ndl)


    #************** Convenience methods for the scratch space *****************
    @property
    def build_location(self):
        """
        The directory in the scratch space where the source tree is unpacked
        to.
        """
        return os.path.join(self.scratch_space.mount_path, 'build_location')


    def ensure_build_location(self):
        """
        Create the build location if it does not exist.
        """
        self.mount_scratch_space()

        if not os.path.isdir(self.build_location):
            os.mkdir(self.build_location)


    @property
    def install_location(self):
        """
        The directory in the scratch space where the package will be installed.
        """
        return os.path.join(self.scratch_space.mount_path, 'install_location')


    def ensure_install_location(self):
        """
        Create the install location if it does not exist.
        """
        self.mount_scratch_space()

        if not os.path.isdir(self.install_location):
            os.mkdir(self.install_location)


    @property
    def binary_packages_location(self):
        """
        The directory in the scratch space that houses the binary packages'
        subdirectories.
        """
        return os.path.join(self.scratch_space.mount_path, 'binary_packages')


    def ensure_binary_packages_location(self):
        """
        Create the binary packages' location if it does not exist.
        """
        self.mount_scratch_space()

        if not os.path.isdir(self.binary_packages_location):
            os.mkdir(self.binary_packages_location)


    def __str__(self):
        return "SourcePackage(%s@%s:%s)" % (self.source_package.name,
            Architecture.to_str(self.architecture), self.version_number)


    def __repr__(self):
        return "tslb.SourcePackage.SourcePackage(%s@%s:%s)" % (
                self.source_package.name,
                Architecture.to_str(self.architecture), self.version_number)


# Some exceptions at our pleasure.
class NoSuchSourcePackage(Exception):
    def __init__(self, name, architecture):
        architecture = architectures[architecture]
        super().__init__("No such source package: `%s@%s'" % (name, architecture))

class NoSuchSourcePackageVersion(Exception):
    def __init__(self, name, architecture, version_number):
        architecture = architectures[architecture]
        super().__init__("No such source package version: `%s@%s:%s'" % (name, architecture, version_number))

class SourcePackageExists(Exception):
    def __init__(self, name, architecture):
        architecture = architectures[architecture]
        super().__init__("Source package `%s@%s' exists already." % (name, architecture))

class SourcePackageVersionExists(Exception):
    def __init__(self, name, architecture, version_number):
        architecture = architectures[architecture]
        super().__init__("Source package version: `%s@%s:%s' exists already." % (name, architecture, version_number))
