from .SourcePackage import SourcePackageVersion
from tslb.VersionNumber import VersionNumberColumn
from sqlalchemy import types, Column, ForeignKey, ForeignKeyConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class BuildPipelineStage(Base):
    __tablename__ = 'build_pipeline_stages'

    name = Column(types.String, primary_key=True)

    def __init__(self, name):
        self.name = name

class BuildPipelineStageEvent(Base):
    __tablename__ = 'build_pipeline_stage_events'

    stage = Column(types.String,
            ForeignKey(BuildPipelineStage.name, onupdate='CASCADE', ondelete='CASCADE'),
            primary_key=True)

    time = Column(types.DateTime(timezone=True), primary_key=True)

    source_package = Column(types.String, primary_key=True)
    architecture = Column(types.String, primary_key=True)
    version_number = Column(VersionNumberColumn, primary_key=True)

    status = Column(types.Integer, nullable=False)
    output = Column(types.String)

    snapshot_path = Column(types.String)
    snapshot_name = Column(types.String)

    __table_args__ =  (ForeignKeyConstraint(
        (source_package, architecture, version_number),
        (SourcePackageVersion.source_package, SourcePackageVersion.architecture,
            SourcePackageVersion.version_number),
            onupdate='CASCADE', ondelete='CASCADE'),)

    class status_values(object):
        failed  = 1000
        begin   = 50000
        success = 100000
        
        values = [ failed, begin, success ]

        str_map = {
                failed: 'failed',
                begin: 'begin',
                success: 'success'
                }

        str_rmap = {
                'failed': failed,
                'begin': begin,
                'success': success
                }

    def __init__(self, stage, time, source_package, architecture, version_number,
            status, output=None, snapshot_path=None, snapshot_name=None):
        self.stage = stage
        self.time = time
        self.source_package = source_package
        self.architecture = architecture
        self.version_number = version_number
        self.status = status
        self.output = output
        self.snapshot_path = snapshot_path
        self.snapshot_name = snapshot_name
