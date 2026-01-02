from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

class VideoView(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    user_id: int
    channel_type: str
    channel_id: int
    video_id: str
    video_title: str
    video_url: str
    views: int
    hashtag: Optional[str] = None

class CreateVideoView(BaseModel):
    user_id: Optional[str] = None
    channel_id: Optional[int] = None
    channel_type: Optional[str] = None
    video_id: str
    video_title: str
    video_url: str
    views: int
    hashtag: Optional[str] = None
