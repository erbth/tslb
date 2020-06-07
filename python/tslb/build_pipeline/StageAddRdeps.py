import os
import re
import stat
import tslb.database as db
import tslb.database.BinaryPackage
from tslb.Console import Color
from tslb.Constraint import DependencyList, VersionConstraint, CONSTRAINT_TYPE_NONE
from tslb.filesystem.FileOperations import simplify_path_static
from tslb.program_analysis import shared_library_tools as sotools
from tslb.build_pipeline.common_functions import update_binary_package_files

class StageAddRdeps(object):
    name = 'add_rdeps'

    def flow_through(spv, rootfs_mountpoint, out):
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

        for name in spv.list_current_binary_packages():
            version = max(spv.list_binary_package_version_numbers(name))
            bps[name] = spv.get_binary_package(name, version)
            rdeps[name] = DependencyList()


        # Update all binary packages' files
        out.write("Updating the binary packages' files ...\n")

        for bp in bps.values():
            update_binary_package_files(bp)


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

        # 'debug' packages depend on the corresponding 'other' packages.
        for name in cat_debug:
            other_name = re.match(r'^(.*)-dbgsym$', name).group(1)

            if other_name not in cat_other:
                out.write("No package `%s' in category 'other' for debug package `%s'." %
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
                            only_latest=True)

                    if not deps:
                        out.write("Did not find a binary package that contains shared object `%s'.\n" % so)
                        return False

                    if len(deps) > 1:
                        out.write("Found multiple binary packages that contain shared object `%s'.\n" % so)
                        return False

                    required_pkgs |= set(deps)

                # Add these binary packages as dependencies
                for name, version in required_pkgs:
                    if name == bp.name:
                        continue

                    out.write("  Adding `%s' -> `%s' >= `%s'\n" % (bp.name, name, version))
                    rdeps[bp.name].add_constraint(VersionConstraint('>=', version), name)


        # Add additional dependencies, which are specified in attributes.
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
                            "ignoring its dependencies" % bp_name +
                            Color.NORMAL + '\n')

                    continue

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


        # Set binary packages' `rdeps' attribute
        for bp_name in bps:
            bps[bp_name].set_attribute('rdeps', rdeps[bp_name])

        return True
