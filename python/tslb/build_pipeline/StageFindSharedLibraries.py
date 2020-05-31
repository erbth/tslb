import multiprocessing
import os
import stat
import subprocess
import traceback
from tslb.Console import Color
from tslb.program_analysis import shared_library_tools as so_tools
from tslb.filesystem.FileOperations import simplify_path_static


class StageFindSharedLibraries(object):
    name = 'find_shared_libraries'

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
        success = True

        # Enter a chroot environment and inspect the package.
        def find_shared_libraries(lib_file_map, base, path):
            full_path = simplify_path_static(base + '/' + path)

            st_buf = os.lstat(full_path)

            if stat.S_ISDIR(st_buf.st_mode):
                for elem in os.listdir(full_path):
                    subdir = os.path.join(path, elem)

                    if subdir == '/usr/lib/gconv':
                        continue

                    find_shared_libraries(lib_file_map, base, subdir)

            elif stat.S_ISLNK(st_buf.st_mode) or stat.S_ISREG(st_buf.st_mode):
                if so_tools.file_belongs_to_shared_library(full_path, out):
                    lib_name = so_tools.guess_library_name(full_path, out)

                    if lib_name not in lib_file_map:
                        lib_file_map[lib_name] = []

                    lib_file_map[lib_name].append(path)

        def inspect_package(queue):
            base = '/tmp/tslb/scratch_space/install_location'

            lib_file_map = {}

            try:
                lib_dirs = ['/lib', '/lib64', '/usr/lib', '/usr/local/lib']

                for lib_dir in lib_dirs:
                    if os.path.isdir(simplify_path_static(base + lib_dir)):
                        find_shared_libraries(lib_file_map, base, lib_dir)

                # Convert the information we collected to chared library
                # objects.
                libs = []

                for lib_name, files in lib_file_map.items():
                    libs.append(so_tools.SharedLibrary(lib_name, *files, fs_base=base))

                queue.put(libs)


            except BaseException as e:
                out.write(Color.RED + "Error: " + Color.NORMAL + str(e) + '\n')
                traceback.print_exc(file=out)
                return 1

            return 0


        try:
            from tslb.package_builder import execute_in_chroot

            queue = multiprocessing.Queue()

            ret = execute_in_chroot(rootfs_mountpoint, inspect_package, queue)
            if ret != 0:
                success = False

            libs = queue.get()

        except BaseException as e:
            success = False
            out.write(str(e) + '\n')

        if not success:
            return False

        # Set the source package's shared libraries
        spv.set_shared_libraries(libs)
        return True
