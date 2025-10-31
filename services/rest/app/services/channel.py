from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.repositories.channel import ChannelRepository
from app.schemas.channel import ChannelCreate, ChannelUpdate
from app.models.user import User, UserRole
from app.models.channel import ChannelType, Channel
from app.models.account import Account
from app.models.proxy import Proxy
from app.utils.rabbitmq_producer import rabbit_producer
from app.utils.scheduler import schedule_channel_task
from fastapi import HTTPException


class ChannelService:
    def __init__(self, db: AsyncSession):
        self.repo = ChannelRepository(db)

    async def get_all_filtered_paginated(
        self,
        user: User,
        user_id: Optional[int] = None,
        id: Optional[int] = None,
        type: Optional[ChannelType] = None,
        link: Optional[str] = None,
        name_channel: Optional[str] = None,
        page: Optional[int] = None,
        size: Optional[int] = None
    ):
        return await self.repo.get_all_filtered_paginated(
            user, user_id, id, type, link, name_channel, page, size
        )

    async def get_by_id(self, channel_id: int, user: User):
        channel = await self.repo.get_by_id(channel_id, user)
        # Проверка прав доступа
        if not channel:
            raise HTTPException(status_code=404, detail="Канал не найден")
        if user.role != UserRole.ADMIN and channel.user_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для просмотра этого канала"
            )
        video = await self.repo.get_videos_by_channel_id(
            channel_id,
            user=user
        )
        return {
            "channel": channel,
            "videos": video
        }

    async def get_by_link(self, link: str):
        return await self.repo.get_by_link(link)

    async def _calculate_offset_for_channel(self, channel_id: int) -> int:
        result = await self.repo.db.execute(select(Channel))
        channels = result.scalars().all()
        channels = sorted(
            channels,
            key=lambda ch: (
                ch.created_at or datetime.min.replace(tzinfo=timezone.utc),
                ch.id,
            ),
        )
        channel_ids = [ch.id for ch in channels]
        try:
            position = channel_ids.index(channel_id)
        except ValueError:
            position = len(channel_ids) - 1
        return position * 5

    async def create(self, dto: ChannelCreate, user: User):
        existing_channel = await self.repo.get_by_link(str(dto.link))
        if existing_channel:
            raise ValueError("Канал уже существует")
        new_channel = await self.repo.create(dto, user.id)
        if not new_channel:
            raise ValueError("Ошибка при создании канала")

        type_channel = dto.type
        offset = await self._calculate_offset_for_channel(new_channel.id)
        immediate_dispatched = schedule_channel_task(
            new_channel.id,
            run_immediately=True,
            offset_minutes=offset,
        )
        if immediate_dispatched:
            return new_channel

        proxies_from_db = await self.repo.db.execute(select(Proxy))
        proxies = proxies_from_db.scalars().all()
        likee_proxies = [p.proxy_str for p in proxies if p.for_likee is True]
        proxies_for_send = [p.proxy_str for p in proxies]

        accounts_from_db = await self.repo.db.execute(select(Account))
        accounts = accounts_from_db.scalars().all()
        accounts_for_send = [account.account_str for account in accounts]

        proxy_payload = likee_proxies if type_channel == ChannelType.LIKEE else proxies_for_send

        rabbit_producer.send_task(
            f"parsing_{dto.type.value}",
            {
                "type": "channel",
                "user_id": user.id,
                "url": new_channel.link,
                "channel_id": new_channel.id,
                "accounts": accounts_for_send,
                "proxy_list": proxy_payload
            }
        )

        return new_channel

    async def create_for_user(self, dto: ChannelCreate,
                              target_user_id: int, current_user: User):
        if current_user.role != UserRole.ADMIN and target_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        existing_channel = await self.repo.get_by_link(str(dto.link))
        if existing_channel:
            raise ValueError("Канал уже существует")

        new_channel = await self.repo.create(dto, target_user_id)
        if not new_channel:
            raise ValueError("Ошибка при создании канала")

        type_channel = dto.type
        offset = await self._calculate_offset_for_channel(new_channel.id)
        immediate_dispatched = schedule_channel_task(
            new_channel.id,
            run_immediately=True,
            offset_minutes=offset,
        )
        if immediate_dispatched:
            return new_channel

        proxies_from_db = await self.repo.db.execute(select(Proxy))
        proxies = proxies_from_db.scalars().all()
        likee_proxies = [p.proxy_str for p in proxies if p.for_likee is True]
        proxies_for_send = [p.proxy_str for p in proxies]

        accounts_from_db = await self.repo.db.execute(select(Account))
        accounts = accounts_from_db.scalars().all()
        accounts_for_send = [account.account_str for account in accounts]

        proxy_payload = likee_proxies if type_channel == ChannelType.LIKEE else proxies_for_send

        rabbit_producer.send_task(
            f"parsing_{dto.type.value}",
            {
                "type": "channel",
                "user_id": target_user_id,
                "url": new_channel.link,
                "channel_id": new_channel.id,
                "accounts": accounts_for_send,
                "proxy_list": proxy_payload
            }
        )

        return new_channel

    async def update(self, channel_id: int, dto: ChannelUpdate, user: User):
        """Изменение канала"""
        channel = await self.repo.get_by_id(channel_id, user)

        if not channel:
            raise HTTPException(status_code=404, detail="Канал не найден")
        # Проверка прав доступа
        if user.role != UserRole.ADMIN and channel.user_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для изменения этого канала"
            )

        return await self.repo.update(channel_id, dto)

    async def delete(self, channel_id: int, user: User):
        channel = await self.repo.get_by_id(channel_id, user)
        if not channel:
            raise HTTPException(status_code=404, detail="Канал не найден")
        if user.role != UserRole.ADMIN and channel.user_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для удаления этого канала"
            )

        await self.repo.delete(channel_id)
        await self.repo.db.commit()
        return True
