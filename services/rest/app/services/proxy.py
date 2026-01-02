from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.proxy import ProxyRepository
from app.schemas.proxy import ProxyBulkCreateRequest, ProxyCreate, ProxyUpdate
from app.utils.proxy import parse_proxy_lines


class ProxyService:
    """Сервис для работы с прокси."""
    def __init__(self, db: AsyncSession):
        """Инициализируем сервис."""
        self.repo = ProxyRepository(db)

    async def get_all(self):
        """Получаем все прокси."""
        return await self.repo.get_all()

    async def get_by_id(self, id: int):
        """Получаем прокси по id."""
        return await self.repo.get_by_id(id)

    async def create_proxy(self, proxy_create: ProxyCreate):
        """Создаем прокси."""
        return await self.repo.create(proxy_create)

    async def update_proxy(self, id: int, proxy_update: ProxyUpdate):
        """Обновляем прокси."""
        return await self.repo.update_proxy(id, proxy_update)

    async def delete_proxy(self, proxy_id: int):
        """Удаляем прокси."""
        return await self.repo.delete(proxy_id)

    async def bulk_create_proxies(self, payload: ProxyBulkCreateRequest):
        """Создаем множество прокси и списка разделенных по .""" # Разделитель \n
        proxies = parse_proxy_lines(payload.raw_data)
        proxy_models = [ProxyCreate(proxy_str=proxy, for_likee=payload.for_likee)
                        for proxy in proxies]
        if not proxy_models:
            return []
        return await self.repo.create_many(proxy_models)

    async def delete_all_proxies(self):
        """Удаляем все прокси."""
        return await self.repo.delete_all()
