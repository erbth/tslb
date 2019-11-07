from tclm import lock_S, lock_Splus, lock_X

class StageDetectManInfo(object):
    name = 'detect_man_info'

    def flow_through(spv):
        """
        :param spv: The source package version to let flow through this segment
            of the pipeline.
        :type spv: SourcePackage.SourcePackageVersion
        :returns: tuple(successful, output)
        :rtype: tuple(bool, str)
        """
        return (True, '')
