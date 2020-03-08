from tslb.tclm import lock_S, lock_Splus, lock_X

class StageAddReadme(object):
    name = 'add_readme'

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
        return True
