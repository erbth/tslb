from time import sleep
from tslb import Architecture
from tslb import CommonExceptions as ce
from tslb import Console
from tslb import SourcePackage
from tslb import rootfs
from tslb import settings
from tslb.Console import Color
from tslb.Constraint import DependencyList, VersionConstraint
from tslb.VersionNumber import VersionNumber
from tslb.filesystem import FileOperations as fops
from tslb.tpm import Tpm2
import multiprocessing
import os
import shutil
import signal
import stat
import subprocess
import sys
import tslb


class PackageBuilder(object):
    """
    Objects of this class can build packages.

    :param mount_namespace: The namespace in which rootfs images shall be
        mounted. Typically the build node's id or similar.

    :param out: An output stream to write to write log output to.
    """
    def __init__(self, mount_namespace, out=sys.stdout):
        self.out = out
        self.mount_namespace = mount_namespace

        # For terminating a running chroot worker process
        self.chroot_process = None


    def stop_build(self):
        """
        Stop a running build. This is intended to be called by a signal handler
        in the process which calls build_package().
        """
        if self.chroot_process is not None and self.chroot_process.is_alive():
            os.killpg(self.chroot_process.pid, signal.SIGTERM)


    def build_package(self, name, arch, version=None):
        """
        Build source package with given name, architecture, and optionally a
        specific version number.

        :param name: The source package's name
        :param arch: The source package's architecture
        :param version: The source package's version number of None to build
            the latest version

        :type name: str
        :type arch: int or str
        :type version: Anything that VersionNumber accepts or NoneType

        :raises PkgBuildFailed: If the package failed to build and the build
            system is sane.

        :raises BaseException: If something system-specific fails.
        """
        arch = Architecture.to_int(arch)

        # Create a corresponding source package (version) object
        spkg = SourcePackage.SourcePackage(name, arch)

        if version:
            spkgv = spkg.get_version(version)
        else:
            spkgv = spkg.get_latest_version()

        self.out.write(Color.YELLOW + "Building package %s:%s@%s\n" %
            (spkg.name, Architecture.to_str(spkg.architecture),
                spkgv.version_number))

        Console.print_horizontal_bar(self.out)
        self.out.write(Color.NORMAL)

        # Find a rootfs image that satisfies the package's compiletime
        # dependencies
        # cdeps is a DependencyList with source package names as objects.
        cdeps = spkgv.get_cdeps()


        # The package manager is essential and should be always
        # installed.
        # cdeps.add_constring(VersionConstraint('', '0'), ('tpm2', arch))

        # Find the binary packages of the newest source packages that match the
        # requirements.
        required_binary_packages = []

        spl = SourcePackage.SourcePackageList(arch)
        available_source_packages = set(spl.list_source_packages())

        for dep_name in cdeps.get_required():
            if dep_name not in available_source_packages:
                raise CannotFulfillDependencies(
                    'Required source package "%s" does not exist.' % dep_name)

            dep_sp = SourcePackage.SourcePackage(dep_name, arch)
            available_versions = sorted(dep_sp.list_version_numbers(), reverse=True)

            found = False

            for v in available_versions:
                if (dep_name, v) in cdeps:
                    dep_spv = dep_sp.get_version(v)

                    # Find newest binary packages currently built out of this
                    # source package version.
                    for bp_name in dep_spv.list_current_binary_packages():
                        bp_v = max(dep_spv.list_binary_package_version_numbers(bp_name))
                        required_binary_packages.append((bp_name, arch, bp_v))

                    found = True
                    break

            if not found:
                raise CannotFulfillDependencies(
                    'No version of the required source package "%s" fulfills '
                    'the requirements.' % dep_name)


        # Create a dependency list with equal-dependencies out of the list of
        # required binary packages.
        cbpdeps = DependencyList()

        for n,a,v in required_binary_packages:
            cbpdeps.add_constraint(VersionConstraint('=', v), (n,a))

        # Finally find the best fitting rootfs image.
        image = rootfs.find_image(cbpdeps)
        if not image:
            raise RuntimeError("No published image available")

        self.out.write(Color.YELLOW + "Found best-fitting rootfs image %s.\n" %
            image + Color.NORMAL)


        # If needed, create and adapt a new rootfs image based on the best
        # fitting one
        installed_pkgs = {(n,a): v for n,a,v in image.packages}

        # Find missing packages
        missing_pkgs = []

        for n,a in cbpdeps.get_required():
            if (n,a) not in installed_pkgs or \
                    ((n,a), installed_pkgs[(n,a)]) not in cbpdeps:

                missing_pkgs.append((n,a))

        self.out.write("Found %d missing packages.\n" %
                len(missing_pkgs))


        if len(missing_pkgs) > 0:
            Console.print_status_box("Creating a new COW cloned image ...",
                self.out)

            new_image = rootfs.cow_clone_image(image)
            image = new_image
            Console.update_status_box(True, self.out)
            self.out.write(Color.YELLOW + "New rootfs image is %s.\n" % image
                + Color.NORMAL)

            # Mount the new image and some pseudo filesystems for the build
            image.mount(self.mount_namespace)
            mountpoint = image.get_mountpoint(self.mount_namespace)

            try:
                mount_pseudo_filesystems(mountpoint)
                tpm_native = Tpm2()

                # # Remove disruptive packages in a chroot environment
                # Console.print_status_box(
                #     "Removing disruptive packages ...", self.out)

                # try:
                #     # Update the image's package list

                #     Console.update_status_box(True, self.out)

                # except BaseException as e:
                #     Console.update_status_box(False, self.out)
                #     self.out.write(Color.RED + "  Error: %s" % e + Color.NORMAL)
                #     raise e


                # # Recalculate missing packages (children may have been removed)
                # missing_pkgs = []

                # for n,a in cdeps.get_required():
                #     if (n,a) not in pkgs:
                #         missing_pkgs.append((n,a))

                # if len(missing_pkgs) > 0:
                #     self.out.write("The following packages are missing:\n")
                #     for n,a in missing_pkgs:
                #         self.out.write("    %s@%s\n" % (n, Architecture.to_str(a)))


                # Mark all packages in the image as automatically installed
                self.out.write(Color.CYAN + 
                    '[------] Marking installed packages as automatically installed\n' + Color.NORMAL)

                try:
                    def _f():
                        try:
                            pkgs = [(n,a) for n,a,_ in tpm_native.list_installed_packages()]
                            tpm_native.mark_auto(pkgs)
                            return 0

                        except BaseException as e:
                            print(e)
                            return 1

                    if execute_in_chroot(mountpoint, _f) != 0:
                        raise Exception

                    Console.print_finished_status_box(Color.CYAN +
                        'Marking installed packages as automatically installed' + Color.NORMAL,
                        True,
                        file=self.out)

                except BaseException as e:
                    Console.print_finished_status_box(Color.CYAN +
                        'Marking installed packages as automatically installed' + Color.NORMAL,
                        False,
                        file=self.out)

                    self.out.write(Color.RED + "Error: %s\n" % e + Color.NORMAL)
                    raise e


                # Install missing packages in an chroot environment
                self.out.write(Color.CYAN + 
                    '[------] Installing packages\n' + Color.NORMAL)

                try:
                    def _f(pkgs):
                        try:
                            tpm_native.install(pkgs)
                            return 0

                        except BaseException as e:
                            print(e)
                            return 1

                    ret = execute_in_chroot(mountpoint, _f, required_binary_packages)

                    if ret != 0:
                        raise Exception("The Package Manager failed.")

                    Console.print_finished_status_box(Color.CYAN +
                        'Installing packages' + Color.NORMAL,
                        True,
                        file=self.out)

                except BaseException as e:
                    Console.print_finished_status_box(Color.CYAN +
                        'Installing packages' + Color.NORMAL,
                        False,
                        file=self.out)

                    self.out.write(Color.RED + "Error: %s\n" % e + Color.NORMAL)
                    raise e


                # Remove unneeded packages and update the image's package list.
                self.out.write(Color.CYAN + 
                    '[------] Removing unneeded packages\n' + Color.NORMAL)

                try:
                    new_pkg_queue = multiprocessing.Queue()

                    def _f():
                        try:
                            tpm_native.remove_unneeded()

                            l = tpm_native.list_installed_packages()

                            new_pkg_queue.put(len(l))

                            for e in l:
                                new_pkg_queue.put(e)

                            return 0

                        except BaseException as e:
                            print(e)
                            return 1

                    if execute_in_chroot(mountpoint, _f) != 0:
                        raise Exception("The Package Manager failed.")

                    # Get the installed packages from the queue.
                    new_pkg_list = []

                    l_cnt = new_pkg_queue.get()
                    for i in range(l_cnt):
                        new_pkg_list.append(new_pkg_queue.get())

                    image.set_package_list(new_pkg_list)

                    Console.print_finished_status_box(Color.CYAN +
                        'Removing unneeded packages' + Color.NORMAL,
                        True,
                        file=self.out)

                except BaseException as e:
                    Console.print_finished_status_box(Color.CYAN +
                        'Removing unneeded packages' + Color.NORMAL,
                        False,
                        file=self.out)

                    self.out.write(Color.RED + "Error: %s\n" % e + Color.NORMAL)
                    raise e


            except:
                unmount_pseudo_filesystems(mountpoint, raises=False)
                image.unmount(self.mount_namespace)
                raise


            # Publish, downgrade lock (for safety) and remount read only.
            unmount_pseudo_filesystems(mountpoint, raises=False)
            image.unmount(self.mount_namespace)

            image.publish()

            image.mount(self.mount_namespace)
            mountpoint = image.get_mountpoint(self.mount_namespace)

            try:
                mount_pseudo_filesystems(mountpoint)
            except:
                unmount_pseudo_filesystems(mountpoint, raises=False)
                image.unmount(self.mount_namespace)
                raise


        else:
            # Mount the rootfs image and some pseudo filesystems for the build
            image.mount(self.mount_namespace)
            mountpoint = image.get_mountpoint(self.mount_namespace)

            try:
                mount_pseudo_filesystems(mountpoint)
            except:
                unmount_pseudo_filesystems(mountpoint, raises=False)
                image.unmount(self.mount_namespace)
                raise


        # Invariant here: image points to a rootfs image that satisfies the
        # package's cdeps and is mounted. The required pseudo-filesystems are
        # mounted, too.

        # Build the package in a chroot environment using a build pipeline
        try:
            self.out.write(Color.YELLOW +
                "Building package in chroot environment ...\n" + Color.NORMAL)

            self.out.flush()


            def f(name, arch, version):
                # Create a new process group so all subprocesses can easily be
                # terminated.
                os.setpgrp()

                try:
                    cmd = ['python3', '-m', 'tslb.pb_rootfs_module',
                        spkg.name, Architecture.to_str(spkg.architecture),
                        str(spkgv.version_number)]

                    r = subprocess.call(cmd, stdout=self.out, stderr=self.out)

                except BaseException as e:
                    self.out.write(Color.RED + "%s\n" % e + Color.NORMAL)
                    r = 100

                return r


            p = start_in_chroot(mountpoint, f,
                spkg.name, spkg.architecture, spkgv.version_number)

            # Release the source package so that the other process can take an
            # X lock on it.
            # TODO: To behave atomically, the lock must be transfered.
            sleep(1)
            del spkg
            del spkgv

            # Publish process id class wide to make it terminatable.
            self.chroot_process = p
            p.join()
            self.chroot_process = None

            if p.exitcode != 0:
                if p.exitcode == 2:
                    raise PkgBuildFailed(
                        "Failed to build package with error code %d (package)." %
                        p.exitcode)

                else:
                    raise Exception(
                        "Failed to build package with error code %d (system)." %
                        p.exitcode)

        except BaseException as e:
            self.out.write(Color.RED + "FAILED: %s\n" % e + Color.NORMAL)
            self.out.flush()
            raise e

        finally:
            unmount_pseudo_filesystems(mountpoint, raises=True)
            image.unmount(self.mount_namespace)

        self.out.write(Color.GREEN + "succeeded.\n" + Color.NORMAL)
        self.out.flush()


