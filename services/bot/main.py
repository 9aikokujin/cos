# Жекина стата не зашла, сделаем через апишку
from datetime import datetime, timedelta

import asyncio
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
import aio_pika
from aio_pika import Connection, Queue, Message
import httpx

from config import config


bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command(commands=["start"]))
async def start_command(message: types.Message):
    await message.answer("Бот запущен и ожидает задачи из RabbitMQ")


async def get_analytics(params: dict = None):
    """Получаем аналитику пользователя."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "http://analytics-api:8000/analytics/analytics",
                params=params or {}
            )
            response.raise_for_status()
            data = response.json()
            return data
        except httpx.RequestError as e:
            print(f"Ошибка запроса: {e}")
            return None
        except httpx.HTTPStatusError as e:
            print(f"HTTP ошибка: {e.response.status_code}")
            return None


async def generator_message(user_id):
    """Генерируем сообщение для пользователя."""
    yesterday = datetime.now() - timedelta(days=1)
    yesterday_date = yesterday.strftime("%Y-%m-%d")

    analytics = await get_analytics({
        "user_id": user_id,
        "group_by": "day",
        "date_from": yesterday_date,
        "date_to": yesterday_date
    })

    if analytics and len(analytics) > 0:
        data = analytics[0]
        views = data.get("total_views", 0)
        day = data.get("day", yesterday_date)

        if views >= 1000000:
            message = f"📅 Вчера ({day})\n📊 Ваши просмотры составили 📈\n{views:,} 👀\n\nОтличный результат! 🎉👏"
        elif views >= 100000:
            message = f"📅 Вчера ({day})\n📊 Ваши просмотры: 📈\n{views:,} 👀\n\nПродолжайте в том же духе! 💪"
        elif views >= 10000:
            message = f"📅 Вчера ({day})\n📊 Ваша активность: 📊\n{views:,} просмотров 👀\n\nОтличная работа! 🌟"
        else:
            message = f"📅 Вчера ({day})\n📊 Ваши просмотры: 📈\n{views:,} 👀\n\nСпасибо за ваш труд! ❤️"
    else:
        message = f"📅 Вчера ({yesterday_date})\n📊 К сожалению, просмотры не были зафиксированы 🤔\n\nПопробуйте сделать интересный контент! 🎯\n\nЕсли вы впервые здесь, возвращайтесь завтра, чтобы посмотреть статистику за сегодня! 🔄"

    return message


async def process_task(message: aio_pika.IncomingMessage):
    """Обрабатываем задачу из очереди."""
    try:
        task_data = json.loads(message.body.decode('utf-8'))
        user_id = task_data.get("user_id")
        user_tg_id = task_data.get("user_tg_id")

        if not user_id:
            print("user_id не указан в задаче")
            await message.ack()
            return

        text = await generator_message(user_id)

        await bot.send_message(chat_id=user_tg_id, text=text)

    except Exception as e:
        print(f"Ошибка обработки задачи: {e}")

    await message.ack()


async def start_rabbitmq():
    """Запускаем RabbitMQ."""
    while True:
        try:
            connection = await aio_pika.connect_robust(config.RABBITMQ_URL)
            channel = await connection.channel()

            queue = await channel.declare_queue(config.RABBITMQ_QUEUE, durable=True)

            await queue.consume(process_task, no_ack=False)
            print("Ожидание задач из RabbitMQ...")

            return connection

        except Exception as e:
            print(f"Ошибка подключения к RabbitMQ: {e}")
            print("Повторная попытка подключения через 5 секунд...")
            await asyncio.sleep(5)


async def main():
    """Запускаем бота."""
    bot_task = asyncio.create_task(dp.start_polling(bot))

    rabbitmq_connection = await start_rabbitmq()

    if rabbitmq_connection:
        try:
            await bot_task
        except KeyboardInterrupt:
            print("Бот остановлен")
            await rabbitmq_connection.close()
    else:
        print("Не удалось подключиться к RabbitMQ")


if __name__ == "__main__":
    asyncio.run(main())
