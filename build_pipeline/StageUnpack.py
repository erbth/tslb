import os
import parse_utils
import settings
import subprocess
from tclm import lock_S, lock_Splus, lock_X

# We need a source location
if 'TSLB' not in settings:
    raise Exception('There is no section `TSLB\' in the tslb config file.')

source_location = settings['TSLB'].get('source_location')
if source_location == None:
    raise Exception('No source location configured in the tslb config file.')


class StageUnpack(object):
    name = 'unpack'

    def flow_through(spv):
        """
        :param spv: The source package version to let flow through this segment
            of the pipeline.
        :type spv: SourcePackage.SourcePackageVersion
        :returns: tuple(successful, output)
        :rtype: tuple(bool, str)
        """
        output = ""

        # Look if the package has a source archive configured
        if spv.has_attribute('source_archive'):
            source_archive = spv.get_attribute('source_archive')
            source_archive_path = os.path.join(source_location, source_archive)

            if not os.path.exists(source_archive_path):
                return (False, 'Source archive `%s\' does not exist.' % source_archive)

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
                return (False, "No source archive found, tried [ %s ]." % ', '.join(tries))
            else:
                spv.set_attribute('source_archive', source_archive)
                output += ("Guessed source archive name: %s\n" % source_archive)


        # Look if we are given an unpack command, and if not, guess one.
        if spv.has_attribute('unpack_command'):
            unpack_command = spv.get_attribute('unpack_command')
            unpack_command = parse_utils.split_quotes(unpack_command)

        else:
            unpack_command = [ 'tar', '-xf', '$(SOURCE_ARCHIVE_PATH)' ]
            tmp = ' '.join(unpack_command)
            spv.set_attribute('unpack_command', tmp)
            output += ("Guessed unpack command to be `%s'\n" % tmp)

        unpack_command = [ c.replace('$(SOURCE_ARCHIVE_PATH)', source_archive_path) for c in unpack_command ]


        # Unpack the package.
        success = False

        with lock_X(spv.fs_build_location_lock):
            try:
                p = subprocess.Popen(unpack_command, cwd=spv.fs_build_location,
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

            # Check for the expected unpacked directory
            if spv.has_attribute('unpacked_source_directory'):
                unpacked_source_directory = spv.get_attribute('unpacked_source_directory')
                usdp = os.path.join(spv.fs_build_location, unpacked_source_directory)

                if not os.path.exists(usdp):
                    output += "The unpacked source directory `%s' does not exist after unpacking." %\
                        unpacked_source_directory

                    success = False

            else:
                dirs = os.listdir(spv.fs_build_location)
                l = len(dirs)

                if l == 0:
                    spv.set_attribute('unpacked_source_directory', None)
                    output += "Set unpacked_source_directory to None.\n"

                elif l > 1:
                    spv.set_attribute('unpacked_source_directory', '.')
                    output += "Set unpacked_source_directory to `.'.\n"

                else:
                    spv.set_attribute('unpacked_source_directory', dirs[0])
                    output += "Set unpacked_source_directory to `%s'.\n" % dirs[0]

        return (success, output)
