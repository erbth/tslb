from tslb.tclm import lock_S, lock_Splus, lock_X
from tslb.Console import Color
import multiprocessing
import os
from tslb import parse_utils
from tslb import settings
import subprocess

class StageBuild(object):
    name = 'build'

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
            # Check if we have a build command.
            if spv.has_attribute('build_command'):
                build_command = spv.get_attribute('build_command')
                build_command = parse_utils.split_quotes(build_command)

            else:
                # Guess one.
                if os.path.exists(os.path.join(spv.fs_build_location,
                    spv.get_attribute('unpacked_source_directory'), 'Makefile')):

                    build_command = [ 'make', '-j', '-l', '$(MAX_PARALLEL_THREADS)' ]

                else:
                    output += "No build command specified and failed to guess one.\n"
                    return (False, output)

                tmp = ' '.join(build_command)
                spv.set_attribute('build_command', tmp)
                output += ("Guessed build command to be `%s'\n" % tmp)


            # Add .5 to round up.
            max_parallel_threads = round(multiprocessing.cpu_count() * 1.2 + 0.5)

            if build_command:
                build_command = [
                        e.replace('$(MAX_PARALLEL_THREADS)', str(max_parallel_threads))
                        for e in build_command ]


            # Build the package.
            if build_command:
                success = False

                try:
                    output += Color.YELLOW + ' '.join(build_command) + Color.NORMAL + '\n'
                    p = subprocess.Popen(build_command,
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
