import asyncio

from config import config
from core.parser import TikTokParser
from utils.logger import TCPLogger
from utils.rabbit_client import RabbitMQParserClient


# if __name__ == "__main__":
#     async def main():
#         print("Starting TikTok parser...", flush=True)
#         max_retries = 10
#         retry_delay = 3

#         for attempt in range(max_retries):
#             try:
#                 print(f"Attempt {attempt + 1}...")
#                 parser = TikTokParser(TCPLogger("tiktok_parser"))
#                 client = RabbitMQParserClient(
#                     amqp_url=config.RABBITMQ_URL,
#                     queue_name="parsing",
#                     logger=TCPLogger("tiktok_parser"),
#                     parser=parser
#                 )
#                 await client.consume()
#                 break

#             except Exception as e:
#                 if attempt < max_retries - 1:
#                     await asyncio.sleep(retry_delay)
#                 else:
#                     raise

#     asyncio.run(main())

# tiktok_parser

if __name__ == "__main__":
    async def main():
        try:
            print("Starting TikTok parser...", flush=True)
            await asyncio.sleep(60)
            parser = TikTokParser(TCPLogger("tiktok_parser"))
            client = RabbitMQParserClient(
                amqp_url=config.RABBITMQ_URL,
                queue_name="parsing_tiktok",
                logger=TCPLogger("tiktok_parser"),
                parser=parser
            )
            print("Attempting to start consuming messages...", flush=True)
            await client.consume()
            print("Consume loop finished (unexpected). Exiting.", flush=True)

        except Exception as e:
            print(f"Critical error occurred: {e}. Waiting 1 minute before exit...", flush=True)
            await asyncio.sleep(60)
            print("Exiting after error and delay.", flush=True)
            raise

    asyncio.run(main())
