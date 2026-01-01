from typing_extensions import Optional, List
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.sql.expression import select
from sqlalchemy import func

from app.models.channel import Channel, ChannelType
from app.models.videos import Videos
from app.schemas.channel import ChannelCreate, ChannelUpdate
from app.models.user import User, UserRole


class ChannelRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_filtered_paginated(
        self,
        user: Optional[User] = None,
        user_id: Optional[int] = None,
        id: Optional[int] = None,
        type: Optional[ChannelType] = None,
        link: Optional[str] = None,
        name_channel: Optional[str] = None,
        page: Optional[int] = None,
        size: Optional[int] = None
    ) -> dict:
        query = select(Channel)

        if user.role != UserRole.ADMIN:
            query = query.filter(Channel.user_id == user.id)
        else:
            if user_id is not None:
                query = query.filter(Channel.user_id == user_id)

        if id is not None:
            query = query.filter(Channel.id == id)
        if type is not None:
            query = query.filter(Channel.type == type)
        if link is not None:
            query = query.filter(Channel.link == link)
        if name_channel is not None:
            query = query.filter(
                func.lower(
                    Channel.name_channel
                ).contains(func.lower(name_channel))
            )

        if page is not None and size is not None:
            offset = (page - 1) * size
            query = query.offset(offset).limit(size)
            result = await self.db.execute(query)
            channels = result.scalars().all()

            count_query = select(func.count()).select_from(query.subquery())
            total_result = await self.db.execute(count_query)
            total = total_result.scalar()

            return {
                "channels": channels,
                "pagination": {
                    "page": page,
                    "size": size,
                    "total": total,
                    "pages": (total + size - 1) // size
                }
            }
        else:
            result = await self.db.execute(query)
            channels = result.scalars().all()
            return {"channels": channels}

    async def get_by_id(
        self, channel_id: int, user: Optional[User] = None
    ) -> Optional[Channel]:
        query = select(Channel).where(Channel.id == channel_id)

        if user is not None and user.role != UserRole.ADMIN:
            query = query.where(Channel.user_id == user.id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_videos_by_channel_id(self, channel_id: int, user: User) -> List[Videos]:
        query = select(Videos).where(Videos.channel_id == channel_id)

        if user.role != UserRole.ADMIN:
            query = query.join(Channel).where(Channel.user_id == user.id)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_link(self, link: str) -> Channel | None:
        result = await self.db.execute(select(Channel).filter_by(link=link))
        return result.scalar_one_or_none()

    async def create(self, dto: ChannelCreate, user_id: int) -> Channel:
        channel_data = dto.model_dump()
        temp_channel = Channel(**channel_data, user_id=user_id)
        channel_name = temp_channel.grap_name_channel()

        channel = Channel(
            type=dto.type,
            link=dto.link,
            name_channel=channel_name,
            user_id=user_id,
            start_views=dto.start_views,
            start_likes=dto.start_likes,
            start_comments=dto.start_comments
        )

        self.db.add(channel)
        await self.db.commit()
        await self.db.refresh(channel)
        return channel

    async def update(self, id: int, dto: ChannelUpdate) -> Channel | None:
        result = await self.db.execute(select(Channel).filter_by(id=id))
        channel = result.scalar_one_or_none()

        if not channel:
            return None

        update_data = dto.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(channel, field, value)

        if 'link' in update_data:
            temp_channel = Channel(link=update_data['link'])
            channel.name_channel = temp_channel.grap_name_channel()
        elif not channel.name_channel and channel.link:
            temp_channel = Channel(link=channel.link)
            channel.name_channel = temp_channel.grap_name_channel()

        if 'link' in update_data:
            temp_channel = Channel(link=update_data['link'])
            channel.name_channel = temp_channel.grap_name_channel()
        elif not channel.name_channel and channel.link:
            temp_channel = Channel(link=channel.link)
            channel.name_channel = temp_channel.grap_name_channel()

        await self.db.commit()
        await self.db.refresh(channel)
        return channel

    async def delete(self, id: int) -> bool:
        result = await self.db.execute(select(Channel).filter_by(id=id))
        channel = result.scalar_one_or_none()

        if not channel:
            return False

        await self.db.delete(channel)
        await self.db.commit()
        return True
