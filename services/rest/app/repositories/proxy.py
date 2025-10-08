from fastapi.exceptions import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import select
from app.models.proxy import Proxy
from app.schemas.proxy import ProxyUpdate


class ProxyRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self):
        result = await self.db.execute(select(Proxy))
        return result.scalars().all()

    async def get_by_id(self, id: int) -> Proxy | None:
        result = await self.db.execute(select(Proxy).filter_by(id=id))
        return result.scalar_one_or_none()

    async def update_proxy(self, proxy_id: int,
                           proxy_update: ProxyUpdate) -> Proxy:
        proxy = await self.get_by_id(proxy_id)

        if not proxy:
            raise HTTPException(status_code=404, detail="Прокси не найден")

        update_data = proxy_update.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(proxy, key, value)

        await self.db.commit()
        await self.db.refresh(proxy)
        return proxy

    async def create(self, proxy_create: dict) -> Proxy:
        proxy_data = proxy_create.model_dump()
        db_proxy = Proxy(**proxy_data)
        self.db.add(db_proxy)
        await self.db.commit()
        await self.db.refresh(db_proxy)
        return db_proxy

    async def delete(self, proxy_id: int):
        proxy = await self.get_by_id(proxy_id)

        if not proxy:
            raise HTTPException(status_code=404, detail="Прокси не найден")

        await self.db.delete(proxy)
        await self.db.commit()
        return proxy
