from tslb import parse_utils
from tslb import program_transformation as progtrans
from tslb import timezone
from tslb.Console import Color
from tslb.build_pipeline.utils import PreparedBuildCommand
import math
import multiprocessing
import os
import subprocess
import tslb.program_transformation.python


class StageAdapt:
    name = 'adapt'

    @staticmethod
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
        chroot_source_dir = None
        if spv.has_attribute('unpacked_source_directory'):
            chroot_source_dir = os.path.join(
                '/tmp/tslb/scratch_space/build_location',
                spv.get_attribute('unpacked_source_directory'))

        chroot_install_location = '/tmp/tslb/scratch_space/install_location'
        max_parallel_threads = math.ceil(multiprocessing.cpu_count() * 1.2)

        # If this source package version has an adapt command, run it.
        if spv.has_attribute('adapt_command'):
            # Prepare the adapt command
            adapt_command = PreparedBuildCommand(
                spv.get_attribute('adapt_command'),
                {
                    'MAX_PARALLEL_THREADS': str(max_parallel_threads),
                    'MAX_LOAD': str(max_parallel_threads),
                    'SOURCE_DIR': str(chroot_source_dir),
                    'SOURCE_VERSION': str(spv.version_number),
                    'INSTALL_LOCATION': chroot_install_location,
                    'ISO_DATETIME': timezone.localtime(timezone.now()).isoformat()
                },
                chroot=rootfs_mountpoint)

            try:
                out.write(Color.YELLOW + str(adapt_command) + Color.NORMAL + '\n')

                from tslb.package_builder import execute_in_chroot

                with adapt_command as cmd:
                    ret = execute_in_chroot(
                        rootfs_mountpoint,
                        subprocess.run,
                        cmd,
                        cwd=chroot_install_location,
                        stdout=out.fileno(),
                        stderr=out.fileno())

                    if ret != 0:
                        return False

            except BaseException as e:
                out.write(str(e) + '\n')
                return False


        # Perform other transformations
        # Compile python code; 4 cores / node -> max. concurrent workers = 6
        if not parse_utils.is_yes(
                spv.get_attribute_or_default('disable_python_compileall', None)):

            out.write(Color.YELLOW + "Compiling python code if the package has such..." + Color.NORMAL + "\n")
            if not progtrans.python.compile_base_in_chroot(
                    rootfs_mountpoint,
                    chroot_install_location,
                    out=out,
                    concurrent_workers=6):
                return False

        return True
