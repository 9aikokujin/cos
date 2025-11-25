# from datetime import datetime, timedelta, timezone
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from app.core.db import SessionLocal
# from app.models.channel import Channel
# from app.models.videos import Videos
# from app.models.account import Account
# from app.models.proxy import Proxy
# from sqlalchemy import select
# from app.utils.rabbitmq_producer import rabbit_producer

# scheduler = AsyncIOScheduler()


# async def restore_scheduled_tasks():
#     """При старте: запустить парсинг всех каналов с интервалом 5 минут, затем повторять каждые 24ч."""
#     async with SessionLocal() as session:
#         result = await session.execute(select(Channel))
#         tasks = result.scalars().all()

#     now = datetime.now(timezone.utc)

#     tasks = sorted(
#         tasks,
#         key=lambda task: (
#             task.created_at or datetime.min.replace(tzinfo=timezone.utc),
#             task.id,
#         ),
#     )

#     for idx, task in enumerate(tasks):
#         job_id = f"task_{task.id}"
#         if scheduler.get_job(job_id):
#             continue

#         # Первый запуск: через (idx * 5) минут после старта
#         first_run = now + timedelta(minutes=5 * idx)

#         scheduler.add_job(
#             func=process_recurring_task,
#             trigger="interval",
#             hours=24,
#             args=[task.id, "channel"],
#             id=job_id,
#             max_instances=1,
#             coalesce=True,
#             misfire_grace_time=600,  # 10 минут на опоздание
#             next_run_time=first_run  # ← вот ключ!
#         )
#         print(f"✅ Задача {task.id} запланирована: первый запуск в {first_run.strftime('%H:%M')}, затем каждые 24ч")


# async def process_recurring_task(task_id: int, type: str):
#     """Отправляет задачу парсинга с актуальными данными из БД."""
#     async with SessionLocal() as db:
#         try:
#             channel = (await db.execute(select(Channel).where(Channel.id == task_id))).scalar()
#             if not channel:
#                 scheduler.remove_job(f"task_{task_id}")
#                 return

#             # Получаем свежие аккаунты и прокси
#             accounts = (await db.execute(select(Account).where(Account.is_active.is_(True)))).scalars().all()
#             proxies = (await db.execute(select(Proxy))).scalars().all()

#             rabbit_producer.send_task(
#                 f"parsing_{channel.type.value.lower()}",
#                 {
#                     "type": "channel",
#                     "user_id": channel.user_id,
#                     "url": channel.link,
#                     "channel_id": channel.id,
#                     "accounts": [a.account_str for a in accounts],
#                     "proxy_list": [p.proxy_str for p in proxies],
#                 }
#             )
#             print(f"📤 Отправлена задача для канала {channel.id} (тип: {channel.type.value})")
#         except Exception as e:
#             print(f"❌ Ошибка в задаче {task_id}: {e}")

import asyncio
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.account import Account
from app.models.channel import Channel, ChannelType
from app.models.proxy import Proxy
from app.utils.rabbitmq_producer import rabbit_producer

MOSCOW_TZ = ZoneInfo("Europe/Moscow")
CI_CD_START_DELAY_MINUTES = 7
CI_CD_STEP_MINUTES = 7
CI_CD_TYPE_PRIORITY = [
    ChannelType.YOUTUBE,
    ChannelType.TIKTOK,
    ChannelType.LIKEE,
    ChannelType.INSTAGRAM,
]

scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
INSTAGRAM_BATCH_JOB_ID = "instagram_batch_job"
INSTAGRAM_BATCH_LOCK_TIMEOUT_MINUTES = 120
_instagram_batch_active = False
_instagram_batch_id: Optional[str] = None
_instagram_batch_started_at: Optional[datetime] = None
_pending_tasks_after_batch: dict[int, tuple[int, Optional[int], Optional[str]]] = {}


def _remove_instagram_batch_job():
    try:
        scheduler.remove_job(INSTAGRAM_BATCH_JOB_ID)
    except JobLookupError:
        pass


