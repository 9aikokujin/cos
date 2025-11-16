from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

import httpx
from core.parser import InstagramParser
from utils.logger import TCPLogger


@dataclass(frozen=True)
class InstagramChannelTask:
    channel_id: int
    url: str
    user_id: int
    parse_started_at: Optional[str] = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "InstagramChannelTask":
        return cls(
            channel_id=int(payload["channel_id"]),
            url=str(payload["url"]),
            user_id=int(payload.get("user_id", 0)),
            parse_started_at=payload.get("parse_started_at"),
        )


class InstagramBatchRunner:
    def __init__(
        self,
        parser: InstagramParser,
        logger: Optional[TCPLogger] = None,
        *,
        retries_per_channel: int = 1,
        session_refresh_on_failure: bool = True,
        collect_attempts: int = 1,
        channels_api_url: Optional[str] = None,
        channels_api_token: Optional[str] = None,
    ):
        self.parser = parser
        self.logger = logger or parser.logger
        self.retries_per_channel = max(1, retries_per_channel)
        self.session_refresh_on_failure = session_refresh_on_failure
        self.collect_attempts = max(1, collect_attempts)
        self.channels_api_url = channels_api_url
        self.channels_api_token = channels_api_token

    def _normalize_tasks(
        self,
        tasks: Iterable[InstagramChannelTask | Mapping[str, Any]],
    ) -> list[InstagramChannelTask]:
        normalized: list[InstagramChannelTask] = []
        for task in tasks:
            if isinstance(task, InstagramChannelTask):
                normalized.append(task)
            else:
                normalized.append(InstagramChannelTask.from_payload(task))
        return normalized

    async def fetch_channels_from_api(self) -> list[InstagramChannelTask]:
        if not self.channels_api_url:
            self.logger.send("INFO", "ℹ️ CHANNELS_API_URL не задан — пропускаем загрузку каналов из API.")
            return []

        url = self.channels_api_url
        if self.channels_api_token:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{self.channels_api_token}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            self.logger.send("INFO", f"❌ Не удалось получить список каналов из API: {exc}")
            return []

        channels = payload.get("channels") or []
        tasks: list[InstagramChannelTask] = []
        for entry in channels:
            channel_id = entry.get("id")
            link = entry.get("link")
            if not channel_id or not link:
                continue
            tasks.append(
                InstagramChannelTask(
                    channel_id=int(channel_id),
                    url=str(link),
                    user_id=int(entry.get("user_id") or 0),
                    parse_started_at=entry.get("parse_started_at"),
                )
            )

        if not tasks:
            self.logger.send("INFO", "⚠️ API каналов не вернуло ни одной записи.")
        else:
            self.logger.send("INFO", f"✅ Из API получено {len(tasks)} Instagram-каналов.")
        return tasks

    async def prepare_sessions(self, accounts: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        filtered = [acc for acc in accounts if acc]
        if not filtered:
            self.logger.send("INFO", "⚠️ Список аккаунтов для batch-парсинга пуст.")
            return {}
        return await self.parser.ensure_initial_cookies(filtered)

    async def run(
        self,
        *,
        channel_tasks: Iterable[InstagramChannelTask | Mapping[str, Any]],
        accounts: Sequence[str],
        proxy_list: Sequence[str],
        max_retries: Optional[int] = None,
    ) -> None:
        """
        Последовательно обходит каналы Instagram, используя заранее подготовленные cookies.
        Авторизация выполняется один раз и переинициируется только при ошибках.
        """
        tasks = self._normalize_tasks(channel_tasks)
        if not tasks:
            self.logger.send("INFO", "⚠️ Нет каналов для batch-парсинга Instagram.")
            return

        if not self.parser.configure_proxy_list(list(proxy_list)):
            return

        sessions = await self.prepare_sessions(accounts)
        if not sessions:
            self.logger.send("INFO", "❌ Не удалось подготовить cookies — batch-парсинг остановлен.")
            return

        for task in tasks:
            success, sessions = await self._process_task(
                task,
                sessions,
                accounts,
                max_retries=max_retries,
            )
            if not success and not sessions:
                self.logger.send("INFO", f"❌ Нет валидных сессий после канала {task.channel_id}, останавливаем batch.")
                break

    async def _process_task(
        self,
        task: InstagramChannelTask,
        sessions: Dict[str, Dict[str, Any]],
        accounts: Sequence[str],
        *,
        max_retries: Optional[int],
    ) -> Tuple[bool, Dict[str, Dict[str, Any]]]:
        current_sessions = sessions
        for attempt in range(1, self.retries_per_channel + 1):
            success = await self.parser.parse_channel_with_sessions(
                url=task.url,
                channel_id=task.channel_id,
                user_id=task.user_id,
                sessions=current_sessions,
                max_retries=max_retries,
                max_attempts_collect=self.collect_attempts,
                parse_started_at=task.parse_started_at,
            )
            if success:
                return True, current_sessions

            if not self.session_refresh_on_failure or attempt == self.retries_per_channel:
                break

            self.logger.send(
                "INFO",
                f"🔁 Канал {task.channel_id}: обновляем сессии перед повторной попыткой ({attempt}/{self.retries_per_channel})",
            )
            current_sessions = await self.prepare_sessions(accounts)
            if not current_sessions:
                return False, {}

        self.logger.send("INFO", f"❌ Не удалось обработать канал {task.channel_id} после {self.retries_per_channel} попыток")
        return False, current_sessions
