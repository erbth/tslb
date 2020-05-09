from tslb.tclm import lock_S, lock_Splus, lock_X
from tslb.Console import Color
import os
from tslb import parse_utils
from tslb import settings
import subprocess

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
            configure_command = parse_utils.split_quotes(configure_command)

        else:
            # Guess one.
            if os.path.exists(os.path.join(spv.build_location,
                spv.get_attribute('unpacked_source_directory'), 'CMakeLists.txt')):

                configure_command = [ 'cmake', '-DCMAKE_BUILD_TYPE=Release',
                    '-DCMAKE_INSTALL_PREFIX=/usr' ]

            elif os.path.exists(os.path.join(spv.build_location,
                spv.get_attribute('unpacked_source_directory'), 'configure')):

                configure_command = [ 'configure', '-prefix=/usr' ]

            else:
                out.write("No configure command specified and failed to guess one.\n")
                return False

            tmp = ' '.join(configure_command)
            spv.set_attribute('configure_command', tmp)
            out.write("Guessed configure command to be `%s'\n" % tmp)


        # Configure the package.
        if configure_command:
            success = False
            raise Exception

            try:
                out.write(Color.YELLOW + ' '.join(configure_command) + Color.NORMAL + '\n')

                ret = subprocess.run(configure_command,
                        cwd=os.path.join(spv.fs_build_location, spv.get_attribute('unpacked_source_directory')),
                        stdout=out.fileno(), stderr=out.fileno())

                if ret.returncode == 0:
                    success = True

            except Exception as e:
                success = False
                out.write(str(e) + '\n')
            except:
                success = False

            return success

        else:
            return True
