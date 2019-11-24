from tclm import lock_S, lock_Splus, lock_X
from Architecture import architectures
from Console import Color
from filesystem import FileOperations as fops
import BinaryPackage as bp
import os
import parse_utils
import settings
import subprocess

class StageSplitIntoBinaryPackages(object):
    name = 'split_into_binary_packages'

    def flow_through(spv):
        """
        :param spv: The source package version to let flow through this segment
            of the pipeline.
        :type spv: SourcePackage.SourcePackageVersion
        :returns: tuple(successful, output)
        :rtype: tuple(bool, str)
        """
        output = ""

        bpv = bp.generate_version_number()
        output += Color.MAGENTA + "BP version: %s" % bpv + Color.NORMAL + '\n'

        # Set the binary packages to be built
        spv.set_current_binary_packages([spv.source_package.name])

        # For now, generate one binary package only.
        b = spv.add_binary_package(spv.source_package.name, bpv)
        bs = [b]

        # Initialize the TPM structures and copy files.
        success = True

        for b in bs:
            with lock_X(b.fs_root_lock):
                cmds = [
                        [ 'tpm', '--create-desc', 'sw' ],
                        [ 'tpm', '--set-name', b.name ],
                        [ 'tpm', '--set-arch', architectures[spv.architecture] ],
                        [ 'tpm', '--set-version', str(bpv) ]
                        ]

                for cmd in cmds:
                    try:
                        output += Color.YELLOW + ' '.join(cmd) + Color.NORMAL + '\n'
                        p = subprocess.Popen(cmd,
                                cwd=b.fs_base,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

                        o, e = p.communicate()
                        ret = p.returncode

                        output += o.decode() + e.decode()

                        if ret != 0:
                            output += Color.RED + "Exit code: %s" % ret + Color.NORMAL
                            success = False

                    except Exception as e:
                        success = False
                        output += str(e) + '\n'
                    except:
                        success = False

                    if not success:
                        break

                # Copy files
                try:
                    dst_base = os.path.join(b.fs_base, 'destdir')

                    fops.traverse_directory_tree (
                            spv.fs_install_location,
                            lambda x : fops.copy_from_base(spv.fs_install_location, x, dst_base))

                except Exception as e:
                    success = False
                    output += str(e) + '\n'
                except:
                    success = False

            if not success:
                break

        return (success, output)
