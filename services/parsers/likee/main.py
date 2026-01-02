import asyncio


from config import config
from core.parser import LikeeParser
from utils.logger import TCPLogger
from utils.rabbit_client import RabbitMQParserClient


if __name__ == "__main__":
    async def main():
        """Запускаем парсер Likee."""
        try:
            print("Начал парсить Likee...", flush=True)
            await asyncio.sleep(60)
            parser = LikeeParser(TCPLogger("likee_parser"))
            client = RabbitMQParserClient(
                amqp_url=config.RABBITMQ_URL,
                queue_name="parsing_likee",
                logger=TCPLogger("likee_parser"),
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