def execute_in_chroot(root, f, *args, **kwargs):
    """
    Executes the function f in a chroot environment, see start_in_chroot.

    :returns: What f returns
    :rtype int:
    """
    p = start_in_chroot(root, f, *args, **kwargs)
    p.join()
    return p.exitcode


def start_in_chroot(root, f, *args, **kwargs):
    """
    Start the function f in a chroot environment using the multiprocessing
    module.

    :param root: The root to change to
    :param f: A function to call there
    :type f: MUST return int or NoneType
    :param *args: are passed to f
    :param **kwargs: are passed to f, too
    :returns: The started (but not joined) process.
    :rtype: multiprocessing.Process
    :raises: what f raises (plus what may fail ...).
    """
    def enter(root, f, *args, **kwargs):
        # Clear environment (but preserve TERM)
        TERM = os.getenv('TERM')
        os.environ.clear()

        os.environ['TERM'] = TERM
        os.environ['HOME'] = '/root'
        os.environ['PS1'] = r'(chroot) \u:\w\$ '
        os.environ['PATH'] = '/bin:/usr/bin:/sbin:/usr/sbin'

        # Special python path for dynamically copied code
        os.environ['PYTHONPATH'] = '/tmp/tslb/lib/python3/dist-packages'

        os.chroot(root)
        os.chdir('/')
        r = f(*args, **kwargs)

        exit(0 if r is None else r)

    p = multiprocessing.Process(target=enter,
        args=(root, f, *args), kwargs=kwargs)

    p.start()
    return p


