import pika
import json
import logging
from typing import Any, Dict
from app.core.config import settings


class RabbitMQProducer:
    """Продюсер RabbitMQ."""
    def __init__(
            self,
            host: str = 'localhost',
            port: int = 5672,
            username: str = 'guest',
            password: str = 'guest'
    ):
        """
        Инициализация продюсера RabbitMQ.
        :param host: Хост RabbitMQ
        :param port: Порт
        :param username: Логин
        :param password: Пароль
        """
        self.connection_params = pika.ConnectionParameters(
            host=host,
            port=port,
            credentials=pika.PlainCredentials(username, password),
            heartbeat=65535,
            blocked_connection_timeout=300,
        )
        self.connection = None
        self.channel = None

    def connect(self):
        """Устанавливает соединение с RabbitMQ и создаёт канал."""
        try:
            self.connection = pika.BlockingConnection(self.connection_params)
            self.channel = self.connection.channel()
            print("✅ Подключение к RabbitMQ установлено")
        except Exception as e:
            logging.error(f"❌ Ошибка подключения к RabbitMQ: {e}")
            raise

    def declare_queue(self, queue_name: str, durable: bool = True):
        """
        Объявляет очередь.
        :param queue_name: Название очереди
        :param durable: Сохранять ли очередь при перезапуске брокера
        """
        if not self.channel:
            raise RuntimeError("Канал не инициализирован. Вызовите connect() сначала.")

        self.channel.queue_declare(queue=queue_name, durable=durable)

    def send_task(self, queue_name: str, task_data: Dict[str, Any]):
        if not self.channel:
            raise RuntimeError("Канал не инициализирован. Вызовите connect() сначала.")

        try:
            body = json.dumps(task_data, ensure_ascii=False)
            print(f"📤 Отправляется тело: {body}")
            print("📋 Content-Type: application/json")

            self.channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    content_type='application/json'
                )
            )
            print(f"✅ Задача отправлена: {task_data}")
        except Exception as e:
            logging.error(f"❌ Ошибка: {e}")
            raise

    def close(self):
        """Закрывает соединение."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            print("🔌 Соединение с RabbitMQ закрыто")

    def __enter__(self):
        """Поддержка контекстного менеджера (with)."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматически закрывает соединение после выхода из with."""
        self.close()


rabbit_producer = RabbitMQProducer(
    host=settings.COS_RABBITMQ_HOST, port=5672,
    username=settings.COS_RABBITMQ_USER,
    password=settings.COS_RABBITMQ_PASSWORD
)
