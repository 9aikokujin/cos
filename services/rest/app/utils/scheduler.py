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
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.account import Account
from app.models.channel import Channel, ChannelType
from app.models.proxy import Proxy
from app.models.videos import Videos
from app.utils.rabbitmq_producer import rabbit_producer

MOSCOW_TZ = ZoneInfo("Europe/Moscow")

scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)


def schedule_channel_task(channel_id: int, *, run_immediately: bool = False) -> bool:
    job_id = f"task_{channel_id}"
    job = scheduler.add_job(
        func=process_recurring_task,
        trigger="cron",
        hour="5,23",
        minute=0,
        args=[channel_id, "channel"],
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
    if next_run:
        next_run_local = (
            next_run.astimezone(MOSCOW_TZ)
            if next_run.tzinfo
            else next_run.replace(tzinfo=MOSCOW_TZ)
        )
        print(
            f"✅ Задача {channel_id} запланирована: следующий запуск "
            f"{next_run_local.strftime('%d.%m %H:%M')} (мск), далее ежедневно в 05:00 и 23:00"
        )
    else:
        print(f"✅ Задача {channel_id} запланирована ежедневно в 05:00 и 23:00 (мск)")

    if run_immediately:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(process_recurring_task(channel_id, "channel"))
            immediate_dispatched = True
        except RuntimeError:
            print(f"⚠️ Не удалось инициировать немедленный запуск для канала {channel_id}: нет активного цикла событий")

    return immediate_dispatched


async def restore_scheduled_tasks():
    """При старте восстанавливает ежедневное расписание (05:00 и 23:00 мск) для всех каналов."""
    async with SessionLocal() as session:
        result = await session.execute(select(Channel))
        tasks = result.scalars().all()

    tasks = sorted(
        tasks,
        key=lambda task: (
            task.created_at or datetime.min.replace(tzinfo=timezone.utc),
            task.id,
        ),
    )

    for task in tasks:
        schedule_channel_task(task.id)


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
            if channel.type == ChannelType.LIKEE:
                proxy_payload = [p.proxy_str for p in proxies if p.for_likee is True]
            else:
                proxy_payload = [p.proxy_str for p in proxies]

            rabbit_producer.send_task(
                f"parsing_{channel.type.value.lower()}",
                {
                    "type": "channel",
                    "user_id": channel.user_id,
                    "url": channel.link,
                    "channel_id": channel.id,
                    "accounts": [a.account_str for a in accounts],
                    "proxy_list": proxy_payload,
                }
            )
            print(f"📤 Отправлена задача для канала {channel.id} (тип: {channel.type.value})")
        except Exception as e:
            print(f"❌ Ошибка в задаче {task_id}: {e}")
