import multiprocessing
import os
import subprocess
from tslb.Console import Color


class StageDetectManInfo(object):
    name = 'detect_man_info'

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
        bps = []

        for name in spv.list_current_binary_packages():
            version = max(spv.list_binary_package_version_numbers(name))
            bps.append(spv.get_binary_package(name, version))

        for bp in bps:
            _dir = os.path.join(bp.scratch_space_base, 'destdir/usr/share/info')
            _dir_file = os.path.join(_dir, 'dir')

            local_dir = os.path.join(bp.scratch_space_base, 'destdir/usr/local/share/info')
            local_dir_file = os.path.join(local_dir, 'dir')

            if os.path.isfile(_dir_file):
                os.unlink(_dir_file)

                if not os.listdir(_dir):
                    os.rmdir(_dir)

            if os.path.isfile(local_dir_file):
                os.unlink(local_dir_file)

                if not os.listdir(local_dir):
                    os.rmdir(local_dir)

        return True
