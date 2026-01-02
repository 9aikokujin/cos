from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Конфигурация парсера Инстаграма."""
    RABBITMQ_URL: str
    CLICKHOUSE_URL: str
    LOGSTASH_HOST: str
    LOGSTASH_PORT: int
    CHANNELS_API_URL: str
    CHANNELS_API_TOKEN: str | None
    INSTAGRAM_BATCH_CALLBACK_URL: str
    INSTAGRAM_BATCH_CALLBACK_TOKEN: str | None = None
    INSTAGRAM_BATCH_STATE_DIR: str = "/app/storage/instagram_batch_state"

    model_config = {
        "env_file": ".env"
    }


config = Config()
