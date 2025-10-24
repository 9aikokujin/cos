from fastapi.exceptions import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import select
from app.models.account import Account
from app.schemas.account import AccountCreate, AccountUpdate


class AccountRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self):
        result = await self.db.execute(select(Account))
        return result.scalars().all()

    async def get_by_id(self, id: int) -> Account | None:
        result = await self.db.execute(select(Account).filter_by(id=id))
        return result.scalar_one_or_none()

    async def update_account(self, account_id: int,
                             account_update: AccountUpdate) -> Account:
        account = await self.get_by_id(account_id)

        if not account:
            raise HTTPException(status_code=404, detail="Аккаунт не найден")

        update_data = account_update.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            setattr(account, key, value)

        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def search_by_account_str(self, query: str) -> list[Account]:
        stmt = select(Account).where(Account.account_str.ilike(f"%{query}%"))
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def create(self, account_create: AccountCreate) -> Account:
        db_account = Account(**account_create.model_dump())
        self.db.add(db_account)
        await self.db.commit()
        await self.db.refresh(db_account)
        return db_account

    async def create_many(self, accounts: list[AccountCreate]) -> list[Account]:
        db_accounts = [Account(**account.model_dump()) for account in accounts]
        self.db.add_all(db_accounts)
        await self.db.commit()
        for account in db_accounts:
            await self.db.refresh(account)
        return db_accounts

    async def delete(self, account_id: int):
        account = await self.get_by_id(account_id)

        if not account:
            raise HTTPException(status_code=404, detail="Аккаунт не найден")

        await self.db.delete(account)
        await self.db.commit()
        return account
