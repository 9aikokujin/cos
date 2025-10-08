from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserRead, UserRegister, UserUpdate, PaginatedUsers
from app.services.user import UserService
from app.api.v1.dependencies import get_current_user, require_role
from app.core.db import get_db


router = APIRouter()


@router.get("/", response_model=PaginatedUsers)
async def get_all(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Получение всех пользователей с пагинацией"""
    service = UserService(db)
    try:
        return await service.get_all_paginated(page, size)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/find/{user_id}", response_model=UserRead)
async def get_user_by_id(user_id: int, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    try:
        return await service.get_by_id(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search", response_model=list[UserRead])
async def search_users(
    name: str = Query(..., description="Имя для поиска"),
    db: AsyncSession = Depends(get_db)
):
    """Поиск пользователей по имени/нику"""
    service = UserService(db)
    try:
        return await service.search_users_by_name(name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/paginated")
async def search_users_paginated(
    name: str = Query(..., description="Имя для поиска"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Поиск пользователей по имени с пагинацией"""
    service = UserService(db)
    try:
        return await service.search_users_by_name_paginated(name, page, size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=UserRead)
async def create_user(
    user_create: UserCreate, db: AsyncSession = Depends(get_db)
):
    service = UserService(db)
    try:
        return await service.create_user(user_create)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{user_id}", response_model=UserRead)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    try:
        return await service.delete_user(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/register", response_model=UserRead)
async def register_user(
    user_register: UserRegister,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    service = UserService(db)
    try:
        return await service.register_user(current_user, user_register)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me", response_model=UserRead)
async def read_current_user(
    user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER))
):
    return user


@router.patch("/update", response_model=UserRead)
async def update_current_user(
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER))
):
    service = UserService(db)
    try:
        return await service.update_own_profile(current_user, user_update)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException as e:
        raise e  # Пробрасываем 403 ошибку
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{user_id}", response_model=UserRead)
async def update_user_by_id(
    user_id: int,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.USER))
):
    service = UserService(db)
    try:
        return await service.update_user(current_user, user_id, user_update)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{user_id}/block", response_model=UserRead)
async def block_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Блокировка пользователя (только для администраторов)"""
    service = UserService(db)
    try:
        user_to_block = await service.get_by_id(user_id)
        if not user_to_block:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        if current_user.id == user_id:
            raise HTTPException(status_code=400, detail="Нельзя заблокировать самого себя")

        if user_to_block.role == UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Нельзя заблокировать администратора")

        return await service.block_user(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{user_id}/unblock", response_model=UserRead)
async def unblock_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Разблокировка пользователя (только для администраторов)"""
    service = UserService(db)
    try:
        user_to_unblock = await service.get_by_id(user_id)
        if not user_to_unblock:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        return await service.unblock_user(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{user_id}/status", response_model=dict)
async def get_user_status(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Получение статуса пользователя (только для администраторов)"""
    service = UserService(db)
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return {
        "user_id": user.id,
        "username": user.username,
        "is_blocked": user.is_blocked,
    }
