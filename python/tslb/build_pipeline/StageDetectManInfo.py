import multiprocessing
import os
import subprocess
from tslb.Console import Color
import tslb.filesystem.FileOperations as fops


MAN_DIRS = ['/usr/share/man', '/usr/local/share/man']
MAN_SECTION_DIRS = ['man%d' % s for s in range(1, 9)]
TEXINFO_DIRS = ['/usr/share/info', '/usr/local/share/info']

MAN_TRIGGER_ATTR = 'activated_triggers_mandb'
MAN_CONFIGURE_SCRIPT_ATTR = 'maintainer_script_configure_mandb'
TEXINFO_TRIGGER_ATTR = 'activated_triggers_texinfo'

MAN_TRIGGER = 'update-mandb'
TEXINFO_TRIGGER = 'update-texinfo'

class StageDetectManInfo(object):
    name = 'detect_man_info'

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
        bps = []

        for name in spv.list_current_binary_packages():
            version = max(spv.list_binary_package_version_numbers(name))
            bps.append(spv.get_binary_package(name, version))

        for bp in bps:
            # Handle texinfo documentation
            have_info = False

            for info_dir in TEXINFO_DIRS:
                full_path = fops.simplify_path_static(
                        bp.scratch_space_base + '/destdir/' + info_dir)

                dir_file = os.path.join(full_path, 'dir')

                if os.path.isfile(dir_file):
                    os.unlink(dir_file)

                if os.path.isdir(full_path):
                    if os.listdir(full_path):
                        have_info = True
                    else:
                        os.rmdir(full_path)

            if have_info:
                print("Adding texinfo update trigger for `%s'." % bp.name, file=out)
                bp.set_attribute(TEXINFO_TRIGGER_ATTR, [TEXINFO_TRIGGER])
            elif bp.has_attribute(TEXINFO_TRIGGER_ATTR):
                bp.unset_attribute(TEXINFO_TRIGGER_ATTR)

            # Add db update trigger for man pages
            if not cls._handle_man_pages(bp, out):
                return False

        return True


    @staticmethod
    def _handle_man_pages(bp, out):
        # Find man pages
        have_mans = False
        all_mans = {}

        for base in MAN_DIRS:
            for section in MAN_SECTION_DIRS:
                path = fops.simplify_path_static(base + "/" + section)
                full_path = fops.simplify_path_static(
                        bp.scratch_space_base + "/destdir/" + path)

                if os.path.isdir(full_path):
                    mans = sorted(os.listdir(full_path))
                    if mans:
                        have_mans = True
                        all_mans[path] = mans


        # Add activated trigger and a configure script to touch all man pages
        # after installation s.t. mandb will add them to the database (because
        # their timestamp is newer than the one of the database).
        if have_mans:
            print("Adding man-db update trigger for `%s'." % bp.name, file=out)
            bp.set_attribute(MAN_TRIGGER_ATTR, [MAN_TRIGGER])

            script = "#!/bin/bash -e\ntype: configure\n\n"
            script += "# Automatically added by the tslb\n"

            for sec in sorted(all_mans.keys()):
                script += 'cd "%s"\n' % sec
                script += 'touch "%s"\n' % sec

                for man in all_mans[sec]:
                    script += 'touch "%s"\n' % man

            script += "exit 0\n"

            bp.set_attribute(MAN_CONFIGURE_SCRIPT_ATTR, script)

        else:
            for attr in [MAN_TRIGGER_ATTR, MAN_CONFIGURE_SCRIPT_ATTR]:
                if bp.has_attribute(attr):
                    bp.unset_attribute(attr)

        return True
