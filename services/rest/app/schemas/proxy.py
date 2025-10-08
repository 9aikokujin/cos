from pydantic import BaseModel
from typing import Optional


class Proxy(BaseModel):
    proxy_str: str
    is_active: bool


class ProxyRead(Proxy):
    id: int


class ProxyCreate(BaseModel):
    proxy_str: str
    for_likee: bool = False


class ProxyUpdate(BaseModel):
    proxy_str: Optional[str] = None
    is_active: Optional[bool] = None
