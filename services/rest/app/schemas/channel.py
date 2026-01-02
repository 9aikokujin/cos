from datetime import datetime
from typing_extensions import Optional
from pydantic import BaseModel

from app.models.channel import ChannelType


class ChannelRead(BaseModel):
    """Чтение канала."""
    id: int
    type: ChannelType
    link: str
    start_views: Optional[int]
    start_likes: Optional[int]
    start_comments: Optional[int]

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChannelCreate(BaseModel):
    """Создание канала."""
    type: ChannelType
    link: str
    name_channel: Optional[str] = None
    start_views: Optional[int]
    start_likes: Optional[int]
    start_comments: Optional[int]


class ChannelUpdate(BaseModel):
    """Обновление канала."""
    type: Optional[ChannelType] = None
    link: Optional[str] = None
    start_views: Optional[int] = 0
    start_likes: Optional[int] = 0
    start_comments: Optional[int] = 0


class ChannelFilter(BaseModel):
    """Фильтр канала."""
    id: Optional[int] = None
    type: Optional[ChannelType] = None
    link: Optional[str] = None
    name_chanel: Optional[str] = None
