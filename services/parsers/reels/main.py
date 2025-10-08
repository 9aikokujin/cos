import asyncio


from config import config
from core.parser import InstagramParser
from utils.logger import TCPLogger
from utils.rabbit_client import RabbitMQParserClient


# if __name__ == "__main__":
#     async def main():
#         max_retries = 10
#         retry_delay = 3

#         for attempt in range(max_retries):
#             try:
#                 parser = InstagramParser(TCPLogger("instagram_parser"))
#                 client = RabbitMQParserClient(
#                     amqp_url=config.RABBITMQ_URL,
#                     queue_name="parsing",
#                     logger=TCPLogger("instagram_parser"),
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


if __name__ == "__main__":
    async def main():
        try:
            print("Starting Shorts parser...", flush=True)
            await asyncio.sleep(60)
            parser = InstagramParser(TCPLogger("instagram_parser"))
            client = RabbitMQParserClient(
                amqp_url=config.RABBITMQ_URL,
                queue_name="parsing_instagram",
                logger=TCPLogger("instagram_parser"),
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
