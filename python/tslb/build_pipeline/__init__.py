import asyncio
from datetime import datetime
import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import threading

from sqlalchemy.orm import aliased
from tslb import BinaryPackage as bp
from tslb import Console
from tslb import database as db
from tslb import timezone
from tslb.Architecture import architectures
from tslb.BinaryPackage import BinaryPackage
from tslb.Console import Color
from tslb.SourcePackage import SourcePackage, SourcePackageVersion
from tslb.database import BuildPipeline as dbbp
from tslb.filesystem import FileOperations as fops
from tslb.buffers import ConsoleBufferFixedSize
from tslb.basic_utils import FDWrapper

from .StageUnpack import StageUnpack
from .StagePatch import StagePatch
from .StageConfigure import StageConfigure
from .StageBuild import StageBuild
from .StageInstallToDestdir import StageInstallToDestdir
from .StageStrip import StageStrip
from .StageAdapt import StageAdapt
from .StageFindSharedLibraries import StageFindSharedLibraries
from .StageDetectManInfo import StageDetectManInfo
from .StageSplitIntoBinaryPackages import StageSplitIntoBinaryPackages
from .StageAddReadme import StageAddReadme
from .StageGenerateMaintainerScripts import StageGenerateMaintainerScripts
from .StageAddRdeps import StageAddRdeps
from .StageCreatePMPackages import StageCreatePMPackages

all_stages = [
        StageUnpack,
        StagePatch,
        StageConfigure,
        StageBuild,
        StageInstallToDestdir,
        StageStrip,
        StageAdapt,
        StageFindSharedLibraries,
        StageSplitIntoBinaryPackages,
        StageDetectManInfo,
        StageAddReadme,
        StageGenerateMaintainerScripts,
        StageAddRdeps,
        StageCreatePMPackages
        ]

outdates_child = {
        'unpack': StagePatch,
        'patch': StagePatch,
        'configure': StagePatch,
        'build': StagePatch,
        'install_to_destdir': StagePatch,
        'strip': StagePatch,
        'adapt': StagePatch,

        # Adding new redeps may change what is installed by a package. Hence
        # all dependent packages need to be rebuilt, because a new rdep may
        # have pulled in, which changes their state.
        # 'find_shared_libraries': StageAddRdeps,
        # 'detect_man_info': StageAddRdeps,
        # 'generate_maintainer_scripts': StageAddRdeps,
        # 'add_readme': StageAddRdeps,
        # 'add_rdeps': StageAddRdeps,

        'find_shared_libraries': StagePatch,
        'split_into_binary_packages': StagePatch,
        'detect_man_info': StagePatch,
        'add_readme': StagePatch,
        'generate_maintainer_scripts': StagePatch,
        'add_rdeps': StagePatch,

        'create_pm_packages': StageAddRdeps
}

def sync_stages_with_db(report=False):
    """
    Add missing stages to the db and remove extra ones.

    :param bool report: If True, the function will print its procedure to
        stdout, otherwise not.
    """
    with db.session_scope() as s:
        # Delete excess stages
        stages = s.query(dbbp.BuildPipelineStage).all()
        all_stage_names = [ st.name for st in all_stages ]

        for stage in stages:
            if stage.name not in all_stage_names:
                if report:
                    print('Deleting stage "%s"' % stage.name)

                s.delete(stage)


        # Adapt wrong parent fields
        parent_stage_names = {}
        previous_name = all_stage_names[0]

        for st in all_stage_names:
            parent_stage_names[st] = previous_name
            previous_name = st

        for st in stages:
            p = parent_stage_names[st.name]

            if st.parent != p:
                if report:
                    print('Changing parent of stage "%s" from "%s" to "%s"' %(
                        st.name, st.parent, p))

                st.parent = p


        # Add missing stages
        stage_names = [ st.name for st in stages ]

        for n in all_stage_names:
            if n not in stage_names:
                if report:
                    print('Adding stage "%s"' % n)

                s.add(dbbp.BuildPipelineStage(n, parent_stage_names[n]))


