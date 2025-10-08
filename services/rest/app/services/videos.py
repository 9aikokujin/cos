# from app.utils.scheduler import scheduler, process_recurring_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from app.repositories.videos import VideosRepository
# from app.utils.rabbitmq_producer import rabbit_producer
from app.schemas.videos import VideosCreate, VideosUpdate
from app.services.videohistory import VideoHistoryService
from app.schemas.videohistory import VideoHistoryCreate
from app.models.user import User, UserRole
from app.models.videos import VideoType, Videos


class VideosService:
    def __init__(
        self,
        db: AsyncSession,
        history_service: VideoHistoryService
    ):
        self.repo = VideosRepository(db)
        self.history_service = history_service

    async def get_all_filtered_paginated(
        self,
        user_id: Optional[int],
        id: Optional[int] = None,
        type: Optional[VideoType] = None,
        link: Optional[str] = None,
        page: Optional[int] = None,
        size: Optional[int] = None
    ):
        user = None
        if user_id is not None:
            result = await self.repo.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

        effective_user_id = None if (
            user and user.role == UserRole.ADMIN
            ) else (user.id if user else None)

        return await self.repo.get_all_filtered_paginated(
            user_id=effective_user_id,
            id=id,
            type=type,
            link=link,
            page=page,
            size=size
        )

    async def get_by_id(self, video_id: int, user_id: int):
        user = None
        if user_id is not None:
            result = await self.repo.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

        if not user:
            raise ValueError("Пользователь не найден")

        user_id_filter = None if user.role == UserRole.ADMIN else user.id
        video = await self.repo.get_by_id(video_id, user_id=user_id_filter)
        if not video:
            raise ValueError("Видео не найдено или недостаточно прав")
        return video

    async def get_by_video_id(self, video_id: int, user: User) -> dict:
        video = await self.repo.get_by_video_id(video_id)

        if not video:
            raise ValueError("Видео не найдено")

        # Проверяем, что у видео есть канал (на всякий случай)
        if not video.channel:
            raise ValueError("Видео не привязано к каналу")

        # Проверка прав: админ видит всё, пользователь — только если канал его
        if user.role != UserRole.ADMIN and video.channel.user_id != user.id:
            raise ValueError("Недостаточно прав для доступа к видео")

        # Получаем все записи истории для видео
        history = await self.history_service.get_all_filtered(
            user=user,
            video_id=video.id
        )

        return {
            "video": video,
            "history": history
        }

    async def get_by_article(self, article: str, user: User):
        video = await self.repo.get_by_article(article, user)
        if not video:
            raise ValueError("Видео не найдено по артиклю")
        return video

    async def create_or_update_and_create_history(
        self,
        dto: VideosCreate | VideosUpdate,
        video_id: Optional[int] = None
    ) -> Videos:
        """
        Создать или обновить видео по ссылке
        или по video_id без проверки пользователя.
        """
        video = None

        # Сначала пробуем найти видео по video_id (PATCH)
        if video_id:
            video = await self.repo.get_by_id(video_id)

        # Если видео не найдено по ID, ищем по link (POST или новая запись)
        if not video:
            video = await self.repo.get_by_link(dto.link)

        if video:
            # Обновляем видео
            update_dto = VideosUpdate(
                type=dto.type,
                name=dto.name,
                image=dto.image,
                article=dto.article,
                # amount_views=dto.amount_views,
                # amount_likes=dto.amount_likes,
                # amount_comments=dto.amount_comments
            )
            video = await self.repo.update(video.id, update_dto)
            is_new = False
        else:
            # Создаём новое видео
            video = await self.repo.create(dto)
            if not video:
                raise ValueError("Ошибка при создании видео")
            is_new = True

        # Создаём новую запись в истории просмотров без проверки пользователя
        history_dto = VideoHistoryCreate(
            video_id=video.id,
            amount_views=dto.amount_views,
            amount_likes=dto.amount_likes,
            amount_comments=dto.amount_comments
        )
        await self.history_service.create(history_dto)

        return video

    async def delete(self, video_id: int, user: User):
        video = await self.repo.get_by_video_id(video_id)
        if user.role != UserRole.ADMIN and video.user_id != user.id:
            raise ValueError("Недостаточно прав для доступа к видео")
        if not video:
            raise ValueError("Видео не найдено или недостаточно прав")
        return await self.repo.delete(video_id)

    async def update_image(self, video_id: int, image: str):
        video = await self.repo.get_by_video_id(video_id)
        if not video:
            raise ValueError("Видео не найдено")
        video.image = image
        await self.repo.db.commit()
        await self.repo.db.refresh(video)
        return video
