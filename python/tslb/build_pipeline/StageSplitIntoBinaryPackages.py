from tslb.tclm import lock_S, lock_Splus, lock_X
from tslb.Architecture import architectures
from tslb.Console import Color
from tslb.filesystem import FileOperations as fops
from tslb import BinaryPackage as bp
import os
from tslb import parse_utils
from tslb import settings
import subprocess

class StageSplitIntoBinaryPackages(object):
    name = 'split_into_binary_packages'

    def flow_through(spv, out):
        """
        :param spv: The source package version to let flow through this segment
            of the pipeline.

        :type spv: SourcePackage.SourcePackageVersion

        :param out: The (wrapped) fd to send output that shall be recorded in
            the db to.  Typically all output would go there.

        :type out: Something like sys.stdout

        :returns: successful
        :rtype: bool
        """
        bpv = bp.generate_version_number()
        out.write(Color.MAGENTA + "BP version: %s" % bpv + Color.NORMAL + '\n')

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
                        out.write(Color.YELLOW + ' '.join(cmd) + Color.NORMAL + '\n')

                        ret = subprocess.run(cmd,
                                cwd=b.fs_base,
                                stdout=out.fileno(), stderr=out.fileno())

                        if ret.returncode != 0:
                            out.write(Color.RED + "Exit code: %s" % ret + Color.NORMAL)
                            success = False

                    except Exception as e:
                        success = False
                        out.write(str(e) + '\n')

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
                    out.write(str(e) + '\n')
                except:
                    success = False

            if not success:
                break

        return success