class BuildPipeline(object):
    """
    The package Build Pipeline.

    :param out: An output stream to log to.
    """
    def __init__(self, out=sys.stdout):
        self.out = out
        self.output_buffer = ConsoleBufferFixedSize(10 * 1024 * 1024)


    def build_source_package_version(self, spv, rootfs_mountpoint):
        """
        :param spv: The source package version to build
        :type spv: SourcePackage.SourcePackage
        :param str rootfs_mountpoint: The root of the mounted root file system
            image that should be used for building the package.
        :returns: True on success else False.
        """
        self.out.write(Color.YELLOW + "Building source package version " + Color.NORMAL +
                "`%s@%s:%s'.\n" % (spv.source_package.name,
                    architectures[spv.architecture], spv.version_number))

        spv.ensure_write_intent()

        # Determine in which stage the package version is
        self.out.write(Color.YELLOW + 'Determining which pipeline stages lie ahead.' + Color.NORMAL + '\n')

        # Find the last successful- and appropriate outdated events.
        # Avoid a cyclic import.
        from tslb.build_state import get_build_state

        with db.session_scope() as s:
            last_successful_event, first_outdated_event_stage = get_build_state(spv, s)

            # Determine through which stages the package must still go, and which
            # stage was the first successful one to base the build on.
            stage_before_first = None

            if last_successful_event is None:
                stages_ahead = all_stages

            else:
                stages_ahead = []
                skip = True

                previous_stage = None

                for stage in all_stages:
                    if skip:
                        if stage.name == first_outdated_event_stage:
                            skip = False
                            stages_ahead.append(stage)
                            stage_before_first = previous_stage

                        elif stage.name == last_successful_event.stage:
                            skip = False
                            stage_before_first = stage

                    else:
                        stages_ahead.append(stage)

                    previous_stage = stage

            self.out.write(' -> '.join([ st.name for st in stages_ahead ]) + '\n\n')


            # If required, restore the state after the stage we start the build
            # with (usually only means to restore a snapshot on the fs).
            if stage_before_first:

                # Find newest build event that actually did something (i.e. was not
                # an outdated event) and look if it is beyond that stage. If yes,
                # we have to restore an older state.
                se = aliased(dbbp.BuildPipelineStageEvent)
                se2 = aliased(dbbp.BuildPipelineStageEvent)

                last_action_event_stage = s.query(se.stage)\
                        .filter(se.source_package == spv.source_package.name,
                                se.architecture == spv.architecture,
                                se.version_number == spv.version_number,
                                se.status != dbbp.BuildPipelineStageEvent.status_values.outdated,
                                ~s.query(se2.stage)\
                                        .filter(se2.source_package == se.source_package,
                                            se2.architecture == se.architecture,
                                            se2.version_number == se.version_number,
                                            se2.status != dbbp.BuildPipelineStageEvent.status_values.outdated,
                                            se2.time > se.time)
                                        .exists())\
                        .first()

                if last_action_event_stage:
                    last_action_event_stage = last_action_event_stage[0]

                if last_action_event_stage != stage_before_first.name:
                    # Find the stage to restore
                    se = aliased(dbbp.BuildPipelineStageEvent)
                    se2 = aliased(dbbp.BuildPipelineStageEvent)

                    restore_event = s.query(se)\
                            .filter(se.source_package == spv.source_package.name,
                                    se.version_number == spv.version_number,
                                    se.architecture == spv.architecture,
                                    se.stage == stage_before_first.name,
                                    ~s.query(se2.stage)\
                                            .filter(se2.source_package == se.source_package,
                                                se2.architecture == se.architecture,
                                                se2.version_number == se.version_number,
                                                se2.stage == se.stage,
                                                se2.time > se.time)\
                                            .exists())\
                            .first()

                    self.out.write(Color.YELLOW + "Restoring state after stage `%s' successfully completed at %s." %
                            (restore_event.stage, restore_event.time) + Color.NORMAL + '\n')

                    # Restore snapshot if there is one
                    if restore_event.snapshot_name:
                        Console.print_status_box("Restoring snapshot `%s'" %
                                restore_event.snapshot_name,
                                file=self.out)

                        if subprocess.run(['umount', os.path.join(rootfs_mountpoint, 'tmp/tslb/scratch_space')]).returncode != 0:
                            raise RuntimeError("Failed to un-bind-mount the scratch space")

                        spv.scratch_space.revert_snapshot(restore_event.snapshot_name)

                        if subprocess.run([
                                'mount', '--bind',
                                spv.scratch_space.mount_path,
                                os.path.join(rootfs_mountpoint, 'tmp/tslb/scratch_space')
                            ]).returncode != 0:

                            raise RuntimeError("Failed to bind-mount the scratch space")

                        Console.update_status_box(True, file=self.out)

                    else:
                        raise RuntimeError("No snapshot for stage `%s'." %
                            restore_event.stage)


            else:
                # Nothing succeeded so far, just clean the scratch space.
                Console.print_status_box("Cleaning the source package version's scratch space.", file=self.out)
                spv.clean_scratch_space()
                Console.update_status_box(True, file=self.out)


        # Only continue if there is something to build.
        if not stages_ahead:
            self.out.write(Color.YELLOW + "Nothing to do.\n" + Color.NORMAL)
            return True

        # Flow through the required stages. This requires a pseudo terminal to
        # catch the stage's output and display it in real time.
        master, slave = pty.openpty()

        ts = os.get_terminal_size()

        fcntl.ioctl(slave, termios.TIOCSWINSZ,
                struct.pack("HHHH", ts.columns, ts.lines, 0, 0))


        # Well, now we need someone to read from the pty ...
        # We have one IO bound task (the reader) and a cpu bound one (the
        # actual package builder - most of the time it will be waiting for a
        # subprocess though, but it could be cpu bound ...). So, asyncio works
        # only with IO bound tasks, multiprocessing is for cpu bound stuff (and
        # overkill here). There remain threads (app-level, but there is only
        # one cpu bound task here ...).
        bg_writer = PipeReaderThread(self.output_buffer, master, self.out)


        # Actually send some stuff now ...
        try:
            for stage in stages_ahead:
                # Log begin
                with db.session_scope() as s:
                    s.add(dbbp.BuildPipelineStageEvent(
                        stage.name,
                        timezone.now(),
                        spv.source_package.name,
                        spv.architecture,
                        spv.version_number,
                        dbbp.BuildPipelineStageEvent.status_values.begin))

                # Walk through stage
                self.out.write(Color.CYAN + 
                    '[------] Flowing through stage %s\n' % stage.name +
                    Color.NORMAL)

                self.output_buffer.clear()
                success = stage.flow_through(spv, rootfs_mountpoint, FDWrapper(slave))

                bg_writer.flush()
                Console.print_finished_status_box(Color.CYAN +
                    'Flowing through stage %s' % stage.name + Color.NORMAL,
                    success,
                    file=self.out)

                # Make a snapshot if the stage succeeded
                if success:
                    snapshot_name = "%s-%s" % (stage.name, datetime.utcnow().isoformat())

                    spv.scratch_space.create_snapshot(snapshot_name)

                else:
                    snapshot_name = None

                try:
                    # Log result
                    with db.session_scope() as s:
                        s.add(dbbp.BuildPipelineStageEvent(
                            stage.name,
                            timezone.now(),
                            spv.source_package.name,
                            spv.architecture,
                            spv.version_number,
                            dbbp.BuildPipelineStageEvent.status_values.success if success else
                                dbbp.BuildPipelineStageEvent.status_values.failed,
                            self.output_buffer.read_data(-1).decode('utf8'),
                            snapshot_name))

                except:
                    if success:
                        spv.delete_snapshot(snapshot_name)
                    raise

                if not success:
                    return False

            return True

        finally:
            # Stop the worker thread if not yet stopped (close() is idempotent)
            bg_writer.close()

            # Close the pty
            os.close(master)
            os.close(slave)


