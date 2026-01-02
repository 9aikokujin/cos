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
        """Запускаем парсер Инстаграма."""
        try:
            print("Начал парсить Инстаграм...", flush=True)
            await asyncio.sleep(60)
            parser = InstagramParser(TCPLogger("instagram_parser"))
            client = RabbitMQParserClient(
                amqp_url=config.RABBITMQ_URL,
                queue_name="parsing_instagram",
                logger=TCPLogger("instagram_parser"),
                parser=parser
            )
            print("Начал потреблять сообщения из очереди...", flush=True)
            await client.consume()
            print("Потребление сообщений из очереди завершено. Выход.", flush=True)

        except Exception as e:
            print(f"Ошибка при парсинге: {e}. Ожидание 1 минуты перед выходом...", flush=True)
            await asyncio.sleep(60)
            print("Выход после ошибки и задержки.", flush=True)
            raise

    asyncio.run(main())
