from VersionNumber import VersionNumber
import tclm
import database
import database.SourcePackage

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

            self.db_spkg = spkg
        except:
            # Release locks
            if write_intent:
                self.fs_root_lock.release_Splus()
                self.db_root_lock.release_Splus()
            else:
                self.fs_root_lock.release_S()
                self.db_root_lock.release_S()


    # Dealing with different versions
    def get_version_numbers(self):
        pass

    def get_version(self, version_number):
        pass

    def get_latest_version(self):
        pass

    def add_version(self, version_number):
        pass


class SourcePackageVersion(object):
    def __init__(self, source_package, version_number):
        self.source_package = source_package
        self.version_number = VersionNumber(version_number)


# Some exceptions for our pleasure.
class NoSuchSourcePackage(Exception):
    def __init__(self, name):
        super().__init__("No such source package: `%s'" % name)
