from pydantic import BaseModel
from typing import List


class UserBase(BaseModel):
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    nickname: str | None = None
    fullname: str | None = None
    status: bool
    is_blocked: bool | None = None


class UserCreate(BaseModel):
    tg_id: int


class UserRead(UserBase, UserCreate):
    id: int
    role: str

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    nickname: str | None = None
    fullname: str | None = None
    status: bool | None = None


class UserRegister(BaseModel):
    username: str | None = None
    fullname: str
    first_name: str | None = None
    last_name: str | None = None
    nickname: str


class PaginatedUsers(BaseModel):
    users: List[UserRead]
    pagination: dict
