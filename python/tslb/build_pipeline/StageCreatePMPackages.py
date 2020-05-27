from tslb import Architecture
from tslb import settings
from tslb.filesystem import FileOperations as fops
from tslb.tclm import lock_S, lock_Splus, lock_X
from tslb import package_utils
from tslb.tpm import Tpm2_pack
import tslb.CommonExceptions as ces
import os
import shutil
import subprocess

class StageCreatePMPackages(object):
    name = 'create_pm_packages'

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

        tpm2_pack = Tpm2_pack()

        for n in spv.list_current_binary_packages():
            bv = max(spv.list_binary_package_version_numbers(n))
            b = spv.get_binary_package(n, bv)

            # Add files
            files = []

            def file_function(p):
                nonlocal files
                files.append((os.path.join('/', p), ''))

            fops.traverse_directory_tree(os.path.join(b.scratch_space_base, 'destdir'), file_function)

            b.set_files(files)


            # Create desc.xml
            with open(os.path.join(b.scratch_space_base, 'desc.xml'), 'w', encoding='utf8') as f:
                f.write(package_utils.desc_from_binary_package(b))

            # Pack
            from tslb.package_builder import execute_in_chroot

            def chroot_func(scratch_space_base, out):
                try:
                    tpm2_pack.pack(scratch_space_base)
                    return 0

                except ces.CommandFailed as e:
                    out.write(str(e))
                    return 1

            chroot_scratch_space_base = '/tmp/tslb/scratch_space/binary_packages/%s/%s' % (
                b.name, b.version_number)

            ret = execute_in_chroot(rootfs_mountpoint, chroot_func,
                                    chroot_scratch_space_base, out)

            if ret != 0:
                success = False
                break


            # Copy the package to the collecting repo
            transport_form = os.path.join(b.scratch_space_base,
                '%s-%s_%s.tpm2' % (b.name, b.version_number,
                    Architecture.to_str(b.architecture)))

            arch_dir = os.path.join(
                    settings.get_collecting_repo_location(),
                    Architecture.to_str(b.architecture))

            if not os.path.isdir(arch_dir):
                os.mkdir(archdir)
                os.chown(archdir, 0, 0)
                os.chmod(archdir, 0o755)

            shutil.copy(transport_form,
                os.path.join(arch_dir, ''))


        return success
