from pydantic import BaseModel
from typing import Optional


class Account(BaseModel):
    """Аккаунт для инстаграма."""
    account_str: str
    is_active: bool


class AccountRead(Account):
    """Чтение аккаунта."""
    id: int


class AccountCreate(BaseModel):
    """Создание аккаунта."""
    account_str: str


class AccountUpdate(BaseModel):
    """Обновление аккаунта."""
    account_str: Optional[str] = None
    is_active: Optional[bool] = None


class AccountBulkCreateRequest(BaseModel):
    """Создание множества аккаунтов."""
    raw_data: str # Строка с аккаунтами разделенными \n
