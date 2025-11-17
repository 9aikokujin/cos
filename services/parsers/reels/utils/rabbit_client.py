import asyncio
import json
from typing import Optional

from aio_pika import connect_robust, IncomingMessage
import httpx
from config import config
from core.batch_runner import InstagramBatchRunner
from core.parser import InstagramParser
from utils.batch_state import BatchProgressStore
from utils.logger import TCPLogger


class RabbitMQParserClient:
    def __init__(
        self,
        amqp_url: str,
        queue_name: str,
        logger: TCPLogger,
        parser: InstagramParser,
        progress_store: Optional[BatchProgressStore] = None,
    ):
        self.amqp_url = amqp_url
        self.queue_name = queue_name
        self.logger = logger
        self.parser = parser
        self.connection = None
        self.channel = None
        self.queue = None
        self.progress_store = progress_store or BatchProgressStore(
            config.INSTAGRAM_BATCH_STATE_DIR
        )

    async def connect(self):
        self.connection = await connect_robust(self.amqp_url)
        self.channel = await self.connection.channel()
        self.queue = await self.channel.declare_queue(
            self.queue_name, durable=True)

    async def handle_message(self, message: IncomingMessage):
        async with message.process():
            task_data_str = message.body.decode()
            task_data = json.loads(task_data_str)
            url: str = task_data.get("url")
            task_type: str = task_data.get("type")
            user_id: int = task_data.get("user_id")
            channel_id: int = task_data.get("channel_id")
            accounts: list = task_data.get("accounts") or []
            proxy_list: list = task_data.get("proxy_list") or []
            parse_started_at = task_data.get("parse_started_at")

            accounts_count = len(accounts)
            proxies_count = len(proxy_list)
            self.logger.send(
                "INFO",
                f"Получена задача на парсинг {task_type}, пользователь: {user_id}, id: {url} "
                f"(аккаунтов: {accounts_count}, прокси: {proxies_count})",
            )
            print(
                f"Получена задача на парсинг {task_type}, пользователь: {user_id}, id: {url} "
                f"(аккаунтов: {accounts_count}, прокси: {proxies_count})"
            )
            if task_type == "channel":
                self.logger.send("INFO", f"Начал парсить канал {url}")
                data = await self.parser.parse_channel(
                            url=url,
                            channel_id=channel_id,
                            user_id=user_id,
                            max_retries=None,
                            accounts=accounts,
                            proxy_list=proxy_list,
                            parse_started_at=parse_started_at,
                        )
            elif task_type == "instagram_batch":
                batch_id = task_data.get("batch_id")
                runner = InstagramBatchRunner(
                    parser=self.parser,
                    logger=self.logger,
                    retries_per_channel=task_data.get("retries_per_channel", 1),
                    session_refresh_on_failure=task_data.get("session_refresh_on_failure", True),
                    collect_attempts=task_data.get("collect_attempts", 3),
                    channels_api_url=config.CHANNELS_API_URL,
                    channels_api_token=config.CHANNELS_API_TOKEN,
                    channels_per_wave=task_data.get("channels_per_wave", 4),
                    pause_between_waves_seconds=task_data.get("pause_between_waves_seconds", 300),
                    progress_store=self.progress_store,
                )
                batch_tasks = task_data.get("channels") or []
                if not batch_tasks:
                    self.logger.send("INFO", "ℹ️ Batch-задача не содержит каналов — загружаем их из API.")
                    batch_tasks = await runner.fetch_channels_from_api()

                if not batch_tasks:
                    self.logger.send("INFO", "⚠️ Нет каналов для batch-парсинга, задача пропущена.")
                    return

                self.logger.send("INFO", f"🚀 Batch Instagram: получено {len(batch_tasks)} каналов.")
                try:
                    await runner.run(
                        channel_tasks=batch_tasks,
                        accounts=accounts,
                        proxy_list=proxy_list,
                        max_retries=task_data.get("max_retries"),
                        batch_id=batch_id,
                    )
                finally:
                    if batch_id:
                        await self._notify_batch_release(batch_id)

            # if task_type == "video":
            #     self.logger.send("INFO", f"Начал парсить видео {url}")
            #     data = await self.parser.parse_video(
            #         url, 1, 1, 1, 3, proxy_list, accounts)

    async def consume(self):
        await self.connect()
        self.logger.send("INFO", f"Подключен к RabbitMQ, ожидаю задачи в очереди '{self.queue_name}'...")
        print(f"Подключен к RabbitMQ, ожидаю задачи в очереди '{self.queue_name}'")
        await self.queue.consume(self.handle_message, no_ack=False)

        await asyncio.Future()

    async def _notify_batch_release(self, batch_id: str):
        if self.progress_store:
            self.progress_store.clear(batch_id)
        callback_url = getattr(config, "INSTAGRAM_BATCH_CALLBACK_URL", None)
        token = getattr(config, "INSTAGRAM_BATCH_CALLBACK_TOKEN", None)
        if not callback_url:
            return
        payload = {"batch_id": batch_id, "token": token or ""}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(callback_url, json=payload)
                resp.raise_for_status()
                self.logger.send("INFO", f"📬 Уведомили сервис о завершении batch {batch_id}")
        except Exception as exc:
            self.logger.send("INFO", f"⚠️ Не удалось уведомить о завершении batch {batch_id}: {exc}")
