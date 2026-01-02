import socket
import json
from datetime import datetime
from typing import Literal
from app.core.config import settings


class TCPLogger:
    """Логирование в Logstash через TCP."""
    def __init__(self, service_name: str, host: str, port: int):
        self.service_name = service_name
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.connect()

    def connect(self):
        """Устанавливает постоянное TCP-подключение."""
        try:
            if self.socket:
                self.socket.close()
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)
            self.socket.connect((self.host, self.port))
            self.connected = True
            print(f"✅ TCPLogger подключён к {self.host}:{self.port}")
        except Exception as e:
            self.connected = False
            self.socket = None
            print(f"❌ Не удалось подключиться к Logstash: {e}")

    def send(self, level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], message: str, **extra):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "message": message,
            "service": self.service_name,
            **extra
        }

        data = json.dumps(log_data) + "\n"  # Добавь \n — Logstash ожидает построчный ввод
        data_bytes = data.encode("utf-8")

        try:
            if not self.connected:
                self.connect()
                if not self.connected:
                    print("⚠️  Пропущено логирование (нет подключения к Logstash)")
                    return

            self.socket.sendall(data_bytes)

        except (ConnectionError, BrokenPipeError, OSError) as e:
            self.connected = False
            self.socket = None
            print(f"⚠️  Соединение с Logstash потеряно: {e}. Попробую переподключиться...")
            # При следующем вызове попробует снова
        except Exception as e:
            print(f"❌ Ошибка при отправке лога: {e}")

    def close(self):
        """Закрывает соединение."""
        if self.socket:
            self.socket.close()
            self.socket = None
        self.connected = False
        print("🔌 TCPLogger: соединение закрыто")
