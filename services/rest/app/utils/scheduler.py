from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.db import SessionLocal
from app.models.channel import Channel
from app.models.videos import Videos
from app.models.account import Account
from app.models.proxy import Proxy
from sqlalchemy import select
from app.utils.rabbitmq_producer import rabbit_producer

scheduler = AsyncIOScheduler()


async def restore_scheduled_tasks():
    """При старте: запустить парсинг всех каналов с интервалом 5 минут, затем повторять каждые 24ч."""
    async with SessionLocal() as session:
        result = await session.execute(select(Channel))
        tasks = result.scalars().all()

    now = datetime.now(timezone.utc)

    tasks = sorted(
        tasks,
        key=lambda task: (
            task.created_at or datetime.min.replace(tzinfo=timezone.utc),
            task.id,
        ),
    )

    for idx, task in enumerate(tasks):
        job_id = f"task_{task.id}"
        if scheduler.get_job(job_id):
            continue

        # Первый запуск: через (idx * 5) минут после старта
        first_run = now + timedelta(minutes=5 * idx)

        scheduler.add_job(
            func=process_recurring_task,
            trigger="interval",
            hours=24,
            args=[task.id, "channel"],
            id=job_id,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,  # 10 минут на опоздание
            next_run_time=first_run  # ← вот ключ!
        )
        print(f"✅ Задача {task.id} запланирована: первый запуск в {first_run.strftime('%H:%M')}, затем каждые 24ч")


async def process_recurring_task(task_id: int, type: str):
    """Отправляет задачу парсинга с актуальными данными из БД."""
    async with SessionLocal() as db:
        try:
            channel = (await db.execute(select(Channel).where(Channel.id == task_id))).scalar()
            if not channel:
                scheduler.remove_job(f"task_{task_id}")
                return

            # Получаем свежие аккаунты и прокси
            accounts = (await db.execute(select(Account).where(Account.is_active.is_(True)))).scalars().all()
            proxies = (await db.execute(select(Proxy))).scalars().all()

            rabbit_producer.send_task(
                f"parsing_{channel.type.value.lower()}",
                {
                    "type": "channel",
                    "user_id": channel.user_id,
                    "url": channel.link,
                    "channel_id": channel.id,
                    "accounts": [a.account_str for a in accounts],
                    "proxy_list": [p.proxy_str for p in proxies],
                }
            )
            print(f"📤 Отправлена задача для канала {channel.id} (тип: {channel.type.value})")
        except Exception as e:
            print(f"❌ Ошибка в задаче {task_id}: {e}")


# import asyncio
# from datetime import datetime, timedelta, timezone
# from typing import Optional
# from zoneinfo import ZoneInfo
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from app.core.db import SessionLocal
# from app.models.channel import Channel
# from app.models.account import Account
# from app.models.proxy import Proxy
# from sqlalchemy import select
# from app.utils.rabbitmq_producer import rabbit_producer

# PARSER_INTERVAL = timedelta(minutes=5)
# MOSCOW_TZ = ZoneInfo("Europe/Moscow")
# DAILY_START_HOUR = 5

# _dispatch_lock = asyncio.Lock()
# _last_dispatch_at: Optional[datetime] = None

# scheduler = AsyncIOScheduler()


# def _next_available_position(exclude_job_id: Optional[str] = None) -> int:
#     used = set()
#     for job in scheduler.get_jobs():
#         if not job.id or not job.id.startswith("task_"):
#             continue
#         if job.id == exclude_job_id:
#             continue
#         position = job.kwargs.get("position") if job.kwargs else None
#         if isinstance(position, int) and position >= 0:
#             used.add(position)

#     if not used:
#         return 0
#     return max(used) + 1


# def _next_run_time_for_position(
#     position: int,
#     reference: Optional[datetime] = None,
#     start_from_next_day: bool = False,
# ) -> datetime:
#     """Возвращает ближайшее время запуска с учётом DAILY_START_HOUR (мск) и шага 5 минут."""
#     if reference is None:
#         reference_msk = datetime.now(MOSCOW_TZ)
#     else:
#         reference_msk = reference.astimezone(MOSCOW_TZ)

#     base = reference_msk.replace(hour=DAILY_START_HOUR, minute=0, second=0, microsecond=0)
#     slot = base + PARSER_INTERVAL * position

#     if start_from_next_day or slot <= reference_msk:
#         base += timedelta(days=1)
#         slot = base + PARSER_INTERVAL * position

#     return slot.astimezone(timezone.utc)


# def schedule_channel_task(
#     channel_id: int,
#     position: Optional[int] = None,
#     start_from_next_day: bool = False,
# ) -> datetime:
#     """Создаёт или обновляет расписание парсинга канала в очереди."""
#     job_id = f"task_{channel_id}"
#     existing_job = scheduler.get_job(job_id)

#     if position is None:
#         if existing_job and existing_job.kwargs and isinstance(existing_job.kwargs.get("position"), int):
#             position = existing_job.kwargs["position"]
#         else:
#             position = _next_available_position(exclude_job_id=job_id)

#     next_run_time = _next_run_time_for_position(position, start_from_next_day=start_from_next_day)

#     scheduler.add_job(
#         func=process_recurring_task,
#         trigger="interval",
#         hours=24,
#         args=[channel_id, "channel"],
#         kwargs={"position": position},
#         id=job_id,
#         max_instances=1,
#         coalesce=True,
#         misfire_grace_time=600,
#         next_run_time=next_run_time,
#         replace_existing=True,
#     )

#     return next_run_time


# async def restore_scheduled_tasks():
#     """При старте: запустить парсинг всех каналов с интервалом 5 минут, затем повторять каждые 24ч."""
#     async with SessionLocal() as session:
#         result = await session.execute(select(Channel))
#         tasks = result.scalars().all()

#     # Стартуем в порядке создания, чтобы сохранялся привычный приоритет
#     tasks = sorted(tasks, key=lambda t: (t.created_at or datetime.min.replace(tzinfo=timezone.utc), t.id))

#     for idx, task in enumerate(tasks):
#         job_id = f"task_{task.id}"
#         if scheduler.get_job(job_id):
#             continue

#         first_run = schedule_channel_task(task.id, position=idx)
#         moscow_time = first_run.astimezone(MOSCOW_TZ)
#         print(
#             f"✅ Задача {task.id} запланирована: первый запуск в "
#             f"{moscow_time.strftime('%H:%M %Z')}, затем каждые 24ч"
#         )


# async def _reserve_dispatch_slot() -> datetime:
#     """Гарантирует минимальный интервал между отправками задач."""
#     global _last_dispatch_at

#     async with _dispatch_lock:
#         now = datetime.now(timezone.utc)

#         if _last_dispatch_at is None:
#             scheduled_time = now
#         else:
#             scheduled_time = max(_last_dispatch_at + PARSER_INTERVAL, now)

#         delay = (scheduled_time - now).total_seconds()
#         if delay > 0:
#             await asyncio.sleep(delay)
#             scheduled_time = datetime.now(timezone.utc)

#         _last_dispatch_at = scheduled_time
#         return scheduled_time


# async def process_recurring_task(task_id: int, type: str, position: Optional[int] = None):
#     """Отправляет задачу парсинга с актуальными данными из БД."""
#     dispatched_at = await _reserve_dispatch_slot()
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
#             print(
#                 "📤 Отправлена задача для канала "
#                 f"{channel.id} (тип: {channel.type.value}) в {dispatched_at.astimezone(MOSCOW_TZ).strftime('%H:%M %Z')}"
#             )
#         except Exception as e:
#             print(f"❌ Ошибка в задаче {task_id}: {e}")
