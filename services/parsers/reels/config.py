from pydantic_settings import BaseSettings


class Config(BaseSettings):
    RABBITMQ_URL: str
    CLICKHOUSE_URL: str
    LOGSTASH_HOST: str
    LOGSTASH_PORT: int
    CHANNELS_API_URL: str = "https://cosmeya.dev-klick.cyou/api/v1/channels/all?type=instagram"
    CHANNELS_API_TOKEN: str | None = (
        "query_id=AAEtOXcbAAAAAC05dxs04sx3&user=%7B%22id%22%3A460798253%2C%22first_name%22%3A%22Eugene%22%2C"
        "%22last_name%22%3A%22Kochetov%22%2C%22username%22%3A%22Eugene_Kochetov%22%2C%22language_code%22%3A%22ru"
        "%22%2C%22is_premium%22%3Atrue%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A%5C%2F"
        "%5C%2Ft.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2F40kwrcUPBycbARBmx1BrKoFRq2p8kFSjB5qp1pOjjYM.svg%22%7D&"
        "auth_date=1756811077&signature=sGPn4HKdOKeWe4iWsqnqUrx0g1D7hxCjPlLKoGCfPCCC79C5BGr6Jf4nQ8vfz8v75u3B"
        "ZleWbKAItfxM0VZkCA&hash=6e2fcae017ce013d8e8d05f160125443dabb4c7bcc08cb92f9e827b90d6d8ae3"
    )
    INSTAGRAM_BATCH_CALLBACK_URL: str = "https://cosmeya.dev-klick.cyou/api/v1/instagram-batch/release"
    INSTAGRAM_BATCH_CALLBACK_TOKEN: str | None = None
    INSTAGRAM_BATCH_STATE_DIR: str = "/tmp/instagram_batch_state"

    model_config = {
        "env_file": ".env"
    }


config = Config()
