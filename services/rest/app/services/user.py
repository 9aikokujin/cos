from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.user import User, UserRole
from app.schemas.user import UserUpdate
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserRead, UserRegister


class UserService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)

    async def get_all_paginated(self, page: int = 1, size: int = 10):
        """Получение всех пользователей с пагинацией"""
        return await self.repo.get_all_paginated(page, size)

    async def search_users_by_name(self, name: str):
        """Поиск пользователей по имени"""
        return await self.repo.search_by_name(name)

    async def search_users_by_name_paginated(
        self, name: str, page: int = 1, size: int = 10
    ):
        """Поиск пользователей по имени с пагинацией"""
        return await self.repo.search_by_name_paginated(name, page, size)

    async def create_user(self, user_create: UserCreate):
        existing_user = await self.repo.get_by_tg_id(user_create.tg_id)
        if existing_user:
            raise ValueError("User already exists")
        return await self.repo.create(user_create)

    async def delete_user(self, user_id: int):
        return await self.repo.delete(user_id)

    async def register_user(
        self, current_user: UserRead, user_register: UserRegister
    ):
        return await self.repo.update_user(current_user.tg_id, user_register)

    async def get_by_telegram_id(self, tg_id: int):
        user = await self.repo.get_by_tg_id(tg_id)
        if not user:
            return None
        return user

    async def update_user(self, current_user: User,
                          target_user_id: int, user_update: UserUpdate):
        """Обновление профиля пользователя с проверкой прав"""
        target_user = await self.repo.get_by_id(target_user_id)
        if not target_user:
            raise ValueError("Пользователь не найден")

        if current_user.role != UserRole.ADMIN and current_user.id != target_user_id:
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для изменения чужого профиля"
            )

        return await self.repo.update_user_by_id(target_user_id, user_update)

    async def block_user(self, user_id: int) -> User:
        """Блокировка пользователя"""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        user.is_blocked = True
        await self.repo.db.commit()
        await self.repo.db.refresh(user)
        return user

    async def unblock_user(self, user_id: int) -> User:
        """Разблокировка пользователя"""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        user.is_blocked = False
        await self.repo.db.commit()
        await self.repo.db.refresh(user)
        return user

    async def update_own_profile(
        self, current_user: User,
        user_update: UserUpdate
    ):
        """Обновление своего собственного профиля"""
        return await self.repo.update_user_by_id(current_user.id, user_update)

    async def get_by_id(self, user_id: int):
        user = await self.repo.get_by_id(user_id)
        if not user:
            return None
        return user

    async def update_user_by_id(self, user_id: int, user_update: UserUpdate):
        """Обновление профиля пользователя по id"""
        return await self.repo.update_user_by_id(user_id, user_update)
