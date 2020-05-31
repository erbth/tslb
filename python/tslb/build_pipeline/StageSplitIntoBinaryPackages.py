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

    def flow_through(spv, rootfs_mountpoint, out):
        """
        :param spv: The source package version that flows though this segment
            of the pipeline.
        :type spv: SourcePackage.SourcePackageVersion
        :param str rootfs_mountpoint: The mountpoint at which the rootfs image
            that should be used for the build is mounted.
        :param out: The (wrapped) fs to which the stage should send output that
            shall be recorded in the db. Typically all output would go there.
        :type out: Something like sys.stdout
        :returns: successful
        :rtype: bool
        """
        bpv = bp.generate_version_number()
        out.write(Color.MAGENTA + "Binary packages' version: %s" % bpv + Color.NORMAL + '\n')


        # First, generate two binary packages for each library: One with the
        # library itself, and the other one with its debugging symbols.

        return False




        # For now, generate one binary package only.
        b = spv.add_binary_package(spv.source_package.name, bpv)
        bs = [b]

        # Set the binary packages to be built
        spv.set_current_binary_packages([spv.source_package.name])

        success = True

        for b in bs:
            # Create destdir
            b.ensure_scratch_space_base()

            dst_base = os.path.join(b.scratch_space_base, 'destdir')
            fops.mkdir_p(dst_base)
            os.chmod(dst_base, 0o755)
            os.chown(dst_base, 0, 0)


            # Copy files
            try:
                fops.traverse_directory_tree (
                        spv.install_location,
                        lambda x : fops.copy_from_base(spv.install_location, x, dst_base))

            except BaseException as e:
                success = False
                out.write(str(e) + '\n')

            if not success:
                break

        return success
