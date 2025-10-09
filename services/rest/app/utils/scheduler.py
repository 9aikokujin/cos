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

    for idx, task in enumerate(tasks):
        job_id = f"task_{task.id}"
        if scheduler.get_job(job_id):
            continue

        # Первый запуск: через (idx * 5) минут после старта
        first_run = now + timedelta(minutes=5 * idx)  # первая задача — сразу (0 мин), вторая — через 5 и т.д.

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