# Mounting- and unmounting pseudo filesystems
def mount_pseudo_filesystems(root):
    """
    Mount all pseudo filesystems under root. Additionally a run/shm or dev/shm
    directory is created as needed.

    Additionally copies python packages and the system config file.

    :param root: The root of the directory tree in which the pseudo filesystems
        shall be mounted

    :raises RuntimeError: If root does not exist
    """
    _mount_procfs(root)
    _mount_sysfs(root)
    _mount_devtmpfs(root)
    _mount_run(root)
    _mount_tmp(root)
    _mount_tslb_aux(root)

    if os.path.islink(os.path.join(root, 'dev', 'shm')):
        if os.path.readlink(os.path.join(root, 'dev', 'shm')) == '/run/shm':
            os.mkdir(os.path.join(root, 'run', 'shm'))

    # elif os.path.isdir(os.path.join(root, 'dev', 'shm')):
    #     os.symlink(
    #         os.path.join('..', 'dev', 'shm'),
    #         os.path.join(root, 'run', 'shm'))

    _copy_python_packages(root)
    _copy_config_file(root)


def unmount_pseudo_filesystems(root, raises=True):
    """
    Unmounts all pseudo filesystems under root.

    :param root: The root of the firectory tree under which the pseudo
        filesystems shall be unmounted.

    :param raises: If True, an exception is raised if unmounting fails.
        Otherwise the function does simply nothing (good for i.e. cleaning
        resources on exit or similar).
    """
    _unmount_tslb_aux(root, raises=raises)
    _unmount_tmp(root, raises=raises)
    _unmount_run(root, raises=raises)
    _unmount_devtmpfs(root, raises=raises)
    _unmount_sysfs(root, raises=raises)
    _unmount_procfs(root, raises=raises)


