from tslb import Architecture
from tslb import package_utils
from tslb import settings
from tslb import tclm
from tslb.build_pipeline.common_functions import update_binary_package_files
from tslb.tpm import Tpm2_pack
from tslb.utils import LogTransformer
import concurrent.futures
import os
import shutil
import sys
import threading
import time
import tslb.CommonExceptions as ces

class StageCreatePMPackages:
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

        # Binary packages should not conflict with each other, hence packaging
        # them in parallel should not yield a deadlock.
        with concurrent.futures.ThreadPoolExecutor(4) as exe:
            tclm_p = tclm.get_local_p()
            console_lock = threading.Lock()

            def package(arg):
                pkg_index, n = arg

                with LogTransformer("%3d: %%(line)s" % pkg_index, out, console_lock) as tr_out:
                    # Use the same TCLM process in all threads.
                    tclm.set_local_p(tclm_p)

                    bv = max(spv.list_binary_package_version_numbers(n))
                    b = spv.get_binary_package(n, bv)


                    # Update files
                    tr_out.write("Updating files of binary package `%s' ...\n" % b.name)
                    update_binary_package_files(b)

                    # Create desc.xml
                    tr_out.write("Packing ...\n")

                    with open(os.path.join(b.scratch_space_base, 'desc.xml'), 'w', encoding='utf8') as f:
                        f.write(package_utils.desc_from_binary_package(b))

                    # Pack
                    from tslb.package_builder import execute_in_chroot

                    def chroot_func(scratch_space_base, out):
                        # Deadlocks can occur when printing immediately from a
                        # forked child process if many forks happen
                        # immediately.
                        time.sleep(0.5)
                        try:
                            tpm2_pack.pack(scratch_space_base, stdout=out, stderr=out)
                            return 0

                        except ces.CommandFailed as e:
                            tr_out.write(str(e))
                            return 1

                    chroot_scratch_space_base = '/tmp/tslb/scratch_space/binary_packages/%s/%s' % (
                        b.name, b.version_number)

                    ret = execute_in_chroot(rootfs_mountpoint, chroot_func,
                                            chroot_scratch_space_base, tr_out)

                    if ret != 0:
                        return False


                    # Copy the package to the collecting repo
                    transport_form = '%s-%s_%s.tpm2' % (b.name, b.version_number,
                            Architecture.to_str(b.architecture))

                    tr_out.write("Copying transport form `%s' to the collecting repo ...\n" % transport_form)

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

                    tr_out.write("\n")

                    return True

            # for arg in enumerate(spv.list_current_binary_packages()):
            #     if not package(arg):
            #         success = False
            #         break

            res = exe.map(package, enumerate(spv.list_current_binary_packages()))
            if not all(res):
                success = False

        return success
