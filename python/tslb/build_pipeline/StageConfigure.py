import multiprocessing
import os
import subprocess
from tslb.Console import Color
from tslb import settings
from tslb.build_pipeline.utils import PreparedBuildCommand

class StageConfigure(object):
    name = 'configure'

    def flow_through(spv, rootfs_mountpoint, out):
        """
        :param spv: The source package version to let flow through this segment
            of the pipeline.

        :type spv: SourcePackage.SourcePackageVersion

        :param str rootfs_mountpoint: The mountpoint at which the rootfs image
            that should be used for the build is mounted.

        :param str rootfs_mountpoint: The mountpoint at which the rootfs image
            that should be used for the build is mounted.

        :param out: The (wrapped) fd to send output that shall be recorded in
            the db to.  Typically all output would go there.

        :type out: Something like sys.stdout

        :returns: successful
        :rtype: bool
        """
        # Check if we have a configure command.
        if spv.has_attribute('configure_command'):
            configure_command = spv.get_attribute('configure_command')

        else:
            # Guess one.
            src_dir = os.path.join(spv.build_location, spv.get_attribute('unpacked_source_directory'))
            if os.path.exists(os.path.join(src_dir, 'CMakeLists.txt')):
                configure_command = "cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_INSTALL_LIBDIR=lib ."

            elif os.path.exists(os.path.join(src_dir, 'configure')):
                configure_command = "./configure --prefix=/usr --sysconfdir=/etc"

            elif os.path.exists(os.path.join(src_dir, 'meson.build')):
                configure_command = "meson setup build . --prefix=/usr --sysconfdir=/etc"

            elif os.path.exists(os.path.join(src_dir, 'pyproject.toml')):
                # Python packages do not have an extra configure-step
                configure_command = None

            elif os.path.exists(os.path.join(src_dir, 'setup.py')):
                # Python packages do not have an extra configure-step
                configure_command = None

            else:
                out.write("No configure command specified and failed to guess one.\n")
                return False

            spv.set_attribute('configure_command', configure_command)
            out.write("Guessed configure command to be `%s'\n" % configure_command)


        # Configure the package.
        if configure_command:
            # Prepare the configure command
            configure_command = PreparedBuildCommand(
                configure_command,
                {
                    'MAX_PARALLEL_THREADS': str(round(multiprocessing.cpu_count() * 1.2 + 0.5)),
                    'MAX_LOAD': str(round(multiprocessing.cpu_count() * 1.2 + 0.5)),
                    'SOURCE_VERSION': str(spv.version_number),
                },
                chroot=rootfs_mountpoint)
        

            # Run the configure command / script
            success = False

            try:
                out.write(Color.YELLOW + str(configure_command) + Color.NORMAL + '\n')

                from tslb.package_builder import execute_in_chroot

                with configure_command as cmd:
                    ret = execute_in_chroot(
                        rootfs_mountpoint,
                        subprocess.run,
                        cmd,
                        cwd=os.path.join('/tmp/tslb/scratch_space/build_location',
                            spv.get_attribute('unpacked_source_directory')),
                        stdout=out.fileno(),
                        stderr=out.fileno())

                if ret == 0:
                    success = True

            except Exception as e:
                success = False
                out.write(str(e) + '\n')
            except:
                success = False

            return success

        else:
            return True
