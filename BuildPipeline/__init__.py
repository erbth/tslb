from Architecture import architectures
from BinaryPackage import BinaryPackage
from Console import Color
from SourcePackage import SourcePackage, SourcePackageVersion
from database import BuildPipeline as dbbp
from filesystem import FileOperations as fops
from sqlalchemy.orm import aliased
import BinaryPackage as bp
import Console
import database as db
import sys
import timezone

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
    s = db.get_session()

    stages = s.query(dbbp.BuildPipelineStage).all()
    all_stage_names = [ st.name for st in all_stages ]

    for stage in stages:
        if stage.name not in all_stage_names:
            s.delete(stage)

    stage_names = [ st.name for st in stages ]

    for n in all_stage_names:
        if n not in stage_names:
            s.add(dbbp.BuildPipelineStage(n))

    s.commit()

class BuildPipeline(object):
    def __init__(self, out = sys.stdout):
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

        # Find the last successful event.
        with db.session_scope() as s:
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

        # Determine through which stages the package must still go.
        if last_successful_event is None:
            stages_ahead = all_stages

        else:
            stages_ahead = []
            skip = True

            for stage in all_stages:
                if skip:
                    if stage.name == last_successful_event.stage:
                        skip = False
                else:
                    stages_ahead.append(stage)

        self.out.write(' -> '.join([ st.name for st in stages_ahead ]) + '\n\n')

        # If required, restore the state after the last successful stage (usually
        # only means to restore a snapshot on the fs).
        if last_successful_event:
            with db.session_scope() as s:
                se = aliased(dbbp.BuildPipelineStageEvent)
                if s.query(se.stage)\
                        .filter(se.source_package == spv.source_package.name,
                                se.architecture == spv.architecture,
                                se.version_number == spv.version_number,
                                se.time > last_successful_event.time)\
                        .first():

                    self.out.write(Color.YELLOW + "Restoring state after stage `%s' successfully completed at %s." %
                            (last_successful_event.stage, last_successful_event.time) + Color.NORMAL + '\n')

                    # Restore snapshot if there is one
                    if last_successful_event.snapshot_name:
                        Console.print_status_box("Restoring snapshot `%s' at `%s'" %
                                (last_successful_event.snapshot_name, last_successful_event.snapshot_path),
                                file=self.out)

                        fops.restore_snapshot(last_successful_event.snapshot_path,
                                last_successful_event.snapshot_name)

                        Console.update_status_box(True, file=self.out)

        else:
            # Nothing succeeded so far, just clean the fs locations.
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