def _mount_procfs(root):
    """
    For internal use only, mount a procfs at root/proc. Creates the proc
    mountpoint if required, but not root.

    :param root: The root of the directory tree in which proc shall be mounted
    :raises RuntimeError: If root does not exist
    """
    if not os.path.isdir(root):
        raise RuntimeError("No such root directory `%s'." % root)

    mountpoint = os.path.join(root, 'proc')
    if not os.path.isdir(mountpoint):
        os.mkdir(mountpoint)
        os.chmod(mountpoint, 0o555)
        os.chown(mountpoint, 0, 0)

    cmd = ['mount', '-t', 'proc', 'proc', mountpoint]

    r = subprocess.call(cmd)
    if r != 0:
        raise ce.CommandFailed(cmd, r)


def _mount_sysfs(root):
    """
    For internal use only, mount a sysfs at root/sys. Creates the sys
    mountpoint if required, but not root.

    :param root: The root of the directory tree in which sysfs shall be mounted
    :raises RuntimeError: If root does not exist
    """
    if not os.path.isdir(root):
        raise RuntimeError("No such root directory `%s'." % root)

    mountpoint = os.path.join(root, 'sys')
    if not os.path.isdir(mountpoint):
        os.mkdir(mountpoint)
        os.chmod(mountpoint, 0o555)
        os.chown(mountpoint, 0, 0)

    cmd = ['mount', '-t', 'sysfs', 'sys', mountpoint]

    r = subprocess.call(cmd)
    if r != 0:
        raise ce.CommandFailed(cmd, r)


