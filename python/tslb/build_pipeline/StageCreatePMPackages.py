from tslb import Architecture
from tslb import settings
from tslb.filesystem import FileOperations as fops
from tslb.tclm import lock_S, lock_Splus, lock_X
import os
import shutil
import subprocess

class StageCreatePMPackages(object):
    name = 'create_pm_packages'

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
        success = True

        for n in spv.list_current_binary_packages():
            vs = sorted(spv.list_binary_package_version_numbers(n))
            bv = vs[-1]
            b = spv.get_binary_package(n, bv)

            # Add files
            files = []

            def file_function(p):
                nonlocal files
                files.append((os.path.join('/', p), ''))

            fops.traverse_directory_tree(os.path.join(b.fs_base, 'destdir'), file_function)

            b.set_files(files)


            # Add files to the TPM package
            cmd = ['tpm', '--add-files']

            r = subprocess.run(cmd, cwd=b.fs_base,
                stdout=out.fileno(), stderr=out.fileno())

            if r.returncode != 0:
                out.write('"%s" exited with code %d.' % (' '.join(cmd), r.returncode))

                success = False
                break


            # Pack
            cmd = ['tpm', '--pack']

            r = subprocess.run(cmd, cwd=b.fs_base,
                stdout=out.fileno(), stderr=out.fileno())

            if r.returncode != 0:
                out.write('"%s" exited with code %d.' % (
                    ' '.join(cmd), r.returncode))

                success = False
                break


            # Copy the package to the collecting repo
            transport_form = os.path.join(b.fs_base,
                '%s-%s_%s.tpm.tar' % (b.name, b.version_number,
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
