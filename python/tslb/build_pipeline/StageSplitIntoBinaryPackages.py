import os
import stat
import subprocess
import zlib
from tslb import BinaryPackage as bpkg
from tslb.Console import Color
from tslb.filesystem import FileOperations as fops
from tslb.program_analysis import shared_library_tools as so_tools

class StageSplitIntoBinaryPackages(object):
    name = 'split_into_binary_packages'

    def flow_through(spv, rootfs_mountpoint, out):
        """
        :param spv: The source package version that flows though this segment
            of the pipeline.
        :type spv: SourcePackage.SourcePackageVersion
        :param str rootfs_mountpoint: The mountpoint at which the rootfs image
            that should be used for the build is mounted.
        :param out: The (wrapped) fs to which the stage should send output that
            shall be recorded in the db. Typically all output would go there.
        :type out: Something like sys.stdout
        :returns: successful
        :rtype: bool
        """
        bp_version_number = bpkg.generate_version_number()
        out.write(Color.MAGENTA +
                "Binary packages' version: %s" % bp_version_number +
                Color.NORMAL + '\n')

        copied_files = set()

        # Read the package's installed files and directories.
        installed_files = set()
        installed_directories = set()

        out.write("  Reading the package's files ...\n")

        def process_file(_file):
            _file = '/' + _file

            st_buf = os.lstat(fops.simplify_path_static(spv.install_location + '/' + _file))

            if stat.S_ISDIR(st_buf.st_mode):
                installed_directories.add(_file)
            else:
                installed_files.add(_file)

        fops.traverse_directory_tree(spv.install_location, process_file)

        out.write("  The package installed %d files and %d directories.\n" %
                (len(installed_files), len(installed_directories)))


        # Map each file to a binary package
        package_file_map = {}

        # First, create two binary packages for each library: One with the
        # library itself, and one with its debug symbols.
        shared_libraries = spv.get_shared_libraries()

        for lib in shared_libraries:
            bp_name = lib.name
            if lib.abi_version_number:
                bp_name += str(lib.abi_version_number)

            out.write("  Adding binary package `%s' for shared library ...\n" % bp_name)

            if bp_name not in package_file_map:
                package_file_map[bp_name] = set()

            # Assign files
            for _file in lib.get_files() - lib.get_dev_symlinks():
                package_file_map[bp_name].add(_file)
                copied_files.add(_file)


            # Eventually create a debug package
            bp_dbg_name = None

            dbg_link = lib.get_gnu_debug_link(spv.install_location, out)
            if dbg_link:
                link, crc32 = dbg_link
                lib_dir = lib.get_library_dir()

                dbg_link_path = os.path.join(lib_dir, link)
                dbg_link_full_path = fops.simplify_path_static(
                        spv.install_location + '/' + dbg_link_path)

                try:
                    # Check if the debug link's CRC32 checksum matches.
                    with open(dbg_link_full_path, 'rb') as f:
                        crc32_dbg_file = zlib.crc32(f.read())

                    if crc32 == crc32_dbg_file:
                        # Create a debug package
                        bp_dbg_name = bp_name + '-dbgsym'

                    else:
                        our.write(Color.YELLOW +
                                "    Debug link checksum mismatch: 0x%08x (link) != 0x%08x (file)." %
                                (crc32, crc32_dbg_file) + Color.NORMAL + '\n')

                except FileNotFoundError:
                    out.write(Color.YELLOW +
                            "    Debug link `%s' does not refer to a file." % link +
                            Color.NORMAL + '\n')

            if bp_dbg_name:
                out.write("    Adding debug package `%s' ...\n" % bp_dbg_name)

                if bp_dbg_name not in package_file_map:
                    package_file_map[bp_dbg_name] = set()

                # Assign files
                for _file in (dbg_link_path,):
                    package_file_map[bp_dbg_name].add(_file)
                    copied_files.add(_file)


        # If shared objects are left after packaging shared libraries, move
        # them to an extra package.
        other_so_files = set()

        remaining_files = installed_files - copied_files
        for lib in shared_libraries:
            remaining_files -= lib.get_dev_symlinks()

        for _file in remaining_files:
            if _file.endswith('.so'):
                other_so_files.add(_file)
                copied_files.add(_file)


        if other_so_files:
            bp_other_so_name = spv.name + '-other_so'
            out.write("\n  Adding a package `%s' for other shared objects ...\n" %
                    bp_other_so_name)

            if bp_other_so_name not in package_file_map:
                package_file_map[bp_other_so_name] = set()

            s = package_file_map[bp_other_so_name]

            for _file in other_so_files:
                s.add(_file)

        # Eventually add a debug package for other shared objects.
        other_so_dbg_files = set()

        for _file in other_so_files:
            dbg_link = so_tools.get_gnu_debug_link(
                    fops.simplify_path_static(spv.install_location + '/' + _file))

            if dbg_link:
                link, crc32 = dbg_link

                link_path = fops.simplify_path_static(os.path.dirname(_file) + '/' + link)
                link_full_path = fops.simplify_path_static(spv.install_location + '/' + link_path)

                # Test if the external debug file exists and if its crc32 sum
                # matches.
                try:
                    with open(link_full_path, 'rb') as f:
                        crc32_file = zlib.crc32(f.read())

                    if crc32 == crc32_file:
                        other_so_dbg_files.add(link_path)
                        copied_files.add(link_path)

                    else:
                        out.write(Color.YELLOW +
                                "    Debug link `%s checksum mismatch: 0x%08x (link) != 0x%08x (file)." %
                                (link, crc32, crc32_file) + Color.NORMAL + '\n')

                except FileNotFoundError:
                    out.write(Color.YELLOW +
                            "    Debug link `%s' does not refer to a file." % link +
                            Color.NORMAL + '\n')


        if other_so_dbg_files:
            bp_other_so_dbg_name = spv.name + '-other_so-dbgsym'
            out.write("  Adding a debug package `%s' for other shared objects ...\n" %
                    bp_other_so_dbg_name)

            if bp_other_so_dbg_name not in package_file_map:
                package_file_map[bp_other_so_dbg_name] = set()

            s = package_file_map[bp_other_so_dbg_name]

            for _file in other_so_dbg_files:
                s.add(_file)


        # If required, create a development package that contains development
        # symlinks of shared libraries, static libraries, headers and other
        # build system related information.
        dev_files = set()

        # Add development symlinks
        for lib in shared_libraries:
            dev_symlinks = lib.get_dev_symlinks()
            dev_files |= dev_symlinks
            copied_files |= dev_symlinks

        # Add static libraries, headers and other build system related
        # information.
        remaining_files = installed_files - copied_files
        for _file in remaining_files:
            if \
                    _file.startswith('/usr/include/') or \
                    (
                        (_file.startswith('/usr/local/include/') or \
                        _file.startswith('/usr/lib/') or \
                        _file.startswith('/usr/local/lib/'))
                    and
                        (_file.endswith('.a') or \
                        _file.endswith('.so') or \
                        _file.endswith('.o') or \
                        _file.endswith('.dbg'))):
                dev_files.add(_file)
                copied_files.add(_file)

        if dev_files:
            bp_dev_name = spv.name + '-dev'
            out.write("\n  Adding a development package `%s' ...\n" % bp_dev_name)

            if bp_dev_name not in package_file_map:
                package_file_map[bp_dev_name] = set()

            s = package_file_map[bp_dev_name]

            for _file in dev_files:
                s.add(_file)


        # If required, create a doc package that contains the package's
        # documentation.
        doc_files = set()
        remaining_files = installed_files - copied_files

        for _file in remaining_files:
            if \
                    _file.startswith('/usr/share/man/') or \
                    _file.startswith('/usr/share/info/') or \
                    _file.startswith('/usr/share/doc/') or \
                    _file.startswith('/usr/local/share/man/') or \
                    _file.startswith('/usr/local/share/info/') or \
                    _file.startswith('/usr/local/share/doc/'):

                doc_files.add(_file)
                copied_files.add(_file)

        if doc_files:
            bp_doc_name = spv.name + '-doc'
            out.write("\n  Adding a documentation package `%s' ...\n" % bp_doc_name)

            if bp_doc_name not in package_file_map:
                package_file_map[bp_doc_name] = set()

            s = package_file_map[bp_doc_name]

            for _file in doc_files:
                s.add(_file)


        # Put all remaining .dbg files into a generic debug package
        remaining_files = installed_files - copied_files
        remaining_dbg_files = set()

        for _file in remaining_files:
            if _file.endswith('.dbg'):
                remaining_dbg_files.add(_file)
                copied_files.add(_file)

        if remaining_dbg_files:
            bp_generic_dbg_name = spv.name + '-dbgsym'
            out.write("\n  Adding a generic debug package `%s' ...\n" % bp_generic_dbg_name)

            if bp_generic_dbg_name not in package_file_map:
                package_file_map[bp_generic_dbg_name] = set()

            s = package_file_map[bp_generic_dbg_name]

            for _file in remaining_dbg_files:
                s.add(_file)


        # If files remain, put them into a generic package.
        remaining_files = installed_files - copied_files

        if remaining_files:
            bp_generic_name = spv.name
            out.write("\n  Adding a generic package `%s' ...\n" % bp_generic_name)

            if bp_generic_name not in package_file_map:
                package_file_map[bp_generic_name] = set()

            s = package_file_map[bp_generic_name]

            for _file in remaining_files:
                s.add(_file)
                copied_files.add(_file)


        # If directories remain, put them into a common package.
        remaining_directories = set()
        for _dir in installed_directories:
            have = False
            for _file in copied_files:
                if _file.startswith(_dir):
                    have = True
                    break

            if have:
                continue

            remaining_directories.add(_dir)

        if remaining_directories:
            bp_common_name = spv.name + '-common'
            out.write("\n  Adding a common package `%s' ...\n" % bp_common_name)

            if bp_common_name not in package_file_map:
                package_file_map[bp_common_name] = set()

            s = package_file_map[bp_common_name]

            for _file in remaining_directories:
                s.add(_file)


        # Create binary packages and copy files
        bps = []

        out.write("\nCreating Packages and copying files ...\n")
        for bp_name, bp_files in package_file_map.items():
            out.write("  %s (%d files)\n" % (bp_name, len(bp_files)))

            bp = spv.add_binary_package(bp_name, bp_version_number)
            bps.append(bp)

            # Copy files
            bp.ensure_scratch_space_base()

            dst_base = os.path.join(bp.scratch_space_base, 'destdir')
            fops.mkdir_p(dst_base)
            os.chmod(dst_base, 0o755)
            os.chown(dst_base, 0, 0)

            try:
                for _file in bp_files:
                    fops.copy_from_base(spv.install_location, _file, dst_base)

            except BaseException as e:
                out.write(str(e) + '\n')
                return False


        # Update the list of binary packages which are currently created from
        # the source package.
        spv.set_current_binary_packages([bp.name for bp in bps])

        return False
