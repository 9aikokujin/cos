import enum
from sqlalchemy import BigInteger, Column, Integer, String
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import Boolean
from app.core.db import Base
from .channel import Channel
from .timestamp import TimestampMixin


class UserRole(enum.Enum):
    ADMIN = "admin"
    USER = "user"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tg_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    nickname = Column(String, nullable=True)
    fullname = Column(String, nullable=True)
    status = Column(Boolean, default=False)

    is_blocked = Column(Boolean, default=False)

    role = Column(
        PgEnum(
            UserRole,
            name="user_role_enum",
            byvalue=True,
            create_type=True
        ),
        nullable=False,
        default=UserRole.USER
    )

    channels = relationship(
        Channel, back_populates="user",
        cascade="all, delete-orphan"
    )
