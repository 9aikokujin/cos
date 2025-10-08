from fastapi import Header, HTTPException
from typing import Optional

async def get_telegram_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    return authorization
