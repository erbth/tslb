from tslb.tclm import lock_S, lock_Splus, lock_X

class StageAddRdeps(object):
    name = 'add_rdeps'

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
        for n in spv.list_current_binary_packages():
            vs = sorted(spv.list_binary_package_version_numbers(n))
            bv = vs[-1]

            b = spv.get_binary_package(n, bv)

            add_rdep_key = "additional-rdeps-%s" % n
            rdeps = spv.get_attribute(add_rdep_key) if spv.has_attribute(add_rdep_key) else []

            b.set_attribute('rdeps', rdeps)

        return True
