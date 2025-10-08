from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.proxy import ProxyRepository
from app.schemas.proxy import ProxyCreate, ProxyUpdate


class ProxyService:
    def __init__(self, db: AsyncSession):
        self.repo = ProxyRepository(db)

    async def get_all(self):
        return await self.repo.get_all()

    async def get_by_id(self, id: int):
        return await self.repo.get_by_id(id)

    async def create_proxy(self, proxy_create: ProxyCreate):
        return await self.repo.create(proxy_create)

    async def update_proxy(self, id: int, proxy_update: ProxyUpdate):
        return await self.repo.update_proxy(id, proxy_update)

    async def delete_proxy(self, proxy_id: int):
        return await self.repo.delete(proxy_id)
