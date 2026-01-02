from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from typing import Optional


class Proxy(BaseModel):
    """Прокси."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    proxy_str: str
    is_active: bool
    for_likee: bool = Field(
        False,
        validation_alias=AliasChoices("for_like", "for_likee"),
        serialization_alias="for_like",
    )


class ProxyRead(Proxy):
    """Чтение прокси."""
    id: int


class ProxyCreate(BaseModel):
    """Создание прокси."""
    model_config = ConfigDict(populate_by_name=True)
    proxy_str: str
    for_likee: bool = Field(
        False,
        validation_alias=AliasChoices("for_like", "for_likee"),
        serialization_alias="for_like",
    )


class ProxyUpdate(BaseModel):
    """Обновление прокси."""
    model_config = ConfigDict(populate_by_name=True)
    proxy_str: Optional[str] = None
    is_active: Optional[bool] = None
    for_likee: Optional[bool] = Field(
        None,
        validation_alias=AliasChoices("for_like", "for_likee"),
        serialization_alias="for_like",
    )


class ProxyBulkCreateRequest(BaseModel):
    """Создание множества прокси."""
    model_config = ConfigDict(populate_by_name=True)
    raw_data: str
    for_likee: bool = Field(
        False,
        validation_alias=AliasChoices("for_like", "for_likee"),
        serialization_alias="for_like",
    )


class ProxyBulkDeleteResponse(BaseModel):
    """Удаление множества прокси."""
    deleted: int
