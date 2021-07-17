import multiprocessing
import os
import re
import subprocess
import traceback
from tslb import attribute_types as tslb_at
from tslb.Console import Color
from tslb.program_transformation import stripping


class StageStrip:
    name = 'strip'

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
        chroot_install_location = '/tmp/tslb/scratch_space/install_location'

        _skip_paths = spv.get_attribute_or_default('strip_skip_paths', [])
        tslb_at.ensure_strip_skip_paths(_skip_paths)
        skip_paths = []

        for p in _skip_paths:
            p = '^' + re.escape(chroot_install_location) + p.lstrip('^')
            skip_paths.append(re.compile(p))

        # Enter a chroot environment and strip debug information from files.
        success = True

        def strip_function():
            try:
                stripping.strip_and_create_debug_links_in_root(
                        chroot_install_location,
                        out=out,
                        parallel=6,
                        skip_paths=skip_paths)

            except BaseException as e:
                out.write(Color.RED + "Error: " + Color.NORMAL + str(e) + '\n')
                traceback.print_exc(file=out)
                return 1

            return 0

        try:
            from tslb.package_builder import execute_in_chroot

            ret = execute_in_chroot(rootfs_mountpoint, strip_function)

            if ret != 0:
                success = False

        except BaseException as e:
            success = False
            out.write(str(e) + '\n')

        return success
