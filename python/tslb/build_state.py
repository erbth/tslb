"""
This modules incorporates functions for modifying and querying packages' build
state. The packages may offer individual functions as well, however the ones
from here shall access the database as directly as possible and hence reduce
overhead. They shall be pretty fast.
"""

from tslb import database as db
from tslb import Architecture
from tslb import build_pipeline as bp
from tslb import database as db
from tslb import timezone
from tslb.database import BuildPipeline as dbbp
from tslb.database import SourcePackage as dbsp
from tslb.SourcePackage import NoSuchSourcePackage, NoSuchSourcePackageVersion
from tslb.VersionNumber import VersionNumber
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import or_


def outdate_package_stage(name, arch, version, stage):
    """
    Outdate the given source package version.

    :raises NoSuchSourcePackage:
    :raises NoSuchSourcePackageVersion:
    :raises ValueError: If the given stage does not exist.
    """
    version = VersionNumber(version)
    arch = Architecture.to_int(arch)

    with db.session_scope() as s:
        # Verify that the source package and -version exist
        sp = aliased(dbsp.SourcePackage)

        if not s.query(sp.name).filter(sp.name == name,
                sp.architecture == arch).first():

            raise NoSuchSourcePackage(name, arch)

        spv = aliased(dbsp.SourcePackageVersion)

        if not s.query(spv.source_package).filter(spv.source_package == name,
                spv.architecture == arch,
                spv.version_number == version).first():

            raise NoSuchSourcePackageVersion(name, arch, version)


        # Verify that the stage exists
        bps = aliased(dbbp.BuildPipelineStage)

        if not s.query(bps.name).filter(bps.name == stage).first():
            raise ValueError("No such build pipeline stage: %s" % stage)


        # Create an outdated event
        oe = dbbp.BuildPipelineStageEvent(stage, timezone.now(), name, arch,
                version, dbbp.BuildPipelineStageEvent.status_values.outdated)

        s.add(oe)


def get_build_state(spv, s=None):
    """
    Get a package's build state from the db.

    :param SourcePackageVersion spv:
    :param s: A db session. If none, a new one will be created.
    :returns tuple(dbbp.BuildPipelineStageEvent, str):
        (Last successful event, last outdated event stage name)
    """
    have_session = False

    if s is None:
        s = db.get_session()
        have_session = True

    try:
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

        return (last_successful_event, first_outdated_event_stage)

    finally:
        if have_session:
            s.rollback()
            s.close()


def get_next_stage(events):
    """
    Get the next stage through which a package must flow or None if the
    package's build finished. This function is designed to be called with
    `get_build_state`'s return value as argument.

    :param tuple(dbbp.BuildPipelineStageEvent, str): return value of
        `get_build_state`
    :returns str|None:
    """
    last_successful_event, first_outdated_event_stage = events

    # Determine which stage lies after the last successful stage
    next_stage = None

    if last_successful_event:
        next_stage = last_successful_event.stage

    if next_stage:
        found = False

        for i,stage in enumerate(bp.all_stages):
            if stage.name == next_stage:
                if i + 1 < len(bp.all_stages):
                    next_stage = bp.all_stages[i + 1]
                else:
                    next_stage = None

                found = True
                break

        if not found:
            # A stage has been removed or something, don't imply anything and
            # do nothing.
            logger.info("Stage `%s' not found in list of stages. Assuming the "
                    "build of package `%s'@%s:%s finished, manually outdate it to cause a rebuild.",
                    next_stage, spv.name, spv.architecture, spv.version)

            next_stage = None

    else:
        next_stage = bp.all_stages[0].name

    # If this package has an outdated event, determine if it lies ahead of
    # `next_stage` and update `next_stage` accordingly.
    if first_outdated_event_stage:
        for stage in bp.all_stages:
            if stage.name == next_stage:
                break

            if stage.name == first_outdated_event_stage:
                next_stage = first_outdated_event_stage
                break

    return next_stage
