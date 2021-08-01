from tslb import maintainer_script_generator as msg
from tslb.Console import Color
from tslb.filesystem.FileOperations import simplify_path_static
import os
import re
import stat


class StageGenerateMaintainerScripts:
    name = 'generate_maintainer_scripts'

    _script_types = ['preinst', 'configure', 'unconfigure', 'postrm']

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
        # Run through analyzers (raise GeneralError in case of failure)
        try:
            SystemdGenerator.run(spv, rootfs_mountpoint, out)

        except GeneralError:
            return False

        # A map bp-name -> [(type, maintainer script)]
        bp_names = spv.list_current_binary_packages()
        bps = {n: spv.get_binary_package(n, max(spv.list_binary_package_version_numbers(n)))
                for n in bp_names}

        scripts = {n: [] for n in bp_names}

        # Read maintainer scripts from source package
        for attr in spv.list_attributes('maintainer_script_*'):
            try:
                bp_name = None
                script_id = None

                m = re.match(r"^maintainer_script_([^:]*)(:(.*))?$", attr)
                script_id = m[1]
                if m[2]:
                    bp_name = m[3]

                script, type_, bp_qual = cls._parse_maintainer_script(
                        script_id, spv.get_attribute(attr))

                if bp_qual is not None and bp_name is not None:
                    raise GeneralError("Binary package qualification in attribute name and script.")

                if bp_qual is None and bp_name is None:
                    raise GeneralError("No binary package qualification given.")


                # Find binary packages
                if bp_name:
                    if bp_name not in scripts:
                        out.write(Color.YELLOW + "WARNING: " + Color.NORMAL +
                                "Binary package `%s' does not exist.\n"
                                "    Referenced by source package attribute `%s'." % (bp_name, attr))
                        continue

                    scripts[bp_name].append((type_, script))
                    continue

                matched = False
                for bp in bp_names:
                    if re.fullmatch(bp_qual, bp):
                        matched = True
                        scripts[bp].append((type_, script))

                if not matched:
                    out.write(Color.YELLOW + "WARNING: " + Color.NORMAL +
                            "Regular expression %s did not match any binary package.\n"
                            "    Referenced by source package attribute `%s'." % (bp_qual, attr))


            except GeneralError as e:
                out.write(Color.RED + "ERROR: " + Color.NORMAL +
                        "source package attribute `%s': %s\n" % (attr, e))
                return False


        # Read maintainer scripts from each binary package
        for bpn in bp_names:
            bp = bps[bpn]

            for attr in bp.list_attributes('maintainer_script_*'):
                try:
                    script_id = re.sub('^maintainer_script_', '', attr)
                    script, type_, _ = cls._parse_maintainer_script(
                            script_id, bp.get_attribute(attr))

                    scripts[bpn].append((type_, script))

                except GeneralError as e:
                    out.write(Color.RED + "ERROR: " + Color.NORMAL +
                            "binary package attribute `%s'::`%s': %s\n" % (bpn, attr, e))
                    return False

            del bp


        # Sort maintainer scripts according to types.
        # A map (type, bp-name) -> [mainter script]
        sorted_scripts = {}
        for type_ in cls._script_types:
            for bpn in bp_names:
                if scripts[bpn]:
                    bp_sorted_scripts = [s for t,s in scripts[bpn] if t == type_]
                    if bp_sorted_scripts:
                        sorted_scripts[(type_, bpn)] = bp_sorted_scripts


        # Collate maintainer scripts for each binary package and write them to
        # new attribute.
        out.write("Collating maintainer scripts...\n")
        for k in sorted_scripts:
            type_, bpn = k
            bp = bps[bpn]

            generator = msg.MaintainerScriptGenerator(bp)
            for s in sorted_scripts[k]:
                try:
                    out.write("  `%s': %s-script `%s' with shebang `%s'.\n" %
                            (bpn, type_, s.script_id, s.shebang))

                    generator.add_script(s)
                except ValueError as e:
                    out.write(Color.RED + "ERROR: " + Color.NORMAL +
                            "Binary package `%s': Could not add maintainer script `%s': %s\n" %
                            (bpn, s.script_id, e))
                    return False

            try:
                collated = generator.collate_scripts()
                bp.set_attribute(cls._collated_name(type_), collated)

            except msg.CollateError as e:
                out.write(Color.RED + "ERROR: " + Color.NORMAL +
                        "Failed to collate %s-maintainer scripts of binary package `%s': %s\n" %
                        (type_, bpn, e))
                return False

            del generator
            del bp


        # Remove collated maintainer scripts that do not exist anymore.
        for bpn in bp_names:
            bp = bps[bpn]
            for type_ in cls._script_types:
                if (type_, bpn) not in sorted_scripts:
                    sid = cls._collated_name(type_)
                    if bp.has_attribute(sid):
                        bp.unset_attribute(sid)

            del bp

        out.write("\n")
        return True


    @staticmethod
    def _collated_name(type_):
        return "collated_%s_script" % type_


    @classmethod
    def _parse_maintainer_script(cls, script_id, text):
        """
        Parse the maintainer script text and extract the header.
        """
        type_ = None
        shebang = None
        before = []
        after = []
        bp_regex = None

        lines = text.split('\n')
        script_text = []

        is_first = True
        empty_lines_skipped = False
        header_complete = False

        num = -1
        for line in lines:
            num += 1

            # Handle shebang in first line
            if is_first:
                is_first = False

                if line.startswith('#!'):
                    shebang = line
                    script_text.append(line)
                    continue

            # Search for header
            line = line.strip()
            if not empty_lines_skipped and not line:
                continue

            empty_lines_skipped = True

            # Parse header
            if not line:
                header_complete = True
                break

            m = re.match(r"^([^\s:]+)\s*:\s*(\S+)$", line)
            if not m:
                raise GeneralError("Malformed header line: `%s'." % line)

            k = m[1]
            v = m[2]

            if k == 'type':
                if v not in cls._script_types:
                    raise GeneralError("Invalid maintainer script type `%s'." % v)
                if type_:
                    raise GeneralError("Multiple `type' attributes.")
                type_ = v

            elif k == 'before':
                before.append(v)

            elif k == 'after':
                after.append(v)

            elif k == 'binary_packages':
                if bp_regex is not None:
                    raise GeneralError("Multiple `binary_packages' attributes.")

                try:
                    bp_regex = re.compile(v)
                except re.error as e:
                    raise GeneralError("Invalid `binary_packages' regular expression: %s" % e)

            else:
                raise GeneralError("Invalid header attribute `%s'." % k)


        if not header_complete:
            raise GeneralError("Could not find trailing empty line that finishes the header.")

        if not type_:
            raise GeneralError("Essential header attribute `type' missing.")


        # Skip remaining empty lines
        while num < len(lines) and not lines[num].strip():
            num += 1

        script_text += lines[num:]
        if not shebang:
            shebang = lines[num]

        return (
                msg.MaintainerScript(
                    script_id,
                    before,
                    after,
                    shebang,
                    '\n'.join(script_text)
                ),
                type_,
                bp_regex
        )


