from pydantic import BaseModel
from typing_extensions import Optional, List
from datetime import datetime


class VideoHistoryRead(BaseModel):
    id: int
    amount_views: int
    amount_likes: int
    amount_comments: int
    video_id: int
    user_id: int
    channel_id: int
    created_at: datetime
    date_published: datetime


class VideoHistoryCreate(BaseModel):
    video_id: int
    amount_views: Optional[int] = None
    amount_likes: Optional[int] = None
    amount_comments: Optional[int] = None
    date_published: Optional[datetime] = None


class HistoryParams(BaseModel):
    id: Optional[int] = None
    date_to: Optional[datetime] = None
    date_from: Optional[datetime] = None
    video_id: Optional[int] = None
    channel_id: Optional[int] = None
    channel_type: Optional[str] = None
    user_id: Optional[int] = None
    articles: Optional[List[str]] = None
    date_published_to: Optional[datetime] = None
    date_published_from: Optional[datetime] = None


class VideoAmountViews(BaseModel):
    date: Optional[datetime] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    date_published: Optional[datetime] = None


class DailyVideoCount(BaseModel):
    date: Optional[datetime] = None
    video_count: Optional[int] = None
    date_published: Optional[datetime] = None
