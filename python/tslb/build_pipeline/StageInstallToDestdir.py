from tslb.Console import Color
from tslb.build_pipeline.utils import PreparedBuildCommand
import multiprocessing
import os
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

        chroot_build_location = '/tmp/tslb/scratch_space/build_location'
        chroot_install_location = '/tmp/tslb/scratch_space/install_location'

        # Check if we have a install to destdir command. If not, try to guess
        # one.
        if not spv.has_attribute('install_to_destdir_command'):
            cmd = None

            source_dir = os.path.join(spv.build_location, spv.get_attribute('unpacked_source_directory'))
            # Does the package use ninja?
            if not cmd:
                for d in ['builddir', 'build']:
                    if not cmd and os.path.exists(os.path.join(source_dir, d, "build.ninja")):
                        cmd = "#!/bin/bash\nset -e\ncd %s\n" % d + \
                                "DESTDIR=$(DESTDIR) ninja -j $(MAX_PARALLEL_THREADS) -l $(MAX_LOAD) install\n"

            if not cmd and  os.path.exists(os.path.join(source_dir, "build.ninja")):
                cmd = "#!/bin/bash\nset -e\n" \
                        "DESTDIR=$(DESTDIR) ninja -j $(MAX_PARALLEL_THREADS) -l $(MAX_LOAD) install\n"

            # Is there a Makefile in the build location that looks like it
            # would respect the variable `DESTDIR'? Or was the Makefile
            # generated by cmake?
            if not cmd:
                makefile_supports_destdir = False
                makefile_path = os.path.join(source_dir, 'Makefile')

                if os.path.exists(makefile_path):
                    with open(makefile_path, 'r', encoding='utf8') as f:
                        first_line = True

                        for l in f:
                            if first_line:
                                if 'cmake generated file' in l.lower():
                                    makefile_supports_destdir = True
                                    break

                                first_line = False

                            if '$(DESTDIR)' in l or '${DESTDIR}' in l:
                                makefile_supports_destdir = True
                                break

                if makefile_supports_destdir:
                    cmd = "make -j $(MAX_PARALLEL_THREADS) -l $(MAX_LOAD) DESTDIR=$(DESTDIR) install"

            # Python packages that use pyproject.toml
            if not cmd:
                if os.path.exists(os.path.join(source_dir, 'pyproject.toml')):
                    cmd = "#!/bin/bash -e\nexec pip3 install --no-index --no-deps --prefix=/usr --root=$(DESTDIR) --no-compile --no-user --root-user-action=ignore dist/*.whl\n"

            # Python packages that use setuptools
            if not cmd:
                if os.path.exists(os.path.join(source_dir, 'setup.py')):
                    cmd = "python3 setup.py install --prefix=/usr --root $(DESTDIR)"

            if not cmd:
                out.write("No install-to-destdir command specified and failed to guess one.\n")
                return False

            spv.set_attribute('install_to_destdir_command', cmd)
            out.write("Guessed install-to-destdir command to be `%s'\n" % cmd)

        install_to_destdir_command = spv.get_attribute('install_to_destdir_command')


        # Add .5 to round up.
        max_parallel_threads = round(multiprocessing.cpu_count() * 1.2 + 0.5)

        if install_to_destdir_command:
            install_to_destdir_command = PreparedBuildCommand(
                install_to_destdir_command,
                {
                    'MAX_PARALLEL_THREADS': str(max_parallel_threads),
                    'MAX_LOAD': str(max_parallel_threads),
                    'DESTDIR': chroot_install_location,
                    'SOURCE_DIR': os.path.join(chroot_build_location, spv.get_attribute('unpacked_source_directory')),
                    'SOURCE_VERSION': str(spv.version_number),
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
