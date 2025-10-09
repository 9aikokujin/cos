from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.core.db import Base
from .timestamp import TimestampMixin


class VideoHistory(Base, TimestampMixin):
    __tablename__ = "video_history"

    id = Column(Integer, primary_key=True, index=True)
    amount_views = Column(Integer, nullable=False)
    amount_likes = Column(Integer, nullable=False)
    amount_comments = Column(Integer, nullable=False)
    date_published = Column(DateTime, nullable=True)

    video_id = Column(ForeignKey("videos.id"), nullable=False, index=True)

    video = relationship(
        "Videos",
        back_populates="history"
    )
