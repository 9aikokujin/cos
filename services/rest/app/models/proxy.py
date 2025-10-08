import enum
from sqlalchemy import BigInteger, Column, Integer, String
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import Boolean
from app.core.db import Base
from .timestamp import TimestampMixin


class Proxy(Base, TimestampMixin):
    __tablename__ = "proxies"

    id = Column(Integer, primary_key=True)
    proxy_str = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    for_likee = Column(Boolean, default=False)

    def toggle_active(self):
        self.is_active = not self.is_active
