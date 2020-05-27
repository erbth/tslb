import multiprocessing
import os
import subprocess
import traceback
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
        :param out: The (wrapped) fs to which the stage should send output that
            shall be recorded in the db. Typically all output would go there.
        :type out: Something like sys.stdout
        :returns: successful
        :rtype: bool
        """
        # Enter a chroot environment and strip debug information from files.
        success = True

        def strip_function():
            chroot_install_location = '/tmp/tslb/scratch_space/install_location'

            try:
                stripping.strip_and_create_debug_links_in_root(
                        chroot_install_location,
                        out)

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