def _mount_devtmpfs(root):
    """
    For internal use only, mount a devtmpfs at root/dev and a devpts at
    root/dev/ptr. Creates the dev mountpoint if required, but not root.

    :param root: The root of the directory tree in which devtmpfs shall be
        mounted

    :raises RuntimeError: If root does not exist
    """
    if not os.path.isdir(root):
        raise RuntimeError("No such root directory `%s'." % root)

    mountpoint = os.path.join(root, 'dev')
    if not os.path.isdir(mountpoint):
        os.mkdir(mountpoint)
        os.chmod(mountpoint, 0o755)
        os.chown(mountpoint, 0, 0)

    cmd = ['mount', '--bind', '/dev', mountpoint]

    r = subprocess.call(cmd)
    if r != 0:
        raise ce.CommandFailed(cmd, r)

    cmd = ['mount', '-t', 'devpts', 'devpts', os.path.join(mountpoint, 'pts'),
        '-ogid=5,mode=620']

    r = subprocess.call(cmd)
    if r != 0:
        raise ce.CommandFailed(cmd, r)


def _mount_run(root):
    """
    For internal use only, mount a tmpfs at root/run. Creates the run
    mountpoint if required, but not root.

    :param root: The root of the directory tree in which run shall be mounted
    :raises RuntimeError: If root does not exist
    """
    if not os.path.isdir(root):
        raise RuntimeError("No such root directory `%s'." % root)

    mountpoint = os.path.join(root, 'run')
    if not os.path.isdir(mountpoint):
        os.mkdir(mountpoint)
        os.chmod(mountpoint, 0o555)
        os.chown(mountpoint, 0, 0)

    cmd = ['mount', '-t', 'tmpfs', 'tmpfs', mountpoint, '-omode=755']

    r = subprocess.call(cmd)
    if r != 0:
        raise ce.CommandFailed(cmd, r)


def _mount_tmp(root):
    """
    For internal use only, mount a tmpfs at root/tmp. Creates the tmp
    mountpoint if required, but not root.

    :param root: The root of the directory tree in which tmp shall be mounted
    :raises RuntimeError: If root does not exist
    """
    if not os.path.isdir(root):
        raise RuntimeError("No such root directory `%s'." % root)

    mountpoint = os.path.join(root, 'tmp')
    if not os.path.isdir(mountpoint):
        os.mkdir(mountpoint)
        os.chmod(mountpoint, 0o1777)
        os.chown(mountpoint, 0, 0)

    cmd = ['mount', '-t', 'tmpfs', 'tmpfs', mountpoint, '-omode=1777']

    r = subprocess.call(cmd)
    if r != 0:
        raise ce.CommandFailed(cmd, r)


