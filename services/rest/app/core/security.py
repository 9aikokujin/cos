from fastapi import Header, HTTPException
from typing import Optional

async def get_telegram_token(authorization: Optional[str] = Header(None)) -> str:
    """Получаем токен телеграма."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Токен не найден")
    return authorization
