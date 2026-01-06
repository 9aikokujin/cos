import unittest
from contextlib import AsyncExitStack

from .conftest import make_app, make_client
from .helpers import block_user, unblock_user, use_role

class BaseApiTest(unittest.IsolatedAsyncioTestCase):
    """Базовый класс: поднимает тестовое FastAPI и клиент."""

    ROLE = "admin"

    @classmethod
    def setUpClass(cls):
        """Открываем тестовый http-клиент перед тестом."""
        cls.app = make_app(role=cls.ROLE)

    async def asyncSetUp(self) -> None:
        """Инициализация сессии."""
        self.stack = AsyncExitStack()
        self.client = await self.stack.enter_async_context(make_client(self.app))
    
    async def asyncTearDown(self) -> None:
        """Закрываем тестовый http-клиент после теста."""
        await self.stack.aclose()


class CreateUser(BaseApiTest):
    """Тесты создания пользователя."""

    async def test_create_user_success(self):
        """Успешное создание нового пользователя."""
        resp = await self.client.post('/api/v1/users/', json={'tg_id': 123})
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload['tg_id'], 123)
        self.assertIn('id', payload)
    
    async def test_duplicate_tg_id(self):
        """
        Ошибка при попытке создать пользователя с уже имеющимся tg_id.
        """
        await self.client.post("/api/v1/users/", json={"tg_id": 123})
        resp = await self.client.post('/api/v1/users/', json={'tg_id': 123})
        self.assertEqual(resp.status_code, 400)


class BlockUnblockAsAdmin(BaseApiTest):
    """
    Тесты блокировки/разблокировки пользователя (только админ).
    + тест, заблокированный пользователь не имеет доступа.
    """

    ROLE = 'admin'

    async def test_block_and_forbid(self):
        """
        Блокировка пользователя от лица админа.
        Проверка заблокирован ли пользователь.
        разблокировка
        """
        resp = await block_user(self.client, 2)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['is_blocked'])

    async def test_user_is_blocked_from_admin(self):
        """
        Заблокированный пользователь не имеет доступа.
        """
        resp = await block_user(self.client, 2)
        async with use_role(self.app, 'user'):
            resp = await self.client.get('/api/v1/users/me')
            self.assertEqual(resp.status_code, 403)
        
    async def test_unblock_user_from_admin(self):
        """Разблокировка пользователя."""
        resp = await unblock_user(self.client, 2)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['is_blocked'])
    
    async def test_user_is_unblocked(self):
        """Пользователь разблокирован."""
        async with use_role(self.app, 'user'):
            resp = await self.client.get('/api/v1/users/me')
            self.assertEqual(resp.status_code, 200)
    
    async def test_user_cant_block(self):
        """Пользователь не имеет права блокировать."""
        async with use_role(self.app, 'user'):
            resp = await block_user(self.client, 1)
            self.assertEqual(resp.status_code, 403)
    
    async def test_cant_block_itself(self):
        """Администратор не может заблокировать себя."""
        resp = await block_user(self.client, 1)
        self.assertEqual(resp.status_code, 400)


