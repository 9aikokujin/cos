import enum
from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.core.db import Base
from .timestamp import TimestampMixin


class TaskSourceTypes(enum.Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    LIKEE = "likee"


class TaskTypes(enum.Enum):
    CHANNEL = "channel"
    VIDEO = "video"


class Task(Base, TimestampMixin):
    __tablename__ = "task"

    id = Column(Integer, primary_key=True)
    parsing_type = Column(Enum(TaskSourceTypes), nullable=False)
    type = Column(Enum(TaskTypes), nullable=False)
    task_str = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=True)

    channel = relationship("Channel", back_populates="tasks")

    def toggle_active(self):
        self.is_active = not self.is_active
