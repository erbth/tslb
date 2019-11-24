from tclm import lock_S, lock_Splus, lock_X
from Console import Color
import multiprocessing
import os
import parse_utils
import settings
import subprocess

class StageInstallToDestdir(object):
    name = 'install_to_destdir'

    def flow_through(spv):
        """
        :param spv: The source package version to let flow through this segment
            of the pipeline.
        :type spv: SourcePackage.SourcePackageVersion
        :returns: tuple(successful, output)
        :rtype: tuple(bool, str)
        """
        output = ''
        success = True

        with lock_X(spv.fs_root_lock):
            # Check if we have a install to destdir command.
            if spv.has_attribute('install_to_destdir_command'):
                install_to_destdir_command = spv.get_attribute('install_to_destdir_command')
                install_to_destdir_command = parse_utils.split_quotes(install_to_destdir_command)

            else:
                output += "No install-to-destdir command specified and failed to guess one.\n"
                return (False, output)


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
                    output += Color.YELLOW + ' '.join(install_to_destdir_command) + Color.NORMAL + '\n'
                    p = subprocess.Popen(install_to_destdir_command,
                            cwd=os.path.join(spv.fs_build_location, spv.get_attribute('unpacked_source_directory')),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

                    o, e = p.communicate()
                    ret = p.returncode

                    output += o.decode() + e.decode()

                    if ret != 0:
                        success = False

                except Exception as e:
                    success = False
                    output += str(e) + '\n'
                except:
                    success = False

        return (success, output)
