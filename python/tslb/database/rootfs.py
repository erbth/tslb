from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, types, ForeignKey
from tslb.VersionNumber import VersionNumberColumn


Base = declarative_base()

class Image(Base):
    __tablename__ = 'rootfs_images'

    id = Column(types.BigInteger, primary_key = True)
    comment = Column(types.String)

    def __repr__(self):
        return f"rootfs.Image {self.id}"

class AvailableImage(Base):
    __tablename__ = 'available_rootfs_images'

    id = Column(types.BigInteger,
            ForeignKey(Image.id, onupdate='CASCADE', ondelete='CASCADE'),
            primary_key = True)

    def __repr__(self):
        return f"rootfs.AvailableImage {self.id}"

class ImageContent(Base):
    __tablename__ = 'rootfs_image_contents'

    id = Column(types.BigInteger,
            ForeignKey(Image.id, onupdate='CASCADE', ondelete='CASCADE'),
            primary_key = True)

    package = Column(types.String, primary_key = True)
    version = Column(VersionNumberColumn, primary_key = True)
    arch = Column(types.Integer, primary_key = True)

    def __init__(self, img_id, package, arch, version):
        self.id = img_id
        self.package = package
        self.arch = arch
        self.version = version

    def __repr__(self):
        return f"rootfs.ImageContent {self.id}, ({self.package}, {self.version}, {self.arch})"
