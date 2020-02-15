from tslb import Architecture
from tslb import rootfs
from tslb import SourcePackage
from tslb.VersionNumber import VersionNumber
from tslb.Constraint import DependencyList, VersionConstraint
from tslb import Console
from tslb.Console import Color
import sys


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


    def build_package(self, name, arch, version=None):
        """
        Build source package with given name, architecture, and optinally a
        specific version number.

        :param name: The source package's name
        :param arch: The source package's architecture
        :param version: The source package's version number of None to build
            the latest version

        :type name: str
        :type arch: int or str
        :type version: Anything that VersionNumber accepts or NoneType

        :raises BaseException: if something failes.
        """
        arch = Architecture.to_int(arch)

        # Create a corresponding source package (version) object
        spkg = SourcePackage.SourcePackage(name, arch, write_intent=True)

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
        # cdeps is a DependencyList with package names as objects.
        cdeps = spkgv.get_cdeps()

        # OK, this is hacky.
        cdeps.l = {(k, arch): v for k,v in cdeps.l.items()}

        image = rootfs.find_image(cdeps)
        if not image:
            raise RuntimeError("No published image available")

        self.out.write(Color.YELLOW + "Found best-fitting rootfs image %s.\n" %
            image + Color.NORMAL)

        return

        # If needed, create and adapt a new rootfs image based on the best
        # fitting one
        pkgs = set(image.packages)

        # Find disruptive packages
        disruptive_pkgs = []

        for n,a,v in pkgs:
            if ((n,a), v) not in cdeps:
                disruptive_pkgs.append((n,a))

        if len(disruptive_pkgs) > 0:
            self.out.write("The following packages are disruptive:\n")
            for n,a in disruptive_pkgs:
                self.out.write("    %s@%s\n" % (n, Architecture.to_str(a)))

        # Find missing packages
        missing_pkgs = []

        for n,a in cdeps.get_required():
            if (n,a) not in pkgs:
                missing_pkgs.append((n,a))


        self.out.write("Found %d disruptive and %d missing packages.\n" %
            (len(disruptive_pkgs), len(missing_packages)))

        if len(disruptive_pkgs) > 0 or len(missing_packages) > 0:
            Console.print_status_box("Creating a new COW cloned image ...",
                self.out)

            new_image = rootfs.cow_clone_image(image)
            image = new_image
            Console.update_status_box(True, self.out)
            self.out.write(Color.YELLOW + "New rootfs image is %s.\n" % image
                + Color.NORMAL)

            # Mount the new image
            image.mount(self.mount_namespace)

            # Remove disruptiv packages in a chroot environment
            # Update the image's package list
            Console.print_status_box(
                "Removing disruptive packages ...", self.out)

            try:
                pass

            except BaseException as e:
                Console.update_status_box(False, self.out)
                self.out.write(Color.RED + "  Error: %s" % e + Color.NORMAL)
                raise e

            # Recalculate missing packages (children may have been removed)
            #
            # Install missing packages

        # Mount the rootfs image and some pseudo filesystems for the build
        #
        # Build the package in a chroot environment using a build pipeline
