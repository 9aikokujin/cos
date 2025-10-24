from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI
from sqlalchemy.sql.expression import select
from app.api.v1.endpoints import user, channel, proxy, videos, account, videohistory
from app.core.db import SessionLocal
from app.models.user import User, UserRole
from app.services.user import UserService
from app.core.config import settings
from app.utils.logger import TCPLogger
from app.utils.rabbitmq_producer import rabbit_producer
from app.utils import logger
from app.utils.scheduler import restore_scheduled_tasks, scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Приложение стартует...")
    async with SessionLocal() as db:
        try:
            result = await db.execute(select(User).where(User.role == UserRole.ADMIN))
            admin = result.first()

            if admin is None:
                new_admin = User(
                    tg_id=settings.TELEGRAM_ADMIN_ID,
                    username="admin",
                    role=UserRole.ADMIN
                )
                db.add(new_admin)
                await db.commit()
                await db.refresh(new_admin)
                print("✅ Администратор создан")
            else:
                print("✅ Администратор уже существует (найден хотя бы один)")

        except Exception as e:
            print(f"❌ Ошибка при инициализации БД: {e}")
            raise e
    # 2. Инициализация RabbitMQ
    # try:
    #     rabbit_producer.connect()
    #     rabbit_producer.declare_queue("parsing", durable=True)
    #     print("✅ RabbitMQ: соединение установлено и очередь объявлена")
    # except Exception as e:
    #     print(f"❌ Не удалось подключиться к RabbitMQ: {e}")
    #     raise
    # await restore_scheduled_tasks()
    # scheduler.start()

    # 3. Инициализация TCPLogger
    # global logger
    # try:
    #     logger = TCPLogger(
    #         service_name="sn_rest",
    #         host=settings.SN_LOGSTASH_HOST,
    #         port=5044
    #     )
    #     print(f"✅ TCPLogger подключён к {settings.SN_LOGSTASH_HOST}:5044")
    # except Exception as e:
    #     print(f"❌ Не удалось подключиться к Logstash: {e}")
    #     logger = None

    yield

    # 4. Завершение
    print("🛑 Приложение останавливается...")
    scheduler.shutdown()
    # if hasattr(logger, "close") and logger is not None:
    #     logger.close()

api_router = APIRouter(lifespan=lifespan)

api_router.include_router(user.router, prefix="/users",
                          tags=["Users"])
api_router.include_router(channel.router, prefix="/channels",
                          tags=["Channels"])
api_router.include_router(proxy.router, prefix="/proxies",
                          tags=["Proxies"])
api_router.include_router(videos.router, prefix="/videos",
                          tags=["Videos"])
api_router.include_router(account.router, prefix="/accounts",
                          tags=["Accounts"])
api_router.include_router(videohistory.router, prefix="/videohistory",
                          tags=["VideoHistory"])
