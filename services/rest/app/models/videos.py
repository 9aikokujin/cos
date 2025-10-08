import enum
from app.core.db import Base
from .timestamp import TimestampMixin
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import Enum


class VideoType(enum.Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    LIKEE = "likee"


class Videos(Base, TimestampMixin):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    link = Column(String, nullable=False)
    type = Column(Enum(VideoType), nullable=False)
    name = Column(String, nullable=True)
    image = Column(String, nullable=True)
    article = Column(String, nullable=True)

    channel_id = Column(ForeignKey("channels.id"), nullable=False, index=True)
    channel = relationship(
        "Channel",
        back_populates="videos"
    )

    history = relationship(
        "VideoHistory",
        back_populates="video",
        cascade="all, delete-orphan"
    )
