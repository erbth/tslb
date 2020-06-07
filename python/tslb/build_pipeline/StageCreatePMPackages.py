from tslb import Architecture
from tslb import settings
from tslb import package_utils
from tslb.tpm import Tpm2_pack
from tslb.build_pipeline.common_functions import update_binary_package_files
import tslb.CommonExceptions as ces
import os
import shutil

class StageCreatePMPackages(object):
    name = 'create_pm_packages'

    def flow_through(spv, rootfs_mountpoint, out):
        """
        :param spv: The source package version that flows though this segment
            of the pipeline.
        :type spv: SourcePackage.SourcePackageVersion
        :param str rootfs_mountpoint: The mountpoint at which the rootfs image
            that should be used for the build is mounted.
        :param out: The (wrapped) fd to which the stage should send output that
            shall be recorded in the db. Typically all output would go there.
        :type out: Something like sys.stdout
        :returns: successful
        :rtype: bool
        """
        success = True

        tpm2_pack = Tpm2_pack()

        for n in spv.list_current_binary_packages():
            bv = max(spv.list_binary_package_version_numbers(n))
            b = spv.get_binary_package(n, bv)


            # Update files
            out.write("Updating files of binary package `%s' ...\n" % b.name)
            update_binary_package_files(b)

            # Create desc.xml
            out.write("Packing ...\n")

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
            transport_form = '%s-%s_%s.tpm2' % (b.name, b.version_number,
                    Architecture.to_str(b.architecture))

            out.write("Copying transport form `%s' to the collecting repo ...\n" % transport_form)

            transport_form = os.path.join(b.scratch_space_base, transport_form)

            arch_dir = os.path.join(
                    settings.get_collecting_repo_location(),
                    Architecture.to_str(b.architecture))

            if not os.path.isdir(arch_dir):
                os.mkdir(archdir)
                os.chown(archdir, 0, 0)
                os.chmod(archdir, 0o755)

            shutil.copy(transport_form,
                os.path.join(arch_dir, ''))

            out.write("\n")


        return success