def _mount_tslb_aux(root):
    """
    For internal use only; bind mount the packaging, source_location and
    collecting_repo at root/tmp/tslb/. Creates the tslb/* mountpoint if
    required, but not root or tmp.

    :param root: The root of the directory tree in which the directories shall
        be mounted.

    :raises RuntimeError: If root or tmp does not exist
    """
    if not os.path.isdir(root) or not os.path.isdir(os.path.join(root, 'tmp')):
        raise RuntimeError(
            "No such root directory `%s' or tmp therein. % root")

    base = os.path.join(root, 'tmp', 'tslb')
    if not os.path.isdir(base):
        os.mkdir(base)
        os.chmod(base, 0o755)
        os.chown(base, 0, 0)

    mountpoint_packaging = os.path.join(base, 'packaging')
    mountpoint_collecting_repo = os.path.join(base, 'collecting_repo')
    mountpoint_source_location = os.path.join(base, 'source_location')

    for mountpoint in [mountpoint_packaging, mountpoint_collecting_repo, mountpoint_source_location]:
        if not os.path.isdir(mountpoint):
            os.mkdir(mountpoint)
            os.chmod(mountpoint, 0o755)
            os.chown(mountpoint, 0, 0)

    cmd = ['mount', '--bind',
        os.path.join(settings.get_fs_root(), 'packaging'), mountpoint_packaging]

    r = subprocess.call(cmd)
    if r != 0:
        raise ce.CommandFailed(cmd, r)

    cmd = ['mount', '--bind',
        settings.get_collecting_repo_location(), mountpoint_collecting_repo]

    r = subprocess.call(cmd)
    if r != 0:
        raise ce.CommandFailed(cmd, r)

    cmd = ['mount', '--bind',
        settings.get_source_location(), mountpoint_source_location]

    r = subprocess.call(cmd)
    if r != 0:
        raise ce.CommandFailed(cmd, r)


def _unmount_procfs(root, raises=True):
    """
    For internal use only, unmount the procfs filesystem under root.

    :param root: The root of the firectory tree in which proc shall be
        unmounted.

    :param raises: If True, an exception is raised if unmounting fails.
        Otherwise the function does simply nothing (good for i.e. cleaning
        resources on exit or similar).
    """
    _unmount(os.path.join(root, 'proc'), raises)


def _unmount_sysfs(root, raises=True):
    """
    For internal use only, unmount the sysfs filesystem under root.

    :param root: The root of the firectory tree in which sys shall be
        unmounted.

    :param raises: If True, an exception is raised if unmounting fails.
        Otherwise the function does simply nothing (good for i.e. cleaning
        resources on exit or similar).
    """
    _unmount(os.path.join(root, 'sys'), raises)


def _unmount_devtmpfs(root, raises=True):
    """
    For internal use only, unmount the devtmpfs and devpts filesystems under
    root.

    :param root: The root of the firectory tree in which dev shall be
        unmounted.

    :param raises: If True, an exception is raised if unmounting fails.
        Otherwise the function does simply nothing (good for i.e. cleaning
        resources on exit or similar).
    """
    _unmount(os.path.join(root, 'dev', 'pts'), raises)
    _unmount(os.path.join(root, 'dev'), raises)


def _unmount_tmp(root, raises=True):
    """
    For internal use only, unmount tmp under root.

    :param root: The root of the firectory tree in which tmp shall be
        unmounted.

    :param raises: If True, an exception is raised if unmounting fails.
        Otherwise the function does simply nothing (good for i.e. cleaning
        resources on exit or similar).
    """
    _unmount(os.path.join(root, 'tmp'), raises)


def _unmount_run(root, raises=True):
    """
    For internal use only, unmount run under root.

    :param root: The root of the directory tree in which run shall be
        unmounted.

    :param raises: If True, an exception is raised if unmounting fails.
        Otherwise the function simply does nothing (good for i.e. cleaning
        resources on exit or similar).
    """
    _unmount(os.path.join(root, 'run'), raises)


