from VersionNumber import VersionNumber
import tclm
from tclm import lock_S, lock_Splus, lock_X
import database
import database.SourcePackage
import database.SourcePackage as dbspkg

class SourcePackageList(object):
    def __init__(self, create_locks = False):
        # Define a few required locks
        self.dbrlp = 'tslb_db.source_packages'
        self.fsrlp = 'tslb_fs.packaging'

        self.db_root_lock = tclm.define_lock(self.dbrlp)
        self.fs_root_lock = tclm.define_lock(self.fsrlp)

        # Create locks if desired
        if create_locks:
            self.db_root_lock.create()
            self.fs_root_lock.create()

            self.fs_root_lock.release_X()
            self.db_root_lock.release_X()

    def get_source_packages(self):
        """
        Returns an ordered list of the source packages' names.
        """
        self.db_root_lock.acquire_S()

        try:
            sps = database.conn.get_session().query(database.SourcePackage.SourcePackage)\
                        .order_by(database.SourcePackage.SourcePackage.name).all()

            names = [ sp.name for sp in sps ]
        except:
            self.db_root_lock.release_S()
            raise

        self.db_root_lock.release_S()
        return names


    def create_source_package(self, name, write_intent = False):
        # Lock the source package list and the fs
        self.fs_root_lock.acquire_X()
        self.db_root_lock.acquire_X()

        try:
            # Create the db tuple
            spkg = database.SourcePackage.SourcePackage()
            spkg.initialize_fields(name)

            s = database.conn.get_session()
            s.add(spkg)
            s.commit()
            del spkg
        except:
            # Unlock the list(s)
            self.db_root_lock.release_X()
            self.fs_root_lock.release_X()
            raise

        self.db_root_lock.release_X()

        try:
            # Create fs location
            pass
        except:
            # Unlock the list(s)
            self.fs_root_lock.release_X()
            raise

        self.fs_root_lock.release_X()

        # Create locks
        spkg = SourcePackage(name, write_intent = write_intent, create_locks = True)
        return spkg

    def destroy_source_package(self, name):
        # Lock the source package list and the fs
        self.fs_root_lock.acquire_X()
        self.db_root_lock.acquire_X()

        try:
            # Remove the db tuple
            s = database.conn.get_session()
            spkg = s.query(database.SourcePackage.SourcePackage).filter_by(name=name).all()

            if len(spkg) > 0:
                s.delete(spkg[0])
                s.commit()
            else:
                raise NoSuchSourcePackage(name)

            # Remove the fs location(s)

        finally:
            # Unlock the list(s)
            self.db_root_lock.release_X()
            self.fs_root_lock.release_X()

class SourcePackage(object):
    def __init__(self, name, write_intent = False, create_locks = False):
        """
        Initially, create_locks must be true for the first time the package was
        used. If write_intent is True, S+ locks are acquired initially.
        """
        self.name = name
        self.write_intent = write_intent

        # Define a few required locks
        dbrlp = 'tslb_db.source_packages.%s' % self.name
        fsrlp = 'tslb_fs.packaging.%s' % self.name

        self.db_root_lock = tclm.define_lock(dbrlp)

        self.fs_root_lock = tclm.define_lock(fsrlp)
        self.fs_source_location_lock = tclm.define_lock(fsrlp + '.source_location')
        self.fs_build_location_lock = tclm.define_lock(fsrlp + '.build_location')
        self.fs_install_location_lock = tclm.define_lock(fsrlp + '.install_location')
        self.fs_packaging_location_lock = tclm.define_lock(fsrlp + '.packaging_location')

        # Create locks if desired
        if create_locks:
            self.fs_root_lock.create()
            self.fs_root_lock.acquire_Splus()
            self.fs_root_lock.release_X()

            self.fs_source_location_lock.create()
            self.fs_source_location_lock.release_X()

            self.fs_build_location_lock.create()
            self.fs_build_location_lock.release_X()

            self.fs_install_location_lock.create()
            self.fs_install_location_lock.release_X()

            self.fs_packaging_location_lock.create()
            self.fs_packaging_location_lock.release_X()

            self.db_root_lock.create()
            self.db_root_lock.acquire_Splus()
            self.db_root_lock.release_X()

            if not write_intent:
                # Downgrade further to S mode
                self.fs_root_lock.acquire_S()
                self.fs_root_lock.release_Splus()

                self.db_root_lock.acquire_S()
                self.db_root_lock.release_Splus()

        else:
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
            s = database.conn.get_session()
            spkgs = s.query(database.SourcePackage.SourcePackage)\
                    .filter_by(name=name)

            if len(spkgs) != 1:
                raise NoSuchSourcePackage(name)

            spkg = spkgs[0]
            s.expunge(spkg)

            self.dbo = spkg
        except:
            # Release locks
            if write_intent:
                self.fs_root_lock.release_Splus()
                self.db_root_lock.release_Splus()
            else:
                self.fs_root_lock.release_S()
                self.db_root_lock.release_S()


    # Attributes
    # General
    def get_creation_time(self):
        return self.dbo.creation_time

    # Different versions
    def list_version_numbers(self):
        s = database.conn.get_session()
        vns = s.query(dbspkg.SourcePackageVersion.version_number)\
                .filter(dbspkg.SourcePackageVersion.source_package == self.name)\
                .all()

        return [ vn[0] for vn in vns ]

    def get_version(self, version_number):
        return SourcePackageVersion(self, version_number)

    def get_latest_version(self):
        # Get latest version number
        s = database.conn.get_session()
        vns = s.query(dbspkg.SourcePackageVersion.version_number)\
                .filter(dbspkg.SourcePackageVersion.source_package == self.name &&
                        dbspkg.SourcePackageVersion.version_number >=
                        dbspkg.SourcePackageVersion.version_number.max())\
                .all()

    def add_version(self, version_number):
        pass


class SourcePackageVersion(object):
    def __init__(self, source_package, version_number):
        self.source_package = source_package
        self.version_number = VersionNumber(version_number)

        # Bind a DB object
        try:
            s = database.conn.get_session()
            dbos = s.query(database.SourcePackage.SourcePackageVersion)\
                    .filter_by(source_package = source_package.get_name(),
                            version_number = version_number).all()

            if len(dbos) != 1:
                raise NoSuchSourcePackageVersion(name, version_number)

            dbo = dbos[0]
            s.expunge(dbo)

            self.dbo = dbo

        except:
            raise


    # Attributes
    # General
    def get_creation_time(self):
        return self.dbo.creation_time

    # Installed files

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
        pass

    def get_attribute(self, key):
        pass

    def set_attribute(self, key):
        pass

    def unset_attribute(self, key):
        pass


# Some exceptions for our pleasure.
class NoSuchSourcePackage(Exception):
    def __init__(self, name):
        super().__init__("No such source package: `%s'" % name)

class NoSuchSourcePackageVersion(Exception):
    def __init__(self, name, version_number):
        super().__init__("No such source package version: `%s@%s'" % (name, version_number))
