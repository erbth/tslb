from tslb import CommonExceptions as ces
from tslb import attribute_types
from tslb import parse_utils
from tslb import rootfs
from tslb.Console import Color
from tslb.Constraint import DependencyList, VersionConstraint, CONSTRAINT_TYPE_NONE
from tslb.SourcePackage import SourcePackage
from tslb.VersionNumber import VersionNumber
from tslb.build_pipeline.common_functions import update_binary_package_files
from tslb.filesystem.FileOperations import simplify_path_static
from tslb.program_analysis import dependencies
from tslb.program_analysis import shared_library_tools as sotools
import copy
import os
import re
import stat
import tslb.database as db
import tslb.database.BinaryPackage


class StageAddRdeps:
    name = 'add_rdeps'

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
        # Retrieve all binary packages of that build
        bps = {}
        rdeps = {}
        rpredeps = {}

        for name in spv.list_current_binary_packages():
            version = max(spv.list_binary_package_version_numbers(name))
            bps[name] = spv.get_binary_package(name, version)
            rdeps[name] = DependencyList()
            rpredeps[name] = DependencyList()


        # Update all binary packages' files
        out.write("Updating the binary packages' files ...\n")

        for bp in bps.values():
            update_binary_package_files(bp)


        # If requested, skip this stage by adding dymm.
        skip_rdeps = False

        if spv.has_attribute("skip_rdeps"):
            val = spv.get_attribute("skip_rdeps")

            if (isinstance(val, bool) and val) or \
                    (isinstance(val, str) and parse_utils.is_yes(val)):

                out.write(Color.YELLOW +
                        "WARNING: Not adding rdeps (except for -all) because of attribute `skip_rdeps'!" +
                        Color.NORMAL + '\n')

                skip_rdeps = True


        # Sort the binary packages into categories
        out.write("Adding runtime dependencies based on package categories ...\n")

        cat_all = set()
        cat_debug = set()
        cat_dev = set()
        cat_doc = set()
        cat_common = set()
        cat_other = set()

        for name in bps:
            if name.endswith('-all'):
                cat_all.add(name)
            elif name.endswith('-dbgsym'):
                cat_debug.add(name)
            elif name.endswith('-dev'):
                cat_dev.add(name)
            elif name.endswith('-doc'):
                cat_doc.add(name)
            elif name.endswith('-common'):
                cat_common.add(name)
            else:
                cat_other.add(name)


        # Add dependencies based on the category a package is in
        # 'all' packages depend on all other packages.
        for name in cat_all:
            for dep_name in bps:
                if dep_name == name:
                    continue

                rdeps[name].add_constraint(
                        VersionConstraint('=', bps[dep_name].version_number),
                        dep_name)

        # Skip remaining rdeps if requested
        if skip_rdeps:
            for name, bp in bps.items():
                if name in cat_all:
                    bp.set_attribute('rdeps', rdeps[name])
                else:
                    bp.set_attribute('rdeps', DependencyList())

            return True

        # 'debug' packages depend on the corresponding packages.
        for name in cat_debug:
            other_name = re.match(r'^(.*)-dbgsym$', name).group(1)

            if other_name not in bps:
                out.write("No package `%s' in for debug package `%s'.\n" %
                        (other_name, name))
                return False

            rdeps[name].add_constraint(
                    VersionConstraint('=', bps[other_name].version_number),
                    other_name)

        # 'dev' packages depend on all 'other' and 'common' packages.
        for name in cat_dev:
            for dep_name in cat_other | cat_common:
                rdeps[name].add_constraint(
                        VersionConstraint('=', bps[dep_name].version_number),
                        dep_name)

        # 'doc' packages depend on 'common' packages.
        for name in cat_doc:
            for dep_name in cat_common:
                rdeps[name].add_constraint(
                        VersionConstraint('=', bps[dep_name].version_number),
                        dep_name)

        # 'other' packages depend on 'common' packages.
        for name in cat_other:
            for dep_name in cat_common:
                rdeps[name].add_constraint(
                        VersionConstraint('=', bps[dep_name].version_number),
                        dep_name)


        # Add shared library dependencies
        out.write("Adding runtime dependencies based on required shared objects ...\n")

        with db.session_scope() as session:
            for bp in bps.values():
                required_sos = set()
                base = os.path.join(bp.scratch_space_base, 'destdir')

                def process(path):
                    nonlocal required_sos

                    st_buf = os.lstat(path)

                    if stat.S_ISDIR(st_buf.st_mode):
                        for elem in os.listdir(path):
                            process(path + '/' + elem)

                    elif stat.S_ISREG(st_buf.st_mode):
                        required_sos |= sotools.determine_required_shared_objects(path)

                process(base)

                # Find packages that contain the required files
                required_pkgs = set()

                for so in required_sos:
                    # NOTE: Directly calling the low-level DB operation
                    # effectively bypasses all locking. However it would be
                    # difficult to lock "all binary packages that could provide
                    # this file" without not locking all binary packages in
                    # S-mode, therefore blocking the entire build system.
                    # However writes to the database are isolated on
                    # transaction level, so this should not yield undefined
                    # dependencies but simply the right ones or none per binary
                    # package on which this binary package depends.
                    #
                    # `deps' is of type list(tuple(name, version))
                    deps = db.BinaryPackage.find_binary_packages_with_file(
                            session,
                            bp.architecture,
                            so if so.startswith('/') else '/' + so,
                            so.startswith('/'),
                            only_newest=True)

                    if not deps:
                        out.write("Did not find a binary package that contains shared object `%s'.\n" % so)
                        return False

                    if len(deps) > 1:
                        out.write("Found multiple binary packages that contain shared object `%s':\n%s\n" %
                                (so, deps))
                        return False

                    required_pkgs |= set(deps)

                # Add these binary packages as dependencies
                for name, version in required_pkgs:
                    if name == bp.name:
                        continue

                    out.write("  Adding `%s' -> `%s' >= `%s'\n" % (bp.name, name, version))
                    rdeps[bp.name].add_constraint(VersionConstraint('>=', version), name)


        # Adding dependencies for perl packages
        if not cls._add_perl_dependencies(bps, rdeps, out):
            return False


        # Invoke dependency analyzers
        with db.session_scope() as db_session:
            # A function to add dependencies returned by analyzers
            def _add_dep(dep, bp_name, rdeps, report_not_found=True):
                """
                :param dep: The dependencies.Dependency to add
                :param bp_name: The binary package's name to which the
                    dependency shall be added
                :param rdeps: The dependency-map to which the dependency
                    shall be added.
                """
                if isinstance(dep, dependencies.Or):
                    i_max = len(dep.formulas) - 1
                    for i,f in enumerate(dep.formulas):
                        if _add_dep(f, bp_name, rdeps, report_not_found= i==i_max):
                            return True

                    return False

                elif isinstance(dep, dependencies.FileDependency):
                    # NOTE: Directly calling the low-level DB operation
                    # effectively bypasses all locking. However it would be
                    # difficult to lock "all binary packages that could
                    # provide this file" without not locking all binary
                    # packages in S-mode, therefore blocking the entire
                    # build system. However writes to the database are
                    # isolated on transaction level, so this should not
                    # yield undefined dependencies but simply the right
                    # ones or none per binary package on which this binary
                    # package depends.
                    #
                    # `res' is of type list(tuple(name, version))
                    res = db.BinaryPackage.find_binary_packages_with_file(
                            db_session,
                            bp.architecture,
                            dep.filename if dep.filename.startswith('/') else '/' + dep.filename,
                            dep.filename.startswith('/'),
                            only_newest=True)

                    if not res:
                        if report_not_found:
                            out.write("  Did not find a binary package that contains file `%s'.\n" %
                                    dep.filename)
                        return False

                    if len(res) > 1:
                        raise dependencies.AnalyzerError(
                                "Found multiple binary packages that contain file `%s':\n%s\n" %
                                (dep.filename, res))

                    name, version = res[0]
                    bdep = dependencies.BinaryPackageDependency(
                        name,
                        [VersionConstraint('>=', version)])

                    return _add_dep(bdep, bp_name, rdeps)

                elif isinstance(dep, dependencies.BinaryPackageDependency):
                    # Don't add self loops
                    if bp_name == dep.bp_name:
                        return True

                    for c in dep.version_constraints:
                        out.write("  Adding `%s' -> `%s' %s\n" % (bp_name, dep.bp_name, c))
                        rdeps[bp_name].add_constraint(c, dep.bp_name)

                    return True

                else:
                    raise ces.SavedYourLife('Invalid dependencies.Dependency type.')


            # Actually run analyzers on all binary packages
            try:
                for analyzer in dependencies.ALL_ANALYZERS:
                    disabled = spv.get_attribute_or_default(
                            'disable_dependency_analyzer_%s_for' % analyzer.name, [])
                    attribute_types.ensure_disable_dependency_analyzer_for(disabled)
                    disabled = [re.compile(e) for e in disabled]

                    out.write("\nRunning dependency analyzer `%s'...\n" % analyzer.name)
                    for bp in bps.values():
                        # Skip dependency analyzers disabled for this binary package
                        skip = False
                        for r in disabled:
                            if r.fullmatch(bp.name):
                                out.write(Color.YELLOW + "  skipping disabled package `%s'..." %
                                        bp.name + Color.NORMAL + "\n")
                                skip = True
                                break

                        if skip:
                            continue

                        # Skip the -doc packages, which as they may contain
                        # examples which should be installable without
                        # requiring the runtime environment needed to run them.
                        if bp.name.endswith('-doc'):
                            continue

                        # Run analyzer
                        deps = analyzer.analyze_root(
                                os.path.join(bp.scratch_space_base, 'destdir'),
                                bp.architecture,
                                out)

                        for dep in deps:
                            _add_dep(dep, bp.name, rdeps)

            except dependencies.AnalyzerError as e:
                out.write(Color.RED + "ERROR: " + str(e) + "\n")
                return False


            # Invoke dependency analyzers on maintainer scripts
            # Add (pre-) dependencies for maintainer scripts
            def _add_maint(pre_deps):
                if pre_deps:
                    out.write("\nAdding pre-dependencies for maintainer scripts...\n")
                    scripts = ('collated_preinst_script', 'collated_postrm_script')
                else:
                    out.write("\nAdding dependencies for maintainer scripts...\n")
                    scripts = ('collated_configure_script', 'collated_unconfigure_script')

                for bp in bps.values():
                    for attr in scripts:
                        val = bp.get_attribute_or_default(attr, None)
                        if val:
                            print(Color.YELLOW + "%s::%s" % (bp.name, attr) +
                                    Color.NORMAL, file=out)

                            for analyzer in dependencies.ALL_ANALYZERS:
                                out.write("\nRunning dependency analyzer `%s'...\n" % analyzer.name)
                                deps = analyzer.analyze_buffer(
                                        val,
                                        bp.architecture,
                                        out)

                                for dep in deps:
                                    _add_dep(dep, bp.name, rpredeps if pre_deps else rdeps)

            try:
                _add_maint(False)
                _add_maint(True)

            except dependencies.AnalyzerError as e:
                out.write(Color.RED + "ERROR: " + str(e) + "\n")
                return False



        # Optionally generate dependencies between -dev packages
        if not cls._generate_dev_dependencies(spv, bps, rdeps, rootfs_mountpoint, out):
            return False


        # Remove dependencies specified in attribute
        if spv.has_attribute('remove_rdeps'):
            out.write("\nRemoving dependencies as specified in attribute:\n")

            remove_rdeps = spv.get_attribute('remove_rdeps')
            attribute_types.ensure_remove_rdeps(remove_rdeps)

            for bp_name, to_remove in remove_rdeps:
                if bp_name not in bps:
                    out.write(Color.MAGENTA +
                            "  Binary package `%s' is not built out of this source package, "
                            "ignoring its removed dependencies" % bp_name +
                            Color.NORMAL + '\n')

                    continue

                if isinstance(to_remove, str):
                    to_remove = [to_remove]

                to_remove = [re.compile(r) for r in to_remove]

                for dep, constraints in rdeps[bp_name].get_object_constraint_list():
                    if any(re.fullmatch(regex, dep) for regex in to_remove):
                        out.write("  `%s' -> `%s'\n" % (bp_name, dep))
                        rdeps[bp_name].remove_dependency(dep)


        # Add additional dependencies which are specified in attributes.
        if spv.has_attribute('additional_rdeps'):
            out.write("\nAdding additional constraints specified by attributes ...\n")

            additional_rdeps = spv.get_attribute('additional_rdeps')

            # Test the list's type
            if not isinstance(additional_rdeps, list):
                out.write("Attribute `additional_rdeps' is not of type list.\n")
                return False

            for t in additional_rdeps:
                if not isinstance(t, tuple) or len(t) != 2:
                    out.write("Attribute `additional_rdeps' is not a list of 2-tuples.\n")
                    return False

                k, v = t
                if not isinstance(k, str) or not isinstance(v, DependencyList) or \
                        any(not isinstance(o, str) for o in v.get_required()):

                    out.write("Attribute `additional_rdeps' has a pair that is "
                            "not of type (str, DependencyList with str objects).\n")

                    return False

            # Add additional rdeps
            for bp_name, dl in additional_rdeps:
                if bp_name not in bps:
                    out.write(Color.MAGENTA +
                            "  Binary package `%s' is not built out of this source package, "
                            "ignoring its additional dependencies" % bp_name +
                            Color.NORMAL + '\n')

                    return False

                # Substitute the currently installed- and currently built
                # version numbers of binary packages
                dl = cls._substitute_version_numbers(dl, spv, bps, rootfs_mountpoint, out)
                if dl is None:
                    return False

                for dep, constraints in dl.get_object_constraint_list():
                    # NOTE: Again, this bypasses locks.
                    versions = db.BinaryPackage.find_binary_packages(session, dep, bp.architecture)

                    if not versions:
                        out.write(Color.MAGENTA + "  WARNING: Binary package `%s', which is "
                        "specified as dependency, does not exist.\n           However the "
                        "build system adds the dependency anyway." % dep + Color.NORMAL + "\n")

                    elif not any((dep, v) in dl for v in versions):
                        out.write(Color.MAGENTA + "  WARNING: None of the existing versions of "
                                "binary package `%s' satisfies the specified constraints.\n"
                                "           However the build system adds the dependency anyway."
                                % dep + Color.NORMAL + "\n")

                    elif not (dep, max(versions)) in dl:
                        out.write(Color.MAGENTA + "  WARNING: The most recent version of "
                                "binary package `%s' does not satisfy the specified constraints.\n"
                                "           However the build system adds the dependency anyway."
                                % dep + Color.NORMAL + "\n")

                    for vc in constraints:
                        rdeps[bp_name].add_constraint(vc, dep)

                        value = ''
                        if vc.constraint_type != CONSTRAINT_TYPE_NONE:
                            value = ' ' + str(vc)

                        out.write("  `%s' -> `%s'%s\n" % (bp_name, dep, value))


        # Set binary packages' `rdeps' and `rpredeps' attributes
        for bp_name in bps:
            bps[bp_name].set_attribute('rdeps', rdeps[bp_name])
            bps[bp_name].set_attribute('rpredeps', rpredeps[bp_name])

        out.write("\n")
        return True


    @staticmethod
    def _substitute_version_numbers(orig_dl, spv, bps, rootfs_mountpoint, out):
        """
        :returns: A DependencyList or None in case of failure.
        """
        # Don't modify the original dl ...
        new_dl = DependencyList()

        for dep, constraints in orig_dl.get_object_constraint_list():
            subs_required = False
            for c in constraints:
                if c.version_number == VersionNumber('current'):
                    # Find version installed in rootfs image
                    img = rootfs.Image(rootfs.get_image_id_from_mountpoint(rootfs_mountpoint))
                    res = img.query_packages(name=dep, arch=spv.architecture)

                    if len(res) == 1:
                        _,_,v = res[0]
                        out.write(("  Substituting version number `%s' "
                            "for `current' in additional rdep `%s'." % (v, dep)) + '\n')

                    else:
                        v = VersionNumber(c.version_number)
                        out.write(Color.MAGENTA + ("  WARNING: Additional rdep `%s' requested "
                            "the currently installed version but is not installed." % dep) +
                            Color.NORMAL + "\n")

                    del img

                    new_dl.add_constraint(
                        VersionConstraint(c.constraint_type, v),
                        dep)

                elif c.version_number == VersionNumber('built'):
                    # Find currently built version
                    bp = bps.get(dep, None)
                    if bp is None:
                        v = VersionNumber(c.version_number)
                        out.write(Color.MAGENTA + ("  WARNING: Additional rdep `%s' requested "
                            "the currently built version but is not built." % dep) +
                            Color.NORMAL + "\n")

                    else:
                        v = bp.version_number
                        out.write(("  Substituting version number `%s' for `built' in "
                            "additional rdep `%s'." % (v, dep)) + '\n')

                    del bp

                    new_dl.add_constraint(
                        VersionConstraint(c.constraint_type, v),
                        dep)

                else:
                    new_dl.add_constraint(copy.deepcopy(c), dep)

        return new_dl


    def _add_perl_dependencies(bps, rdeps, out):
        # Perl-packages depend on perl
        perl_packages = []

        for bp in bps.values():
            # Skip -dbgsym packages
            if bp.name.endswith('-dbgsym'):
                continue

            for file_,sha512 in bp.get_files():
                if file_.startswith('/usr/lib/perl') or file_.startswith('/usr/local/lib/perl'):

                    perl_packages.append(bp)
                    break

        if not perl_packages:
            return True

        out.write("\nAdding runtime dependency on perl for perl-packages ...\n")

        # Find perl
        with db.session_scope() as session:
            paths = ['/bin/perl', '/usr/bin/perl']

            # `perl' is of type List(Tuple(name, version))
            perl = None
            for path in paths:
                perl = db.BinaryPackage.find_binary_packages_with_file(
                        session,
                        bp.architecture,
                        path,
                        True,
                        only_newest=True)

                if perl:
                    break

            if not perl:
                out.write(Color.RED + "  ERROR: Could not find the binary package "
                    "containing perl." + Color.NORMAL + "\n")
                return False

            perl = perl[0]

            for bp in perl_packages:
                # Don't add self loops ...
                if bp.name == perl[0] or bp.name == perl[0] + '-common':
                    continue

                out.write("  Adding `%s' -> `%s' >= `%s'\n" % (bp.name, perl[0], perl[1]))
                rdeps[bp.name].add_constraint(VersionConstraint('>=', perl[1]), perl[0])

        return True


    def _generate_dev_dependencies(spv, bps, rdeps, rootfs_mountpoint, out):
        """
        Optionally generate dependencies between -dev packages if enabled.

        :returns bool: True on success, False on error
        """
        mode = spv.get_attribute_or_default('dev_dependencies', None)
        if not mode:
            return True

        if mode != 'cdeps_headers':
            print(Color.RED + "Invalid value for 'dev_dependencies': `%s'." % mode +
                    Color.NORMAL, file=out)
            return False

        print(Color.YELLOW + "\nAdding dependencies between -dev packages using mode '%s'..." % mode +
                Color.NORMAL, file=out)

        # Find the -dev package(s)
        dev_pkgs = []
        for n in bps:
            if n.endswith('-dev'):
                dev_pkgs.append(n)

        if not dev_pkgs:
            return True

        # To find installed packages
        img = rootfs.Image(rootfs.get_image_id_from_mountpoint(rootfs_mountpoint))

        # Examine cdeps
        cdeps = spv.get_attribute('cdeps')
        deps_to_add = set()

        patterns = [re.compile(p) for p in [
            '/usr/(local/)?include/.*\.h'
        ]]

        for cdep in cdeps.get_required():
            # Find the binary packages of the cdep
            cdep_sp = SourcePackage(cdep, spv.architecture)
            cdep_spv = None

            for v in reversed(sorted(cdep_sp.list_version_numbers())):
                if (cdep, v) in cdeps:
                    cdep_spv = cdep_sp.get_version(v)
                    break

            if not cdep_spv:
                print(Color.RED + "Could not find a suitable source package version for cdep on `%s'." %
                        cdep + Color.NORMAL, file=out)
                return False

            cdep_bp_names = cdep_spv.list_current_binary_packages()

            # Add a dependency on -dev packages of the cdep if they contain
            # header files in well known locations.
            for n in cdep_bp_names:
                if not n.endswith('-dev'):
                    continue

                # Find installed version
                res = img.query_packages(name=n, arch=spv.architecture)
                if len(res) != 1:
                    print(Color.RED + ("Binary package `%s' not installed exactly one time "
                            "in the image (%d times).") % (n, len(res)) + Color.NORMAL, file=out)
                    return False

                # Check if it is the latest version
                _,_,v = res[0]
                if v != max(cdep_spv.list_binary_package_version_numbers(n)):
                    print(Color.RED + ("The installed binary package version `%s:%s' is "
                            "not the latest built version of the corresponding source "
                            "package.") % (n, v) + Color.NORMAL, file=out)

                # Examine files of the binary package
                cdep_bp = cdep_spv.get_binary_package(n, v)

                for p,_ in cdep_bp.get_files():
                    for pattern in patterns:
                        if pattern.fullmatch(p):
                            deps_to_add.add((n, v))
                            break

                del cdep_bp

            del cdep_spv
            del cdep_sp


        # Finally add dependencies
        for bpn in dev_pkgs:
            for n, v in deps_to_add:
                print("  `%s' -> `%s' >= %s" % (bpn, n, v))
                rdeps[bpn].add_constraint(VersionConstraint('>=', v), n)

        return True
