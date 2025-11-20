import asyncio

from config import config
from core.parser import TikTokParser
from utils.logger import TCPLogger
from utils.rabbit_client import RabbitMQParserClient

# Сколько воркеров одновременно поднимать. Меняйте число явно здесь.
WORKER_COUNT = 1


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


async def run_worker(worker_id: int):
    """
    Запускает отдельного воркера с собственным экземпляром парсера.
    Каждый воркер открывает своё подключение к RabbitMQ и обрабатывает задачи независимо.
    """
    logger = TCPLogger(f"tiktok_parser_{worker_id}")
    parser = TikTokParser(logger)
    client = RabbitMQParserClient(
        amqp_url=config.RABBITMQ_URL,
        queue_name="parsing_tiktok",
        logger=logger,
        parser=parser,
    )

    # Бесконечный перезапуск при ошибках подключения, чтобы воркер не умирал навсегда.
    while True:
        try:
            print(f"[worker {worker_id}] Starting consumer...", flush=True)
            await client.consume()
            print(f"[worker {worker_id}] Consumer exited unexpectedly, restarting...", flush=True)
        except Exception as e:
            print(f"[worker {worker_id}] Critical error: {e}. Restart in 15s...", flush=True)
            await asyncio.sleep(15)


if __name__ == "__main__":
    async def main():
        try:
            print("Starting TikTok parser workers...", flush=True)
            await asyncio.sleep(60)

            worker_count = max(1, int(WORKER_COUNT))
            tasks = [asyncio.create_task(run_worker(i + 1)) for i in range(worker_count)]
            print(f"Spawned {worker_count} worker(s).", flush=True)
            await asyncio.gather(*tasks)

        except Exception as e:
            print(f"Critical error occurred: {e}. Waiting 1 minute before exit...", flush=True)
            await asyncio.sleep(60)
            print("Exiting after error and delay.", flush=True)
            raise

    asyncio.run(main())
