from tslb import Architecture
from tslb import utils
from tslb.Console import Color
from tslb.management_shell import *
from tslb.scratch_space import ScratchSpace, ScratchSpacePool, NoSuchSnapshot
import re
import subprocess


class RootDirectory(Directory):
    """
    A directory for managing scratch spaces
    """
    def __init__(self):
        super().__init__()
        self.name = "scratch_space"


    def listdir(self):
        return [
            SpacesDirectory(),
            SpacesDeleteOldSnapshots(),
            SpacesDelete()
        ]


class SpacesDirectory(Directory):
    """
    A directory representing all scratch spaces.
    """
    def __init__(self):
        super().__init__()
        self.name = "spaces"


    def listdir(self):
        return [ SpaceDirectory(name) for name in ScratchSpacePool().list_scratch_spaces() ]


class SpacesDeleteOldSnapshots(Action):
    """
    Delete all but the latest snapshot of build pipeline stage in each scratch
    space which belongs to the given architecture. Snapshots that do not belong
    to a build pipline stage are also deleted.
    """
    def __init__(self):
        super().__init__(True)
        self.name = "delete_old_snapshots"


    def run(self, *args):
        if len(args) != 2:
            print("Usage: %s <architecture>" % args[0])
            return

        try:
            arch = Architecture.to_str(args[1])
            utils.remove_old_snapshots_from_scratch_spaces_in_arch(
                    arch, 1,
                    print_fn=lambda n,sn: print("  Deleting %s:%s" % (n,sn)))

        except BaseException as e:
            print(Color.RED + "FAILED: " + Color.NORMAL + str(e) + "\n")


class SpacesDelete(Action):
    """
    Delete a scratch space.
    """
    def __init__(self):
        super().__init__(True)
        self.name = "delete"


    def run(self, *args):
        if len(args) != 2:
            print("Usage %s <scratch space>" % args[0])
            return

        try:
            if ScratchSpacePool().delete_scratch_space(args[1]):
                print("deleted.")
            else:
                print("did not exist.")

        except BaseException as e:
            print(Color.RED + "FAILED: " + Color.NORMAL + str(e) + "\n")


#************************ Individual scratch spaces ***************************
class SpaceDirectory(Directory):
    """
    One scratch space
    """
    def __init__(self, name):
        super().__init__()
        self.name = name


    def listdir(self):
        return [
            SpaceListSnapshots(self.name),
            SpaceInspectSnapshot(self.name),
            SpaceRevertSnapshot(self.name),
            SpaceDeleteOldSnapshots(self.name)
        ]


class SpaceBaseFactory:
    """
    A base class that contains a scratch space factory, which creates (and
    locks) scratch spaces if required.
    """
    def create_space(self, rw=False):
        """
        :param rw: Set to True if the scratch space should be created in RW
            mode.
        """
        return ScratchSpace(ScratchSpacePool(), self.space_name, rw)


class SpaceListSnapshots(Action, SpaceBaseFactory):
    """
    List this scratch space's snapshots. Optionally add a pattern, which may
    contain stars ('*') as wildcard, to filter the snapshots.
    """
    def __init__(self, name):
        super().__init__(False)
        self.space_name = name
        self.name = "list_snapshots"


    def run(self, *args):
        pattern = "*"
        if len(args) > 1:
            pattern = ' '.join(args[1:])

        # Prepare pattern
        pattern = re.compile("^" + re.escape(pattern).replace(r'\*', '.*') + "$")

        s = self.create_space()
        for snap in s.list_snapshots():
            if not re.match(pattern, snap):
                continue

            print(snap)


class SpaceInspectSnapshot(Action, SpaceBaseFactory):
    """
    Mount a snapshot (readonly) and run a shell from the tools system.
    """
    def __init__(self, name):
        super().__init__(False)
        self.space_name = name
        self.name = "inspect_snapshot"


    def run(self, *args):
        if len(args) != 2:
            print("Usage: %s <snapshot's name>" % args[0])
            return

        snap_name = args[1]

        s = self.create_space()

        try:
            s.mount_snapshot(snap_name)
            subprocess.run(['bash'], cwd=s.get_snapshot_mount_path(snap_name))

        except NoSuchSnapshot:
            print("No such snapshot.")
        except BaseException as e:
            print(Color.RED + "FAILED: " + Color.NORMAL + str(e) + "\n")
        finally:
            s.unmount_snapshot(snap_name)


class SpaceRevertSnapshot(Action, SpaceBaseFactory):
    """
    Revert to a specific snapshot.
    """
    def __init__(self, name):
        super().__init__(True)
        self.space_name = name
        self.name = "revert_snapshot"


    def run(self, *args):
        if len(args) != 2:
            print("Usage: %s <snapshot's name>" % args[0])
            return

        snap_name = args[1]

        s = self.create_space(True)
        try:
            s.revert_snapshot(snap_name)
        except NoSuchSnapshot:
            print("No such snapshot.")
        except BaseException as e:
            print(Color.RED + "FAILED: " + Color.NORMAL + str(e) + "\n")


class SpaceDeleteOldSnapshots(Action, SpaceBaseFactory):
    """
    Delete all but the latest snapshot of each build pipeline stage. Snapshots,
    which do not correspond to any build pipeline stage, are not deleted.
    """
    def __init__(self, name):
        super().__init__(True)
        self.space_name = name
        self.name = "delete_old_snapshots"


    def run(self, *args):
        try:
            s = self.create_space(True)
            utils.remove_old_snapshots_from_scratch_space(s, keep=1,
                    print_fn=lambda n: print("  Deleting %s ..." % n))

        except BaseException as e:
            print(Color.RED + "FAILED: " + Color.NORMAL + str(e) + "\n")
