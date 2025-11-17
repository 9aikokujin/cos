import asyncio
import json

from aio_pika import connect_robust, IncomingMessage
from config import config
from core.batch_runner import InstagramBatchRunner
from core.parser import InstagramParser
from utils.logger import TCPLogger


class RabbitMQParserClient:
    def __init__(self, amqp_url: str, queue_name: str,
                 logger: TCPLogger, parser: InstagramParser):
        self.amqp_url = amqp_url
        self.queue_name = queue_name
        self.logger = logger
        self.parser = parser
        self.connection = None
        self.channel = None
        self.queue = None

    async def connect(self):
        self.connection = await connect_robust(self.amqp_url)
        self.channel = await self.connection.channel()
        self.queue = await self.channel.declare_queue(
            self.queue_name, durable=True)

    async def handle_message(self, message: IncomingMessage):
        async with message.process():
            task_data_str = message.body.decode()
            print(task_data_str)
            task_data = json.loads(task_data_str)
            url: str = task_data.get("url")
            task_type: str = task_data.get("type")
            user_id: int = task_data.get("user_id")
            channel_id: int = task_data.get("channel_id")
            accounts: list = task_data.get("accounts") or []
            proxy_list: list = task_data.get("proxy_list") or []
            parse_started_at = task_data.get("parse_started_at")

            self.logger.send("INFO", f"Получена задача на парсинг {task_type}, пользователь: {user_id}, id: {url} с аккаунтами: {accounts} и прокси: {proxy_list}")
            print(f"Получена задача на парсинг {task_type}, пользователь: {user_id}, id: {url}")
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
                runner = InstagramBatchRunner(
                    parser=self.parser,
                    logger=self.logger,
                    retries_per_channel=task_data.get("retries_per_channel", 1),
                    session_refresh_on_failure=task_data.get("session_refresh_on_failure", True),
                    collect_attempts=task_data.get("collect_attempts", 3),
                    channels_api_url=config.CHANNELS_API_URL,
                    channels_api_token=config.CHANNELS_API_TOKEN,
                )
                batch_tasks = task_data.get("channels") or []
                if not batch_tasks:
                    self.logger.send("INFO", "ℹ️ Batch-задача не содержит каналов — загружаем их из API.")
                    batch_tasks = await runner.fetch_channels_from_api()

                if not batch_tasks:
                    self.logger.send("INFO", "⚠️ Нет каналов для batch-парсинга, задача пропущена.")
                    return

                self.logger.send("INFO", f"🚀 Batch Instagram: получено {len(batch_tasks)} каналов.")
                await runner.run(
                    channel_tasks=batch_tasks,
                    accounts=accounts,
                    proxy_list=proxy_list,
                    max_retries=task_data.get("max_retries"),
                )

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
