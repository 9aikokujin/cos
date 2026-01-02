from typing import Callable
from fastapi import Request, HTTPException, Depends, status
from fastapi.param_functions import Security
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.utils.telegram_auth import check_telegram_auth
from app.schemas.user import UserCreate
from app.services.user import UserService
from app.models.user import User, UserRole

import urllib.parse
import json


bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> User:
    """Получаем текущего пользователя."""
    token = credentials.credentials

    try:
        telegram_data = dict(pair.split("=") for pair in token.split("&"))
    except Exception:
        raise HTTPException(status_code=400, detail="Неверный формат токена телеграма")

    # if not telegram_data or not check_telegram_auth(telegram_data):
    #     raise HTTPException(status_code=401, detail="Invalid Telegram authorization")

    if not telegram_data:
        raise HTTPException(status_code=400, detail="Данные телеграма не найдены")

    user_encoded = telegram_data.get("user")
    if not user_encoded:
        raise HTTPException(status_code=400, detail="Данные пользователя не найдены")

    user_json_str = urllib.parse.unquote(user_encoded)
    user_data = json.loads(user_json_str)

    telegram_id_str = user_data.get("id")
    if not telegram_id_str:
        raise HTTPException(status_code=400, detail="ID в данных телеграма не найден")

    try:
        telegram_id = int(telegram_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат ID")

    user_service = UserService(db)
    user = await user_service.get_by_telegram_id(telegram_id)

    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user


def require_role(*roles: UserRole):
    async def role_checker(current_user: User = Depends(get_current_user)):
        """Проверка прав доступа и блокировки пользователя"""
        if current_user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail="Недостаточно прав для выполнения этого действия"
            )

        if current_user.is_blocked:
            raise HTTPException(
                status_code=403,
                detail="Ваш аккаунт заблокирован. Обратитесь к администратору."
            )
        return current_user
    return role_checker
