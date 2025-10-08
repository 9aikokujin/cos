import enum
from sqlalchemy import BigInteger, Column, Integer, String
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import Boolean
from app.core.db import Base
from .timestamp import TimestampMixin


class Account(Base, TimestampMixin):
    __tablename__ = "account"

    id = Column(Integer, primary_key=True)
    account_str = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

    def toggle_active(self):
        self.is_active = not self.is_active
