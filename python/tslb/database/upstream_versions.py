from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, types, ForeignKey
from tslb.VersionNumberColumn import VersionNumberColumn
from tslb import timezone


Base = declarative_base()

class UpstreamVersion(Base):
    __tablename__ = 'upstream_versions'

    name = Column(types.String, primary_key=True)
    version_number = Column(VersionNumberColumn, primary_key=True)
    download_url = Column(types.String, nullable=False)
    signature_download_url = Column(types.String, nullable=False)
    retrieval_time = Column(types.DateTime(timezone=True), nullable=False)


    def __init__(self, name, version_number,
            download_url, signature_download_url, retrieval_time=None):

        if retrieval_time is None:
            retrieval_time = timezone.now()

        self.name = name
        self.version_number = version_number
        self.download_url = download_url
        self.signature_download_url = signature_download_url
        self.retrieval_time = retrieval_time
