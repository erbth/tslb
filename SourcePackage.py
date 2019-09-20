from VersionNumber import VersionNumber
import tclm

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


    def read_from_db(self):
        pass

    def write_to_db(self):
        pass

class SourcePackageVersion(object):
    def __init__(self, source_package, version_number):
        self.version_number = VersionNumber(version_number)
