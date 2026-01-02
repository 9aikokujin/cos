from pydantic import BaseModel
from typing import List


class UserBase(BaseModel):
    """Пользователь."""
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    nickname: str | None = None
    fullname: str | None = None
    status: bool
    is_blocked: bool | None = None


class UserCreate(BaseModel):
    """Создание пользователя."""
    tg_id: int


class UserRead(UserBase, UserCreate):
    """Чтение пользователя."""
    id: int
    role: str

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Обновление пользователя."""
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    nickname: str | None = None
    fullname: str | None = None
    status: bool | None = None


class UserRegister(BaseModel):
    """Регистрация пользователя."""
    username: str | None = None
    fullname: str
    first_name: str | None = None
    last_name: str | None = None
    nickname: str


class PaginatedUsers(BaseModel):
    """Пагинация пользователей."""
    users: List[UserRead]
    pagination: dict
