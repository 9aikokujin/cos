from datetime import datetime
from typing import Optional
from app.schemas.videos import VideosCreate, VideosUpdate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import NoResultFound

from app.models.channel import Channel
from app.models.user import User, UserRole
from app.models.videos import Videos, VideoType


class VideosRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_filtered_paginated(
        self,
        user_id: Optional[int] = None,
        id: Optional[int] = None,
        type: Optional[VideoType] = None,
        channel_id: Optional[int] = None,
        articles: Optional[str] = None,
        link: Optional[str] = None,
        name: Optional[str] = None,
        page: Optional[int] = None,
        size: Optional[int] = None
    ) -> dict:
        query = select(Videos).order_by(Videos.created_at.desc())

        if user_id is not None:
            # Все видео из каналов, принадлежащих пользователю
            query = query.join(Channel).filter(Channel.user_id == user_id)

        # Фильтрация
        if id is not None:
            query = query.filter(Videos.id == id)
        if type is not None:
            query = query.filter(Videos.type == type)
        if articles is not None:
            # Ищем артикул как часть строки: например, "#sv" в "#sv,#jw"
            query = query.filter(Videos.articles.contains(articles))
        if link is not None:
            query = query.filter(Videos.link.ilike(f"%{link}%"))
        if name is not None:
            query = query.filter(Videos.name.ilike(f"%{name}%"))
        if channel_id is not None:
            query = query.filter(Videos.channel_id == channel_id)

        query = query.order_by(Videos.created_at.desc())

        # Пагинация
        if page is not None and size is not None:
            offset = (page - 1) * size
            query = query.offset(offset).limit(size)
            result = await self.db.execute(query)
            videos = result.scalars().all()

            # Подсчет общего количества для пагинации
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total = total_result.scalar()

            return {
                "videos": videos,
                "pagination": {
                    "page": page,
                    "size": size,
                    "total": total,
                    "pages": (total + size - 1) // size
                }
            }
        else:
            result = await self.db.execute(query)
            videos = result.scalars().all()
            return {"videos": videos}

    async def get_by_id(self, video_id: int, user: Optional[User] = None) -> Optional[Videos]:
        """
        Получить видео по ID. Используется только для обновления видео.
        """
        query = select(Videos).where(Videos.id == video_id)
        result = await self.db.execute(query)
        try:
            return result.scalar_one()
        except NoResultFound:
            return None

    async def get_by_article(self, articles: str, user: Optional[User] = None) -> Optional[Videos]:
        """
        Получить видео по артиклю.
        """
        query = select(Videos).where(Videos.articles == articles)
        result = await self.db.execute(query)
        try:
            return result.scalar_one()
        except NoResultFound:
            return None

    async def get_by_video_id(self, video_id: int):
        stmt = (
            select(Videos)
            .where(Videos.id == video_id)
            .options(
                selectinload(Videos.channel)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_link(self, link: str) -> Optional[Videos]:
        """
        Проверить существование видео по ссылке.
        """
        query = select(Videos).where(Videos.link == link)
        result = await self.db.execute(query)
        try:
            return result.scalar_one_or_none()
        except NoResultFound:
            return None

    async def create(self, dto: VideosCreate) -> Videos:
        channel = await self.db.get(Channel, dto.channel_id)
        if not channel:
            raise ValueError("Канал не найден")

        video = Videos(
            name=dto.name,
            type=dto.type,
            link=dto.link,
            articles=dto.articles,
            channel_id=dto.channel_id,
            image=dto.image,
        )
        if dto.articles:
            video.articles = ",".join(sorted(set(dto.articles)))
        else:
            video.articles = None
        self.db.add(video)
        await self.db.commit()
        await self.db.refresh(video)
        return video

    async def update(self, video_id: int, dto: "VideosUpdate") -> Optional[Videos]:
        """
        Обновить видео по ID.
        """
        query = select(Videos).where(Videos.id == video_id)
        result = await self.db.execute(query)
        try:
            video = result.scalar_one()
        except NoResultFound:
            return None

        # Обновляем только непустые поля
        if dto.type is not None:
            video.type = dto.type
        if dto.link is not None:
            video.link = dto.link
        if dto.image is not None:
            video.image = dto.image
        if dto.articles is not None:
            video.articles = ",".join(sorted(set(dto.articles))) if dto.articles else None

        video.updated_at = func.now()

        await self.db.commit()
        await self.db.refresh(video)
        return video

    async def delete(self, video_id: int) -> bool:
        """
        Удалить видео по ID.
        Возвращает True, если удаление прошло успешно.
        """
        video = await self.get_by_video_id(video_id)
        if not video:
            return False

        await self.db.delete(video)
        await self.db.commit()
        return True
