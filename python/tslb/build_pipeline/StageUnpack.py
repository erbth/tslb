import os
from tslb import parse_utils
from tslb import settings
import subprocess


class StageUnpack(object):
    name = 'unpack'

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
        source_location = settings.get_source_location()

        # Look if the package has a source archive configured
        if spv.has_attribute('source_archive'):
            source_archive = spv.get_attribute('source_archive')
            source_archive_path = os.path.join(source_location, source_archive)

            if not os.path.exists(source_archive_path):
                out.write('Source archive `%s\' does not exist.' % source_archive)
                return False

        else:
            # If not, guess a few
            found = False

            tries = [
                    "%s-%s.tar.xz" % (spv.source_package.name, spv.version_number),
                    "%s-%s.tar.bz2" % (spv.source_package.name, spv.version_number),
                    "%s-%s.tar.gz" % (spv.source_package.name, spv.version_number),
                    "%s-%s.tgz" % (spv.source_package.name, spv.version_number),
                    ]

            for source_archive in tries:
                source_archive_path = os.path.join(source_location, source_archive)
                if os.path.exists(source_archive_path):
                    found = True
                    break

            if not found:
                out.write("No source archive found, tried [ %s ]." % ', '.join(tries))
                return False
            else:
                spv.set_attribute('source_archive', source_archive)
                out.write("Guessed source archive name: %s\n" % source_archive)


        # Look if we are given an unpack command, and if not, guess one.
        if spv.has_attribute('unpack_command'):
            unpack_command = spv.get_attribute('unpack_command')
            unpack_command = parse_utils.split_quotes(unpack_command)

        else:
            unpack_command = ['tar', '-xf', '$(SOURCE_ARCHIVE_PATH)']
            tmp = ' '.join(unpack_command)
            spv.set_attribute('unpack_command', tmp)
            out.write("Guessed unpack command to be `%s'\n" % tmp)

        unpack_command = [c.replace('$(SOURCE_ARCHIVE_PATH)', source_archive_path) for c in unpack_command]


        # Unpack the package.
        try:
            spv.ensure_build_location()

            ret = subprocess.run(unpack_command, cwd=spv.build_location,
                    stdout=out.fileno(), stderr=out.fileno())

            if ret.returncode != 0:
                return False

        except BaseException as e:
            out.write(str(e) + '\n')
            return False


        # Check for the expected unpacked directory
        if spv.has_attribute('unpacked_source_directory'):
            unpacked_source_directory = spv.get_attribute('unpacked_source_directory')
            usdp = os.path.join(spv.build_location, unpacked_source_directory)

            if not os.path.exists(usdp):
                out.write("The unpacked source directory `%s' does not exist after unpacking.\n" %\
                    unpacked_source_directory)

                return False

        else:
            dirs = os.listdir(spv.build_location)
            l = len(dirs)

            if l == 0:
                spv.set_attribute('unpacked_source_directory', None)
                out.write("Set unpacked_source_directory to None.\n")

            elif l > 1:
                spv.set_attribute('unpacked_source_directory', '.')
                out.write("Set unpacked_source_directory to `.'.\n")

            else:
                spv.set_attribute('unpacked_source_directory', dirs[0])
                out.write("Set unpacked_source_directory to `%s'.\n" % dirs[0])

        return True
