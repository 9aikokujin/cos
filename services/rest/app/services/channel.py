from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.repositories.channel import ChannelRepository
from app.schemas.channel import ChannelCreate, ChannelUpdate
from app.models.user import User, UserRole
from app.models.channel import ChannelType
from app.models.account import Account
from app.models.proxy import Proxy
from app.utils.rabbitmq_producer import rabbit_producer
from app.utils.scheduler import scheduler, process_recurring_task
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

    async def create(self, dto: ChannelCreate, user: User):
        existing_channel = await self.repo.get_by_link(str(dto.link))
        if existing_channel:
            raise ValueError("Канал уже существует")
        new_channel = await self.repo.create(dto, user.id)
        if not new_channel:
            raise ValueError("Ошибка при создании канала")

        proxies_from_db = await self.repo.db.execute(select(Proxy))
        proxies = proxies_from_db.scalars().all()
        likee_proxies = [p.proxy_str for p in proxies if p.for_likee is True]
        proxies_for_send = [p.proxy_str for p in proxies]

        accounts_from_db = await self.repo.db.execute(select(Account))
        accounts = accounts_from_db.scalars().all()
        accounts_for_send = []
        for account in accounts:
            accounts_for_send.append(account.account_str)

        type_channel = ChannelType.get_by_value(dto.type.value)
        if type_channel == ChannelType.LIKEE:
            rabbit_producer.send_task(
                f"parsing_{dto.type.value}",
                {
                    "type": "channel",
                    "user_id": user.id,
                    "url": new_channel.link,
                    "channel_id": new_channel.id,
                    "accounts": accounts_for_send,
                    "proxy_list": likee_proxies
                }
            )

            job_id = f"task_{new_channel.id}"
            scheduler.add_job(
                process_recurring_task,
                "interval",
                hours=24,
                args=[new_channel.id, "channel"],
                id=job_id,
                max_instances=1,
            )
            return new_channel

        rabbit_producer.send_task(
            f"parsing_{dto.type.value}",
            {
                "type": "channel",
                "user_id": user.id,
                "url": new_channel.link,
                "channel_id": new_channel.id,
                "accounts": accounts_for_send,
                "proxy_list": proxies_for_send
            }
        )

        job_id = f"task_{new_channel.id}"
        scheduler.add_job(
            process_recurring_task,
            "interval",
            hours=24,
            args=[new_channel.id, "channel"],
            id=job_id,
            max_instances=1,
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

        proxies_from_db = await self.repo.db.execute(select(Proxy))
        proxies = proxies_from_db.scalars().all()
        likee_proxies = [p.proxy_str for p in proxies if p.for_likee is True]
        proxies_for_send = [p.proxy_str for p in proxies]

        accounts_from_db = await self.repo.db.execute(select(Account))
        accounts = accounts_from_db.scalars().all()
        accounts_for_send = []
        for account in accounts:
            accounts_for_send.append(account.account_str)

        proxy_payload = likee_proxies if dto.type == ChannelType.LIKEE else proxies_for_send

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

        job_id = f"task_{new_channel.id}"
        scheduler.add_job(
            process_recurring_task,
            "interval",
            hours=24,
            args=[new_channel.id, "channel"],
            id=job_id,
            max_instances=1,
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
