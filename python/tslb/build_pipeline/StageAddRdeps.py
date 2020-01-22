from tslb.tclm import lock_S, lock_Splus, lock_X

class StageAddRdeps(object):
    name = 'add_rdeps'

    def flow_through(spv):
        """
        :param spv: The source package version to let flow through this segment
            of the pipeline.
        :type spv: SourcePackage.SourcePackageVersion
        :returns: tuple(successful, output)
        :rtype: tuple(bool, str)
        """
        for n in spv.list_current_binary_packages():
            vs = sorted(spv.list_binary_package_version_numbers(n))
            bv = vs[-1]

            b = spv.get_binary_package(n, bv)

            add_rdep_key = "additional-rdeps-%s" % n
            rdeps = spv.get_attribute(add_rdep_key) if spv.has_attribute(add_rdep_key) else []

            b.set_attribute('rdeps', rdeps)

        return (True, '')
