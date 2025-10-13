from datetime import date as dt_date
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from app.repositories.videohistory import VideoHistoryRepository
from app.schemas.videohistory import VideoHistoryCreate, DailyVideoCount
from app.models.videos import Videos
from app.models.user import User, UserRole
from app.models.channel import Channel, ChannelType
from app.models.videohistory import VideoHistory
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload


class VideoHistoryService:
    def __init__(self, db: AsyncSession):
        self.repo = VideoHistoryRepository(db)

    async def get_all_filtered(
        self,
        user: User,
        id: Optional[int] = None,
        date_to: Optional[dt_date] = None,
        date_from: Optional[dt_date] = None,
        user_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        channel_type: Optional[ChannelType] = None,
        date_published_to: Optional[dt_date] = None,
        date_published_from: Optional[dt_date] = None,
        video_id: Optional[int] = None,
    ):
        # Если пользователь не админ, он видит только свою историю
        if user.role != UserRole.ADMIN:
            user_id = user.id

        # Передаём все фильтры в репозиторий
        return await self.repo.get_filtered(
            id=id,
            date_to=date_to,
            date_from=date_from,
            user_id=user_id,
            channel_id=channel_id,
            channel_type=channel_type,
            date_published_to=date_published_to,
            date_published_from=date_published_from,
            video_id=video_id,
        )

    async def get_by_id(self, video_history_id: int, user: User):
        video_history = await self.repo.get_by_id(video_history_id)

        if not video_history:
            raise ValueError("Видео не найдено")

        if user.role != UserRole.ADMIN and video_history.user_id != user.id:
            raise ValueError("Недостаточно прав для доступа к видео")

        return video_history

    async def create(self, dto: VideoHistoryCreate):
        # user_id = user.id if user.role != UserRole.ADMIN else None
        video_history = await self.repo.create(dto)
        if not video_history:
            raise ValueError("Ошибка при создании истории")
        return video_history

    async def get_aggregated_views_by_date_art(
        self,
        user: User,
        **filters
    ):
        # Если пользователь — не админ, добавляем фильтр по его user_id
        if user.role == UserRole.USER:
            filters["user_id"] = user.id

        return await self.repo.get_aggregated_by_date_art(**filters)

    async def get_aggregated_views_by_date_all(
        self,
        user: User,
        **filters
    ):
        # Если пользователь — не админ, добавляем фильтр по его user_id
        if user.role == UserRole.USER:
            filters["user_id"] = user.id

        return await self.repo.get_aggregated_by_date_all(**filters)

    async def get_video_stats_for_csv(
        self,
        user: User,
        channel_type: Optional[ChannelType] = None,
        target_user_id: Optional[int] = None,
        pub_date_from: Optional[dt_date] = None,
        pub_date_to: Optional[dt_date] = None,
    ):
        query = (
            select(Videos)
            .join(Videos.channel)
            .join(Channel.user)
            .options(
                selectinload(Videos.history)
            )
            .where(Videos.article.isnot(None))
        )

        # Фильтр по пользователю
        if target_user_id is not None:
            query = query.where(Channel.user_id == target_user_id)

        # Фильтр по типу канала
        if channel_type is not None:
            query = query.where(Channel.type == channel_type)

        result = await self.repo.db.execute(query)
        videos = result.scalars().all()

        # Оставляем только с артиклем
        filtered_videos = [v for v in videos if v.article]

        stats = []
        all_dates = set()

        # Собираем данные и все возможные даты из истории
        for video in filtered_videos:
            daily_views = {}
            daily_likes = {}
            daily_comments = {}

            for record in video.history:
                record_date = record.created_at.date()
                daily_views[record_date] = max(
                    daily_views.get(record_date, 0),
                    record.amount_views
                )
                daily_likes[record_date] = max(
                    daily_likes.get(record_date, 0),
                    record.amount_likes
                )
                daily_comments[record_date] = max(
                    daily_comments.get(record_date, 0),
                    record.amount_comments
                )
                all_dates.add(record_date)

            stats.append({
                "link": video.link,
                "daily_views": daily_views,
                "daily_likes": daily_likes,
                "daily_comments": daily_comments
            })

        if pub_date_from or pub_date_to:
            filtered_all_dates = set()
            for d in all_dates:
                if pub_date_from and d < pub_date_from:
                    continue
                if pub_date_to and d > pub_date_to:
                    continue
                filtered_all_dates.add(d)
            all_dates = filtered_all_dates

        sorted_dates = sorted(all_dates)
        return stats, sorted_dates

    async def get_daily_video_with_article_count(
        self,
        date_from: Optional[dt_date] = None,
        date_to: Optional[dt_date] = None,
        channel_id: Optional[int] = None,
        channel_type: Optional[str] = None,
        user_id: Optional[int] = None,
        article: Optional[str] = None,
    ) -> List[DailyVideoCount]:

        subq = (
            select(
                func.date(VideoHistory.date_published).label("view_date"),
                VideoHistory.video_id
            )
            .distinct()
            .join(Videos, VideoHistory.video_id == Videos.id)
            .where(Videos.article.isnot(None))
            .where(VideoHistory.date_published.isnot(None))
        )

        if date_from is not None:
            subq = subq.where(VideoHistory.date_published >= date_from)
        if date_to is not None:
            subq = subq.where(
                VideoHistory.date_published < date_to + timedelta(days=1)
            )

        if channel_id is not None:
            subq = subq.where(Videos.channel_id == channel_id)
        if article is not None:
            subq = subq.where(Videos.article == article)

        subq = subq.join(Channel, Videos.channel_id == Channel.id)
        if user_id is not None:
            subq = subq.where(Channel.user_id == user_id)
        if channel_type is not None:
            subq = subq.where(Channel.type == channel_type)

        subq = subq.subquery()

        query = (
            select(
                subq.c.view_date.label("date"),
                func.count(subq.c.video_id).label("video_count")
            )
            .group_by(subq.c.view_date)
            .order_by(subq.c.view_date)
        )

        result = await self.repo.db.execute(query)
        rows = result.all()

        return [
            DailyVideoCount(date=row.date, video_count=row.video_count)
            for row in rows
        ]

    async def get_daily_video_count_all(
        self,
        date_from: Optional[dt_date] = None,
        date_to: Optional[dt_date] = None,
        channel_id: Optional[int] = None,
        channel_type: Optional[str] = None,
        user_id: Optional[int] = None,
        article: Optional[str] = None,
    ) -> List[DailyVideoCount]:

        subq = (
            select(
                func.date(VideoHistory.date_published).label("view_date"),
                VideoHistory.video_id
            )
            .distinct()
            .join(Videos, VideoHistory.video_id == Videos.id)
            .where(VideoHistory.date_published.isnot(None))
        )

        if date_from is not None:
            subq = subq.where(VideoHistory.date_published >= date_from)
        if date_to is not None:
            subq = subq.where(
                VideoHistory.date_published < date_to + timedelta(days=1)
            )

        if channel_id is not None:
            subq = subq.where(Videos.channel_id == channel_id)
        if article is not None:
            subq = subq.where(Videos.article == article)

        subq = subq.join(Channel, Videos.channel_id == Channel.id)
        if user_id is not None:
            subq = subq.where(Channel.user_id == user_id)
        if channel_type is not None:
            subq = subq.where(Channel.type == channel_type)

        subq = subq.subquery()

        query = (
            select(
                subq.c.view_date.label("date"),
                func.count(subq.c.video_id).label("video_count")
            )
            .group_by(subq.c.view_date)
            .order_by(subq.c.view_date)
        )

        result = await self.repo.db.execute(query)
        rows = result.all()

        return [
            DailyVideoCount(date=row.date, video_count=row.video_count)
            for row in rows
        ]
