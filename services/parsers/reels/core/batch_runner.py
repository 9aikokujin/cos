# Пробуем запустить парсинг инст акков пачкой, получать список каналов из API и парсить их за одну очередь
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

import httpx
from core.parser import InstagramParser
from utils.batch_state import BatchProgressStore
from utils.logger import TCPLogger


@dataclass(frozen=True)
class InstagramChannelTask:
    """Задача для batch-парсинга Instagram."""
    channel_id: int
    url: str
    user_id: int
    parse_started_at: Optional[str] = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "InstagramChannelTask":
        """Создает задачу для batch-парсинга Instagram из payload."""
        return cls(
            channel_id=int(payload["channel_id"]),
            url=str(payload["url"]),
            user_id=int(payload.get("user_id", 0)),
            parse_started_at=payload.get("parse_started_at"),
        )


class InstagramBatchRunner:
    """Запускает batch-парсинг Instagram."""
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
        channels_per_wave: int = 5,
        pause_between_waves_seconds: int = 150,
        progress_store: Optional[BatchProgressStore] = None,
    ):
        """Инициализирует запуск batch-парсинга Instagram."""
        self.parser = parser
        self.logger = logger or parser.logger
        self.retries_per_channel = max(1, retries_per_channel)
        self.session_refresh_on_failure = session_refresh_on_failure
        self.collect_attempts = max(1, collect_attempts)
        self.channels_api_url = channels_api_url
        self.channels_api_token = channels_api_token
        self.channels_per_wave = max(0, int(channels_per_wave))
        self.pause_between_waves_seconds = max(0, int(pause_between_waves_seconds))
        self.progress_store = progress_store

    def _normalize_tasks(
        self,
        tasks: Iterable[InstagramChannelTask | Mapping[str, Any]],
    ) -> list[InstagramChannelTask]:
        """Нормализует задачи для batch-парсинга Instagram."""
        normalized: list[InstagramChannelTask] = []
        for task in tasks:
            if isinstance(task, InstagramChannelTask):
                normalized.append(task)
            else:
                normalized.append(InstagramChannelTask.from_payload(task))
        return normalized

    async def fetch_channels_from_api(self) -> list[InstagramChannelTask]:
        """Загружает каналы из API."""
        if not self.channels_api_url:
            self.logger.send("INFO", "CHANNELS_API_URL не задан — пропускаем загрузку каналов из API.")
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
            self.logger.send("INFO", f"Не удалось получить список каналов из API: {exc}")
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
            self.logger.send("INFO", "API каналов не вернуло ни одной записи.")
        else:
            self.logger.send("INFO", f"Из API получено {len(tasks)} Instagram-каналов.")
        return tasks

    async def prepare_sessions(self, accounts: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        """Подготавливает сессии для аккаунтов."""
        filtered = [acc for acc in accounts if acc]
        if not filtered:
            self.logger.send("INFO", "Список аккаунтов для batch-парсинга пуст.")
            return {}
        return await self.parser.ensure_initial_cookies(filtered)

    async def run(
        self,
        *,
        channel_tasks: Iterable[InstagramChannelTask | Mapping[str, Any]],
        accounts: Sequence[str],
        proxy_list: Sequence[str],
        max_retries: Optional[int] = None,
        retry_pause_seconds: int = 300,
        refetch_on_full_failure: bool = True,
        batch_id: Optional[str] = None,
    ) -> None:
        """
        Последовательно обходит каналы Instagram, используя заранее подготовленные cookies.
        Авторизация выполняется один раз и переинициируется только при ошибках.
        """
        tasks = self._normalize_tasks(channel_tasks)
        if not tasks:
            self.logger.send("INFO", "Нет каналов для batch-парсинга Instagram.")
            return

        processed_cache: set[int] = set()
        processed_since_pause = 0
        if batch_id and self.progress_store:
            processed_cache = self.progress_store.load(batch_id)
            if processed_cache:
                tasks = self._filter_processed(tasks, processed_cache, batch_id)
                processed_since_pause = (
                    len(processed_cache) % self.channels_per_wave
                    if self.channels_per_wave
                    else 0
                )
        if not tasks:
            self.logger.send(
                "INFO",
                "Batch-очередь пуста: все каналы ранее завершились успешно, завершаем задачу.",
            )
            return

        if not self.parser.configure_proxy_list(list(proxy_list)):
            return

        sessions = await self.prepare_sessions(accounts)
        if not sessions:
            self.logger.send("INFO", "Не удалось подготовить cookies — batch-парсинг остановлен.")
            return

        attempt = 1
        while True:
            success_any = False
            sessions_depleted = False

            for idx, task in enumerate(tasks, start=1):
                success, sessions = await self._process_task(
                    task,
                    sessions,
                    accounts,
                    max_retries=max_retries,
                )
                if success:
                    success_any = True
                    if batch_id and self.progress_store:
                        self.progress_store.mark_processed(batch_id, task.channel_id)
                        processed_cache.add(task.channel_id)
                if not sessions:
                    sessions_depleted = True
                    self.logger.send(
                        "INFO",
                        f"Сессии закончились на канале {task.channel_id}, дальнейшая обработка невозможна.",
                    )
                    break

                if self.channels_per_wave:
                    processed_since_pause += 1
                    threshold_reached = processed_since_pause >= self.channels_per_wave
                    if threshold_reached:
                        processed_since_pause = 0
                        if (
                            self.pause_between_waves_seconds > 0
                            and not sessions_depleted
                            and idx < len(tasks)
                        ):
                            wait_display = (
                                f"{self.pause_between_waves_seconds // 60} мин"
                                if self.pause_between_waves_seconds % 60 == 0
                                else f"{self.pause_between_waves_seconds} сек"
                            )
                            self.logger.send(
                                "INFO",
                                f"Обработано {self.channels_per_wave} каналов, ждём {wait_display} для снижения нагрузки.",
                            )
                            await asyncio.sleep(self.pause_between_waves_seconds)

            if sessions_depleted:
                break

            if success_any or not tasks:
                break

            if retry_pause_seconds > 0:
                if retry_pause_seconds % 60 == 0:
                    wait_display = f"{retry_pause_seconds // 60} мин"
                else:
                    wait_display = f"{retry_pause_seconds} сек"
            else:
                wait_display = "0 сек"

            self.logger.send(
                "INFO",
                f"Все {len(tasks)} каналов завершились ошибками (попытка {attempt}). "
                f"Ждём {wait_display} перед повтором.",
            )
            attempt += 1
            if retry_pause_seconds > 0:
                await asyncio.sleep(retry_pause_seconds)

            if refetch_on_full_failure:
                refreshed = await self.fetch_channels_from_api()
                if refreshed:
                    tasks = self._filter_processed(refreshed, processed_cache, batch_id)
                    self.logger.send("INFO", f"Обновлён список каналов: {len(tasks)} записей.")
                elif not tasks:
                    self.logger.send("INFO", "После повторной загрузки каналов список пуст — выходим.")
                    break

            sessions = await self.prepare_sessions(accounts)
            if not sessions:
                self.logger.send("INFO", "Не удалось восстановить валидные cookies после ожидания, batch остановлен.")
                break

    def _filter_processed(
        self,
        tasks: list[InstagramChannelTask],
        processed_cache: set[int],
        batch_id: Optional[str],
    ) -> list[InstagramChannelTask]:
        """Фильтрует обработанные каналы при повторном запуске."""
        if not processed_cache:
            return tasks
        filtered = [task for task in tasks if task.channel_id not in processed_cache]
        skipped = len(tasks) - len(filtered)
        if skipped > 0:
            if batch_id:
                self.logger.send(
                    "INFO",
                    f"Batch {batch_id}: пропускаем {skipped} каналов, уже обработаны ранее.",
                )
            else:
                self.logger.send(
                    "INFO",
                    f"Пропущено {skipped} каналов из-за ранее сохранённого прогресса.",
                )
        return filtered

    async def _process_task(
        self,
        task: InstagramChannelTask,
        sessions: Dict[str, Dict[str, Any]],
        accounts: Sequence[str],
        *,
        max_retries: Optional[int],
    ) -> Tuple[bool, Dict[str, Dict[str, Any]]]:
        """Обрабатывает задачу парсинга Instagram."""
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
                f"Канал {task.channel_id}: обновляем сессии перед повторной попыткой ({attempt}/{self.retries_per_channel})",
            )
            current_sessions = await self.prepare_sessions(accounts)
            if not current_sessions:
                return False, {}

        self.logger.send("INFO", f"Не удалось обработать канал {task.channel_id} после {self.retries_per_channel} попыток")
        return False, current_sessions
