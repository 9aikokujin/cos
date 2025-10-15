from datetime import datetime
from typing import List
from typing_extensions import Optional
from pydantic import BaseModel, field_validator

from app.models.videos import VideoType


class VideosCreate(BaseModel):
    type: VideoType
    link: str
    name: Optional[str] = None
    channel_id: int
    image: Optional[str] = None
    articles: Optional[List[str]] = None
    amount_views: Optional[int] = None
    amount_likes: Optional[int] = None
    amount_comments: Optional[int] = None
    date_published: Optional[datetime] = None


class VideosUpdate(BaseModel):
    type: Optional[VideoType] = None
    link: Optional[str] = None
    name: Optional[str] = None
    image: Optional[str] = None
    articles: Optional[List[str]] = None
    amount_views: Optional[int] = None
    amount_likes: Optional[int] = None
    amount_comments: Optional[int] = None
    date_published: Optional[datetime] = None


class VideoFilter(BaseModel):
    id: Optional[int] = None
    type: Optional[VideoType] = None
    link: Optional[str] = None
    name: Optional[str] = None
    articles: Optional[List[str]] = None
