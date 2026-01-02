from fastapi.exceptions import HTTPException
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import select
from app.models.proxy import Proxy
from app.schemas.proxy import ProxyCreate, ProxyUpdate


class ProxyRepository:
    """Репозиторий для работы с прокси."""
    def __init__(self, db: AsyncSession):
        """Инициализируем репозиторий."""
        self.db = db

    async def get_all(self):
        """Получаем все прокси."""
        result = await self.db.execute(select(Proxy))
        return result.scalars().all()

    async def get_by_id(self, id: int) -> Proxy | None:
        """Получаем прокси по ID."""
        result = await self.db.execute(select(Proxy).filter_by(id=id))
        return result.scalar_one_or_none()

    async def update_proxy(self, proxy_id: int,
                           proxy_update: ProxyUpdate) -> Proxy:
        """Обновляем прокси."""
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
        """Создаем прокси."""
        proxy_data = proxy_create.model_dump()
        db_proxy = Proxy(**proxy_data)
        self.db.add(db_proxy)
        await self.db.commit()
        await self.db.refresh(db_proxy)
        return db_proxy

    async def create_many(self, proxies: list[ProxyCreate]) -> list[Proxy]:
        """Создаем множество прокси."""
        db_proxies = [Proxy(**proxy.model_dump()) for proxy in proxies]
        self.db.add_all(db_proxies)
        await self.db.commit()
        for proxy in db_proxies:
            await self.db.refresh(proxy)
        return db_proxies

    async def delete(self, proxy_id: int):
        """Удаляем прокси."""
        proxy = await self.get_by_id(proxy_id)

        if not proxy:
            raise HTTPException(status_code=404, detail="Прокси не найден")

        await self.db.delete(proxy)
        await self.db.commit()
        return proxy

    async def delete_all(self) -> int:
        """Удаляем все прокси."""
        result = await self.db.execute(delete(Proxy))
        await self.db.commit()
        return result.rowcount or 0
