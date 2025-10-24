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
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload


class VideoHistoryService:
    def __init__(self, db: AsyncSession):
        self.repo = VideoHistoryRepository(db)

    @staticmethod
    def _normalize_user_ids(user_ids: Optional[List[int]]) -> Optional[List[int]]:
        if not user_ids:
            return None
        # Убираем None и дубликаты, сохраняя порядок
        normalized = []
        for item in user_ids:
            if item is None or item in normalized:
                continue
            normalized.append(item)
        return normalized or None

    def _resolve_user_ids(
        self,
        user: User,
        user_id: Optional[int],
        user_ids: Optional[List[int]],
    ) -> Optional[List[int]]:
        if user.role != UserRole.ADMIN:
            return [user.id]
        normalized = self._normalize_user_ids(user_ids)
        if normalized:
            return normalized
        if user_id is not None:
            return [user_id]
        return None

    async def get_all_filtered(
        self,
        user: User,
        id: Optional[int] = None,
        date_to: Optional[dt_date] = None,
        date_from: Optional[dt_date] = None,
        user_id: Optional[int] = None,
        user_ids: Optional[List[int]] = None,
        channel_id: Optional[int] = None,
        articles: Optional[List[str]] = None,
        channel_type: Optional[ChannelType] = None,
        date_published_to: Optional[dt_date] = None,
        date_published_from: Optional[dt_date] = None,
        video_id: Optional[int] = None,
    ):
        effective_user_ids = self._resolve_user_ids(user, user_id, user_ids)
        records = await self.repo.get_filtered(
            id=id,
            date_to=date_to,
            date_from=date_from,
            user_ids=effective_user_ids,
            channel_id=channel_id,
            articles=articles,
            channel_type=channel_type,
            date_published_to=date_published_to,
            date_published_from=date_published_from,
            video_id=video_id,
        )
        formatted = []
        for item in records:
            video = getattr(item, "video", None)
            payload = {
                "id": item.id,
                "video_id": item.video_id,
                "amount_views": item.amount_views,
                "amount_likes": item.amount_likes,
                "amount_comments": item.amount_comments,
                "date_published": item.date_published.isoformat() if item.date_published else None,
                "created_at": item.created_at.isoformat() if getattr(item, "created_at", None) else None,
                "updated_at": item.updated_at.isoformat() if getattr(item, "updated_at", None) else None,
                "video_name": getattr(video, "name", None),
                "video_link": getattr(video, "link", None) if video else None,
                "video_articles": getattr(video, "articles", None) if video else None,
            }
            formatted.append(payload)
        return formatted

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
        filters = dict(filters)
        filters["user_ids"] = self._resolve_user_ids(
            user,
            filters.get("user_id"),
            filters.get("user_ids"),
        )
        filters.pop("user_id", None)
        return await self.repo.get_aggregated_by_date_art(**filters)

    async def get_aggregated_views_by_date_all(
        self,
        user: User,
        **filters
    ):
        filters = dict(filters)
        filters["user_ids"] = self._resolve_user_ids(
            user,
            filters.get("user_id"),
            filters.get("user_ids"),
        )
        filters.pop("user_id", None)
        return await self.repo.get_aggregated_by_date_all(**filters)

    async def get_video_stats_for_csv(
        self,
        user: User,
        channel_type: Optional[ChannelType] = None,
        target_user_id: Optional[int] = None,
        target_user_ids: Optional[List[int]] = None,
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
            .where(Videos.articles.isnot(None))
        )
        # Фильтр по пользователю
        effective_user_ids = self._resolve_user_ids(
            user,
            target_user_id,
            target_user_ids,
        )
        if effective_user_ids:
            query = query.where(Channel.user_id.in_(effective_user_ids))
        # Фильтр по типу канала
        if channel_type is not None:
            query = query.where(Channel.type == channel_type)
        result = await self.repo.db.execute(query)
        videos = result.scalars().all()
        # Оставляем только с артиклем
        filtered_videos = [v for v in videos if v.articles]
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
                "video_name": video.name,
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
        user_ids: Optional[List[int]] = None,
        articles: Optional[List[str]] = None,
    ) -> List[DailyVideoCount]:
        subq = (
            select(
                func.date(VideoHistory.date_published).label("view_date"),
                VideoHistory.video_id
            )
            .distinct()
            .join(Videos, VideoHistory.video_id == Videos.id)
            .where(Videos.articles.isnot(None))
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
        # 🔥 КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: фильтр по подстроке
        if articles:
            or_conditions = [Videos.articles.contains(tag) for tag in articles]
            subq = subq.where(or_(*or_conditions))
        subq = subq.join(Channel, Videos.channel_id == Channel.id)
        effective_user_ids = self._normalize_user_ids(user_ids)
        if effective_user_ids is None and user_id is not None:
            effective_user_ids = [user_id]
        if effective_user_ids:
            subq = subq.where(Channel.user_id.in_(effective_user_ids))
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
        user_ids: Optional[List[int]] = None,
        articles: Optional[List[str]] = None,
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
        # 🔥 КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: фильтр по подстроке
        if articles:
            or_conditions = [Videos.articles.contains(tag) for tag in articles]
            subq = subq.where(or_(*or_conditions))
        subq = subq.join(Channel, Videos.channel_id == Channel.id)
        effective_user_ids = self._normalize_user_ids(user_ids)
        if effective_user_ids is None and user_id is not None:
            effective_user_ids = [user_id]
        if effective_user_ids:
            subq = subq.where(Channel.user_id.in_(effective_user_ids))
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
