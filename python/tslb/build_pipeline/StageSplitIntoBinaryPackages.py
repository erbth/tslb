import itertools
import os
import re
import stat
import subprocess
import zlib
from tslb import BinaryPackage as bpkg
from tslb import attribute_types
from tslb.Console import Color
from tslb.filesystem import FileOperations as fops
from tslb.program_analysis import shared_library_tools as so_tools

LDCONFIG_TRIGGER_ATTR = "activated_triggers_auto_ldconfig"

class StageSplitIntoBinaryPackages:
    name = 'split_into_binary_packages'

    @classmethod
    def flow_through(cls, spv, rootfs_mountpoint, out):
        """
        :param spv: The source package version that flows though this segment
            of the pipeline.
        :type spv: SourcePackage.SourcePackageVersion
        :param str rootfs_mountpoint: The mountpoint at which the rootfs image
            that should be used for the build is mounted.
        :param out: The (wrapped) fd to which the stage should send output that
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
        out.write("\nAssigning files to binary packages...\n")
        package_file_map = {}

        # First, process packaging hints
        pkg_hints = spv.get_attribute_or_default('packaging_hints', [])
        attribute_types.ensure_packaging_hints(pkg_hints)

        available_files = installed_files | installed_directories
        for bp_name, patterns in pkg_hints:
            if isinstance(patterns, str):
                patterns = [patterns]

            patterns = [re.compile(p) for p in patterns]

            # Match files and directories
            assigned_files = set()
            for f in available_files:
                # Skip .dbg files
                if f.endswith('.dbg'):
                    continue

                for p in patterns:
                    if p.fullmatch(f):
                        # Assign file
                        if bp_name not in package_file_map:
                            out.write("  Adding binary package `%s' from hints...\n" % bp_name)
                            package_file_map[bp_name] = set()

                        package_file_map[bp_name].add(f)
                        copied_files.add(f)
                        assigned_files.add(f)

            available_files -= assigned_files


        # Then create binary packages for each library, or move the library to
        # the package that holds already some of its files.
        shared_libraries = spv.get_shared_libraries()

        for lib in shared_libraries:
            files = lib.get_files() - lib.get_dev_symlinks()

            # If any of the non-development files have been moved already, move
            # the entire library there (that is all files that have not been
            # moved yet)
            bp_name = None
            for file_ in files:
                if file_ in copied_files:
                    for p, fs in package_file_map.items():
                        if file_ in fs:
                            bp_name = p
                            break

                if bp_name:
                    break

            # Create a binary package if required. Note that no empty binary
            # package will be created because then all files have been moved
            # and bp_name is not empty.
            if not bp_name:
                bp_name = lib.name
                if lib.abi_version_number:
                    bp_name += str(lib.abi_version_number)

                out.write("  Adding binary package `%s' for shared library ...\n" % bp_name)

                if bp_name not in package_file_map:
                    package_file_map[bp_name] = set()

            # Assign files
            for file_ in files:
                if file_ in copied_files:
                    continue

                package_file_map[bp_name].add(file_)
                copied_files.add(file_)


        # Create debug packages for the packages that have been created so far.
        if not cls._create_debug_packages(
                spv, package_file_map, copied_files, out):
            return False


        # If shared objects are left after packaging shared libraries, move
        # them to an extra package (except python modules).
        other_so_files = set()

        remaining_files = installed_files - copied_files
        for lib in shared_libraries:
            remaining_files -= lib.get_dev_symlinks()

        for _file in remaining_files:
            if re.match(r'/usr(/local)?/lib/python', _file):
                continue

            # Don't assign linker scripts as these are development files.
            if _file.endswith('.so'):
                with open(fops.simplify_path_static(spv.install_location + '/' + _file), 'rb') as f:
                    if f.read(4) == b'\x7fELF':
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
            # Skip .so-files from python packages
            if re.match(r'/usr(/local)?/lib/python', _file):
                continue

            if \
                    _file.startswith('/usr/include/') or \
                    _file.startswith('/usr/local/include/') or \
                    (
                        (_file.startswith('/usr/lib/') or \
                        _file.startswith('/usr/local/lib/'))
                    and
                        (_file.endswith('.a') or \
                        _file.endswith('.so') or \
                        _file.endswith('.o') or \
                        _file.endswith('.la') or \
                        # _file.endswith('.dbg') or \
                        _file.endswith('.pc'))
                    ) or \
                    _file.startswith('/usr/share/pkgconfig') or \
                    _file.startswith('/usr/local/share/pkgconfig') or \
                    _file.startswith('/usr/share/aclocal') or \
                    _file.startswith('/usr/share/automake') or \
                    _file.startswith('/usr/lib/cmake/') or \
                    _file.startswith('/usr/share/cmake/'):

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


        # Put remaining files under /etc into a common package.
        remaining_files = installed_files - copied_files
        files_for_common = []
        for file_ in remaining_files:
            if file_.startswith('/etc/'):
                files_for_common.append(file_)
                copied_files.add(file_)

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


        # If directories remain, put them into the common package, too.
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

        if remaining_directories or files_for_common:
            bp_common_name = spv.name + '-common'
            out.write("\n  Adding a common package `%s' ...\n" % bp_common_name)

            if bp_common_name not in package_file_map:
                package_file_map[bp_common_name] = set()

            s = package_file_map[bp_common_name]

            for _file in remaining_directories:
                s.add(_file)

            for file_ in files_for_common:
                s.add(file_)


        # Now there are many small binary packages. Some of them might form a
        # native package in a programming language, such as perl- or python
        # packages. Merge these together.
        out.write("\nLooking for higher level packages from programming languages etc. ...\n")
        cls._merge_perl_packages(spv, package_file_map, out)
        out.write("\n")


        # Apply additional file assignments specified as attributes
        if spv.has_attribute('additional_file_placement'):
            out.write("\nProcessing additional file placement rules ...\n")
            additional_file_placement = spv.get_attribute('additional_file_placement')

            if not isinstance(additional_file_placement, list):
                out.write("Attribute `additional_file_placement' is not of type list.\n")
                return False

            # Build reverse package-file map to remove files from current
            # placement.
            file_package_map = {}
            for bp_name, bp_files in package_file_map.items():
                for _file in bp_files:
                    file_package_map[_file] = bp_name

            # Apply additional placement patterns.
            assigned_files = set()
            for bp_name, bp_patterns in additional_file_placement:
                if isinstance(bp_patterns, str):
                    patterns = [bp_patterns]
                elif isinstance(bp_patterns, list) or isinstance(bp_patterns, tuple):
                    patterns = bp_patterns
                else:
                    out.write("Attribute `additional_file_placement[%s]' is neither list, tuple nor str.\n" %
                            bp_name)

                    return False

                try:
                    patterns = [re.compile(p) for p in patterns]
                except re.error as e:
                    out.write("Attribute `additional_file_placement[%s]': Invalid regex: %s.\n" %
                            (bp_name, e))
                    return False

                # Create a binary package with the requested name if it does
                # not exist yet.
                if bp_name not in package_file_map:
                    out.write("  Adding additional binary package `%s' ...\n" % bp_name)
                    package_file_map[bp_name] = set()

                s = package_file_map[bp_name]

                # Find matching files
                files = set()

                installed_items = installed_files | installed_directories

                for pattern in patterns:
                    for _file in installed_items - assigned_files:
                        m = re.fullmatch(pattern, _file)
                        if m:
                            files.add(_file)

                # Reassign files and directories
                for _file in files:
                    # Directories may not be contained in the file_package_map
                    # if they are not packaged explicitely.
                    if _file in file_package_map:
                        package_file_map[file_package_map[_file]].remove(_file)

                    package_file_map[bp_name].add(_file)
                    file_package_map[_file] = bp_name
                    assigned_files.add(_file)


        # Remove empty packages
        bp_names = list(package_file_map.keys())
        for name in bp_names:
            if not package_file_map[name]:
                out.write("  Removing empty binary package `%s'.\n" % name)
                del package_file_map[name]


        # Add an empty package that can be used to install all binary packages
        # built out of this source package
        out.write("\n  Adding an empty '-all' package ...\n")

        for bp_name in package_file_map.keys():
            if bp_name.endswith('-all'):
                out.write("An '-all' package exists already\n")
                return False

        bp_all_name = spv.name + '-all'
        package_file_map[bp_all_name] = set()


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
                # NOTE: Do not modify the files in the destination before the
                # last file was copied, because some might be hard links which
                # have not been copied yet and therefore the effect caused by
                # the changed other links is less obvious if the other links
                # are not there yet.
                for _file in bp_files:
                    fops.copy_from_base(spv.install_location, _file, dst_base)

            except BaseException as e:
                out.write(str(e) + '\n')
                return False


        # Update the list of binary packages which are currently created from
        # the source package.
        spv.set_current_binary_packages([bp.name for bp in bps])


        # Copy lists of package manager triggers specified in the source
        # package version to the binary packages.
        if not cls._collect_package_manager_triggers(spv, bps, out):
            return False


        # Add ldconfig triggers based on shared libraries in packages
        if not cls._add_ldconfig_triggers(spv, bps, package_file_map, out):
            return False

        return True


    @staticmethod
    def _merge_perl_packages(spv, package_file_map, out):
        # Look for `.packlist'-files
        packlist_regex = re.compile(r'^/usr/.*lib/perl\d+/[^/]+/.+/\.packlist$')

        perl_packages = {}
        for pkg in package_file_map:
            packlist_paths = []

            for file_ in package_file_map[pkg]:
                if re.match(packlist_regex, file_):
                    packlist_paths.append(file_)

            if packlist_paths:
                perl_packages[pkg] = packlist_paths

        if not perl_packages:
            return

        print("  Found perl packages in the following binary packages:", file=out)
        for pkg, packlists in perl_packages.items():
            print("    %s: %s" % (pkg, packlists), file=out)

        # Find binary packages that have files part of other perl-packages
        file_package_map = {}
        for bp_name, bp_files in package_file_map.items():
            for file_ in bp_files:
                file_package_map[file_] = bp_name

        perl_package_for_package = {}
        for pkg, packlists in perl_packages.items():
            files = []
            for pl in packlists:
                full_path = fops.simplify_path_static(spv.install_location + '/' + pl)
                with open(full_path, 'r', encoding='utf8') as f:
                    for l in f:
                        files.append(l.strip().replace(
                            '/tmp/tslb/scratch_space/install_location', '')
                            .split(' ')[0])

            for file_ in files:
                associated_pkg = file_package_map.get(file_)
                if not associated_pkg:
                    out.write(Color.ORANGE + "  File `%s' in .packlist but in no binary package." %
                            file_ + Color.NORMAL + "\n")

                    continue

                # Don't merge packages into themselves
                if associated_pkg == pkg:
                    continue

                # Don't merge the -doc package
                if associated_pkg == spv.name + '-doc':
                    continue

                perl_package_for_package[associated_pkg] = pkg

        del file_package_map

        # Move all files from those binary packages to the perl-package,
        # effectively merging them into the perl-package (they will be removed
        # later because they are empty).
        print(file=out)

        generic_dbg_pkg = spv.name + '-dbgsym'
        for pkg, perl_pkg in perl_package_for_package.items():
            print("    Merging `%s' into `%s'." % (pkg, perl_pkg), file=out)
            package_file_map[perl_pkg] |= package_file_map[pkg]
            package_file_map[pkg].clear()

            # If there is a -dbgsym packages for the merged package, merge it
            # with the generic -dbgsym package

            dbg_pkg = pkg + "-dbgsym"
            if dbg_pkg in package_file_map:
                print("    Merging `%s' into `%s'." % (dbg_pkg, generic_dbg_pkg), file=out)
                if generic_dbg_pkg not in package_file_map:
                    package_file_map[generic_dbg_pkg] = set()

                package_file_map[generic_dbg_pkg] |= package_file_map[dbg_pkg]
                package_file_map[dbg_pkg].clear()


    @classmethod
    def _create_debug_packages(cls, spv, package_file_map, copied_files, out):
        """
        Create debug packages based on elf-file placement.
        """
        # Go through all packages and find debug symbol files that belong to
        # the packages. If files are found, move them to a corresponding
        # -dbgsym package.
        # The existing packages will not be changed or only the currently
        # examined package will be changed (if it is a -dbgsym package).
        bp_names = list(package_file_map.keys())
        for bp_name in bp_names:
            files = package_file_map[bp_name]

            debug_links = set()

            for file_ in files:
                full_path = fops.simplify_path_static(spv.install_location + "/" + file_)

                # Only considert regular files (and not e.g. shared libraries'
                # symlinks).
                st_buf = os.lstat(full_path)
                if not stat.S_ISREG(st_buf.st_mode):
                    continue

                # Read GNU debug link
                dbg_link = so_tools.get_gnu_debug_link(full_path)
                if not dbg_link:
                    continue

                link, crc32 = dbg_link
                link_path = fops.simplify_path_static(os.path.dirname(file_) + "/" + link)
                link_full_path = fops.simplify_path_static(spv.install_location + "/" + link_path)

                # Test if the external debug file exists and if its crc32 sum
                # matches.
                try:
                    with open(link_full_path, 'rb') as f:
                        crc32_file = zlib.crc32(f.read())

                    if crc32 == crc32_file:
                        # Only consider files that have not been assigned to packages
                        # yet.
                        if link_path not in copied_files:
                            debug_links.add(link_path)

                    else:
                        out.write(Color.YELLOW +
                                "    Debug link `%s checksum mismatch: 0x%08x (link) != 0x%08x (file)." %
                                (link, crc32, crc32_file) + Color.NORMAL + '\n')

                except FileNotFoundError:
                    out.write(Color.YELLOW +
                            "    Debug link `%s' does not refer to a file." % link +
                            Color.NORMAL + '\n')

            if debug_links:
                # Create -dbgsym package (unless this is a -dbgsym package) and
                # move files
                if bp_name.endswith('-dbgsym'):
                    dbg_bp_name = bp_name
                else:
                    dbg_bp_name = bp_name + '-dbgsym'

                if dbg_bp_name not in package_file_map:
                    out.write("  Adding a debug package `%s' ...\n" % dbg_bp_name)
                    package_file_map[dbg_bp_name] = set()

                for file_ in debug_links:
                    package_file_map[dbg_bp_name].add(file_)
                    copied_files.add(file_)

        return True


    @staticmethod
    def _collect_package_manager_triggers(spv, bps, out):
        out.write("\nCopying package manager trigger lists ...\n")

        for trg_type in ('activated', 'interested'):
            # Enumerate attributes
            unqualified = trg_type + '_triggers'
            attrs = []
            if spv.has_attribute(unqualified):
                attrs.append(unqualified)

            attrs += spv.list_attributes(unqualified + "_*")

            # Read trigger lists and verify their types
            trg_lists = []

            for attr in attrs:
                try:
                    trg_list = spv.get_attribute(attr)
                    attribute_types.ensure_package_manager_trigger_list_sp(trg_list)
                    trg_lists.append((attr, trg_list))

                except attribute_types.InvalidAttributeType as e:
                    out.write(Color.RED + "ERROR" + Color.NORMAL + ": %s: %s\n" % (attr, e))
                    return False

            # Copy lists to matching binary packages
            attrs_set = { bp.name: set() for bp in bps }
            for t in trg_lists:
                sp_attr, l = t
                bp_attr = sp_attr.replace(unqualified, unqualified + '_from_sp')

                for bp in bps:
                    collated_trg_list = []

                    for bpl in l:
                        if re.fullmatch(bpl[0], bp.name):
                            collated_trg_list += bpl[1] if isinstance(bpl[1], list) else [bpl[1]]

                    if collated_trg_list:
                        out.write("  %s -> %s:%s\n" % (sp_attr, bp.name, bp_attr))
                        collated_trg_list.sort()
                        bp.set_attribute(bp_attr, collated_trg_list)
                        attrs_set[bp.name].add(bp_attr)

            # Remove _from_sp attributes that do not exist anymore.
            # Note that this is currently never called as
            # split_into_binary_packages always creates a new bp version.
            for bp in bps:
                for attr in bp.list_attributes(unqualified + "_from_sp"):
                    if attr not in attrs_set[bp.name]:
                        bp.unset_attribute(attr)

        return True


    @classmethod
    def _add_ldconfig_triggers(cls, spv, bps, package_file_map, out):
        out.write("\nAdding ldconfig-triggers for packages with shared libraries ...\n")

        file_package_map = { f: bp_name for bp_name, fs in package_file_map.items() for f in fs }
        libs = spv.get_shared_libraries()
        lib_files = [f for l in libs for f in l.get_files()]

        for bp in bps:
            has_shared_libraries = False
            for f in lib_files:
                if file_package_map.get(f) == bp.name:
                    has_shared_libraries = True
                    break

            if has_shared_libraries:
                print("  %s" % bp.name, file=out)
                bp.set_attribute(LDCONFIG_TRIGGER_ATTR, ["ldconfig"])

            else:
                if bp.has_attribute(LDCONFIG_TRIGGER_ATTR):
                    bp.unset(LDCONFIG_TRIGGER_ATTR)

        return True
