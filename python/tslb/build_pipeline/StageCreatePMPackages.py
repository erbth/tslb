from tslb.tclm import lock_S, lock_Splus, lock_X
from tslb.filesystem import FileOperations as fops
import os

class StageCreatePMPackages(object):
    name = 'create_pm_packages'

    def flow_through(spv):
        """
        :param spv: The source package version to let flow through this segment
            of the pipeline.
        :type spv: SourcePackage.SourcePackageVersion
        :returns: tuple(successful, output)
        :rtype: tuple(bool, str)
        """
        output = ''
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

        success = False
        return (success, output)
