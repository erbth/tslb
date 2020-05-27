import traceback

from tslb import utils
from tslb import Console
from tslb.Console import Color
from tslb import filesystem as fs
from . import *


class RootDirectory(Directory):
    """
    A directory that contains actions etc. to manage the build system itself.
    """
    def __init__(self):
        super().__init__()
        self.name = "tslb"


    def listdir(self):
        return [
            ActionInitiallyCreateLocks(),
            ActionMount(),
            ActionUnmount(),
            ActionSyncBuildPipelineStages(),
            ActionListBuildPipelineStages()
        ]


class ActionInitiallyCreateLocks(Action):
    """
    Create locks for all elements at the tclm.
    """
    def __init__(self):
        super().__init__(writes=True)
        self.name = "initially_create_locks"


    def run(self, *args):
        try:
            print(Color.YELLOW + "Creating locks ..." + Color.NORMAL)
            utils.initially_create_all_locks()
            print(Color.GREEN + "done." + Color.NORMAL)

        except BaseException as e:
            print(Color.RED + "FAILED: " + Color.NORMAL + str(e) + "\n")
            traceback.print_exc()


class ActionMount(Action):
    """
    Mount cephfs.
    """
    def __init__(self):
        super().__init__(writes=True)
        self.name = "mount_cephfs"


    def run(self, *args):
        Console.print_status_box('Mounting filesystem')

        try:
            fs.mount()
        except:
            Console.update_status_box(False)
            raise
        else:
            Console.update_status_box(True)


class ActionUnmount(Action):
    """
    Unmount cephfs.
    """
    def __init__(self):
        super().__init__(writes=True)
        self.name = "unmount_cephfs"


    def run(self, *args):
        Console.print_status_box('Unmounting filesystem')

        try:
            fs.unmount()
        except:
            Console.update_status_box(False)
            raise
        else:
            Console.update_status_box(True)


class ActionSyncBuildPipelineStages(Action):
    """
    Sync the defined buld pipeline stages with the database.
    """
    def __init__(self):
        super().__init__(writes=True)
        self.name = "sync_build_pipline_stages"


    def run(self, *args):
        from tslb import build_pipeline as bpp

        try:
            bpp.sync_stages_with_db(report=True)
            print(Color.GREEN + "done." + Color.NORMAL + "\n")

        except BaseException as e:
            print(Color.RED + "FAILED:" + Color.NORMAL + str(e) + "\n")
            traceback.print_exc()


class ActionListBuildPipelineStages(Action):
    """
    List all defined stages of the build pipeline.
    """
    def __init__(self):
        super().__init__()
        self.name = "list_build_pipeline_stages"


    def run(self, *args):
        from tslb import build_pipeline as bpp

        for stage in bpp.all_stages:
            print(stage.name)
