from contextlib import asynccontextmanager

from ..dependencies import get_current_user
from .conftest import ROLE_OVERRIDES


async def block_user(client, user_id: int):
    """Блокирока пользователя."""
    return await client.patch(f'/api/v1/users/{user_id}/block')

async def unblock_user(client, user_id: int):
    """Разблокирока пользователя."""
    return await client.patch(f'/api/v1/users/{user_id}/unblock')

@asynccontextmanager
async def use_role(app, role: str):
    """Быстрая смена роли пользователя."""
    prev = app.dependency_overrides.get(get_current_user, None)
    app.dependency_overrides[get_current_user] = ROLE_OVERRIDES[role]
    try:
        yield
    finally:
        if prev is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = prev