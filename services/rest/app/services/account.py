from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.account import AccountRepository
from app.schemas.account import (AccountBulkCreateRequest, AccountCreate,
                                 AccountUpdate)
from app.utils.account import parse_account_lines


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

    async def bulk_create_accounts(self, payload: AccountBulkCreateRequest):
        accounts = parse_account_lines(payload.raw_data)
        account_models = [AccountCreate(account_str=account) for account in accounts]
        if not account_models:
            return []
        return await self.repo.create_many(account_models)

    async def update_account(self, id: int, account_update: AccountUpdate):
        return await self.repo.update_account(id, account_update)

    async def delete_account(self, account_id: int):
        return await self.repo.delete(account_id)
