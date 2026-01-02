from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional

from sqlalchemy.ext.asyncio.session import AsyncSession

from app.core.db import get_db
from app.models.user import User, UserRole
from app.models.channel import ChannelType
from app.api.v1.dependencies import require_role
from app.schemas.channel import ChannelCreate, ChannelUpdate
from app.services.channel import ChannelService


router = APIRouter()


@router.get("/all")
async def get_channels(
    user_id: Optional[int] = Query(None),
    id: Optional[int] = Query(None),
    type: Optional[ChannelType] = Query(None),
    link: Optional[str] = Query(None),
    name_channel: Optional[str] = Query(None),
    page: Optional[int] = Query(None, ge=1),
    size: Optional[int] = Query(None, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER))
):
    """Получаем все каналы."""
    service = ChannelService(db)

    result = await service.get_all_filtered_paginated(
        user=user,
        user_id=user_id,
        id=id,
        type=type,
        link=link,
        name_channel=name_channel,
        page=page,
        size=size
    )
    return result


@router.get("/{channel_id}")
async def get_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER))
):
    """Получаем канал по ID."""
    service = ChannelService(db)
    channel = await service.get_by_id(channel_id, user)
    return channel


@router.post("/")
async def create_channel(
    channel_new: ChannelCreate,
    user_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER))
):
    """Создаем канал."""
    service = ChannelService(db)

    target_user_id = user_id if user_id is not None else user.id

    if user.role != UserRole.ADMIN and target_user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Недостаточно прав для создания канала другому пользователю"
        )

    channel = await service.create_for_user(channel_new, target_user_id, user)
    return channel


@router.patch("/{channel_id}")
async def update_channel(
    channel_id: int,
    channel_update: ChannelUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER))
):
    """Обновляем канал."""
    service = ChannelService(db)
    updated_channel = await service.update(channel_id, channel_update, user)
    return updated_channel


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER))
):
    """Удаляем канал."""
    service = ChannelService(db)
    deleted_channel = await service.delete(channel_id, user)
    return deleted_channel
