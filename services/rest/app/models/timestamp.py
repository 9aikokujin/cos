from sqlalchemy import Column, DateTime, func
from sqlalchemy.ext.declarative import declared_attr


class TimestampMixin:
    """Миксин для timestamp."""
    @declared_attr
    def created_at(cls):
        """Время создания."""
        return Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        )

    @declared_attr
    def updated_at(cls):
        """Время обновления."""
        return Column(DateTime(timezone=True), server_default=func.now(),
                      onupdate=func.now(), nullable=False)
