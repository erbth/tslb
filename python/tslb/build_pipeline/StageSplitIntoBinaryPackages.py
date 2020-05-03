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

        success = True

        for b in bs:
            with lock_X(b.fs_root_lock):
                # Create destdir
                dst_base = os.path.join(b.fs_base, 'destdir')
                fops.mkdir_p(dst_base)
                os.chmod(dst_base, 0o755)
                os.chown(dst_base, 0, 0)


                # Copy files
                try:
                    fops.traverse_directory_tree (
                            spv.fs_install_location,
                            lambda x : fops.copy_from_base(spv.fs_install_location, x, dst_base))

                except BaseException as e:
                    success = False
                    out.write(str(e) + '\n')

            if not success:
                break

        return success
