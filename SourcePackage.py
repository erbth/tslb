from Architecture import architectures
from BinaryPackage import BinaryPackage, NoSuchBinaryPackage
from CommonExceptions import NoSuchAttribute, MissingWriteIntent, AttributeManuallyHeld
from filesystem import FileOperations as fops
from SharedLibraryTools import SharedLibrary
from VersionNumber import VersionNumber
from sqlalchemy.orm import aliased
from tclm import lock_S, lock_Splus, lock_X
from time import sleep
import BinaryPackage as bp
import base64
import database
import database.BinaryPackage as dbbpkg
import database.SourcePackage as dbspkg
import filesystem as fs
import os
import pickle
import tclm
import timezone

class SourcePackageList(object):
    def __init__(self, architecture, create_locks = False):
        if architecture not in architectures.keys():
            raise ValueError('Invalid architecture')

        self.architecture = architecture

        # Define a few required locks
        self.dbrlp = 'tslb_db.%s.source_packages' % architectures[architecture]
        self.fsrlp = 'tslb_fs.%s.packaging' % architectures[architecture]

        self.db_root_lock = tclm.define_lock(self.dbrlp)
        self.fs_root_lock = tclm.define_lock(self.fsrlp)

        # Create locks if desired
        if create_locks:
            self.fs_root_lock.create(True)
            self.db_root_lock.create(True)

            self.db_root_lock.release_X()
            self.fs_root_lock.release_X()

    def list_source_packages(self, architecture=None):
        """
        Returns an ordered list of the source packages' names. By default,
        packages of all architectures are selected and not only these from this
        list.

        :param architecture: If not None, the list of packages will be filtered
            by the supplied architecture.
        :type architecture: int or None
        :returns: list(tuple(name, architecture))
        :rtype: list(tuple(str, int))
        """
        with lock_S(self.db_root_lock):
            s = database.get_session()
            sp = aliased(dbspkg.SourcePackage)

            if architecture:
                if architecture not in architectures.keys():
                    raise ValueError("Invalid architecture")

                return s.query(sp.name, sp.architecture)\
                        .filter(sp.architecture == architecture)\
                        .order_by(sp.name, sp.architecture).all()
            else:
                return s.query(sp.name, sp.architecture).order_by(sp.name, sp.architecture).all()

    def create_source_package(self, name):
        # Lock the source package list and the fs
        with lock_X(self.fs_root_lock):
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

                    # Create fs location
                    fs_base = os.path.join(fs.root, 'packaging', name)

                    # Transactionality
                    try:
                        fops.mkdir_p (fs_base, 0o755)

                        # Create locks
                        SourcePackage(name, self.architecture, write_intent = True,
                                create_locks = True, db_session = s)

                        s.commit()

                    except:
                        fops.rm_rf(fs_base)
                        raise

                    return SourcePackage(name, self.architecture, write_intent = True)

                except:
                    s.rollback()
                    raise
                finally:
                    s.close()

    def destroy_source_package(self, name):
        # Lock the source package list and the fs
        with lock_X(self.fs_root_lock):
            with lock_X(self.db_root_lock):
                # Remove the db tuple(s)
                s = database.get_session()
                spkg = s.query(dbspkg.SourcePackage).\
                        filter_by(name=name, architecture=self.architecture).first()

                if spkg:
                    s.delete(spkg)
                    s.commit()

                # Remove the fs location(s)
                fops.rm_rf (os.path.join(fs.root, 'packaging', name))

