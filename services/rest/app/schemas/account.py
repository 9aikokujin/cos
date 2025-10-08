from pydantic import BaseModel
from typing import Optional


class Account(BaseModel):
    account_str: str
    is_active: bool


class AccountRead(Account):
    id: int


class AccountCreate(BaseModel):
    account_str: str


class AccountUpdate(BaseModel):
    account_str: Optional[str] = None
    is_active: Optional[bool] = None