class SystemdGenerator:
    @classmethod
    def run(cls, spv, rootfs_mountpoint, out):
        cfg = spv.get_attribute_or_default('maint_gen_systemd', None)
        if cfg is not None:
            if cfg == 'disable':
                print(Color.YELLOW +
                        "  Systemd maintainer script generator disabled for entire source package." +
                        Color.NORMAL, file=out)
                return

            else:
                print("  SystemdGenerator: " + Color.READ + "ERROR:" + Color.NORMAL +
                        "invalid configuration value `%s'." % cfg, file=out)
                raise GeneralError

        # Make sure the scratch space is mounted s.t. paths are accesible
        spv.ensure_install_location()

        # For each binary package
        for bp_name in spv.list_current_binary_packages():
            cls._run_for_bp(
                spv,
                spv.get_binary_package(bp_name, max(spv.list_binary_package_version_numbers(bp_name))),
                rootfs_mountpoint,
                out)


    @classmethod
    def _run_for_bp(cls, spv, bp, rootfs_mountpoint, out):
        # Find systemd services
        p = re.compile(r'(?:/lib|/usr/lib|/etc)/systemd/system/([^/]+\.service)')

        def handle_file(f):
            m = p.fullmatch(f)
            if not m:
                return

            service = m[1]
            script_prefix = "maintainer_script_mgs_" + service

            print("  `%s': Adding maintainer scripts for systemd service `%s'." %
                    (bp.name, service), file=out)

            # Add maintainer configure script
            bp.set_attribute(script_prefix + "_c",
"""#!/bin/bash -e
type: configure

if type systemctl >/dev/null 2>&1
then
    systemctl daemon-reload

    if [ -z "$1" ]
    then
        systemctl enable %(service)s
        systemctl start %(service)s

    elif [ "$1" == "change" ]
    then
        systemctl is-active %(service)s && systemctl restart %(service)s
    fi
fi

exit 0
""" %
                {'service': service})

            # Add unconfigure script
            bp.set_attribute(script_prefix + "_u",
"""#!/bin/bash -e
type: unconfigure

if type systemctl >/dev/null 2>&1
then
    if [ -z "$1" ]
    then
        systemctl disable %(service)s
        systemctl stop %(service)s
    fi
fi

exit 0
""" %
                {'service': service})


        # Examine all files
        def _work(f, rel_path):
            st_buf = os.lstat(f)

            if stat.S_ISDIR(st_buf.st_mode):
                for c in os.listdir(f):
                    _work(os.path.join(f, c), simplify_path_static(rel_path + '/' + c))

            elif stat.S_ISREG(st_buf.st_mode):
                handle_file(simplify_path_static(rel_path))

        _work(os.path.join(bp.scratch_space_base, 'destdir'), '/')


#**************************** local Exceptions ********************************
class GeneralError(Exception):
    pass
