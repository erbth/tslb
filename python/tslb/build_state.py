"""
This modules incorporates functions for modifying and querying packages' build
state. The packages may offer individual functions as well, however the ones
from here shall access the database as directly as possible and hence reduce
overhead. They shall be pretty fast.
"""

from tslb import database as db
from tslb.database import BuildPipeline as dbbp
from tslb.database import SourcePackage as dbsp
from tslb.SourcePackage import NoSuchSourcePackage, NoSuchSourcePackageVersion
from tslb.VersionNumber import VersionNumber
from tslb import Architecture
from tslb import timezone
from sqlalchemy.orm import aliased


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
