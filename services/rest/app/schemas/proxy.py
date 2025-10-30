from pydantic import AliasChoices, BaseModel, ConfigDict, Field
from typing import Optional


class Proxy(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    proxy_str: str
    is_active: bool
    for_likee: bool = Field(
        False,
        validation_alias=AliasChoices("for_like", "for_likee"),
        serialization_alias="for_like",
    )


class ProxyRead(Proxy):
    id: int


class ProxyCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    proxy_str: str
    for_likee: bool = Field(
        False,
        validation_alias=AliasChoices("for_like", "for_likee"),
        serialization_alias="for_like",
    )


class ProxyUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    proxy_str: Optional[str] = None
    is_active: Optional[bool] = None
    for_likee: Optional[bool] = Field(
        None,
        validation_alias=AliasChoices("for_like", "for_likee"),
        serialization_alias="for_like",
    )


class ProxyBulkCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    raw_data: str
    for_likee: bool = Field(
        False,
        validation_alias=AliasChoices("for_like", "for_likee"),
        serialization_alias="for_like",
    )


class ProxyBulkDeleteResponse(BaseModel):
    deleted: int
