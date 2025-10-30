from datetime import datetime, timedelta
from fastapi.exceptions import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import select
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload
from typing import Optional, List
from app.models.videohistory import VideoHistory
from app.schemas.videohistory import VideoHistoryCreate, VideoAmountViews
from app.models.videos import Videos
from app.models.channel import Channel


class VideoHistoryRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_filtered(
        self,
        id: Optional[int] = None,
        date_to: Optional[datetime] = None,
        date_from: Optional[datetime] = None,
        video_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        channel_type: Optional[str] = None,
        user_id: Optional[int] = None,
        user_ids: Optional[List[int]] = None,
        articles: Optional[List[str]] = None,
        date_published_to: Optional[datetime] = None,
        date_published_from: Optional[datetime] = None,
    ):
        query = (
            select(VideoHistory)
            .options(selectinload(VideoHistory.video))
            .join(VideoHistory.video)
            .join(Videos.channel)
        )

        if id is not None:
            query = query.where(VideoHistory.id == id)

        if video_id is not None:
            query = query.where(VideoHistory.video_id == video_id)

        if date_to is not None:
            query = query.where(VideoHistory.created_at <= date_to)

        if date_from is not None:
            query = query.where(VideoHistory.created_at >= date_from)

        if articles is not None and len(articles) > 0:
            query = query.where(or_(*[Videos.articles.contains(tag) for tag in articles]))

        effective_user_ids = user_ids or ([user_id] if user_id is not None else None)
        if effective_user_ids:
            query = query.where(Channel.user_id.in_(effective_user_ids))

        if channel_id is not None:
            query = query.where(Videos.channel_id == channel_id)

        if channel_type is not None:
            query = query.where(Channel.type == channel_type)

        if date_published_to is not None:
            query = query.where(
                VideoHistory.date_published <= date_published_to)

        if date_published_from is not None:
            query = query.where(
                VideoHistory.date_published >= date_published_from)

        result = await self.db.scalars(query)
        return result.all()

    async def get_by_date_to(self, date_to: datetime) -> list[VideoHistory]:
        result = await self.db.execute(
            select(VideoHistory).where(VideoHistory.created_at <= date_to)
        )
        return result.scalars().all()

    async def get_by_date_from(self,
                               date_from: datetime) -> list[VideoHistory]:
        result = await self.db.execute(
            select(VideoHistory).where(VideoHistory.created_at >= date_from)
        )
        return result.scalars().all()

    async def get_by_date_published_to(self, date_published_to: datetime) -> list[VideoHistory]:
        result = await self.db.execute(
            select(VideoHistory).where(VideoHistory.date_published <= date_published_to)
        )
        return result.scalars().all()

    async def get_by_date_published_from(self, date_published_from: datetime) -> list[VideoHistory]:
        result = await self.db.execute(
            select(VideoHistory).where(VideoHistory.date_published >= date_published_from)
        )
        return result.scalars().all()

    async def get_by_id(self, id: int) -> VideoHistory | None:
        result = await self.db.execute(select(VideoHistory).filter_by(id=id))
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: int) -> list[VideoHistory]:
        result = await self.db.execute(
            select(VideoHistory).where(Channel.user_id == user_id)
        )
        return result.scalars().all()

    async def get_by_channel_id(self, channel_id: int) -> list[VideoHistory]:
        result = await self.db.execute(
            select(VideoHistory).where(Videos.channel_id == channel_id)
        )
        return result.scalars().all()

    async def get_by_channel_type(self,
                                  channel_type: str) -> list[VideoHistory]:
        result = await self.db.execute(
            select(VideoHistory).where(Channel.type == channel_type)
        )
        return result.scalars().all()

    async def get_by_article(self, articles: str) -> list[VideoHistory]:
        result = await self.db.execute(
            select(VideoHistory).where(Videos.articles == articles)
        )
        return result.scalars().all()

    async def get_by_video_id(self, video_id: int) -> list[VideoHistory]:
        query = select(VideoHistory).where(VideoHistory.video_id == video_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create(self, dto: VideoHistoryCreate,
                     user_id: Optional[int] = None) -> VideoHistory:
        # Если не админ — проверяем, что видео принадлежит пользователю
        if user_id is not None:
            result = await self.db.execute(
                select(Videos)
                .join(Channel)
                .filter(Videos.id == dto.video_id, Channel.user_id == user_id)
            )
            video = result.scalar_one_or_none()
            if not video:
                raise ValueError("Видео не найдено или недостаточно прав")

        # Создаём запись
        history = VideoHistory(**dto.model_dump())
        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(history)
        return history

    async def delete(self, video_history_id: int):
        video_history = await self.get_by_id(video_history_id)

        if not video_history:
            raise HTTPException(status_code=404,
                                detail="VideoHistory не найден")

        await self.db.delete(video_history)
        await self.db.commit()
        return video_history

    async def get_aggregated_by_date_art(
        self,
        id: Optional[int] = None,
        date_to: Optional[datetime] = None,
        date_from: Optional[datetime] = None,
        video_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        channel_type: Optional[str] = None,
        date_published_to: Optional[datetime] = None,
        date_published_from: Optional[datetime] = None,
        user_id: Optional[int] = None,
        user_ids: Optional[List[int]] = None,
        articles: Optional[List[str]] = None,
    ):
        query = (
            select(
                func.date(VideoHistory.created_at).label("view_date"),
                Videos.articles.label("articles"),
                Videos.name.label("video_name"),
                func.max(VideoHistory.amount_views).label("max_views"),
                func.max(VideoHistory.amount_likes).label("max_likes"),
                func.max(VideoHistory.amount_comments).label("max_comments"),
            )
            .join(VideoHistory.video)
            .join(Videos.channel)
            .where(Videos.articles.is_not(None))
        )

        # --- Фильтры ---
        if id is not None:
            query = query.where(VideoHistory.id == id)

        if video_id is not None:
            query = query.where(VideoHistory.video_id == video_id)

        if date_to is not None:
            query = query.where(VideoHistory.created_at <= date_to + timedelta(days=1))

        if date_from is not None:
            query = query.where(VideoHistory.created_at >= date_from)

        if date_published_to is not None:
            query = query.where(VideoHistory.date_published <= date_published_to)

        if date_published_from is not None:
            query = query.where(VideoHistory.date_published >= date_published_from)

        effective_user_ids = user_ids or ([user_id] if user_id is not None else None)
        if effective_user_ids:
            query = query.where(Channel.user_id.in_(effective_user_ids))

        if channel_id is not None:
            query = query.where(Videos.channel_id == channel_id)

        if channel_type is not None:
            query = query.where(Channel.type == channel_type)

        if articles:
            query = query.where(or_(*[Videos.articles.like(f"%{a}%") for a in articles]))

        # --- Группировка и сортировка ---
        query = query.group_by(func.date(VideoHistory.created_at), Videos.articles, Videos.name)
        query = query.order_by(func.date(VideoHistory.created_at))

        # --- Выполнение ---
        result = await self.db.execute(query)
        rows = result.all()
        print(f"Это ровсы: {rows}")

        # --- Форматирование ---
        return [
            {
                "date": row.view_date,
                "articles": row.articles,
                "video_name": row.video_name,
                "views": int(row.max_views or 0),
                "likes": int(row.max_likes or 0),
                "comments": int(row.max_comments or 0),
            }
            for row in rows
        ]

    async def get_aggregated_by_date_all(
        self,
        id: Optional[int] = None,
        date_to: Optional[datetime] = None,
        date_from: Optional[datetime] = None,
        video_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        channel_type: Optional[str] = None,
        date_published_to: Optional[datetime] = None,
        date_published_from: Optional[datetime] = None,
        user_id: Optional[int] = None,
        user_ids: Optional[List[int]] = None,
        articles: Optional[List[str]] = None,
    ):
        view_date_expr = func.date(VideoHistory.created_at)
        daily_max_query = (
            select(
                VideoHistory.video_id.label("video_id"),
                view_date_expr.label("view_date"),
                func.max(VideoHistory.amount_views).label("max_views"),
                func.max(VideoHistory.amount_likes).label("max_likes"),
                func.max(VideoHistory.amount_comments).label("max_comments"),
            )
            .select_from(VideoHistory)
            .join(VideoHistory.video)
            .join(Videos.channel)
        )

        if id is not None:
            daily_max_query = daily_max_query.where(VideoHistory.id == id)

        if video_id is not None:
            daily_max_query = daily_max_query.where(VideoHistory.video_id == video_id)

        if date_to is not None:
            daily_max_query = daily_max_query.where(
                VideoHistory.created_at < date_to + timedelta(days=1)
            )

        if date_from is not None:
            daily_max_query = daily_max_query.where(VideoHistory.created_at >= date_from)

        if date_published_to is not None:
            daily_max_query = daily_max_query.where(
                VideoHistory.date_published <= date_published_to
            )

        if date_published_from is not None:
            daily_max_query = daily_max_query.where(
                VideoHistory.date_published >= date_published_from
            )

        effective_user_ids = user_ids or ([user_id] if user_id is not None else None)
        if effective_user_ids:
            daily_max_query = daily_max_query.where(Channel.user_id.in_(effective_user_ids))

        if channel_id is not None:
            daily_max_query = daily_max_query.where(Videos.channel_id == channel_id)

        if channel_type is not None:
            daily_max_query = daily_max_query.where(Channel.type == channel_type)

        if articles is not None and len(articles) > 0:
            daily_max_query = daily_max_query.where(
                or_(*[Videos.articles.contains(tag) for tag in articles])
            )

        daily_max_query = daily_max_query.group_by(
            VideoHistory.video_id,
            view_date_expr,
        )

        daily_max_subquery = daily_max_query.subquery()

        aggregated_query = (
            select(
                daily_max_subquery.c.view_date,
                func.sum(daily_max_subquery.c.max_views).label("total_views"),
                func.sum(daily_max_subquery.c.max_likes).label("total_likes"),
                func.sum(daily_max_subquery.c.max_comments).label("total_comments"),
            )
            .select_from(daily_max_subquery)
            .group_by(daily_max_subquery.c.view_date)
            .order_by(daily_max_subquery.c.view_date)
        )

        result = await self.db.execute(aggregated_query)
        rows = result.all()

        return [
            VideoAmountViews(
                date=row.view_date,
                views=int(row.total_views) if row.total_views is not None else 0,
                likes=int(row.total_likes) if row.total_likes is not None else 0,
                comments=int(row.total_comments) if row.total_comments is not None else 0,
            )
            for row in rows
        ]
