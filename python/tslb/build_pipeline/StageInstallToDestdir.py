import multiprocessing
import os
import subprocess
from tslb.Console import Color
from tslb.build_pipeline.utils import PreparedBuildCommand

class StageInstallToDestdir(object):
    name = 'install_to_destdir'

    def flow_through(spv, rootfs_mountpoint, out):
        """
        :param spv: The source package version to let flow through this segment
            of the pipeline.

        :type spv: SourcePackage.SourcePackageVersion

        :param str rootfs_mountpoint: The mountpoint at which the rootfs image
            that should be used for the build is mounted.

        :param out: The (wrapped) fd to send output that shall be recorded in
            the db to.  Typically all output would go there.

        :type out: Something like sys.stdout

        :returns: successful
        :rtype: bool
        """
        success = True

        chroot_build_location = '/tmp/tslb/scratch_space/build_location'
        chroot_install_location = '/tmp/tslb/scratch_space/install_location'

        # Check if we have a install to destdir command.
        if spv.has_attribute('install_to_destdir_command'):
            install_to_destdir_command = spv.get_attribute('install_to_destdir_command')

        else:
            out.write("No install-to-destdir command specified and failed to guess one.\n")
            return False


        # Add .5 to round up.
        max_parallel_threads = round(multiprocessing.cpu_count() * 1.2 + 0.5)

        if install_to_destdir_command:
            install_to_destdir_command = PreparedBuildCommand(
                install_to_destdir_command,
                {
                    'MAX_PARALLEL_THREADS': str(max_parallel_threads),
                    'MAX_LOAD': str(max_parallel_threads),
                    'DESTDIR': chroot_install_location
                },
                chroot=rootfs_mountpoint)


        # Install the package.
        spv.ensure_install_location()

        if install_to_destdir_command:

            try:
                out.write(Color.YELLOW + str(install_to_destdir_command) + Color.NORMAL + '\n')

                from tslb.package_builder import execute_in_chroot

                with install_to_destdir_command as cmd:
                    ret = execute_in_chroot(
                        rootfs_mountpoint,
                        subprocess.run,
                        cmd,
                        cwd=os.path.join(chroot_build_location, spv.get_attribute('unpacked_source_directory')),
                        stdout=out.fileno(),
                        stderr=out.fileno())

                if ret != 0:
                    success = False

            except Exception as e:
                success = False
                out.write(str(e) + '\n')

        return success
