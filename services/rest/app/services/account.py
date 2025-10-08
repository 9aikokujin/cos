from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.account import AccountRepository
from app.schemas.account import AccountCreate, AccountUpdate


class AccountService:
    def __init__(self, db: AsyncSession):
        self.repo = AccountRepository(db)

    async def get_all(self):
        return await self.repo.get_all()

    async def get_by_id(self, id: int):
        return await self.repo.get_by_id(id)

    async def search_accounts(self, query: str):
        return await self.repo.search_by_account_str(query)

    async def create_account(self, account_create: AccountCreate):
        return await self.repo.create(account_create)

    async def update_account(self, id: int, account_update: AccountUpdate):
        return await self.repo.update_account(id, account_update)

    async def delete_account(self, account_id: int):
        return await self.repo.delete(account_id)
