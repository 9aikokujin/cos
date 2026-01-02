import enum
from sqlalchemy import Column, Integer, String, Boolean, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.core.db import Base
from .timestamp import TimestampMixin


class TaskSourceTypes(enum.Enum):
    """Тип источника задачи."""
    YOUTUBE = "youtube" # Ютуб
    TIKTOK = "tiktok" # ТикТок
    INSTAGRAM = "instagram" # Инстаграм
    LIKEE = "likee" # Лайк


class TaskTypes(enum.Enum):
    """Тип задачи."""
    CHANNEL = "channel" # Канал
    # VIDEO = "video" # Видео


class Task(Base, TimestampMixin):
    """Задача."""
    __tablename__ = "task"

    id = Column(Integer, primary_key=True)
    parsing_type = Column(Enum(TaskSourceTypes), nullable=False)
    type = Column(Enum(TaskTypes), nullable=False)
    task_str = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=True)

    channel = relationship("Channel", back_populates="tasks")

    def toggle_active(self):
        """Переключаем активность задачи."""
        self.is_active = not self.is_active
