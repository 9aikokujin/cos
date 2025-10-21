import asyncio
import json

from aio_pika import connect_robust, IncomingMessage
from core.parser import LikeeParser
from utils.logger import TCPLogger


class RabbitMQParserClient:
    def __init__(self, amqp_url: str, queue_name: str,
                 logger: TCPLogger, parser: LikeeParser):
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
            proxy_list: list = task_data.get("proxy_list")

            self.logger.send("INFO", f"Получена задача на парсинг {task_type}, пользователь: {user_id}, id: {url} и прокси: {proxy_list}")
            print(f"Получена задача на парсинг {task_type}, пользователь: {user_id}, id: {url}")
            if task_type == "channel":
                self.logger.send("INFO", f"Начал парсить канал {url}")
                data = await self.parser.parse_channel(
                    url,
                    channel_id,
                    user_id,
                    proxy_list=proxy_list,
                    max_retries=3,
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
