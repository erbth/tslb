import multiprocessing
import os
import subprocess
from tslb.tclm import lock_S, lock_Splus, lock_X
from tslb.Console import Color
from tslb import parse_utils
from tslb import settings

class StageBuild(object):
    name = 'build'

    def flow_through(spv, rootfs_mountpoint, out):
        """
        :param spv: The source package version to let flow through this segment
            of the pipeline.

        :type spv: SourcePackage.SourcePackageVersion

        :param str rootfs_mountpoint: The mountpoint at which the rootfs image
            that should be used for the build is mounted.

        :param out: The (wrapped) fd to send output that shall be recorded in
            the db to. Typically all output would go there.

        :type out: Something like sys.stdout

        :returns: successful
        :rtype: bool
        """
        # Check if we have a build command.
        if spv.has_attribute('build_command'):
            build_command = spv.get_attribute('build_command')
            build_command = parse_utils.split_quotes(build_command)

        else:
            # Guess one.
            if os.path.exists(os.path.join(spv.build_location,
                spv.get_attribute('unpacked_source_directory'), 'Makefile')):

                build_command = [ 'make', '-j', '$(MAX_PARALLEL_THREADS)', '-l', '$(MAX_PARALLEL_THREADS)' ]

            else:
                out.write("No build command specified and failed to guess one.\n")
                return False

            tmp = ' '.join(build_command)
            spv.set_attribute('build_command', tmp)
            out.write("Guessed build command to be `%s'\n" % tmp)


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
                out.write(Color.YELLOW + ' '.join(build_command) + Color.NORMAL + '\n')

                # Avoid a cylic import
                from tslb.package_builder import execute_in_chroot

                ret = execute_in_chroot(
                    rootfs_mountpoint,
                    subprocess.call,
                    build_command,
                    cwd=os.path.join('/tmp/tslb/scratch_space/build_location', spv.get_attribute('unpacked_source_directory')),
                    stdout=out.fileno(),
                    stderr=out.fileno())

                if ret == 0:
                    success = True

            except Exception as e:
                success = False
                out.write(str(e) + '\n')
            except:
                success = False

            return False
            return success

        else:
            return True
