from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    RABBITMQ_URL: str
    CLICKHOUSE_URL: str
    LOGSTASH_HOST: str
    LOGSTASH_PORT: int

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


config = Config()
