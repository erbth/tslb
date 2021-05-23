"""
This modules incorporates functions for modifying and querying packages' build
state. The packages may offer individual functions as well, however the ones
from here shall access the database as directly as possible and hence reduce
overhead. They shall be pretty fast.
"""

from tslb import Architecture
from tslb import CommonExceptions as ces
from tslb import build_pipeline as bp
from tslb import database as db
from tslb import database as db
from tslb import parse_utils
from tslb import tclm
from tslb import timezone
from tslb.SourcePackage import NoSuchSourcePackage, NoSuchSourcePackageVersion
from tslb.SourcePackage import SourcePackageList, SourcePackage
from tslb.VersionNumber import VersionNumber
from tslb.database import BuildPipeline as dbbp
from tslb.database import SourcePackage as dbsp
from sqlalchemy.orm import aliased
from sqlalchemy.sql.expression import or_


def outdate_package_stage(name, arch, version, stage, session=None):
    """
    Outdate the given source package version.

    :param session: Optional DB session or None to create one.

    :raises NoSuchSourcePackage:
    :raises NoSuchSourcePackageVersion:
    :raises RuntimeError: If there's no lock for the given packages...
    :raises ValueError: If the given stage does not exist.
    """
    version = VersionNumber(version)
    arch = Architecture.to_int(arch)

    # Acquire lock
    dblp = 'tslb.db.%s.source_packages.%s.%s' % \
            (Architecture.architectures[arch], name, str(version).replace('.', '_'))

    dblk = tclm.define_lock(dblp)

    own_session = session is None

    with tclm.lock_X(dblk):
        if own_session:
            session = db.get_session()

        try:
            # Verify that the source package and -version exist
            sp = aliased(dbsp.SourcePackage)

            if not session.query(sp.name).filter(sp.name == name,
                    sp.architecture == arch).first():

                raise NoSuchSourcePackage(name, arch)

            spv = aliased(dbsp.SourcePackageVersion)

            if not session.query(spv.source_package).filter(spv.source_package == name,
                    spv.architecture == arch,
                    spv.version_number == version).first():

                raise NoSuchSourcePackageVersion(name, arch, version)


            # Verify that the stage exists
            bps = aliased(dbbp.BuildPipelineStage)

            if not session.query(bps.name).filter(bps.name == stage).first():
                raise ValueError("No such build pipeline stage: %s" % stage)


            # Create an outdated event
            oe = dbbp.BuildPipelineStageEvent(stage, timezone.now(), name, arch,
                    version, dbbp.BuildPipelineStageEvent.status_values.outdated)

            session.add(oe)

            if own_session:
                session.commit()

        except:
            if own_session:
                session.rollback()
            raise

        finally:
            if own_session:
                session.close()

def outdate_enabled_versions_in_arch(arch, stage):
    """
    Outdate all "enabled" versions of each package in the given architecture.

    :raises ValueError: If the given stage does not exist
    """
    # Acquire S+ lock on architecture
    dbrlp = 'tslb.db.%s' % Architecture.to_str(arch)
    dbrlk = tclm.define_lock(dbrlp)

    with tclm.lock_Splus(dbrlk):
        with db.session_scope() as s:
            # Outdate all enabled versions
            for name in SourcePackageList(arch).list_source_packages():
                enabled_versions = []

                sp = SourcePackage(name, arch)
                for v in sp.list_version_numbers():
                    try:
                        if parse_utils.is_yes(sp.get_version(v).get_attribute('enabled')):
                            enabled_versions.append(v)

                    except ces.NoSuchAttribute:
                        pass

                # Free lock
                del sp

                for v in enabled_versions:
                    outdate_package_stage(name, arch, v, stage, session=s)


def get_build_state(spv, s=None):
    """
    Get a package's build state from the db.

    :param SourcePackageVersion spv:
    :param s: A db session. If none, a new one will be created.
    :returns tuple(dbbp.BuildPipelineStageEvent, str|NoneType):
        (Last successful event, last outdated event stage name or None)
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

        candidates = s.query(se.stage)\
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
                                .exists())

        candidates = [t[0] for t in candidates]

        first_outdated_event_stage = None
        for stage in reversed(bp.all_stages):
            if stage.name in candidates:
                first_outdated_event_stage = stage.name

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
                    next_stage = bp.all_stages[i + 1].name
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


def get_last_successful_stage_event(spv, stage, s=None):
    """
    Get the newset successful event for the given stage.

    :param SourcePackageVersion spv:
    :param str stage:
    :param s: A db session. If None, a new one will be created.
    :returns dbbp.BuildPipelineStageEvent|None:
        Last successful event of that stage or None
    """
    have_session = False

    if s is None:
        s = db.get_session()
        have_session = True

    try:
        se = aliased(dbbp.BuildPipelineStageEvent)
        se2 = aliased(dbbp.BuildPipelineStageEvent)
        last_successful_event = s.query(se)\
                .filter(se.source_package == spv.source_package.name,
                        se.architecture == spv.architecture,
                        se.version_number == spv.version_number,
                        se.stage == stage,
                        se.status == dbbp.BuildPipelineStageEvent.status_values.success,
                        ~s.query(se2.stage)\
                                .filter(se2.source_package == se.source_package,
                                    se2.architecture == se.architecture,
                                    se2.version_number == se.version_number,
                                    se2.stage == se.stage,
                                    se2.status == se.status,
                                    se2.time > se.time)\
                                .exists())\
                .first()

        if last_successful_event:
            s.expunge(last_successful_event)

        return last_successful_event

    finally:
        if have_session:
            s.rollback()
            s.close()
