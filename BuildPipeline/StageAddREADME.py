from tclm import lock_S, lock_Splus, lock_X

class StageAddREADME(object):
    name = 'add_readme'

    def flow_through(spv):
        """
        :param spv: The source package version to let flow through this segment
            of the pipeline.
        :type spv: SourcePackage.SourcePackageVersion
        :returns: tuple(successful, output)
        :rtype: tuple(bool, str)
        """
        output = ""
        success = True

        return (success, output)
