from fastapi.exceptions import HTTPException
from sqlalchemy import or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import select

from app.models.user import User
from app.schemas.user import UserCreate, UserRegister, UserUpdate


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_paginated(self, page: int, size: int):
        """Получение всех пользователей с пагинацией"""
        offset = (page - 1) * size
        query = select(User).offset(offset).limit(size)
        result = await self.db.execute(query)
        users = result.scalars().all()

        count_query = select(func.count()).select_from(User)
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        return {
            "users": users,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
                "pages": (total + size - 1) // size
            }
        }

    async def get_by_id(self, id: int) -> User | None:
        result = await self.db.execute(select(User).filter_by(id=id))
        return result.scalar_one_or_none()

    async def get_by_tg_id(self, tg_id: int) -> User | None:
        result = await self.db.execute(select(User).filter_by(tg_id=tg_id))
        return result.scalar_one_or_none()

    async def search_by_name(self, name: str) -> list[User]:
        """Поиск пользователей по имени/никнейму"""
        query = select(User).where(
            or_(
                User.first_name.ilike(f"%{name}%"),
                User.last_name.ilike(f"%{name}%"),
                User.nickname.ilike(f"%{name}%"),
                User.fullname.ilike(f"%{name}%"),
                User.username.ilike(f"%{name}%")
            )
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def search_by_name_paginated(
        self, name: str, page: int = 1, size: int = 10
    ) -> dict:
        """Поиск пользователей по имени с пагинацией"""
        offset = (page - 1) * size
        query = select(User).where(
            or_(
                User.first_name.ilike(f"%{name}%"),
                User.last_name.ilike(f"%{name}%"),
                User.nickname.ilike(f"%{name}%"),
                User.fullname.ilike(f"%{name}%"),
                User.username.ilike(f"%{name}%")
            )
        ).offset(offset).limit(size)

        result = await self.db.execute(query)
        users = result.scalars().all()

        count_query = select(func.count()).select_from(User).where(
            or_(
                User.first_name.ilike(f"%{name}%"),
                User.last_name.ilike(f"%{name}%"),
                User.nickname.ilike(f"%{name}%"),
                User.fullname.ilike(f"%{name}%"),
                User.username.ilike(f"%{name}%")
            )
        )
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        return {
            "users": users,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
                "pages": (total + size - 1) // size
            }
        }

    async def update_user(
        self, user_tg_id: int, user_update: UserRegister
    ) -> User:
        """Регистрация пользователя."""
        user = await self.get_by_tg_id(user_tg_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        for key, value in user_update.model_dump(exclude_unset=True).items():
            setattr(user, key, value)

        user.status = True

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_user_by_id(
        self, user_id: int, user_update: UserUpdate
    ) -> User:
        """Обновление профиля по id"""
        user = await self.get_by_id(user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        for key, value in user_update.model_dump(exclude_unset=True).items():
            setattr(user, key, value)

        user.status = True

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def block_user(self, user_id: int):
        user = await self.get_by_id(user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.is_blocked = True

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def create(self, user_create: UserCreate) -> User:
        db_user = User(**user_create.model_dump())
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user

    async def delete(self, user_id: int):
        user = await self.get_by_id(user_id)

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        await self.db.delete(user)
        await self.db.commit()
        return user
