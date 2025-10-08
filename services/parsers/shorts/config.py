from pydantic_settings import BaseSettings


class Config(BaseSettings):
    RABBITMQ_URL: str
    CLICKHOUSE_URL: str
    LOGSTASH_HOST: str
    LOGSTASH_PORT: int

    model_config = {
        "env_file": ".env"
    }


config = Config()
