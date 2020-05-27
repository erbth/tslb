import multiprocessing
import os
import subprocess
import traceback
from tslb.Console import Color
from tslb.program_transformation import stripping


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
        return False
