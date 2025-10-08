from pydantic_settings import BaseSettings, SettingsConfigDict

class Config(BaseSettings):
    CLICKHOUSE_HOST: str = "localhost"
    CLICKHOUSE_PORT: int = 8123
    CLICKHOUSE_USER: str = "default"
    CLICKHOUSE_PASSWORD: str = ""
    CLICKHOUSE_DATABASE: str = "default"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

config = Config()
