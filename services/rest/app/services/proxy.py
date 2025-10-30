from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.proxy import ProxyRepository
from app.schemas.proxy import ProxyBulkCreateRequest, ProxyCreate, ProxyUpdate
from app.utils.proxy import parse_proxy_lines


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

    async def bulk_create_proxies(self, payload: ProxyBulkCreateRequest):
        proxies = parse_proxy_lines(payload.raw_data)
        proxy_models = [ProxyCreate(proxy_str=proxy, for_likee=payload.for_likee)
                        for proxy in proxies]
        if not proxy_models:
            return []
        return await self.repo.create_many(proxy_models)

    async def delete_all_proxies(self):
        return await self.repo.delete_all()
