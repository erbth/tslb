from tslb.tclm import lock_S, lock_Splus, lock_X
from tslb.Console import Color
import os
from tslb import parse_utils
from tslb import settings
import subprocess

class StageConfigure(object):
    name = 'configure'

    def flow_through(spv):
        """
        :param spv: The source package version to let flow through this segment
            of the pipeline.
        :type spv: SourcePackage.SourcePackageVersion
        :returns: tuple(successful, output)
        :rtype: tuple(bool, str)
        """
        output = ''

        with lock_X(spv.fs_build_location_lock):
            # Check if we have a configure command.
            if spv.has_attribute('configure_command'):
                configure_command = spv.get_attribute('configure_command')
                configure_command = parse_utils.split_quotes(configure_command)

            else:
                # Guess one.
                if os.path.exists(os.path.join(spv.fs_build_location,
                    spv.get_attribute('unpacked_source_directory'), 'CMakeLists.txt')):

                    configure_command = [ 'cmake', '-DCMAKE_BUILD_TYPE=Debug',
                        '-DCMAKE_INSTALL_PREFIX=/usr' ]

                elif os.path.exists(os.path.join(spv.fs_build_location,
                    spv.get_attribute('unpacked_source_directory'), 'configure')):

                    configure_command = [ 'configure', '-prefix=/usr' ]

                else:
                    output += "No configure command specified and failed to guess one.\n"
                    return (False, output)

                tmp = ' '.join(configure_command)
                spv.set_attribute('configure_command', tmp)
                output += ("Guessed configure command to be `%s'\n" % tmp)


            # Configure the package.
            if configure_command:
                success = False

                try:
                    output += Color.YELLOW + ' '.join(build_command) + Color.NORMAL + '\n'
                    p = subprocess.Popen(configure_command,
                            cwd=os.path.join(spv.fs_build_location, spv.get_attribute('unpacked_source_directory')),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

                    o, e = p.communicate()
                    ret = p.returncode

                    output += o.decode() + e.decode()

                    if ret == 0:
                        success = True

                except Exception as e:
                    success = False
                    output += str(e) + '\n'
                except:
                    success = False

                return (success, output)

            else:
                return (True, output)
