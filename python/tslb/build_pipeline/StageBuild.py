import multiprocessing
import os
import subprocess
from tslb.Console import Color
from tslb.build_pipeline.utils import PreparedBuildCommand

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

        else:
            # Guess one.
            source_dir = os.path.join(spv.build_location, spv.get_attribute('unpacked_source_directory'))
            found = False

            for d in ['builddir', 'build']:
                if not found and os.path.exists(os.path.join(source_dir, d, 'build.ninja')):
                    build_command = "#!/bin/bash\nset -e\ncd %s\n" % d + \
                            "ninja -j $(MAX_PARALLEL_THREADS) -l $(MAX_LOAD)\n"
                    found = True

            if not found and os.path.exists(os.path.join(source_dir, 'build.ninja')):
                build_command = "ninja -j $(MAX_PARALLEL_THREADS) -l $(MAX_LOAD)"
                found = True

            if not found and os.path.exists(os.path.join(source_dir, 'Makefile')):
                build_command = "make -j $(MAX_PARALLEL_THREADS) -l $(MAX_LOAD)"
                found = True

            if not found and os.path.exists(os.path.join(source_dir, 'pyproject.toml')):
                build_command = "pip3 wheel -w dist --no-cache-dir --no-build-isolation --no-deps ."
                found = True

            if not found and os.path.exists(os.path.join(source_dir, 'setup.py')):
                build_command = "python3 setup.py build -j $(MAX_PARALLEL_THREADS_REDUCED)"
                found = True

            if not found:
                out.write("No build command specified and failed to guess one.\n")
                return False

            spv.set_attribute('build_command', build_command)
            out.write("Guessed build command to be `%s'\n" % build_command)


        # Add .5 to round up.
        max_parallel_threads = round(multiprocessing.cpu_count() * 1.2 + 0.5)

        # ~4 cores per build node - for packages the build system of which
        # cannot use system load.
        max_parallel_threads_reduced = 5

        if build_command:
            build_command = PreparedBuildCommand(
                build_command,
                {
                    'MAX_PARALLEL_THREADS': str(max_parallel_threads),
                    'MAX_PARALLEL_THREADS_REDUCED': str(max_parallel_threads_reduced),
                    'MAX_LOAD': str(max_parallel_threads),
                    'SOURCE_VERSION': str(spv.version_number),
                },
                chroot=rootfs_mountpoint)


        # Build the package.
        if build_command:
            success = False

            try:
                out.write(Color.YELLOW + str(build_command) + Color.NORMAL + '\n')

                # Avoid a cylic import
                from tslb.package_builder import execute_in_chroot

                with build_command as cmd:
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
