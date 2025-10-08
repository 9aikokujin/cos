import socket
import json
from datetime import datetime
from typing import Literal
from config import config


class TCPLogger:
    def __init__(self, service_name: str):
        self.host = config.LOGSTASH_HOST
        self.port = config.LOGSTASH_PORT
        self.service_name = service_name

    def send(self, level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], message: str, **extra):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "message": message,
            "service": self.service_name,
            **extra
        }

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.host, self.port))
                s.sendall(json.dumps(log_data).encode("utf-8"))
        except Exception as e:
            print(f"Failed to send log: {e}")
