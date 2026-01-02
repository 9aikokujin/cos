import os
from datetime import datetime
from fastapi import APIRouter, Depends, Query, File, UploadFile
from typing import Optional, List

from sqlalchemy.ext.asyncio.session import AsyncSession

from app.core.db import get_db
from app.models.user import User, UserRole
from app.models.videos import VideoType
from app.api.v1.dependencies import require_role
from app.schemas.videos import (
    VideosCreate, VideosUpdate
)
from app.services.videos import VideosService
from app.services.videohistory import VideoHistoryService

UPLOAD_DIR = "uploads/videos"
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter()


@router.get("/")
async def get_videos(
    id: Optional[int] = Query(None),
    type: Optional[VideoType] = Query(None),
    link: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    page: Optional[int] = Query(None, ge=1),
    size: Optional[int] = Query(None, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user_id: Optional[int] = Query(None),
    user_ids: Optional[List[int]] = Query(
        None,
        description="Можно передавать несколько ID: user_ids=1&user_ids=2"
    ),
):
    """Получаем все видео."""
    history_service = VideoHistoryService(db)
    service = VideosService(db, history_service)
    result = await service.get_all_filtered_paginated(
        user_id=user_id,
        user_ids=user_ids,
        id=id,
        type=type,
        link=link,
        name=name,
        page=page,
        size=size
    )
    return result


@router.get("/{video_id}")
async def get_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER))
):
    """Получаем видео по ID."""
    history_service = VideoHistoryService(db)
    service = VideosService(db, history_service)
    videos = await service.get_by_video_id(video_id, user)
    return videos


@router.post("/")
async def create_video(
    video_new: VideosCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создаем видео."""
    history_service = VideoHistoryService(db)
    videos_service = VideosService(db, history_service=history_service)
    video = await videos_service.create_or_update_and_create_history(video_new)
    return video


@router.patch("/{video_id}")
async def update_video(
    video_id: int,
    video_update: VideosUpdate,
    db: AsyncSession = Depends(get_db),
    # user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER)) # Убрал проверку роли, т.к. этот метод используется только для обновления видео парсерами
):
    """Обновляем видео."""
    history_service = VideoHistoryService(db)
    service = VideosService(db, history_service)
    video = await service.create_or_update_and_create_history(
        video_update, video_id=video_id)
    return video


@router.delete("/{video_id}")
async def delete_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER))
):
    """Удаляем видео."""
    history_service = VideoHistoryService(db)
    service = VideosService(db, history_service)
    await service.delete(video_id, user)


@router.post("/{id}/upload-image/")
async def upload_video_image(
    id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Загружаем изображение видео."""
    history_service = VideoHistoryService(db)
    service = VideosService(db, history_service)
    file_path = None
    if file:
        file_name = f"{id}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, file_name)
        with open(file_path, "wb") as f:
            f.write(await file.read())

    videos = await service.update_image(id, file_path)
    return videos
