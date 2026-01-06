from fastapi import FastAPI
# from starlette.testclient import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from contextlib import asynccontextmanager


from app.api.v1.endpoints import user as user_router
from app.api.v1.dependencies import get_db, get_current_user
from app.core.db import Base
from app.models.user import User, UserRole

engine = create_async_engine('sqlite+aiosqlite:///:memory:')
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def test_lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        session.add_all([
            User(tg_id=1, username="Admin", role=UserRole.ADMIN, status=True),
            User(tg_id=2, username='UsualUser', role=UserRole.USER, status=True),
        ])
        await session.commit()
    yield
    await engine.dispose()

async def override_db()-> AsyncSession:
    async with SessionLocal() as session:
        yield session
    
async def override_current_user_as_admin():
    async with SessionLocal() as session:
        return await session.get(User, 1)
    
async def override_current_user_as_usual():
    async with SessionLocal() as session:
        return await session.get(User, 2)

ROLE_OVERRIDES = {
    "admin": override_current_user_as_admin,
    "user": override_current_user_as_usual,
}

def make_app(role: str = 'admin'):
    app = FastAPI(lifespan=test_lifespan)
    app.include_router(user_router.router, prefix='/api/v1/users')
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = ROLE_OVERRIDES.get(role, override_current_user_as_admin)
    return app

@asynccontextmanager
async def make_client(app: FastAPI):
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c