def schedule_instagram_batch_job(offset_minutes: int = 0) -> None:
    hours, minute = _compute_time_slots(offset_minutes)
    hour_expr = ",".join(str(h) for h in hours)
    slots_display = ", ".join(f"{h:02d}:{minute:02d}" for h in hours)
    scheduler.add_job(
        func=_instagram_batch_job,
        trigger="cron",
        hour=hour_expr,
        minute=minute,
        id=INSTAGRAM_BATCH_JOB_ID,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
        replace_existing=True,
    )
    print(f"✅ Batch-задача Instagram запланирована ежедневно по слотам {slots_display} (мск)")


async def _instagram_batch_job():
    await dispatch_instagram_batch("scheduled_daily")


def _compute_time_slots(offset_minutes: int) -> tuple[list[int], int]:
    """Calculate 24h-based hours for morning/evening slots and shared minute."""
    if offset_minutes < 0:
        offset_minutes = 0

    morning_total = 5 * 60 + offset_minutes
    morning_hour = (morning_total // 60) % 24
    minute = morning_total % 60

    evening_total = 20 * 60 + offset_minutes
    evening_hour = (evening_total // 60) % 24

    hours = sorted({morning_hour, evening_hour})
    return hours, minute


def _mark_instagram_batch_state(active: bool, batch_id: Optional[str] = None):
    global _instagram_batch_active, _instagram_batch_id, _instagram_batch_started_at
    _instagram_batch_active = active
    if active:
        _instagram_batch_id = batch_id
        _instagram_batch_started_at = datetime.now(timezone.utc)
    else:
        _instagram_batch_id = None
        _instagram_batch_started_at = None


def _queue_after_batch(
    task_id: int,
    schedule_offset_minutes: Optional[int],
    schedule_wave_anchor: Optional[str],
) -> None:
    """
    Сохраняем задачу, которую нужно отправить после окончания Instagram batch.
    Используем dict, чтобы не плодить дубликаты по channel_id.
    """
    _pending_tasks_after_batch[task_id] = (
        task_id,
        schedule_offset_minutes,
        schedule_wave_anchor,
    )


def _dispatch_pending_after_batch() -> int:
    """
    Запускает отложенные задачи, накопленные во время активного Instagram batch.
    Возвращает число успешно добавленных джобов.
    """
    if not _pending_tasks_after_batch:
        return 0

    pending = list(_pending_tasks_after_batch.values())
    _pending_tasks_after_batch.clear()

    now = datetime.now(MOSCOW_TZ)
    dispatched = 0

    for task_id, schedule_offset_minutes, schedule_wave_anchor in pending:
        run_at = now + timedelta(seconds=1 + dispatched)
        job_id = f"deferred_task_{task_id}_{int(run_at.timestamp())}"
        try:
            scheduler.add_job(
                func=process_recurring_task,
                trigger="date",
                run_date=run_at,
                args=[task_id, "channel"],
                kwargs={
                    "schedule_offset_minutes": schedule_offset_minutes,
                    "schedule_wave_anchor": schedule_wave_anchor,
                },
                id=job_id,
                replace_existing=False,
                max_instances=1,
                coalesce=True,
            )
            dispatched += 1
        except Exception as exc:
            print(f"⚠️ Не удалось добавить отложенную задачу {task_id}: {exc}")

    if dispatched:
        print(f"▶️ Запущено {dispatched} отложенных задач после завершения Instagram batch.")
    return dispatched


def is_instagram_batch_active() -> bool:
    return _instagram_batch_active


def get_instagram_batch_state() -> tuple[bool, Optional[str], Optional[datetime]]:
    return _instagram_batch_active, _instagram_batch_id, _instagram_batch_started_at


def release_instagram_batch(batch_id: Optional[str] = None) -> bool:
    active, current_batch_id, _ = get_instagram_batch_state()
    if not active:
        return False
    if batch_id and current_batch_id and batch_id != current_batch_id:
        return False
    _mark_instagram_batch_state(False)
    print("ℹ️ Instagram batch lock released.")
    _dispatch_pending_after_batch()
    return True


async def _auto_release_instagram_batch(batch_id: str):
    await asyncio.sleep(max(1, INSTAGRAM_BATCH_LOCK_TIMEOUT_MINUTES * 60))
    active, current_batch_id, _ = get_instagram_batch_state()
    if active and current_batch_id == batch_id:
        print("⚠️ Авто-сброс блокировки Instagram batch по таймауту.")
        _mark_instagram_batch_state(False)
        _dispatch_pending_after_batch()


def _normalize_parse_started_at(
    now: datetime,
    schedule_offset_minutes: Optional[int],
    schedule_wave_anchor: Optional[str],
) -> datetime:
    """
    Возвращает скорректированное время начала парсинга.
    Для ежедневного расписания (wave_anchor == "daily") учитывает смещение,
    чтобы у каналов, перенесённых за полночь из-за offset, оставалась дата исходного слота.
    """
    if schedule_wave_anchor != "daily" or schedule_offset_minutes is None:
        return now

    morning_total = 5 * 60 + schedule_offset_minutes
    evening_total = 20 * 60 + schedule_offset_minutes
    expected_minute = morning_total % 60

    if now.minute != expected_minute:
        return now

    schedule_points = (
        (morning_total, (morning_total // 60) % 24),
        (evening_total, (evening_total // 60) % 24),
    )

    for total_minutes, expected_hour in schedule_points:
        if now.hour == expected_hour:
            day_shift = total_minutes // 1440
            if day_shift:
                return now - timedelta(days=day_shift)
            return now
    return now


def schedule_channel_task(
    channel_id: int,
    *,
    run_immediately: bool = False,
    offset_minutes: int = 0,
) -> bool:
    hours, minute = _compute_time_slots(offset_minutes)
    hour_expr = ",".join(str(h) for h in hours)
    job_id = f"task_{channel_id}"
    job = scheduler.add_job(
        func=process_recurring_task,
        trigger="cron",
        hour=hour_expr,
        minute=minute,
        args=[channel_id, "channel"],
        kwargs={
            "schedule_offset_minutes": offset_minutes,
            "schedule_wave_anchor": "daily",
        },
        id=job_id,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
        replace_existing=True,
    )
    immediate_dispatched = False
    next_run = getattr(job, "next_run_time", None)
    if next_run is None:
        next_run = getattr(job, "next_fire_time", None)
    if next_run is None:
        # APScheduler 4.x no longer exposes next_run_time; compute manually.
        try:
            now = datetime.now(MOSCOW_TZ)
            next_run = job.trigger.get_next_fire_time(None, now)
        except Exception:
            next_run = None
    slots_display = ", ".join(f"{h:02d}:{minute:02d}" for h in hours)

    if next_run:
        next_run_local = (
            next_run.astimezone(MOSCOW_TZ)
            if next_run.tzinfo
            else next_run.replace(tzinfo=MOSCOW_TZ)
        )
        print(
            f"✅ Задача {channel_id} запланирована: следующий запуск "
            f"{next_run_local.strftime('%d.%m %H:%M')} (мск), далее ежедневно по слотам {slots_display}"
        )
    else:
        print(
            f"✅ Задача {channel_id} запланирована ежедневно по слотам {slots_display} (мск)"
        )

    if run_immediately:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                process_recurring_task(
                    channel_id,
                    "channel",
                    schedule_offset_minutes=offset_minutes,
                    schedule_wave_anchor="daily",
                )
            )
            immediate_dispatched = True
        except RuntimeError:
            print(f"⚠️ Не удалось инициировать немедленный запуск для канала {channel_id}: нет активного цикла событий")

    return immediate_dispatched


async def restore_scheduled_tasks():
    """
    Точка выбора расписания.
    Держите активным только один из вариантов ниже (раскомментируйте нужный).
    """
    # --- Ежедневная очередь 05:00 и 20:00 (оставьте включённой для боевого режима) ---
    await _restore_scheduled_tasks_daily()

    # --- CICD очередь: запуск через 7 минут и шагом 7 минут ---
    # await restore_scheduled_tasks_cicd()


async def _restore_scheduled_tasks_daily():
    """При старте восстанавливает ежедневное расписание (05:00 и 20:00 мск) для всех каналов."""
    async with SessionLocal() as session:
        result = await session.execute(select(Channel))
        channels = result.scalars().all()

    if not channels:
        _remove_instagram_batch_job()
        return

    def _sort_key(task: Channel):
        return (
            task.created_at or datetime.min.replace(tzinfo=timezone.utc),
            task.id,
        )

    instagram_channels = sorted(
        [channel for channel in channels if channel.type == ChannelType.INSTAGRAM],
        key=_sort_key,
    )
    other_channels = sorted(
        [channel for channel in channels if channel.type != ChannelType.INSTAGRAM],
        key=_sort_key,
    )

    for index, channel in enumerate(other_channels):
        offset = index * 5
        schedule_channel_task(channel.id, offset_minutes=offset)

    if instagram_channels:
        schedule_instagram_batch_job(offset_minutes=0)
    else:
        _remove_instagram_batch_job()


def _round_robin_channels(channels: list[Channel]) -> list[Channel]:
    """Перестраивает список каналов в порядке YT → TikTok → Likee → Instagram."""
    buckets = {channel_type: deque() for channel_type in CI_CD_TYPE_PRIORITY}
    leftovers = deque()
    for channel in channels:
        bucket = buckets.get(channel.type)
        (bucket if bucket is not None else leftovers).append(channel)

    ordered = []
    while True:
        appended = False
        for channel_type in CI_CD_TYPE_PRIORITY:
            bucket = buckets[channel_type]
            if bucket:
                ordered.append(bucket.popleft())
                appended = True
        if not appended:
            break
    ordered.extend(leftovers)
    return ordered


async def restore_scheduled_tasks_cicd(
    start_delay_minutes: int = CI_CD_START_DELAY_MINUTES,
    step_minutes: int = CI_CD_STEP_MINUTES,
):
    """
    Альтернативная очередь для CICD: запуск через 7 минут после старта,
    далее каждые 7 минут, в порядке YouTube → TikTok → Likee → Instagram.
    """
    async with SessionLocal() as session:
        result = await session.execute(select(Channel))
        channels = result.scalars().all()

    _remove_instagram_batch_job()

    channels = sorted(
        channels,
        key=lambda task: (
            task.created_at or datetime.min.replace(tzinfo=timezone.utc),
            task.id,
        ),
    )

    if not channels:
        return

    instagram_channels = [channel for channel in channels if channel.type == ChannelType.INSTAGRAM]
    other_channels = [channel for channel in channels if channel.type != ChannelType.INSTAGRAM]

    ordered_channels = _round_robin_channels(other_channels)
    total = len(ordered_channels)
    cycle_minutes = max(step_minutes * total, step_minutes)
    first_run = datetime.now(MOSCOW_TZ) + timedelta(minutes=max(start_delay_minutes, 0))

    for index, channel in enumerate(ordered_channels):
        job_id = f"cicd_task_{channel.id}"
        next_run = first_run + timedelta(minutes=step_minutes * index)
        scheduler.add_job(
            func=process_recurring_task,
            trigger="interval",
            minutes=cycle_minutes,
            next_run_time=next_run,
            args=[channel.id, "channel"],
            kwargs={
                "schedule_wave_anchor": "cicd",
                "schedule_offset_minutes": step_minutes * index,
            },
            id=job_id,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
            replace_existing=True,
        )
        print(
            f"🚀 CICD очередь: канал {channel.id} стартует {next_run.strftime('%d.%m %H:%M')} "
            f"и повторяется каждые {cycle_minutes} минут (шаг {step_minutes} мин.)"
        )

    if instagram_channels:
        await dispatch_instagram_batch("cicd_startup")


async def process_recurring_task(
    task_id: int,
    type: str,
    schedule_offset_minutes: Optional[int] = None,
    schedule_wave_anchor: Optional[str] = None,
):
    """Отправляет задачу парсинга с актуальными данными из БД."""
    async with SessionLocal() as db:
        try:
            channel = (await db.execute(select(Channel).where(Channel.id == task_id))).scalar()
            if not channel:
                for job_id in (f"task_{task_id}", f"cicd_task_{task_id}"):
                    try:
                        scheduler.remove_job(job_id)
                    except JobLookupError:
                        continue
                return

            if channel.type != ChannelType.INSTAGRAM and is_instagram_batch_active():
                _queue_after_batch(
                    task_id=task_id,
                    schedule_offset_minutes=schedule_offset_minutes,
                    schedule_wave_anchor=schedule_wave_anchor,
                )
                print(
                    f"⏸ Instagram batch активен — откладываем отправку задачи для канала "
                    f"{channel.id} ({channel.type.value}). Отложено: {len(_pending_tasks_after_batch)}"
                )
                return

            # Получаем свежие аккаунты и прокси
            accounts = (await db.execute(select(Account).where(Account.is_active.is_(True)))).scalars().all()
            proxies = (await db.execute(select(Proxy))).scalars().all()
            likee_proxies = [p.proxy_str for p in proxies if p.for_likee is True]
            generic_proxies = [p.proxy_str for p in proxies if p.for_likee is not True]
            proxy_payload = likee_proxies if channel.type == ChannelType.LIKEE else generic_proxies

            now_local = datetime.now(MOSCOW_TZ)
            started_at_dt = _normalize_parse_started_at(
                now_local,
                schedule_offset_minutes,
                schedule_wave_anchor,
            )
            parse_started_at = started_at_dt.isoformat()
            rabbit_producer.send_task(
                f"parsing_{channel.type.value.lower()}",
                {
                    "type": "channel",
                    "user_id": channel.user_id,
                    "url": channel.link,
                    "channel_id": channel.id,
                    "accounts": [a.account_str for a in accounts],
                    "proxy_list": proxy_payload,
                    "parse_started_at": parse_started_at,
                }
            )
            print(f"📤 Отправлена задача для канала {channel.id} (тип: {channel.type.value})")
        except Exception as e:
            print(f"❌ Ошибка в задаче {task_id}: {e}")


async def dispatch_instagram_batch(reason: Optional[str] = None) -> bool:
    """Формирует и отправляет единую задачу batch-парсинга для всех Instagram-каналов."""
    async with SessionLocal() as session:
        channels_result = await session.execute(
            select(Channel).where(Channel.type == ChannelType.INSTAGRAM)
        )
        instagram_channels = channels_result.scalars().all()

        if not instagram_channels:
            print("ℹ️ Нет Instagram-каналов для batch-парсинга.")
            return False

        accounts_result = await session.execute(
            select(Account).where(Account.is_active.is_(True))
        )
        accounts = accounts_result.scalars().all()

        proxies_result = await session.execute(select(Proxy))
        proxies = proxies_result.scalars().all()

    if not accounts:
        print("⚠️ Нет активных аккаунтов для batch-парсинга Instagram.")
        return False

    proxy_payload = [p.proxy_str for p in proxies if p.for_likee is not True]
    parse_started_at = datetime.now(MOSCOW_TZ).isoformat()
    batch_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{len(instagram_channels)}"
    _mark_instagram_batch_state(True, batch_id=batch_id)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_auto_release_instagram_batch(batch_id))
    except RuntimeError:
        pass

    payload = {
        "type": "instagram_batch",
        "channels": [
            {
                "channel_id": channel.id,
                "url": channel.link,
                "user_id": channel.user_id,
                "parse_started_at": parse_started_at,
            }
            for channel in instagram_channels
        ],
        "accounts": [account.account_str for account in accounts],
        "proxy_list": proxy_payload,
        "parse_started_at": parse_started_at,
        "batch_id": batch_id,
    }

    rabbit_producer.send_task("parsing_instagram", payload)
    message = f"📤 Отправлена batch-задача Instagram на {len(instagram_channels)} каналов (batch_id={batch_id})"
    if reason:
        message += f" ({reason})"
    print(message)
    return True
