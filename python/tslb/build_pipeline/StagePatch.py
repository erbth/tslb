import multiprocessing
import os
import subprocess
from tslb.Console import Color
from tslb.build_pipeline.utils import PreparedBuildCommand


class StagePatch(object):
    name = 'patch'

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
        # If this source package version has no patch command, simply do
        # nothing.
        if not spv.has_attribute('patch_command'):
            return True

        chroot_source_dir = os.path.join(
            '/tmp/tslb/scratch_space/build_location',
            spv.get_attribute('unpacked_source_directory'))

        max_parallel_threads = round(multiprocessing.cpu_count() * 1.2 + 0.5)

        # Prepare the patch command
        patch_command = PreparedBuildCommand(
            spv.get_attribute('patch_command'),
            {
                'MAX_PARALLEL_THREADS': str(max_parallel_threads),
                'MAX_LOAD': str(max_parallel_threads)
            },
            chroot=rootfs_mountpoint)

        try:
            out.write(Color.YELLOW + str(patch_command) + Color.NORMAL + '\n')

            from tslb.package_builder import execute_in_chroot

            with patch_command as cmd:
                ret = execute_in_chroot(
                    rootfs_mountpoint,
                    subprocess.run,
                    cmd,
                    cwd=chroot_source_dir,
                    stdout=out.fileno(),
                    stderr=out.fileno())

                if ret != 0:
                    return False

        except BaseException as e:
            out.write(str(e) + '\n')
            return False

        return True