def _unmount_tslb_aux(root, raises=True):
    """
    For internal use only; unmount
    tmp/tslb/{packaging,collecting_repo,source_location} under root.

    :param root: The root of the directory tree in which the directories shall
        be unmounted.

    :param raises: If True, an exception is raised if unmounting fails.
        Otherwise the function simply does nothing (good for i.e. cleaning
        resources on exit or similar).
    """
    _unmount(os.path.join(root, 'tmp', 'tslb', 'source_location'), raises)
    _unmount(os.path.join(root, 'tmp', 'tslb', 'collecting_repo'), raises)
    _unmount(os.path.join(root, 'tmp', 'tslb', 'packaging'), raises)


def _unmount(target, raises=True):
    """
    For internal use only, unmount a filesystem.

    :param target: The mountpoint or device
    :param raises: If True, an exception is raised if unmounting fails.
        Otherwise the function does simply nothing (good for i.e. cleaning
        resources on exit or similar).

    :raises CommonExceptions.CommandFailed: If unmounting fails and raises is
        True.
    """
    cmd = ['umount', target]
    
    r = subprocess.call(cmd)

    if r != 0 and raises:
        raise ce.CommandFailed(cmd, r)


def _copy_python_packages(root):
    """
    Copies the tslb package to root/tmp/tslb/lib/...

    :param root: The root of the target directory tree.
    """
    tmp = os.path.join(root, 'tmp')

    if not os.path.isdir(tmp):
        raise RuntimeError("tmp dir at '%s' does not exist." % tmp)

    name = tslb.__name__

    path = os.path.join(tmp, 'tslb', 'lib', 'python3', 'dist-packages', name)
    fops.mkdir_p(path)

    pkg_paths = set(tslb.__path__._path)

    to_copy = []

    for p in pkg_paths:
        def f(e):
            abs_e = os.path.join(p, e)
            s = os.stat(abs_e)

            if e.find('__pycache__') < 0:
                if stat.S_ISDIR(s.st_mode):
                    to_copy.append(('d', p, e))

                # For now, only importable modules and no scripts (without .py ending)
                # should be required in the chroot environment.
                elif stat.S_ISREG(s.st_mode) and e.endswith('.py'):
                    to_copy.append(('f', p, e))

                elif stat.S_ISLNK(s.st_mode):
                    to_copy.append(('l', p, e))

        fops.traverse_directory_tree(p, f, skip_hidden=True)

    for t, b, e in to_copy:
        src = os.path.join(b, e)
        dst = os.path.join(path, e)

        if t == 'f':
            shutil.copyfile(src, dst)
            shutil.copystat(src, dst)

        elif t == 'l':
            shutil.copyfile(src, dst, follow_symlinks=False)

        elif t == 'd':
            os.mkdir(dst)
            shutil.copystat(src, dst)


def _copy_config_file(root):
    """
    Copies the system config file to root/tslb/system.ini.
    """
    tmp = os.path.join(root, 'tmp')

    if not os.path.isdir(tmp):
        raise RuntimeError("tmp dir at '%s' does not exist." % tmp)

    fops.mkdir_p(os.path.join(root, 'tmp', 'tslb'))
    shutil.copy2(
        settings.get_config_file_path(),
        os.path.join(root, 'tmp', 'tslb', 'system.ini'))



# *************************** Exceptions **************************************
class PkgBuildFailed(Exception):
    """
    To be raised when a package failed to build and the build system worked
    that is no infrastractural problem occured.
    """
    def __init__(self, msg):
        super().__init__(msg)


class CannotFulfillDependencies(PkgBuildFailed):
    """
    To be raised when a package's cdeps cannot be fulfilled. Usually this is
    because the dependent packages are not available (yet).
    """
    def __init__(self, msg):
        super().__init__(msg)
