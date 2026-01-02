from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """ Конфигурация для бота"""
    RABBITMQ_URL: str
    TELEGRAM_BOT_TOKEN: str
    RABBITMQ_QUEUE: str = 'bot_task_queue'


    model_config = {
        "env_file": ".env"
    }


config = Config()