class SourcePackage(object):
    def __init__(self, name, architecture, write_intent = False, create_locks = False, db_session=None):
        """
        Initially, create_locks must be true for the first time the package was
        used. If write_intent is True, S+ locks are acquired initially.
        """
        self.name = name
        self.architecture = architecture
        self.write_intent = write_intent

        # Define a few required locks
        self.dbrlp = 'tslb_db.%s.source_packages.%s' % (architectures[self.architecture], self.name)
        self.fsrlp = 'tslb_fs.%s.packaging.%s' % (architectures[self.architecture], self.name)

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
            self.read_from_db(db_session)

            # The fs location for this source package:
            self.fs_base = os.path.join(fs.root, 'packaging', name)

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
            raise MissingWriteIntent
            # self.write_intent = True

            # self.fs_root_lock.acquire_Splus()
            # self.fs_root_lock.release_S()

            # self.db_root_lock.acquire_Splus()
            # self.db_root_lock.release_S()

    def read_from_db(self, db_session=None):
        s = db_session if db_session else database.conn.get_session()
        dbo = s.query(dbspkg.SourcePackage)\
                .filter_by(name=self.name, architecture=self.architecture)\
                .first()

        if dbo is None:
            raise NoSuchSourcePackage(self.name, self.architecture)

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

        s = database.get_session()
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

                try:
                    pvs = aliased(dbspkg.SourcePackageVersion)
                    if s.query(pvs)\
                            .filter(pvs.source_package == self.name,
                                    pvs.architecture == self.architecture,
                                    pvs.version_number == version_number)\
                            .first():
                        raise SourcePackageVersionExists(self.name, self.architecture, version_number)

                    # Create the fs locations
                    fs_base = os.path.join(self.fs_base, str(version_number))

                    try:
                        os.mkdir (fs_base, 0o755)

                        for d in [ 'build_location', 'install_location', 'binary_packages' ]:
                            os.mkdir (os.path.join(fs_base, d), 0o755)

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

                    except:
                        fops.rm_rf (fs_base)
                        raise

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
                fops.rm_rf(os.path.join(self.source_package.fs_base, str(self.version_number)))

                # Delete the db tuple
                s = database.get_session()

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

        # For convenience:
        self.architecture = self.source_package.architecture

        # Create locks if requested
        vs = str(self.version_number).replace('.', '_')
        self.fsrlp = source_package.fsrlp + "." + vs
        self.dbrlp = source_package.dbrlp + "." + vs

        self.fs_root_lock = tclm.define_lock(self.fsrlp)
        self.fs_build_location_lock = tclm.define_lock(self.fsrlp + '.build_location')
        self.fs_install_location_lock = tclm.define_lock(self.fsrlp + '.install_location')
        self.fs_binary_packages_lock = tclm.define_lock(self.fsrlp + '.binary_packages')

        self.db_root_lock = tclm.define_lock(self.dbrlp)
        self.db_binary_packages_lock = tclm.define_lock(self.dbrlp + '.binary_packages')

        if create_locks:
            self.ensure_write_intent()

            for l in [
                    self.fs_build_location_lock,
                    self.fs_install_location_lock,
                    self.fs_binary_packages_lock,
                    self.db_binary_packages_lock ]:
                l.create(False)

        # Bind a DB object
        self.read_from_db(db_session)

        # Fs locations
        self.fs_base = os.path.join(self.source_package.fs_base, str(self.version_number))
        self.fs_build_location = os.path.join(self.fs_base, 'build_location')
        self.fs_install_location = os.path.join(self.fs_base, 'install_location')
        self.fs_binary_packages = os.path.join(self.fs_base, 'binary_packages')


    # Peripheral methods
    def read_from_db(self, db_session = None):
        s = database.conn.get_session() if db_session is None else db_session
        dbos = s.query(dbspkg.SourcePackageVersion)\
                .filter_by(source_package = self.source_package.name,
                        architecture = self.architecture,
                        version_number = self.version_number).all()

        if len(dbos) != 1:
            raise NoSuchSourcePackageVersion(self.source_package.name,
                    self.architecture, self.version_number)

        dbo = dbos[0]

        if not db_session:
            s.expunge(dbo)

        self.dbo = dbo

    def ensure_write_intent(self):
        """
        A convenience method that calls self.source_package.ensure_write_intent.
        """
        self.source_package.ensure_write_intent()

    def clean_fs_locations(self):
        """
        Delete all content from the build- and install locations on the tslb fs.
        The binary packages are not removed because they'll get new version
        numbers and may still be needed for inspection.
        """
        fops.clean_directory(self.fs_build_location)
        fops.clean_directory(self.fs_install_location)


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
            s = database.get_session()

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
            s.commit()

            self.read_from_db()

    def get_installed_files(self):
        """
        :returns: list(tuple(path, sha512sum))
        :rtype: list(tuple(str, str))
        """
        s = database.get_session()

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
        :rtype: list(SharedLibraryTools.SharedLibrary)
        """
        libs = []

        s = database.get_session()

        ls = aliased(dbspkg.SourcePackageSharedLibrary)
        dblibs = s.query(ls)\
                .filter(ls.source_package == self.source_package.name,
                        ls.architecture == self.architecture,
                        ls.source_package_version_number == self.version_number)\
                .all()

        for dblib in dblibs:
            fs = aliased(dbspkg.SourcePackageSharedLibraryFile)
            files = s.query(fs.name)\
                    .filter(fs.id == dblib.id)\
                    .all()

            files = [ e[0] for e in files ]

            libs.append(SharedLibrary(dblib, files))

        return libs

    def set_shared_libraries(self, libs):
        """
        :param libs: list(shared libraries)
        :rtype: list(SharedLibraryTools.SharedLibrary)
        """
        with lock_X(self.db_root_lock):
            s = database.get_session()
            s.begin()

            # Delete all currently stored shared libraries
            sl = aliased(dbspkg.SourcePackageSharedLibrary)
            s.query(sl)\
                    .filter(sl.source_package == self.source_package.name,
                            sl.architecture == self.architecture,
                            sl.source_package_version_number == self.version_number)\
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
                id = s.id

                # Insert files
                s.execute(dbspkg.SourcePackageSharedLibraryFile.__table__.insert(
                    [
                        { 'id': id, 'path': f } for f in l.files
                    ]))

            s.commit()

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
        s = database.get_session()

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
            s = database.get_session()

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
            s.commit()
            self.read_from_db()

    def list_all_binary_packages(self):
        """
        List all binary packages that were built from this source package,
        whether they would still be built or not.

        :returns: list(names)
        :rtype: list(str)
        """
        s = database.get_session()

        bp = aliased(dbbpkg.BinaryPackage)
        names = s.query(bp.name)\
                .filter(bp.source_package == self.source_package.name,
                        bp.architecture == self.architecture,
                        bp.source_package_version_number == self.version_number)\
                .all()

        return [ n[0] for n in names ]

    def list_binary_package_version_numbers(self, name):
        """
        List the version numbers of the given binary package.

        :param name: The binary package's name
        :type name: str
        :returns: list(version numbers)
        :rtype: list(VersionNumber) (may be empty if no such binary package exists)
        """
        s = database.get_session()

        bp = aliased(dbbpkg.BinaryPackage)
        vs = s.query(bp.version_number)\
                .filter(bp.source_package == self.source_package.name,
                        bp.architecture == self.architecture,
                        bp.source_package_version_number == self.version_number,
                        bp.name == name)\
                .all()

        return [ v[0] for v in vs ]

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

        with lock_X(self.fs_binary_packages_lock):
            with lock_X(self.db_root_lock):
                s = database.get_session()

                try:
                    # Create fs locations
                    fs_base = os.path.join(self.fs_binary_packages, str(version_number))

                    try:
                        os.mkdir (fs_base, 0o755)

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

                    except:
                        fops.rm_rf (fs_base)

                    # Create a new binary package object that is not bound to the
                    # former session and can therefore be returned.
                    return BinaryPackage(self, name, version_number)

                except:
                    s.rollback()
                finally:
                    s.close()

    def delete_binary_package(self, name, version_number):
        """
        Remove the given binary package

        :param name: The binary package's name
        :type name: str
        :param version_number: The binary package's version number
        """
        self.ensure_write_intent()

        version_number = VersionNumber(version_number)

        with lock_X(self.fs_binary_packages_lock):
            with lock_X(self.db_root_lock):
                s = database.get_session()

                # Delete db tuple
                s.query(dbbpkg.BinaryPackage)\
                        .filter_by(source_package = self.source_package.name,
                                architecture = self.architecture,
                                source_package_version_number = self.version_number,
                                name = name,
                                version_number = version_number)\
                        .delete()

                s.commit()
                s.close()

                # Delete fs location
                fops.rm_rf(os.path.join(self.fs_binary_packages, str(version_number)))

    # Key-Value-Store like attributes
    def list_attributes(self):
        """
        :returns: A list of all keys
        """
        s = database.get_session()
        
        pa = aliased(dbspkg.SourcePackageVersionAttribute)
        l = s.query(pa.key)\
                .filter(pa.source_package == self.source_package.name,
                        pa.architecture == self.architecture,
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
        s = database.get_session()

        pa = aliased(dbspkg.SourcePackageVersionAttribute)
        v = s.query(pa.value)\
                .filter(pa.source_package == self.source_package.name,
                        pa.architecture == self.architecture,
                        pa.version_number == self.version_number,
                        pa.key == key)\
                .all()

        if len(v) == 0:
            raise NoSuchAttribute("Source package version `%s@%s:%s'" %
                    (self.source_package.name, self.architecture,
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
        s = database.get_session()

        pa = aliased(dbspkg.SourcePackageVersionAttribute)
        v = s.query(pa.modified_time, pa.reassured_time, pa.manual_hold_time)\
                .filter(pa.source_package == self.source_package.name,
                        pa.architecture == self.architecture,
                        pa.version_number == self.version_number,
                        pa.key == key)\
                .all()

        if len(v) == 0:
            raise NoSuchAttribute("Source package version `%s@%s:%s'" %
                    (self.source_package.name, self.architecture,
                        self.version_number), key)

        return v[0]

    def manually_hold_attribute(self, key, remove=False, time=None):
        self.ensure_write_intent()

        with lock_X(self.db_root_lock):
            s = database.get_session()

            pa = aliased(dbspkg.SourcePackageVersionAttribute)
            v = s.query(pa)\
                    .filter(pa.source_package == self.source_package.name,
                            pa.architecture == self.architecture,
                            pa.version_number == self.version_number,
                            pa.key == key)\
                    .all()

            if len(v) == 0:
                raise NoSuchAttribute("Source package version `%s@%s:%s'" %
                        (self.source_package.name, self.architecture,
                            self.version_number), key)

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
                        pa.architecture == self.architecture,
                        pa.version_number == self.version_number,
                        pa.key == key)\
                .all()

        if len(v) == 0:
            raise NoSuchAttribute("Source package version `%s@%s:%s'" %
                    (self.source_package.name, self.architecture,
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
            s = database.get_session()

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

            s.commit()

    def unset_attribute(self, key):
        self.ensure_write_intent()

        with lock_X(self.db_root_lock):
            s = database.get_session()

            pa = aliased(dbspkg.SourcePackageVersionAttribute)
            a = s.query(pa)\
                    .filter(pa.source_package == self.source_package.name,
                            pa.architecture == self.architecture,
                            pa.version_number == self.version_number,
                            pa.key == key)\
                    .all()

            if len(a) == 0:
                raise NoSuchAttribute("Source package version `%s@%s:%s'" %
                        (self.source_package.name, self.architecture,
                            self.version_number), key)

            a = a[0]

            # Manually held?
            if a.manual_hold_time is not None:
                raise AttributeManuallyHeld(key)

            s.delete(a)
            s.commit()


# Some exceptions for our pleasure.
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
