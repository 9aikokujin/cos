# добавить возможность фильтрации по артиклям (несколько штук) DONE

from datetime import date as dt_date
from http.client import HTTPException
from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from app.services.videohistory import VideoHistoryService
from app.schemas.videohistory import HistoryParams
from app.models.user import User, UserRole
from app.api.v1.dependencies import require_role
from sqlalchemy.ext.asyncio.session import AsyncSession
from fastapi.responses import StreamingResponse
from app.models.channel import ChannelType
import io
import csv

from app.core.db import get_db

router = APIRouter()


@router.get("/")
async def get_all_video_history(
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER)),
    user_ids: Optional[List[int]] = Query(None, description="Можно передавать несколько ID: user_ids=1&user_ids=2"),
    params: HistoryParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Получаем все историю видео."""
    service = VideoHistoryService(db)
    if user_ids:
        params.user_ids = user_ids

    result = await service.get_all_filtered(
        user=user,
        **params.model_dump()
    )
    return result


@router.get("/filtered_stats_art")
async def get_filtered_history_with_article(
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER)),
    articles: Optional[str] = Query(None, description="Можно передавать через запятую: #sv,#jw"),
    user_ids: Optional[List[int]] = Query(None, description="Можно передавать несколько ID: user_ids=1&user_ids=2"),
    params: HistoryParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Получаем историю видео с артиклями."""
    service = VideoHistoryService(db)

    if articles:
        params.articles = [a.strip() for a in articles.split(",") if a.strip()]
    if user_ids:
        params.user_ids = user_ids

    result = await service.get_aggregated_views_by_date_art(
        user=user,
        **params.model_dump()
    )
    return result


@router.get("/filtered_stats_all")
async def get_filtered_history_all(
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER)),
    user_ids: Optional[List[int]] = Query(None, description="Можно передавать несколько ID: user_ids=1&user_ids=2"),
    params: HistoryParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Получаем все истории видео."""
    service = VideoHistoryService(db)
    if user_ids:
        params.user_ids = user_ids

    result = await service.get_aggregated_views_by_date_all(
        user=user,
        **params.model_dump()
    )
    return result


@router.get("/daily_article_count")
async def daily_video_with_article_count(
    date_from: Optional[dt_date] = Query(None),
    date_to: Optional[dt_date] = Query(None),
    channel_id: Optional[int] = Query(None),
    channel_type: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    user_ids: Optional[List[int]] = Query(None),
    articles: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Получаем статистику видео с артиклем за выбранный день
    отталкиваясь от даты публикации видео в соц сети.
    """
    service = VideoHistoryService(db)

    result = await service.get_daily_video_with_article_count(
        date_from=date_from,
        date_to=date_to,
        channel_id=channel_id,
        channel_type=channel_type,
        user_id=user_id,
        user_ids=user_ids,
        articles=articles,
    )

    return [
        {
            "date": r.date.isoformat() if r.date else None,
            "video_count": (getattr(r, "video_count", 0) or 0),
            "views": (getattr(r, "views", 0) or 0),
            "likes": (getattr(r, "likes", 0) or 0),
            "comments": (getattr(r, "comments", 0) or 0),
        }
        for r in result
    ]


@router.get("/daily_count_all")
async def daily_video_count_all(
    date_from: Optional[dt_date] = Query(None),
    date_to: Optional[dt_date] = Query(None),
    channel_id: Optional[int] = Query(None),
    channel_type: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    user_ids: Optional[List[int]] = Query(None),
    articles: Optional[List[str]] = None,
    db: AsyncSession = Depends(get_db),
):
    """Получаем количество видео за выбранный день."""
    service = VideoHistoryService(db)

    result = await service.get_daily_video_count_all(
        date_from=date_from,
        date_to=date_to,
        channel_id=channel_id,
        channel_type=channel_type,
        user_id=user_id,
        user_ids=user_ids,
        articles=articles,
    )

    return [
        {"date": r.date.isoformat(), "video_count": r.video_count}
        for r in result
    ]


@router.get("/download_stats_csv")
async def download_video_stats_csv(
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER)),
    channel_type: Optional[str] = Query(None, description="youtube, tiktok, instagram, likee"),
    user_id: Optional[int] = Query(None, description="Только для админа"),
    user_ids: Optional[List[int]] = Query(None, description="Только для админа. Можно указать несколько user_id"),
    date_from: Optional[dt_date] = Query(None, description="Дата публикации ОТ (включительно)"),
    date_to: Optional[dt_date] = Query(None, description="Дата публикации ДО (включительно)"),
    db: AsyncSession = Depends(get_db),
):
    """Скачиваем статистику видео в CSV формате."""
    requested_user_ids = []
    if user_ids:
        requested_user_ids.extend(user_ids)
    if user_id is not None:
        requested_user_ids.append(user_id)
    requested_user_ids = [uid for uid in requested_user_ids if uid is not None]
    if not requested_user_ids:
        requested_user_ids = None

    if user.role != UserRole.ADMIN:
        if requested_user_ids and any(uid != user.id for uid in requested_user_ids):
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        actual_user_ids: Optional[List[int]] = [user.id]
    else:
        actual_user_ids = list(dict.fromkeys(requested_user_ids)) if requested_user_ids else None

    actual_channel_type = None
    if channel_type:
        try:
            actual_channel_type = ChannelType(channel_type.lower())
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Неверный тип канала. Допустимые значения: {[t.value for t in ChannelType]}"
            ) from exc

    service = VideoHistoryService(db)
    stats, sorted_dates = await service.get_video_stats_for_csv(
        user=user,
        channel_type=actual_channel_type,
        target_user_id=None,
        target_user_ids=actual_user_ids,
        pub_date_from=date_from,
        pub_date_to=date_to,
    )

    output = io.StringIO()
    writer = csv.writer(output)

    header = ["Название видео", "Ссылка на ролик"] + [d.isoformat() for d in sorted_dates]
    writer.writerow(header)

    for item in stats:
        row = [
            item.get("video_name") or "",
            item["link"],
        ]
        daily_views = item["daily_views"]
        for d in sorted_dates:
            row.append(daily_views.get(d, ""))
        writer.writerow(row)

    output.seek(0)
    filename = f"video_stats_{dt_date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/{id}")
async def get_video_history(
    id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER)),
):
    """Получаем историю видео по ID."""
    service = VideoHistoryService(db)
    result = await service.get_by_id(id, user)
    return result
