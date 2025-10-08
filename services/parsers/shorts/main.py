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
        try:
            print("Starting Shorts parser...", flush=True)
            await asyncio.sleep(60)
            parser = ShortsParser(TCPLogger("shorts_parser"))
            client = RabbitMQParserClient(
                amqp_url=config.RABBITMQ_URL,
                queue_name="parsing_youtube",
                logger=TCPLogger("shorts_parser"),
                parser=parser
            )
            print("Attempting to start consuming messages...", flush=True)
            await client.consume()
            print("Consume loop finished (unexpected). Exiting.", flush=True)

        except Exception as e:
            logging.error(f"Critical error in main parser loop: {e}", exc_info=True)
            print(f"Critical error occurred: {e}. Waiting 1 minute before exit...", flush=True)
            await asyncio.sleep(60)
            print("Exiting after error and delay.", flush=True)
            raise

    asyncio.run(main())
