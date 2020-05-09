from tslb.tclm import lock_S, lock_Splus, lock_X
from tslb.Console import Color
import multiprocessing
import os
from tslb import parse_utils
from tslb import settings
import subprocess

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

        # Check if we have a install to destdir command.
        if spv.has_attribute('install_to_destdir_command'):
            install_to_destdir_command = spv.get_attribute('install_to_destdir_command')
            install_to_destdir_command = parse_utils.split_quotes(install_to_destdir_command)

        else:
            out.write("No install-to-destdir command specified and failed to guess one.\n")
            return False


        # Add .5 to round up.
        max_parallel_threads = round(multiprocessing.cpu_count() * 1.2 + 0.5)

        if install_to_destdir_command:
            install_to_destdir_command = [
                    e.replace('$(MAX_PARALLEL_THREADS)', str(max_parallel_threads))\
                            .replace('$(DESTDIR)', os.path.join(spv.fs_install_location))
                    for e in install_to_destdir_command ]


        # Install the package.
        if install_to_destdir_command:

            try:
                out.write(Color.YELLOW + ' '.join(install_to_destdir_command) + Color.NORMAL + '\n')

                ret = subprocess.run(install_to_destdir_command,
                        cwd=os.path.join(spv.fs_build_location, spv.get_attribute('unpacked_source_directory')),
                        stdout=out.fileno(), stderr=out.fileno())

                if ret.returncode != 0:
                    success = False

            except Exception as e:
                success = False
                out.write(str(e) + '\n')
            except:
                success = False

        return success
