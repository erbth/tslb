from .SourcePackage import SourcePackageVersion
from tslb.VersionNumber import VersionNumberColumn
from sqlalchemy import types, Column, ForeignKey, ForeignKeyConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class BuildPipelineStage(Base):
    __tablename__ = 'build_pipeline_stages'

    name = Column(types.String, primary_key=True)

    # Can be the same as name for the first stage (ONLY for the first stage
    # ...)
    parent = Column(types.String, nullable=False)

    def __init__(self, name, parent):
        self.name = name
        self.parent = parent

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
        failed   =   1000
        begin    =  50000
        success  = 100000
        outdated = 150000
        
        values = [ failed, begin, success ]

        str_map = {
                failed: 'failed',
                begin: 'begin',
                success: 'success',
                outdated: 'outdated'
                }

        str_rmap = {
                'failed': failed,
                'begin': begin,
                'success': success,
                'outdated': outdated
                }


        @classmethod
        def to_str(cls, s):
            """
            Convert the given state to string representation 

            :type s: int or str
            """
            if isinstance(s, int):
                if s not in cls.str_map:
                    raise ValueError("Invalid BuildPipelineEvent state %s" % s)

                return cls.str_map(s)

            else:
                s = str(s)

                if s not in cls.str_rmap:
                    raise ValueError("Invalid BuildPipelineEvent state %s" % s)

                return s


        @classmethod
        def to_int(cls, s):
            """
            Convert the given state to int representation

            :type s: int or str
            """
            if isinstance(s, int):
                if s not in cls.str_map:
                    raise ValueError("Invalid BuildPipelineEvent state %s" % s)

                return s

            else:
                s = str(s)

                if s not in cls.str_rmap:
                    raise ValueError("Invalid BuildPipelineEvent state %s" % s)

                return cls.str_rmap(s)


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
