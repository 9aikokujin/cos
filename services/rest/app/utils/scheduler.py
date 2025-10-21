# import time
# from app.core.db import SessionLocal
# from app.models.channel import Channel
# from app.models.videos import Videos
# from app.models.account import Account
# from app.models.proxy import Proxy
# from sqlalchemy import select
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# import logging
# import asyncio

# import random
# from app.utils.rabbitmq_producer import rabbit_producer

# scheduler = AsyncIOScheduler()


# async def restore_scheduled_tasks():
#     """Восстанавливает все активные задачи из БД при старте"""
#     async with SessionLocal() as session:
#         result = await session.execute(select(Channel))
#         tasks = result.scalars().all()

#         proxies_from_db = await session.execute(select(Proxy))
#         proxy = proxies_from_db.scalars().all()
#         proxies_for_send = [p.proxy_str for p in proxy]

#         accounts_from_db = await session.execute(select(Account).where(Account.is_active.is_(True)))
#         accounts = accounts_from_db.scalars().all()
#         accounts_for_send = [account.account_str for account in accounts]

#     await asyncio.sleep(300)
#     for task in tasks:
#         job_id = f"task_{task.id}"
#         if scheduler.get_job(job_id):
#             continue
#         type = task.type

#         rabbit_producer.send_task(
#             f"parsing_{type.value.lower()}",
#             {
#                 "type": "channel",
#                 "user_id": task.user_id,
#                 "url": f"{task.link}",
#                 "channel_id": task.id,
#                 "accounts": accounts_for_send,
#                 "proxy_list": proxies_for_send
#             }
#         )

#         scheduler.add_job(
#             process_recurring_task,
#             "interval",
#             hours=24,
#             args=[task.id, "channel"],
#             id=job_id,
#             max_instances=1,
#         )
#         # await asyncio.sleep(300)


# async def process_recurring_task(task_id: int, type: str):
#     """Функция для выполнения повторяющихся действий"""
#     print("Выполняем повторяющуюся задачу ")
#     if type == "channel":
#         async with SessionLocal() as db:
#             try:
#                 result = await db.execute(select(Channel).where(
#                     Channel.id == task_id))
#                 channel = result.scalar()
#                 accounts_from_db = await db.execute(select(Account).where(Account.is_active.is_(True)))
#                 accounts = accounts_from_db.scalars().all()
#                 accounts_for_send = []
#                 for account in accounts:
#                     accounts_for_send.append(account.account_str)

#                 proxy_from_db = await db.execute(select(Proxy))
#                 proxy = proxy_from_db.scalars().all()
#                 proxies_for_send = []
#                 for p in proxy:
#                     proxies_for_send.append(p.proxy_str)

#                 if channel:
#                     print(f"✅ Начата задача {task_id}")
#                     rabbit_producer.send_task(
#                         f"parsing_{channel.type.value.lower()}",
#                         {
#                             "type": "channel",
#                             "user_id": channel.user_id,
#                             "url": f"{channel.link}",
#                             "channel_id": channel.id,
#                             "accounts": accounts_for_send,
#                             "proxy_list": proxies_for_send
#                         }
#                     )
#                 else:
#                     print(f"❌ Задача {task_id} не найдена")
#             except Exception as e:
#                 print(f"❌ Ошибка при инициализации БД: {e}")
#                 raise e



import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.db import SessionLocal
from app.models.channel import Channel
from app.models.account import Account
from app.models.proxy import Proxy
from sqlalchemy import select
from app.utils.rabbitmq_producer import rabbit_producer

PARSER_INTERVAL = timedelta(minutes=5)
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
DAILY_START_HOUR = 5

_dispatch_lock = asyncio.Lock()
_last_dispatch_at: Optional[datetime] = None

scheduler = AsyncIOScheduler()


def _next_available_position(exclude_job_id: Optional[str] = None) -> int:
    used = set()
    for job in scheduler.get_jobs():
        if not job.id or not job.id.startswith("task_"):
            continue
        if job.id == exclude_job_id:
            continue
        position = job.kwargs.get("position") if job.kwargs else None
        if isinstance(position, int) and position >= 0:
            used.add(position)

    if not used:
        return 0
    return max(used) + 1


def _next_run_time_for_position(
    position: int,
    reference: Optional[datetime] = None,
    start_from_next_day: bool = False,
) -> datetime:
    """Возвращает ближайшее время запуска с якорем на DAILY_START_HOUR (мск) и шагом 5 минут."""
    if reference is None:
        reference_msk = datetime.now(MOSCOW_TZ)
    else:
        reference_msk = reference.astimezone(MOSCOW_TZ)

    base = reference_msk.replace(hour=DAILY_START_HOUR, minute=0, second=0, microsecond=0)
    slot = base + PARSER_INTERVAL * position

    if start_from_next_day or slot <= reference_msk:
        base += timedelta(days=1)
        slot = base + PARSER_INTERVAL * position

    return slot.astimezone(timezone.utc)


def schedule_channel_task(
    channel_id: int,
    position: Optional[int] = None,
    start_from_next_day: bool = False,
) -> datetime:
    """Создаёт или обновляет расписание парсинга канала согласно очереди."""
    job_id = f"task_{channel_id}"
    existing_job = scheduler.get_job(job_id)

    if position is None:
        if existing_job and existing_job.kwargs and isinstance(existing_job.kwargs.get("position"), int):
            position = existing_job.kwargs["position"]
        else:
            position = _next_available_position(exclude_job_id=job_id)

    next_run_time = _next_run_time_for_position(position, start_from_next_day=start_from_next_day)

    scheduler.add_job(
        func=process_recurring_task,
        trigger="interval",
        hours=24,
        args=[channel_id, "channel"],
        kwargs={"position": position},
        id=job_id,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
        next_run_time=next_run_time,
        replace_existing=True,
    )

    return next_run_time


async def restore_scheduled_tasks():
    """При старте: восстановить очередь и равномерно распределить каналы."""
    async with SessionLocal() as session:
        result = await session.execute(select(Channel))
        tasks = result.scalars().all()

    tasks = sorted(
        tasks,
        key=lambda t: (t.created_at or datetime.min.replace(tzinfo=timezone.utc), t.id),
    )

    for idx, task in enumerate(tasks):
        first_run = schedule_channel_task(task.id, position=idx)
        moscow_time = first_run.astimezone(MOSCOW_TZ)
        print(
            f"✅ Задача {task.id} запланирована: первый запуск в "
            f"{moscow_time.strftime('%H:%M %Z')}, затем каждые 24ч"
        )


async def _reserve_dispatch_slot() -> datetime:
    """Гарантирует выдержку не менее 5 минут между отправками задач."""
    global _last_dispatch_at

    async with _dispatch_lock:
        now = datetime.now(timezone.utc)

        if _last_dispatch_at is None:
            scheduled_time = now
        else:
            scheduled_time = max(_last_dispatch_at + PARSER_INTERVAL, now)

        delay = (scheduled_time - now).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)
            scheduled_time = datetime.now(timezone.utc)

        _last_dispatch_at = scheduled_time
        return scheduled_time


async def process_recurring_task(task_id: int, type: str, position: Optional[int] = None):
    """Отправляет задачу парсинга с актуальными данными из БД."""
    dispatched_at = await _reserve_dispatch_slot()
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
            print(
                "📤 Отправлена задача для канала "
                f"{channel.id} (тип: {channel.type.value}) в {dispatched_at.astimezone(MOSCOW_TZ).strftime('%H:%M %Z')}"
            )
        except Exception as e:
            print(f"❌ Ошибка в задаче {task_id}: {e}")