class PipeReaderThread:
    """
    A class wrapping a thread and required communications machinery for reading
    from a pipe in the background. The content is stored in a console buffer
    and can be retrieved as needed. The thread will be a deamon, hence it exits
    automatically if the program's main thread exits. Moreover it is stopped
    when the object is deleted (i.e. all references to it are deleted).

    :param buffer: The console buffer to write the data to. Must only have a
        append_data(bytes) function.

    :param int fd: The fd to read from.

    :param output: If not None the data is tee'd there, too. Must have a
        .write(str) function then ...
    """
    def __init__(self, buf, fd, output=None):
        self.buf = buf
        self.fd = fd
        self.output = output

        self.pread, self.pwrite = os.pipe()
        self.thread = threading.Thread(target=self._worker_func, daemon=True)
        self.thread.start()
        self._closed = False
        self._flush_complete = threading.Event()


    def _worker_func(self):
        w_fd = FDWrapper(self.fd)
        w_pread = FDWrapper(self.pread)

        while True:
            rset,_,_ = select.select([w_fd, w_pread], [], [])

            if w_fd in rset:
                data = os.read(self.fd, 10000)
                self.buf.append_data(data)

                if self.output:
                    self.output.write(data.decode('utf8'))


            if w_pread in rset:
                cmd = os.read(self.pread, 1)
                if cmd == b'q':
                    break

                elif cmd == b'f':
                    self._flush_complete.set()
                    pass


    def flush(self):
        if not self._closed:
            self._flush_complete.clear()
            os.write(self.pwrite, b'f')
            self._flush_complete.wait()

    def close(self):
        if not self._closed:
            os.write(self.pwrite, b'q')

            self.thread.join()
            os.close(self.pread)
            os.close(self.pwrite)

            self._closed = True


    def __del__(self):
        self.close()
