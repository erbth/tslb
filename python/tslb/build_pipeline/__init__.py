from tslb.Architecture import architectures
from tslb.BinaryPackage import BinaryPackage
from tslb.Console import Color
from tslb.SourcePackage import SourcePackage, SourcePackageVersion
from tslb.database import BuildPipeline as dbbp
from tslb.filesystem import FileOperations as fops
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import or_
from tslb import BinaryPackage as bp
from tslb import Console
from tslb import database as db
import sys
from tslb import timezone

from .StageUnpack import StageUnpack
from .StagePatch import StagePatch
from .StageConfigure import StageConfigure
from .StageBuild import StageBuild
from .StageInstallToDestdir import StageInstallToDestdir
from .StageFindSharedLibraries import StageFindSharedLibraries
from .StageDetectManInfo import StageDetectManInfo
from .StageSplitIntoBinaryPackages import StageSplitIntoBinaryPackages
from .StageAddREADME import StageAddREADME
from .StageAddRdeps import StageAddRdeps
from .StageCreatePMPackages import StageCreatePMPackages

all_stages = [
        StageUnpack,
        StagePatch,
        StageConfigure,
        StageBuild,
        StageInstallToDestdir,
        StageFindSharedLibraries,
        StageSplitIntoBinaryPackages,
        StageDetectManInfo,
        StageAddREADME,
        StageAddRdeps,
        StageCreatePMPackages
        ]

def sync_stages_with_db():
    """
    Add missing stages to the db and remove extra ones.
    """
    with db.session_scope() as s:
        # Delete excess stages
        stages = s.query(dbbp.BuildPipelineStage).all()
        all_stage_names = [ st.name for st in all_stages ]

        for stage in stages:
            if stage.name not in all_stage_names:
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
                st.parent = p


        # Add missing stages
        stage_names = [ st.name for st in stages ]

        for n in all_stage_names:
            if n not in stage_names:
                s.add(dbbp.BuildPipelineStage(stage.name, parent_stage_names[n]))


class BuildPipeline(object):
    """
    The package Build Pipeline.

    :param out: An output stream to log to.
    """
    def __init__(self, out=sys.stdout):
        self.out = out

    def build_source_package_version(self, spv):
        """
        :param spv: The source package version to build
        :type spv: SourcePackage.SourcePackage
        :returns: True on success else False.
        """
        self.out.write(Color.YELLOW + "Building source package version " + Color.NORMAL +
                "`%s@%s:%s'.\n" % (spv.source_package.name,
                    architectures[spv.architecture], spv.version_number))

        spv.ensure_write_intent()

        # Determine in which stage the package version is
        self.out.write(Color.YELLOW + 'Determining which pipeline stages lie ahead.' + Color.NORMAL + '\n')

        # Find the last successful- and appropriate outdated events.
        with db.session_scope() as s:
            # Last successful
            se = aliased(dbbp.BuildPipelineStageEvent)
            se2 = aliased(dbbp.BuildPipelineStageEvent)
            last_successful_event = s.query(se)\
                    .filter(se.source_package == spv.source_package.name,
                            se.architecture == spv.architecture,
                            se.version_number == spv.version_number,
                            se.status == dbbp.BuildPipelineStageEvent.status_values.success,
                            ~s.query(se2.stage)\
                                    .filter(se2.source_package == se.source_package,
                                        se2.architecture == se.architecture,
                                        se2.version_number == se.version_number,
                                        se2.status == se.status,
                                        se2.time > se.time)\
                                    .exists())\
                    .first()

            if last_successful_event:
                s.expunge(last_successful_event)

            # Appropriate outdated event
            se = aliased(dbbp.BuildPipelineStageEvent)
            se2 = aliased(dbbp.BuildPipelineStageEvent)

            candidates = s.query(se)\
                    .filter(se.source_package == spv.source_package.name,
                            se.architecture == spv.architecture,
                            se.version_number == spv.version_number,
                            se.status == dbbp.BuildPipelineStageEvent.status_values.outdated,
                            ~s.query(se2.stage)\
                                    .filter(se2.source_package == se.source_package,
                                        se2.architecture == se.architecture,
                                        se2.version_number == se.version_number,
                                        se2.status == dbbp.BuildPipelineStageEvent.status_values.success,
                                        se2.time > se.time)\
                                    .exists())\
                    .cte('candidates')

            c = aliased(candidates)
            c2 = aliased(candidates)

            bps = aliased(dbbp.BuildPipelineStage)

            first_outdated_event_stage = s.query(c.c['stage'])\
                    .join(bps)\
                    .filter(or_(bps.parent == bps.name,
                        ~s.query(c2)\
                                .filter(c2.c['stage'] == bps.parent)\
                                .exists()))\
                    .first()

            if first_outdated_event_stage:
                first_outdated_event_stage = first_outdated_event_stage[0]


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
                        Console.print_status_box("Restoring snapshot `%s' at `%s'" %
                                (restore_event.snapshot_name, restore_event.snapshot_path),
                                file=self.out)

                        fops.restore_snapshot(restore_event.snapshot_path,
                                restore_event.snapshot_name)

                        Console.update_status_box(True, file=self.out)

                    else:
                        raise RuntimeError("No snapshot `%s'." % restore_event.snapshot_path)


            else:
                # Nothing succeeded so far - or before this stage, just clean the
                # fs locations.
                Console.print_status_box("Cleaning fs locations.", file=self.out)
                spv.clean_fs_locations()
                Console.update_status_box(True, file=self.out)


        # Flow through the required stages
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
            Console.print_status_box('Flowing through stage %s' % stage.name, file=self.out)

            success, output = stage.flow_through(spv)

            Console.update_status_box(success, file=self.out)

            if output:
                print(output, file=self.out)

            # Make a snapshot
            if success:
                snapshot_path = spv.fs_base
                snapshot_name = "%s-%s" % (stage.name, timezone.now())

                fops.make_snapshot(snapshot_path, snapshot_name)

            else:
                snapshot_path = None
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
                        output,
                        snapshot_path,
                        snapshot_name))

            except:
                if success:
                    fops.remove_snapshot(snapshot_path, snapshot_name)
                raise

            if not success:
                return False

        return True
