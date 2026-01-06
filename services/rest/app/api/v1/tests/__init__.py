import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "dummy")
os.environ.setdefault("TELEGRAM_ADMIN_ID", "1")
os.environ.setdefault("COS_LOGSTASH_PORT", "0")
os.environ.setdefault("COS_LOGSTASH_HOST", "localhost")
os.environ.setdefault("COS_RABBITMQ_USER", "guest")
os.environ.setdefault("COS_RABBITMQ_PASSWORD", "guest")
os.environ.setdefault("COS_RABBITMQ_HOST", "localhost")