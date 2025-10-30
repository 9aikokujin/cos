import os
import sys
from pathlib import Path
from datetime import date as dt_date
from typing import Any, Dict, List, Optional, Tuple

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from types import SimpleNamespace
import importlib

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "token")
os.environ.setdefault("TELEGRAM_ADMIN_ID", "1")
os.environ.setdefault("COS_LOGSTASH_PORT", "5000")
os.environ.setdefault("COS_LOGSTASH_HOST", "localhost")
os.environ.setdefault("COS_RABBITMQ_USER", "user")
os.environ.setdefault("COS_RABBITMQ_PASSWORD", "password")
os.environ.setdefault("COS_RABBITMQ_HOST", "localhost")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = Path(__file__).resolve().parents[1]
for path in (str(PROJECT_ROOT), str(SERVICE_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

scheduler_module = importlib.import_module("app.utils.scheduler")

if not hasattr(scheduler_module, "schedule_channel_task"):
    def schedule_channel_task_stub(*args, **kwargs):
        return None

    scheduler_module.schedule_channel_task = schedule_channel_task_stub  # type: ignore[attr-defined]

if not hasattr(scheduler_module, "process_recurring_task"):
    async def process_recurring_task_stub(*args, **kwargs):
        return None

    scheduler_module.process_recurring_task = process_recurring_task_stub  # type: ignore[attr-defined]

if not hasattr(scheduler_module, "scheduler"):
    scheduler_module.scheduler = SimpleNamespace(  # type: ignore[attr-defined]
        add_job=lambda *args, **kwargs: None,
        get_job=lambda *args, **kwargs: None,
        remove_job=lambda *args, **kwargs: None,
    )

from app.main import app  # noqa: E402  # type: ignore
from app.api.v1 import dependencies  # noqa: E402  # type: ignore
from app.api.v1.endpoints import videohistory  # noqa: E402  # type: ignore
from app.models.user import User, UserRole  # noqa: E402  # type: ignore


@pytest.fixture
def admin_user() -> User:
    return User(
        id=1,
        tg_id=111,
        username="admin",
        role=UserRole.ADMIN,
        is_blocked=False,
    )


@pytest.fixture
def regular_user() -> User:
    return User(
        id=2,
        tg_id=222,
        username="regular",
        role=UserRole.USER,
        is_blocked=False,
    )


@pytest_asyncio.fixture
async def client(admin_user: User):
    async def dummy_db():
        yield None

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(_app):
        yield

    app.dependency_overrides[dependencies.get_current_user] = lambda: admin_user
    app.dependency_overrides[dependencies.get_db] = dummy_db
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = noop_lifespan

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client

    app.dependency_overrides.clear()
    app.router.lifespan_context = original_lifespan


@pytest.mark.asyncio
async def test_get_all_video_history_accepts_multiple_users(
    client: AsyncClient,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: Dict[str, Any] = {}

    class ServiceStub:
        def __init__(self, db: Any):
            pass

        async def get_all_filtered(self, **kwargs):
            captured.update(kwargs)
            return [{"id": 1, "video_name": "Video 1"}]

    monkeypatch.setattr(videohistory, "VideoHistoryService", ServiceStub)

    response = await client.get(
        "/api/v1/videohistory/",
        params={"user_ids": ["1", "2"]},
    )

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "video_name": "Video 1"}]
    assert captured["user"] == admin_user
    assert captured["user_ids"] == [1, 2], captured


@pytest.mark.asyncio
async def test_filtered_stats_art_accepts_multiple_users(
    client: AsyncClient,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: Dict[str, Any] = {}

    class ServiceStub:
        def __init__(self, db: Any):
            pass

        async def get_aggregated_views_by_date_art(self, **kwargs):
            captured.update(kwargs)
            return [{"date": "2024-01-01", "articles": "#art", "views": 10, "video_name": "Video 1"}]

    monkeypatch.setattr(videohistory, "VideoHistoryService", ServiceStub)

    response = await client.get(
        "/api/v1/videohistory/filtered_stats_art",
        params={"user_ids": ["1", "2"]},
    )

    assert response.status_code == 200
    assert response.json() == [{"date": "2024-01-01", "articles": "#art", "views": 10, "video_name": "Video 1"}]
    assert captured["user"] == admin_user
    assert captured["user_ids"] == [1, 2], captured


@pytest.mark.asyncio
async def test_filtered_stats_all_accepts_multiple_users(
    client: AsyncClient,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: Dict[str, Any] = {}

    class ServiceStub:
        def __init__(self, db: Any):
            pass

        async def get_aggregated_views_by_date_all(self, **kwargs):
            captured.update(kwargs)
            return [{"date": "2024-01-01", "views": 100, "likes": 10, "comments": 1}]

    monkeypatch.setattr(videohistory, "VideoHistoryService", ServiceStub)

    response = await client.get(
        "/api/v1/videohistory/filtered_stats_all",
        params={"user_ids": ["1", "2"]},
    )

    assert response.status_code == 200
    assert response.json() == [
        {"date": "2024-01-01", "views": 100, "likes": 10, "comments": 1}
    ]
    assert captured["user"] == admin_user
    assert captured["user_ids"] == [1, 2], captured


@pytest.mark.asyncio
async def test_daily_video_with_article_count_accepts_multiple_users(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: Dict[str, Any] = {}

    class ResultStub:
        def __init__(self, result_date: dt_date, video_count: int):
            self.date = result_date
            self.video_count = video_count

    class ServiceStub:
        def __init__(self, db: Any):
            pass

        async def get_daily_video_with_article_count(self, **kwargs):
            captured.update(kwargs)
            return [ResultStub(dt_date(2024, 1, 1), 5)]

    monkeypatch.setattr(videohistory, "VideoHistoryService", ServiceStub)

    response = await client.get(
        "/api/v1/videohistory/daily_article_count",
        params={"user_ids": ["1", "3"]},
    )

    assert response.status_code == 200
    assert response.json() == [{"date": "2024-01-01", "video_count": 5}]
    assert captured["user_ids"] == [1, 3]


@pytest.mark.asyncio
async def test_daily_video_count_all_accepts_multiple_users(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: Dict[str, Any] = {}

    class ResultStub:
        def __init__(self, result_date: dt_date, video_count: int):
            self.date = result_date
            self.video_count = video_count

    class ServiceStub:
        def __init__(self, db: Any):
            pass

        async def get_daily_video_count_all(self, **kwargs):
            captured.update(kwargs)
            return [ResultStub(dt_date(2024, 2, 2), 7)]

    monkeypatch.setattr(videohistory, "VideoHistoryService", ServiceStub)

    response = await client.get(
        "/api/v1/videohistory/daily_count_all",
        params={"user_ids": ["4", "5"]},
    )

    assert response.status_code == 200
    assert response.json() == [{"date": "2024-02-02", "video_count": 7}]
    assert captured["user_ids"] == [4, 5]


@pytest.mark.asyncio
async def test_download_video_stats_csv_accepts_multiple_users(
    client: AsyncClient,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: Dict[str, Any] = {}

    class ServiceStub:
        def __init__(self, db: Any):
            pass

        async def get_video_stats_for_csv(
            self, **kwargs
        ) -> Tuple[List[Dict[str, Any]], List[dt_date]]:
            captured.update(kwargs)
            stats = [
                {
                    "video_name": "Video 1",
                    "link": "https://example.com/video/1",
                    "daily_views": {dt_date(2024, 1, 1): 15, dt_date(2024, 1, 2): 20},
                    "daily_likes": {},
                    "daily_comments": {},
                }
            ]
            return stats, [dt_date(2024, 1, 1), dt_date(2024, 1, 2)]

    monkeypatch.setattr(videohistory, "VideoHistoryService", ServiceStub)

    response = await client.get(
        "/api/v1/videohistory/download_stats_csv",
        params={"user_ids": ["1", "2"]},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    content = response.text.splitlines()
    assert content[0].startswith("Название видео,Ссылка на ролик,2024-01-01,2024-01-02")
    assert "Video 1" in content[1]
    assert captured["user"] == admin_user
    assert captured["target_user_ids"] == [1, 2]


@pytest.mark.asyncio
async def test_get_video_history_by_id_returns_stubbed_value(
    client: AsyncClient,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: Dict[str, Any] = {}

    class ServiceStub:
        def __init__(self, db: Any):
            pass

        async def get_by_id(self, id: int, user: Optional[User] = None):
            captured["id"] = id
            captured["user"] = user
            return {"id": id, "value": "ok"}

    monkeypatch.setattr(videohistory, "VideoHistoryService", ServiceStub)

    response = await client.get("/api/v1/videohistory/42")

    assert response.status_code == 200
    assert response.json() == {"id": 42, "value": "ok"}
    assert captured["id"] == 42
    assert captured["user"] == admin_user
