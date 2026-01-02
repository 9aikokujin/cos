import enum
import re
from sqlalchemy import Column, Integer, String, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.core.db import Base
from .timestamp import TimestampMixin


class ChannelType(enum.Enum):
    """Тип канала."""
    TIKTOK = "tiktok" # ТикТок
    YOUTUBE = "youtube" # Ютуб
    INSTAGRAM = "instagram" # Инстаграм
    LIKEE = "likee" # Лайк


class Channel(Base, TimestampMixin):
    """Канал."""
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(ChannelType), nullable=False)
    link = Column(String, nullable=False)
    name_channel = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False)
    videos = relationship(
        "Videos",
        back_populates="channel",
        cascade="all, delete-orphan"
    )

    user = relationship("User", back_populates="channels")
    tasks = relationship("Task", back_populates="channel",
                         cascade="all, delete-orphan")

    start_views = Column(Integer, default=0)
    start_likes = Column(Integer, default=0)
    start_comments = Column(Integer, default=0)

    def grap_name_channel(self):
        """Получаем название канала."""
        link = self.link.strip()
        tiktok_pattern = r'https://www\.tiktok\.com/@([^/?\?]+)'
        match = re.search(tiktok_pattern, link)
        if match:
            return match.group(1)
        youtube_pattern = r'https://www\.youtube\.com/channel/([^/?\?]+)'
        match = re.search(youtube_pattern, link)
        if match:
            return match.group(1)
        youtube_user_pattern = r'https://www\.youtube\.com/@([^/?\?]+)'
        match = re.search(youtube_user_pattern, link)
        if match:
            return match.group(1)
        instagram_pattern = r'https://www\.instagram\.com/([^/?\?]+)'
        match = re.search(instagram_pattern, link)
        if match:
            return match.group(1)
        parts = link.strip("/").split("/")
        if parts:
            last_part = parts[-1]
            clean_name = last_part.split('?')[0]
            return clean_name
        return None
