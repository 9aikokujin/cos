from playwright.async_api import async_playwright
import asyncio
import re
import aio_pika
import json
import socket
import logging
import time
import sys

from config import config
from core.parser import ShortsParser
from utils.logger import TCPLogger
from utils.rabbit_client import RabbitMQParserClient


if __name__ == "__main__":
    async def main():
        """Запускаем парсер Ютуба."""
        try:
            print("Начал парсить Ютуб...", flush=True)
            await asyncio.sleep(60)
            parser = ShortsParser(TCPLogger("shorts_parser"))
            client = RabbitMQParserClient(
                amqp_url=config.RABBITMQ_URL,
                queue_name="parsing_youtube",
                logger=TCPLogger("shorts_parser"),
                parser=parser
            )
            print("Начал потреблять сообщения из очереди...", flush=True)
            await client.consume()
            print("Потребление сообщений из очереди завершено. Выход.", flush=True)

        except Exception as e:
            logging.error(f"Ошибка при парсинге: {e}", exc_info=True)
            print(f"Ошибка при парсинге: {e}. Ожидание 1 минуты перед выходом...", flush=True)
            await asyncio.sleep(60)
            print("Выход после ошибки и задержки.", flush=True)
            raise

    asyncio.run(main())
