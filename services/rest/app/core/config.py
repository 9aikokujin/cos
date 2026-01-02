from pydantic_settings import BaseSettings

from dotenv import load_dotenv


load_dotenv()


class Settings(BaseSettings):
    """Настройки."""
    DATABASE_URL: str
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_ADMIN_ID: int

    COS_LOGSTASH_PORT: int | str
    COS_LOGSTASH_HOST: str

    COS_RABBITMQ_USER: str
    COS_RABBITMQ_PASSWORD: str
    COS_RABBITMQ_HOST: str
    INSTAGRAM_BATCH_CONTROL_TOKEN: str | None = None

    model_config = {
        "env_file": ".env"
    }


settings = Settings()
