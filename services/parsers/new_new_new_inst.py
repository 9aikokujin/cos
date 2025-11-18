import asyncio
import inspect
import json
import random
# import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, Union
from urllib.parse import quote, urlparse

import httpx
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, async_playwright
# from utils.logger import TCPLogger
import pyotp

# try:  # поддержка новых версий playwright-stealth
#     from playwright_stealth import stealth_async as apply_stealth
# except ImportError:  # fallback на старый API
#     try:
#         from playwright_stealth import Stealth  # type: ignore

#         async def apply_stealth(page):
#             await Stealth().apply_stealth_async(page)
#     except Exception:  # если stealth не установлен/сломался
#         apply_stealth = None  # type: ignore

INSTAGRAM_APP_ID = "936619743392459"
DEFAULT_DOC_ID_REEL = "25981206651899035"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
BASE_REQUEST_HEADERS = {
    "x-ig-app-id": INSTAGRAM_APP_ID,
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "*/*",
    "Referer": "https://www.instagram.com/",
}
IMPORTANT_COOKIES = {
    "sessionid",
    "csrftoken",
    "ds_user_id",
    "mid",
    "shbid",
    "shbts",
    "rur",
    "ig_did",
    "ig_nrcb",
}
COOKIES_FILE_PATH = Path(__file__).with_name("instagram_cookies.json")
REQUEST_TIMEOUT = 20.0
MAX_PARALLEL_LOGIN_TASKS = 3
HTTPX_USES_PROXY_PARAM = "proxy" in inspect.signature(httpx.AsyncClient.__init__).parameters


class InvalidCredentialsError(Exception):
    """Возникает при некорректных учётных данных Instagram."""


class InstagramParser:
    def __init__(
            self,
            # logger: TCPLogger,
    ):
        # self.logger = logger
        self.proxy_list: list[str] = []
        self.cookie_file_path = COOKIES_FILE_PATH
        self.session_cache: Dict[str, Dict[str, Any]] = self._load_cookie_store()
        self.account_credentials: Dict[str, Dict[str, str]] = {}
        self.invalid_accounts: set[str] = set()

    @staticmethod
    def _parse_started_at(value: Optional[Union[str, datetime]]) -> datetime:
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str) and value.strip():
            text = value.strip()
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(text)
            except ValueError:
                dt = datetime.now(timezone.utc)
        else:
            dt = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def _log_summary(
        self,
        url: str,
        channel_id: int,
        video_count: int,
        total_views: int,
        started_at: datetime,
        ended_at: datetime,
        success: bool,
    ) -> None:
        status_icon = "✅" if success else "⚠️"
        status_text = "Успешно спарсили" if success else "Не удалось спарсить"
        print(
            f"{status_icon} {status_text} {url} с {channel_id} "
            f"кол-во видео - {video_count}, кол-во просмотров - {total_views}, "
            f"время начала парсинга - {started_at.isoformat()}, конец парсинга - {ended_at.isoformat()}",
        )

    def _load_cookie_store(self) -> Dict[str, Dict[str, Any]]:
        if self.cookie_file_path.exists():
            try:
                with self.cookie_file_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
                    print(f"⚠️ Некорректный формат cookie-файла {self.cookie_file_path}, ожидается dict")
            except Exception as exc:
                print(f"⚠️ Не удалось прочитать cookie-файл {self.cookie_file_path}: {exc}")
        return {}

    def _persist_cookie_store(self) -> None:
        try:
            self.cookie_file_path.parent.mkdir(parents=True, exist_ok=True)
            with self.cookie_file_path.open("w", encoding="utf-8") as f:
                json.dump(self.session_cache, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            print(f"⚠️ Не удалось сохранить cookies в {self.cookie_file_path}: {exc}")

    def _build_headers(self, user_agent: Optional[str] = None, csrf_token: Optional[str] = None) -> Dict[str, str]:
        headers = dict(BASE_REQUEST_HEADERS)
        if user_agent:
            headers["User-Agent"] = user_agent
        if csrf_token:
            headers["x-csrftoken"] = csrf_token
        headers.setdefault("X-Requested-With", "XMLHttpRequest")
        return headers

    @staticmethod
    def _parse_proxy(proxy_str: Optional[str]) -> Optional[Dict[str, str]]:
        if not proxy_str:
            return None
        try:
            if "@" in proxy_str:
                auth, host_port = proxy_str.split("@", 1)
                username, password = auth.split(":", 1)
                host, port = host_port.split(":", 1)
                return {
                    "server": f"http://{host}:{port}",
                    "username": username,
                    "password": password,
                }
            host, port = proxy_str.split(":", 1)
            return {"server": f"http://{host}:{port}"}
        except Exception as exc:
            # print(f"⚠️ Неверный формат прокси '{proxy_str}': {exc}")
            return None

    @staticmethod
    def _dedupe_proxies(proxies: list[Optional[str]]) -> list[Optional[str]]:
        seen: set[Optional[str]] = set()
        ordered: list[Optional[str]] = []
        for proxy in proxies:
            if proxy not in seen:
                ordered.append(proxy)
                seen.add(proxy)
        return ordered

    @staticmethod
    def _normalize_proxy_input(proxy_list: Optional[Any]) -> list[str]:
        if proxy_list is None:
            return []
        if isinstance(proxy_list, str):
            text = proxy_list.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                proxy_list = [item.strip() for item in text.replace("\r", "\n").split("\n") if item.strip()]
            else:
                proxy_list = parsed
        normalized: list[str] = []
        for proxy in proxy_list:
            if not proxy:
                continue
            normalized.append(str(proxy).strip())
        return normalized
    
    async def _start_playwright(self):
        try:
            return await async_playwright().start()
        except Exception as exc:
            print(f"❌ Не удалось запустить Playwright: {exc}")
            return None
        
    
    async def _safe_close(self, obj, label: str, method: str = "close"):
        if not obj:
            return
        closer = getattr(obj, method, None)
        if not closer:
            return
        try:
            result = closer()
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            print(f"⚠️ Ошибка закрытия {label}: {exc}")

    async def _cleanup_browser_stack(self, page=None, context=None, browser=None):
        await self._safe_close(page, "page")
        await self._safe_close(context, "context")
        await self._safe_close(browser, "browser")

    def configure_proxy_list(self, proxy_list: Optional[list[str]]) -> bool:
        if proxy_list is None:
            print("❌ proxy_list не передан — задача остановлена.")
            return False
        normalized_proxies = self._normalize_proxy_input(proxy_list)
        if normalized_proxies:
            print(f"🔁 Обновляем список прокси из аргумента: {normalized_proxies}")
        else:
            print("ℹ️ Парсинг будет выполнен без прокси (после нормализации список пуст).")
        self.proxy_list = normalized_proxies
        return True

    @staticmethod
    def _extract_auth_cookies(raw_cookies: list[Dict[str, Any]]) -> Dict[str, str]:
        auth_cookies: Dict[str, str] = {}
        for cookie in raw_cookies:
            name = cookie.get("name")
            value = cookie.get("value")
            domain = cookie.get("domain", "")
            if not name or not value:
                continue
            if "instagram.com" not in domain:
                continue
            if name in IMPORTANT_COOKIES or domain.endswith("instagram.com"):
                auth_cookies[name] = value
        return auth_cookies

    def _update_cookie_entry(
        self,
        username: str,
        cookies: Dict[str, str],
        user_agent: Optional[str],
        proxy: Optional[str],
    ) -> Dict[str, Any]:
        entry = {
            "cookies": cookies,
            "user_agent": user_agent or DEFAULT_USER_AGENT,
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "proxy": proxy,
        }
        self.session_cache[username] = entry
        self._persist_cookie_store()
        return entry

    def _drop_session(self, username: str) -> None:
        if username in self.session_cache:
            self.session_cache.pop(username, None)
            self._persist_cookie_store()

    async def _refresh_session(self, username: str) -> Optional[Dict[str, Any]]:
        creds = self.account_credentials.get(username)
        if not creds:
            print(f"⚠️ Нет сохранённых учётных данных для {username}, пропускаем обновление cookies")
            return None
        return await self._login_and_store_cookies(
            username,
            creds.get("password", ""),
            creds.get("two_factor_code", ""),
        )

    @staticmethod
    def _format_proxy_for_httpx(proxy_str: Optional[str]) -> Optional[str]:
        if not proxy_str:
            return None
        if proxy_str.startswith("http://") or proxy_str.startswith("https://"):
            return proxy_str
        if "@" in proxy_str:
            auth, host_port = proxy_str.split("@", 1)
            return f"http://{auth}@{host_port}"
        return f"http://{proxy_str}"

    def _iter_proxy_candidates(self, entry: Dict[str, Any]) -> list[Optional[str]]:
        assigned_proxy = entry.get("proxy")
        candidates: list[Optional[str]] = []

        def add_candidate(value: Optional[str]) -> None:
            if value not in candidates:
                candidates.append(value)

        if assigned_proxy:
            add_candidate(str(assigned_proxy))
        else:
            add_candidate(None)

        for proxy in self._dedupe_proxies(self.proxy_list or []):
            add_candidate(proxy)

        add_candidate(None)
        return candidates

    def _record_successful_proxy(
        self,
        username: str,
        entry: Dict[str, Any],
        proxy: Optional[str],
    ) -> None:
        current_proxy = entry.get("proxy")
        if current_proxy == proxy:
            return

        entry["proxy"] = proxy
        if username in self.session_cache:
            self.session_cache[username]["proxy"] = proxy
            self._persist_cookie_store()

    async def _validate_cookies(
        self,
        entry: Optional[Dict[str, Any]],
        *,
        proxy: Optional[str] = None,
    ) -> tuple[bool, Optional[int]]:
        if not entry:
            return False, None
        cookies = entry.get("cookies") or {}
        if not cookies.get("sessionid"):
            return False, None
        headers = self._build_headers(entry.get("user_agent"), cookies.get("csrftoken"))
        proxy_for_httpx = self._format_proxy_for_httpx(proxy)
        client_kwargs: Dict[str, Any] = {"timeout": REQUEST_TIMEOUT}
        if proxy_for_httpx:
            if HTTPX_USES_PROXY_PARAM:
                client_kwargs["proxy"] = proxy_for_httpx
            else:
                client_kwargs["proxies"] = {
                    "http": proxy_for_httpx,
                    "https": proxy_for_httpx,
                }
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.get(
                    "https://i.instagram.com/api/v1/accounts/current_user/",
                    headers=headers,
                    cookies=cookies,
                )
                status = resp.status_code
                if status == 200:
                    return True, status
                if status in (401, 403, 400):
                    return False, status
                if status == 429:
                    print("⚠️ Получен 429 при проверке cookies, оставляем их валидными.")
                    return True, status
        except Exception as exc:
            print(f"⚠️ Ошибка при проверке cookies: {exc}")
        return False, None

    async def ensure_initial_cookies(self, accounts: list[str]) -> Dict[str, Dict[str, Any]]:
        valid_sessions: Dict[str, Dict[str, Any]] = {}
        if not accounts:
            return valid_sessions

        self.invalid_accounts.clear()

        proxy_pool = self._dedupe_proxies(self.proxy_list or [])
        if proxy_pool:
            if None not in proxy_pool:
                proxy_pool.append(None)
        else:
            proxy_pool = [None]

        proxy_pool = list(proxy_pool)
        total_unique_proxies = len(proxy_pool)

        proxy_condition = asyncio.Condition()
        in_use_proxies: set[Optional[str]] = set()

        async def acquire_specific_proxy(
            proxy: Optional[str],
            tried: set[Optional[str]],
        ) -> bool:
            async with proxy_condition:
                if proxy not in proxy_pool or proxy in tried:
                    return False
                if proxy in in_use_proxies:
                    return False
                in_use_proxies.add(proxy)
                return True

        async def acquire_proxy(
            tried: set[Optional[str]],
        ) -> tuple[bool, Optional[str]]:
            async with proxy_condition:
                while True:
                    for proxy in proxy_pool:
                        if proxy not in in_use_proxies and proxy not in tried:
                            in_use_proxies.add(proxy)
                            return True, proxy
                    if len(tried) >= total_unique_proxies:
                        return False, None
                    await proxy_condition.wait()

        async def release_proxy(proxy: Optional[str]) -> None:
            async with proxy_condition:
                if proxy in in_use_proxies:
                    in_use_proxies.remove(proxy)
                    proxy_condition.notify_all()

        # ограничиваем количество одновременно открытых браузеров
        max_workers = min(total_unique_proxies or 1, MAX_PARALLEL_LOGIN_TASKS, len(accounts))
        max_workers = max(1, max_workers)

        result_lock = asyncio.Lock()

        async def mark_valid(username: str, entry: Dict[str, Any]) -> None:
            async with result_lock:
                valid_sessions[username] = entry

        async def mark_invalid(username: str) -> None:
            async with result_lock:
                self.invalid_accounts.add(username)

        async def process_account(account: str) -> None:
            try:
                username, password, two_factor_code = account.split(":", 2)
            except ValueError:
                print(f"⚠️ Некорректный формат аккаунта '{account}', ожидается username:password:2fa")
                return

            self.account_credentials[username] = {
                "password": password,
                "two_factor_code": two_factor_code,
            }

            cached_entry = self.session_cache.get(username)
            last_proxy: Optional[str] = None
            if cached_entry:
                last_proxy = cached_entry.get("proxy")
                is_valid, status_code = await self._validate_cookies(
                    cached_entry,
                    proxy=last_proxy,
                )
                if is_valid:
                    await mark_valid(username, cached_entry)
                    return
                status_text = status_code if status_code is not None else "unknown"
                print(f"🔁 Куки {username} в кеше просрочены или недоступны (статус {status_text}) — обновляем")
                self._drop_session(username)

            tried_proxies: set[Optional[str]] = set()

            if last_proxy in proxy_pool:
                acquired_specific = await acquire_specific_proxy(last_proxy, tried_proxies)
                if acquired_specific:
                    entry_specific: Optional[Dict[str, Any]] = None
                    try:
                        entry_specific = await self._login_and_store_cookies(
                            username,
                            password,
                            two_factor_code,
                            proxy_candidates=[last_proxy],
                        )
                    except InvalidCredentialsError as cred_exc:
                        print(f"⚠️ Пропускаем аккаунт {username}: {cred_exc}")
                        self._drop_session(username)
                        await mark_invalid(username)
                        return
                    except Exception as exc:
                        print(f"⚠️ Ошибка авторизации {username} через прокси {last_proxy}: {exc}")
                    finally:
                        await release_proxy(last_proxy)

                    tried_proxies.add(last_proxy)

                    if entry_specific:
                        await mark_valid(username, entry_specific)
                        return

            while len(tried_proxies) < total_unique_proxies:
                acquired, proxy = await acquire_proxy(tried_proxies)
                if not acquired:
                    break

                entry: Optional[Dict[str, Any]] = None
                try:
                    entry = await self._login_and_store_cookies(
                        username,
                        password,
                        two_factor_code,
                        proxy_candidates=[proxy],
                    )
                except InvalidCredentialsError as cred_exc:
                    print(f"⚠️ Пропускаем аккаунт {username}: {cred_exc}")
                    self._drop_session(username)
                    await mark_invalid(username)
                    return
                except Exception as exc:
                    print(f"⚠️ Ошибка авторизации {username} через прокси {proxy}: {exc}")
                finally:
                    await release_proxy(proxy)

                tried_proxies.add(proxy)

                if entry:
                    await mark_valid(username, entry)
                    return

            print(f"❌ Не удалось обновить cookies для {username} — исчерпаны прокси/попытки")

        semaphore = asyncio.Semaphore(max_workers)

        async def worker(account: str) -> None:
            async with semaphore:
                await process_account(account)

        tasks = [asyncio.create_task(worker(account)) for account in accounts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                print(f"⚠️ Необработанная ошибка при сборе cookies: {result}")

        if self.invalid_accounts:
            invalid_list = ", ".join(sorted(self.invalid_accounts))
            print(f"⚠️ Аккаунты с некорректным паролем: {invalid_list}")

        return valid_sessions

    async def _login_and_store_cookies(
        self,
        username: str,
        password: str,
        two_factor_code: str,
        proxy_candidates: Optional[list[Optional[str]]] = None,
    ) -> Optional[Dict[str, Any]]:
        cached_entry = self.session_cache.get(username)
        if cached_entry:
            try:
                is_valid, status_code = await self._validate_cookies(
                    cached_entry,
                    proxy=cached_entry.get("proxy"),
                )
                if is_valid:
                    print(f"♻️ Куки для {username} ещё действительны — повторный логин не требуется (статус {status_code})")
                    return cached_entry
                else:
                    print(f"🔁 Куки для {username} устарели — инициируем новое получение")
                    self._drop_session(username)
            except Exception as exc:
                print(f"⚠️ Ошибка при проверке сохранённых cookies {username}: {exc}")

        proxy_pool = self._dedupe_proxies(proxy_candidates or self.proxy_list or [])
        if proxy_candidates is None:
            if proxy_pool and None not in proxy_pool:
                proxy_pool.append(None)
            if not proxy_pool:
                proxy_pool = [None]
        elif not proxy_pool:
            proxy_pool = [None]

        for proxy_str in proxy_pool:
            playwright = await self._start_playwright()
            if not playwright:
                continue
            browser = None
            context = None
            page = None
            try:
                device = playwright.devices.get("iPhone 14 Pro")
                browser = await playwright.chromium.launch(
                    headless=False,
                    args=["--window-size=390,844"],
                )
                context_kwargs: Dict[str, Any] = {
                    **(device or {}),
                    "locale": "en-US",
                    # "timezone_id": "America/Vancouver",
                }
                proxy_config = self._parse_proxy(proxy_str)
                if proxy_config:
                    context_kwargs["proxy"] = proxy_config

                context = await browser.new_context(**context_kwargs)
                page = await context.new_page()
                # if apply_stealth:
                #     try:
                #         await apply_stealth(page)
                #     except Exception as stealth_exc:
                #         print(f"⚠️ Не удалось применить playwright-stealth: {stealth_exc}")

                cookies = await self.login_to_instagram(page, username, password, two_factor_code)
                if cookies:
                    user_agent = await page.evaluate("navigator.userAgent")
                    entry = self._update_cookie_entry(username, cookies, user_agent, proxy_str)
                    print(f"✅ Сохранены cookies для {username} (прокси: {proxy_str})")
                    return entry
                print(f"⚠️ Не удалось авторизоваться с аккаунтом {username} на прокси {proxy_str}")
            except InvalidCredentialsError as cred_exc:
                self._drop_session(username)
                raise cred_exc
            except Exception as exc:
                print(f"⚠️ Ошибка авторизации {username} через прокси {proxy_str}: {exc}")
            finally:
                await self._cleanup_browser_stack(page, context, browser)
                await self._safe_close(playwright, "playwright", method="stop")
        return None

    async def _request_with_sessions(
        self,
        sessions: Dict[str, Dict[str, Any]],
        url: str,
        *,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> tuple[httpx.Response, str, Dict[str, Any]]:
        if not sessions:
            raise RuntimeError("Нет доступных сохранённых cookies для Instagram")

        session_items = list(sessions.items())
        random.shuffle(session_items)
        last_exception: Optional[Exception] = None

        for username, entry in session_items:
            headers = self._build_headers(entry.get("user_agent"), entry["cookies"].get("csrftoken"))
            for proxy in self._iter_proxy_candidates(entry):
                client_kwargs: Dict[str, Any] = {
                    "timeout": REQUEST_TIMEOUT,
                    "headers": headers,
                    "cookies": entry["cookies"],
                }
                proxy_for_httpx = self._format_proxy_for_httpx(proxy)
                if proxy_for_httpx:
                    if HTTPX_USES_PROXY_PARAM:
                        client_kwargs["proxy"] = proxy_for_httpx
                    else:
                        client_kwargs["proxies"] = {
                            "http": proxy_for_httpx,
                            "https": proxy_for_httpx,
                        }
                try:
                    async with httpx.AsyncClient(**client_kwargs) as client:
                        response = await client.request(method, url, params=params, data=data)

                    status = response.status_code
                    if status == 200:
                        self._record_successful_proxy(username, entry, proxy)
                        return response, username, entry

                    if status in (401, 403):
                        print(f"⚠️ Сессия {username} вернула {status}, обновляем cookies...")
                        self._drop_session(username)
                        refreshed = await self._refresh_session(username)
                        if refreshed:
                            sessions[username] = refreshed
                        else:
                            sessions.pop(username, None)
                        break

                    if status == 400:
                        print(f"⚠️ Сессия {username} вернула 400, пробуем другую сессию.")
                        break

                    if status == 429:
                        print(f"⚠️ Сессия {username} получила 429 (rate limit), пробуем другую.")
                        break

                    if status == 404:
                        self._record_successful_proxy(username, entry, proxy)
                        return response, username, entry

                    response.raise_for_status()
                    self._record_successful_proxy(username, entry, proxy)
                    return response, username, entry
                except Exception as exc:
                    last_exception = exc
                    proxy_label = proxy if proxy else "без прокси"
                    print(f"⚠️ Ошибка при запросе ({username}, прокси {proxy_label}): {exc}")
                    if not isinstance(
                        exc,
                        (
                            httpx.ConnectError,
                            httpx.ProxyError,
                            httpx.TimeoutException,
                        ),
                    ):
                        break
                    continue

        if last_exception:
            raise last_exception
        raise RuntimeError("Не удалось выполнить запрос: отсутствуют рабочие сессии Instagram")

    async def _request_with_specific_session(
        self,
        sessions: Dict[str, Dict[str, Any]],
        username: str,
        entry: Dict[str, Any],
        url: str,
        *,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> tuple[httpx.Response, str, Dict[str, Any]]:
        headers = self._build_headers(entry.get("user_agent"), entry["cookies"].get("csrftoken"))
        last_exception: Optional[Exception] = None

        for proxy in self._iter_proxy_candidates(entry):
            client_kwargs: Dict[str, Any] = {
                "timeout": REQUEST_TIMEOUT,
                "headers": headers,
                "cookies": entry["cookies"],
            }
            proxy_for_httpx = self._format_proxy_for_httpx(proxy)
            if proxy_for_httpx:
                if HTTPX_USES_PROXY_PARAM:
                    client_kwargs["proxy"] = proxy_for_httpx
                else:
                    client_kwargs["proxies"] = {
                        "http": proxy_for_httpx,
                        "https": proxy_for_httpx,
                    }
            try:
                async with httpx.AsyncClient(**client_kwargs) as client:
                    response = await client.request(method, url, params=params, data=data)

                status = response.status_code
                if status in (200, 404):
                    self._record_successful_proxy(username, entry, proxy)
                    return response, username, entry

                if status in (401, 403):
                    print(f"⚠️ Сессия {username} устарела ({status}), пытаемся обновить.")
                    self._drop_session(username)
                    refreshed = await self._refresh_session(username)
                    if refreshed:
                        sessions[username] = refreshed
                        return await self._request_with_specific_session(
                            sessions,
                            username,
                            refreshed,
                            url,
                            method=method,
                            params=params,
                            data=data,
                        )
                    sessions.pop(username, None)
                    return await self._request_with_sessions(
                        sessions,
                        url,
                        method=method,
                        params=params,
                        data=data,
                    )

                if status == 400:
                    print(f"⚠️ Сессия {username} вернула 400, переключаемся на другую.")
                    return await self._request_with_sessions(
                        sessions,
                        url,
                        method=method,
                        params=params,
                        data=data,
                    )

                if status == 429:
                    print(f"⚠️ Сессия {username} получила 429, переключаемся.")
                    return await self._request_with_sessions(
                        sessions,
                        url,
                        method=method,
                        params=params,
                        data=data,
                    )

                response.raise_for_status()
                self._record_successful_proxy(username, entry, proxy)
                return response, username, entry
            except Exception as exc:
                last_exception = exc
                proxy_label = proxy if proxy else "без прокси"
                print(f"⚠️ Ошибка запроса через сессию {username} (прокси {proxy_label}): {exc}")
                if not isinstance(
                    exc,
                    (
                        httpx.ConnectError,
                        httpx.ProxyError,
                        httpx.TimeoutException,
                    ),
                ):
                    break
                continue

        if last_exception:
            raise last_exception
        return await self._request_with_sessions(
            sessions,
            url,
            method=method,
            params=params,
            data=data,
        )

    async def _fetch_profile_via_api(
        self,
        sessions: Dict[str, Dict[str, Any]],
        username: str,
    ) -> tuple[Optional[Dict[str, Any]], Optional[str], Optional[Dict[str, Any]]]:
        url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
        response, session_username, entry = await self._request_with_sessions(sessions, url)

        if response.status_code == 404:
            print(f"⚠️ Профиль @{username} не найден (404).")
            return None, session_username, entry

        try:
            data = response.json()
        except Exception as exc:
            raise RuntimeError(f"Не удалось распарсить профиль @{username}: {exc}") from exc

        user_data = (data or {}).get("data", {}).get("user")
        if not user_data:
            raise RuntimeError(f"Неожиданная структура ответа профиля @{username}: {data}")

        return user_data, session_username, entry

    async def _fetch_reel_via_api(
        self,
        sessions: Dict[str, Dict[str, Any]],
        shortcode: str,
        preferred_session: Optional[tuple[str, Dict[str, Any]]] = None,
        doc_id: str = DEFAULT_DOC_ID_REEL,
    ) -> tuple[Optional[Dict[str, Any]], Optional[str], Optional[Dict[str, Any]]]:
        variables = {
            "shortcode": shortcode,
            "fetch_like_count": True,
            "fetch_comment_count": True,
            "parent_comment_count": 24,
            "has_threaded_comments": True,
        }
        variables_str = json.dumps(variables, separators=(",", ":"))
        url = (
            "https://www.instagram.com/graphql/query/"
            f"?doc_id={doc_id}&variables={quote(variables_str)}"
        )

        if preferred_session and preferred_session[0] in sessions:
            response, session_username, entry = await self._request_with_specific_session(
                sessions,
                preferred_session[0],
                preferred_session[1],
                url,
            )
        else:
            response, session_username, entry = await self._request_with_sessions(sessions, url)

        if response.status_code == 404:
            print(f"⚠️ Рил {shortcode} не найден (404).")
            return None, session_username, entry

        try:
            data = response.json()
        except Exception as exc:
            raise RuntimeError(f"Не удалось распарсить JSON рила {shortcode}: {exc}") from exc

        media = (data or {}).get("data", {}).get("shortcode_media")
        if not media:
            print(f"⚠️ Неожиданная структура для рила {shortcode}: {data}")
            return None, session_username, entry

        return media, session_username, entry

    async def _fetch_user_clips(
        self,
        sessions: Dict[str, Dict[str, Any]],
        user_id: str,
        *,
        page_size: int = 12,
        max_pages: Optional[int] = None,
        preferred_session: Optional[tuple[str, Dict[str, Any]]] = None,
    ) -> tuple[list[Dict[str, Any]], Optional[tuple[str, Dict[str, Any]]]]:
        clips_url = "https://www.instagram.com/api/v1/clips/user/"
        collected: list[Dict[str, Any]] = []
        next_max_id: Optional[str] = None
        session_hint = preferred_session

        pages_fetched = 0

        while True:
            if max_pages is not None and pages_fetched >= max_pages:
                break
            pages_fetched += 1
            payload: Dict[str, Any] = {
                "target_user_id": user_id,
                "page_size": page_size,
            }
            if next_max_id:
                payload["max_id"] = next_max_id

            if session_hint and session_hint[0] in sessions:
                response, session_username, session_entry = await self._request_with_specific_session(
                    sessions,
                    session_hint[0],
                    session_hint[1],
                    clips_url,
                    method="POST",
                    data=payload,
                )
            else:
                response, session_username, session_entry = await self._request_with_sessions(
                    sessions,
                    clips_url,
                    method="POST",
                    data=payload,
                )

            try:
                data = response.json()
            except Exception as exc:
                print(f"⚠️ Не удалось декодировать JSON списка рилов: {exc}")
                break

            items = data.get("items", [])
            for item in items:
                media = item.get("media")
                if isinstance(media, dict):
                    collected.append(media)

            paging_info = data.get("paging_info", {}) or {}
            more_available = bool(paging_info.get("more_available"))
            next_max_id = paging_info.get("max_id")
            session_hint = (session_username, session_entry)

            if not more_available or not next_max_id:
                break

        return collected, session_hint

    async def save_html_on_error(self, page, url: str, error_message: str):
        """Save page HTML on error for debugging"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.replace(".", "_")
            path = parsed_url.path.replace("/", "_").strip("_")
            filename = f"error_{domain}_{path}_{timestamp}.html"
            html_content = await page.content()
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"HTML saved to {filename} due to error: {error_message}")
        except Exception as save_error:
            print(f"Failed to save HTML: {str(save_error)}")

    # async def get_2fa_code(self, page, two_factor_code):
    #     two_factor_page = await page.context.new_page()
    #     try:
    #         await two_factor_page.goto(
    #             f"https://2fa.fb.rip/{two_factor_code}", timeout=60000)
    #         await two_factor_page.wait_for_selector(
    #             "div#verifyCode", timeout=60000)
    #         two_factor_code_element = await two_factor_page.query_selector(
    #             "div#verifyCode")
    #         if two_factor_code_element:
    #             code = await two_factor_code_element.inner_text()
    #             code = re.sub(r"\D", "", code)
    #             if len(code) == 6 and code.isdigit():
    #                 print(f"2FA код успешно получен: {code}")
    #                 return code
    #             else:
    #                 print(f"Неверный формат 2FA кода: {code}")
    #                 return None
    #         else:
    #             print("Элемент 2FA кода не найден")
    #             return None
    #     except Exception as e:
    #         await self.save_html_on_error(
    #             two_factor_page,
    #             f"https://2fa.fb.rip/{two_factor_code}", str(e))
    #         print(f"Не удалось получить 2FA код: {e}")
    #         return None
    #     finally:
    #         await two_factor_page.close()

    # async def get_2fa_code(self, page, two_factor_code):
    #     two_factor_page = await page.context.new_page()
    #     try:
    #         await two_factor_page.goto(
    #             f"https://2fa.fb.rip/{two_factor_code}", timeout=60000)
    #         await two_factor_page.wait_for_selector(
    #             "div#verifyCode", timeout=60000)
    #         two_factor_code_element = await two_factor_page.query_selector(
    #             "div#verifyCode")
    #         if two_factor_code_element:
    #             code = await two_factor_code_element.inner_text()
    #             code = re.sub(r"\D", "", code)
    #             if len(code) == 6 and code.isdigit():
    #                 print(f"2FA код успешно получен: {code}")
    #                 return code
    #             else:
    #                 print(f"Неверный формат 2FA кода: {code}")
    #                 return None
    #         else:
    #             print("Элемент 2FA кода не найден")
    #             return None
    #     except Exception as e:
    #         await self.save_html_on_error(
    #             two_factor_page,
    #             f"https://2fa.fb.rip/{two_factor_code}", str(e))
    #         print(f"Не удалось получить 2FA код: {e}")
    #         return None
    #     finally:
    #         await two_factor_page.close()

    async def get_2fa_code(self, two_factor_code):
        totp = pyotp.TOTP(two_factor_code)
        # print("Current OTP:", totp.now())
        return totp.now()

    async def login_to_instagram(self, page, username, password, two_factor_code) -> Optional[Dict[str, str]]:
        # Сбор ошибок API
        api_errors = []

        async def log_response(response):
            if "www.instagram.com/api/v1" in response.url or "i.instagram.com/api" in response.url:
                try:
                    status = response.status
                    if status >= 400:
                        body = await response.text()
                        print(f"API Error {status} from {response.url}: {body[:500]}")
                        api_errors.append({"url": response.url, "status": status, "body": body})
                except Exception as e:
                    print(f"Не удалось прочитать тело ответа API: {e}")

        page.on("response", log_response)

        try:
            print(f"Начало авторизации для пользователя {username}")

            # Логируем среду
            user_agent = await page.evaluate("navigator.userAgent")
            language = await page.evaluate("navigator.language")
            timezone = await page.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone")
            try:
                ip = await page.evaluate("await (await fetch('https://api.ipify.org?format=json')).json().then(r => r.ip)")
            except:
                ip = "unknown"
            print(f"User-Agent: {user_agent}")
            print(f"Language: {language}, Timezone: {timezone}, IP: {ip}")

            await page.goto("https://www.instagram.com", timeout=50000)
            await page.wait_for_load_state("networkidle", timeout=30000)
            print("Страница загружена")

            # Обработка баннера cookies
            print("Проверка наличия баннера cookies")
            cookie_found = False
            cookie_selectors = [
                'button:has-text("Allow all cookies")',
                'button:has-text("Decline optional cookies")',
            ]
            for selector in cookie_selectors:
                print(f"Поиск кнопки cookies: {selector}")
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    btn = await page.query_selector(selector)
                    if btn and await btn.is_visible() and await btn.is_enabled():
                        print(f"Клик по кнопке cookies: {selector}")
                        await btn.click()
                        await page.wait_for_timeout(3000)
                        cookie_found = True
                        break
                except Exception as e:
                    print(f"Селектор {selector} не сработал: {e}")

            if not cookie_found:
                print("Баннер cookies не найден или не обработан — продолжаем")

            # === КНОПКА "Log in" на главной ===
            print("Поиск начальной кнопки Log in")
            login_button = await page.query_selector('button:has-text("Log in")')
            if not login_button:
                await self.save_html_on_error(page, page.url, "Кнопка Log in не найдена")
                print("Кнопка Log in не найдена")
                return None

            is_visible = await login_button.is_visible()
            is_enabled = await login_button.is_enabled()
            print(f"Кнопка Log in видима: {is_visible}, активна: {is_enabled}")
            if not (is_visible and is_enabled):
                await self.save_html_on_error(page, page.url, "Кнопка Log in неактивна")
                return None

            print("Клик по кнопке Log in")
            await login_button.click(timeout=30000)
            await page.wait_for_timeout(4000)

            # === ПРОВЕРКА ОШИБОК НА ФОРМЕ ===
            print("Проверка сообщений об ошибке после перехода на форму")
            error_selectors = [
                'p:has-text("Sorry, your password was incorrect")',
                'p:has-text("We couldn\'t find an account with that username")',
                'span:has-text("Incorrect username or password")',
                'div:has-text("There was a problem logging you into Instagram")',
                'div[role="alert"]',
            ]
            for sel in error_selectors:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    err_text = (await el.text_content()).strip()
                    print(f"Ошибка на форме: {err_text}")
                    await self.save_html_on_error(page, page.url, f"Ошибка входа: {err_text}")
                    err_lower = err_text.lower()
                    if "incorrect password" in err_lower or "incorrect username or password" in err_lower:
                        raise InvalidCredentialsError(f"Неверный пароль для {username}")
                    if "couldn't find an account" in err_lower:
                        raise InvalidCredentialsError(f"Аккаунт {username} не найден")
                    return None

            # === ОЖИДАНИЕ ФОРМЫ ===
            print("Ожидание поля username")
            try:
                await page.wait_for_selector('input[name="username"]', timeout=20000)
            except PlaywrightTimeoutError:
                await self.save_html_on_error(page, page.url, "Форма входа не загрузилась")
                print("Форма входа не появилась")
                return None

            # === ЗАПОЛНЕНИЕ USERNAME ===
            username_field = await page.query_selector('input[name="username"]')
            if not username_field:
                await self.save_html_on_error(page, page.url, "Поле username отсутствует")
                return None

            await username_field.fill(username)
            actual_user = await username_field.input_value()
            print(f"Введён username: '{username}', фактическое значение: '{actual_user}'")
            if actual_user != username:
                print("Поле username не сохранило значение")
                return None

            # === ЗАПОЛНЕНИЕ PASSWORD ===
            password_field = await page.query_selector('input[name="password"]')
            if not password_field:
                await self.save_html_on_error(page, page.url, "Поле password отсутствует")
                return None

            await password_field.fill(password)
            print("Пароль введён")

            # === КНОПКА ВХОДА НА ФОРМЕ ===
            final_login_button = await page.query_selector('button[type="submit"]')
            if not final_login_button:
                # fallback: иногда это div с aria-label
                final_login_button = await page.query_selector('div[role="button"][aria-label="Log in"]')

            if not final_login_button:
                await self.save_html_on_error(page, page.url, "Кнопка входа на форме не найдена")
                print("Кнопка входа на форме не найдена")
                return None

            is_vis = await final_login_button.is_visible()
            is_en = await final_login_button.is_enabled()
            print(f"Кнопка входа на форме: видима={is_vis}, активна={is_en}")
            if not (is_vis and is_en):
                await self.save_html_on_error(page, page.url, "Кнопка входа неактивна")
                return None

            print("Клик по финальной кнопке Log in")
            await final_login_button.click(timeout=30000)
            await page.wait_for_timeout(6000)

            # === ПОСЛЕ КЛИКА: ПРОВЕРКА URL И ОШИБОК ===
            current_url = page.url
            title = await page.title()
            print(f"После входа: URL={current_url}, Title={title}")

            # Проверка на challenge / suspended
            if "/challenge/" in current_url:
                await self.save_html_on_error(page, current_url, "Требуется верификация (challenge)")
                print("Обнаружен challenge — требуется ручная верификация")
                return None

            if "/suspended/" in current_url:
                await self.save_html_on_error(page, current_url, "Аккаунт приостановлен")
                print("Аккаунт приостановлен")
                return None

            # Повторная проверка ошибок на форме (иногда появляются позже)
            for sel in error_selectors:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    err_text = (await el.text_content()).strip()
                    print(f"Ошибка после отправки формы: {err_text}")
                    await self.save_html_on_error(page, page.url, f"Ошибка после входа: {err_text}")
                    err_lower = err_text.lower()
                    if "incorrect password" in err_lower or "incorrect username or password" in err_lower:
                        raise InvalidCredentialsError(f"Неверный пароль для {username}")
                    if "couldn't find an account" in err_lower:
                        raise InvalidCredentialsError(f"Аккаунт {username} не найден")
                    return None

            # === 2FA ===
            print("Проверка 2FA")
            try:
                await page.wait_for_selector('input[aria-label="Code"]', timeout=15000)
                print("Обнаружено поле 2FA")
                code_field = await page.query_selector('input[aria-label="Code"]')
                if not code_field:
                    raise Exception("Поле кода не найдено")

                verification_code = await self.get_2fa_code(
                    # page,
                    two_factor_code
                )
                if not verification_code:
                    print("Не удалось получить 2FA код")
                    return None

                await code_field.fill(verification_code)
                print(f"2FA код введён: {verification_code}")

                continue_btn = await page.query_selector('div[role="button"][aria-label="Continue"]')
                if continue_btn:
                    await continue_btn.click()
                    await page.wait_for_timeout(3000)

                # Trust device
                trust_checkbox = await page.query_selector('div[role="checkbox"][aria-label*="Trust"]')
                if trust_checkbox:
                    await trust_checkbox.click()
                    print("Устройство помечено как доверенное")

            except PlaywrightTimeoutError:
                print("2FA не требуется")

            # === КНОПКА "Not now" ===
            try:
                # Попробуем найти кнопку по тексту и роли
                not_now_button = page.get_by_role("button", name="Not now")
                if await not_now_button.is_visible(timeout=5000):
                    await not_now_button.click()
                    print("Клик по 'Not now'")
                else:
                    # Попробуем русскую локализацию
                    not_now_button_ru = page.get_by_role("button", name="Не сейчас")
                    if await not_now_button_ru.is_visible(timeout=3000):
                        await not_now_button_ru.click()
                        print("Клик по 'Не сейчас'")
            except Exception as e:
                print(f"'Not now' не найден или не удалось нажать: {e}")

            # === ФИНАЛЬНАЯ ПРОВЕРКА: УСПЕХ ===
            await page.wait_for_timeout(5000)
            if "instagram.com/accounts/login/" in page.url:
                print("Всё ещё на странице входа — вход не удался")
                await self.save_html_on_error(page, page.url, "Вход не удался: остался на login-странице")
                try:
                    page_text = await page.content()
                except Exception:
                    page_text = ""
                lowered = page_text.lower()
                if "incorrect password" in lowered or "incorrect username or password" in lowered:
                    raise InvalidCredentialsError(f"Неверный пароль для {username}")
                if "couldn't find" in lowered and "account" in lowered:
                    raise InvalidCredentialsError(f"Аккаунт {username} не найден")
                return None

            cookies = self._extract_auth_cookies(await page.context.cookies())

            if "/accounts/onetap/" in page.url or "/accounts/login/" not in page.url:
                print("Успешный вход в Instagram")
                if cookies:
                    return cookies
                print("⚠️ Не удалось извлечь cookies после успешного входа")
                return None

            print("Неясное состояние после входа — возможно, частичный успех")
            if cookies:
                return cookies
            print("⚠️ Не удалось извлечь cookies в неясном состоянии входа")
            return None

        except InvalidCredentialsError:
            raise
        except Exception as e:
            print(f"Исключение в login_to_instagram: {str(e)}")
            await self.save_html_on_error(page, page.url or "https://www.instagram.com", "Необработанная ошибка")
            return None

    async def scroll_until(self, page, url: str, selector: str,
                           delay: float = 5.0, max_idle_rounds: int = 5):
        prev_count = 0
        idle_rounds = 0
        max_scroll_attempts = 3
        reel_data = set()

        for attempt in range(max_scroll_attempts):
            print(f"Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

            while True:
                # Собираем все элементы рилсов
                reel_elements = await page.query_selector_all('a[href*="/reel/"]')
                for element in reel_elements:
                    href = await element.get_attribute('href')
                    if href and href.startswith('/'):
                        full_url = f"https://www.instagram.com{href}"
                        # Ищем элемент с классом x1lvsgvq для получения URL изображения
                        image_element = await element.query_selector('div.x1lvsgvq')
                        image_url = None
                        if image_element:
                            style = await image_element.get_attribute('style')
                            if style and 'background-image: url' in style:
                                # Извлекаем URL из background-image
                                start = style.find('url("') + 5
                                end = style.find('")')
                                if start > 4 and end > start:
                                    image_url = style[start:end]
                        reel_data.add((full_url, image_url))

                # Прокрутка страницы
                await page.evaluate("""
                    async () => {
                        return new Promise((resolve) => {
                            let totalHeight = 0;
                            const distance = 1000;
                            const timer = setInterval(() => {
                                const scrollHeight = document.body.scrollHeight;
                                window.scrollBy(0, distance);
                                totalHeight += distance;

                                if (totalHeight >= scrollHeight) {
                                    clearInterval(timer);
                                    resolve();
                                }
                            }, 100);
                        });
                    }
                """)
                await page.wait_for_timeout(int(delay * 1000))
                current_count = await page.eval_on_selector_all(selector, "els => els.length")
                print(f"Текущее количество элементов: {current_count}, URL-ов рилов: {len(reel_data)}")

                if current_count == prev_count:
                    idle_rounds += 1
                    print(f"Количество элементов не изменилось, idle_rounds: {idle_rounds}")
                    if idle_rounds >= max_idle_rounds:
                        print(f"Достигнут конец списка рилов для профиля {url}")
                        print(f"Собрано {len(reel_data)} пар (URL рила, URL изображения)")
                        break
                else:
                    idle_rounds = 0
                    prev_count = current_count

                is_at_bottom = await page.evaluate("""
                    () => {
                        return (window.innerHeight + window.scrollY) >= document.body.scrollHeight;
                    }
                """)
                if is_at_bottom and idle_rounds >= max_idle_rounds:
                    print(f"Достигнут конец страницы для {url}")
                    break

        return list(reel_data)

    def generate_short_title(self, full_title: str, max_length: int = 20) -> str:
        if not full_title:
            return ""
        # Убираем переносы строк и лишние пробелы
        clean_title = " ".join(full_title.split())
        if len(clean_title) <= max_length:
            return clean_title
        truncated = clean_title[:max_length]
        last_space = truncated.rfind(' ')
        if last_space != -1:
            return truncated[:last_space]
        return truncated

    def extract_article_tag(self, caption: str) -> Optional[str]:
        """Возвращает первый найденный артикул-хештег (#sv, #jw и т.д.) или None."""
        if not caption:
            return None
        caption_lower = caption.lower()
        for tag in ["#sv", "#jw", "#qz", "#sr", "#fg"]:
            if tag in caption_lower:
                # Найти точное написание в оригинале (сохранить регистр)
                start = caption_lower.find(tag)
                if start != -1:
                    return caption[start:start + len(tag)]
        return None

    def _extract_metrics_from_media(self, shortcode_media: Dict[str, Any]) -> Dict[str, Any]:
        likes = (
            shortcode_media
            .get("edge_media_preview_like", {})
            .get("count")
        )
        comments = (
            shortcode_media
            .get("edge_media_to_parent_comment", shortcode_media.get("edge_media_to_comment", {}))
            .get("count")
        )
        views = shortcode_media.get("video_view_count") or shortcode_media.get("video_play_count")
        ts = shortcode_media.get("taken_at_timestamp")
        caption_edges = (
            shortcode_media
            .get("edge_media_to_caption", {})
            .get("edges", [])
        )
        caption = caption_edges[0]["node"]["text"] if caption_edges else ""
        preview = shortcode_media.get("display_url") or shortcode_media.get("thumbnail_src")
        video_url = shortcode_media.get("video_url")

        return {
            "shortcode": shortcode_media.get("shortcode"),
            "likes": likes or 0,
            "comments": comments or 0,
            "views": views or 0,
            "timestamp": ts,
            "caption": caption or "",
            "preview_image": preview,
            "video_url": video_url,
        }

    @staticmethod
    def extract_username_from_url(profile_url: str) -> Optional[str]:
        parsed = urlparse(profile_url)
        path = parsed.path.strip("/")
        if not path:
            return None
        return path.split("/")[0]

    async def _run_channel_with_session_provider(
        self,
        *,
        url: str,
        username: str,
        channel_id: int,
        user_id: int,
        target_items: Optional[int],
        session_provider: Callable[[], Awaitable[Dict[str, Dict[str, Any]]]],
        max_attempts_collect: int,
        history_created_at_iso: str,
    ) -> Tuple[bool, int, int]:
        clips_media: list[Dict[str, Any]] = []
        preferred_session: Optional[tuple[str, Dict[str, Any]]] = None
        profile_data: Optional[Dict[str, Any]] = None
        processed = 0
        total_views = 0

        for attempt in range(1, max_attempts_collect + 1):
            attempt_suffix = f" (попытка {attempt}/{max_attempts_collect})" if max_attempts_collect > 1 else ""
            try:
                sessions = await session_provider()
            except Exception as exc:
                print(f"❌ Не удалось подготовить cookies{attempt_suffix}: {exc}")
                if attempt >= max_attempts_collect:
                    return False, processed, total_views
                continue

            if not sessions:
                print(f"❌ Не удалось получить валидные cookies ни для одного аккаунта{attempt_suffix}.")
                if attempt >= max_attempts_collect:
                    return False, processed, total_views
                continue

            if attempt == 1:
                print(f"🔐 Используем сохранённые cookies {len(sessions)} аккаунтов для парсинга @{username}")
            else:
                print(f"🔁 Повторная попытка, используем {len(sessions)} сессий для @{username} (попытка {attempt}/{max_attempts_collect})")

            preferred_session = None
            clips_media = []
            try:
                profile_data_result, session_username, session_entry = await self._fetch_profile_via_api(sessions, username)
            except Exception as exc:
                print(f"❌ Ошибка получения профиля @{username}{attempt_suffix}: {exc}")
                if attempt >= max_attempts_collect:
                    return False, processed, total_views
                continue

            if not profile_data_result:
                print(f"⚠️ Профиль @{username} недоступен или отсутствует{attempt_suffix}.")
                if attempt >= max_attempts_collect:
                    return False, processed, total_views
                continue

            profile_data = profile_data_result
            if session_username and session_entry:
                preferred_session = (session_username, session_entry)

            instagram_user_id = profile_data.get("id")
            if not instagram_user_id:
                print(f"❌ Не удалось получить ID пользователя для @{username}")
                return False, processed, total_views

            try:
                clips_media, fetched_session = await self._fetch_user_clips(
                    sessions,
                    instagram_user_id,
                    page_size=50,
                    max_pages=None,
                    preferred_session=preferred_session,
                )
            except Exception as exc:
                print(f"❌ Ошибка получения списка рилов для @{username}{attempt_suffix}: {exc}")
                if attempt >= max_attempts_collect:
                    return False, processed, total_views
                continue

            if fetched_session:
                preferred_session = fetched_session

            if not clips_media:
                print(f"⚠️ API не вернуло рилы для @{username}{attempt_suffix}.")
                if attempt >= max_attempts_collect:
                    return False, processed, total_views
                continue

            if target_items and len(clips_media) < target_items:
                print(f"⚠️ Получено только {len(clips_media)} рилов из ожидаемых {target_items} для @{username}{attempt_suffix}.")
                if attempt < max_attempts_collect:
                    print(f"🔁 Пробуем повторить сбор рилов для @{username}...")
                    continue

            break

        if not clips_media:
            return False, processed, total_views

        if target_items and len(clips_media) < target_items:
            print(f"⚠️ После {max_attempts_collect} попыток удалось получить только {len(clips_media)} из {target_items} рилов для @{username}.")

        items_limit = target_items if target_items else len(clips_media)
        reel_sequence = clips_media[:items_limit] if items_limit < len(clips_media) else clips_media
        print(f"📹 Получено {len(clips_media)} рилов для @{username}, обрабатываем {len(reel_sequence)}")

        image_tasks: list[tuple[int, str]] = []

        async def download_image(image_url: str) -> bytes:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
                return resp.content

        async def upload_image(video_id: int, image_url: str):
            try:
                image_bytes = await download_image(image_url)
                file_name = image_url.split("/")[-1].split("?")[0] or f"{video_id}.jpg"
                async with httpx.AsyncClient(timeout=30.0) as client:
                    files = {"file": (file_name, image_bytes, "image/jpeg")}
                    resp = await client.post(
                        f"https://cosmeya.dev-klick.cyou/api/v1/videos/{video_id}/upload-image/",
                        files=files,
                    )
                    resp.raise_for_status()
                    print(f"📸 Загружено превью для видео {video_id}")
            except Exception as exc:
                print(f"❌ Ошибка загрузки превью {video_id}: {exc}")

        async def save_video_and_image(
            channel_id: int,
            reel_code: str,
            reel_url: str,
            play_count: int,
            amount_likes: int,
            amount_comments: int,
            image_url: str,
            date_published: Optional[str],
            article: str,
            caption_text: str,
        ):
            video_name = self.generate_short_title(caption_text, max_length=20)

            video_data = {
                "type": "instagram",
                "channel_id": channel_id,
                "link": reel_url,
                "name": video_name,
                "article": article,
                "amount_views": play_count,
                "amount_likes": amount_likes,
                "amount_comments": amount_comments,
                "image_url": image_url,
                "date_published": date_published,
                "history_created_at": history_created_at_iso,
            }
            try:
                async with httpx.AsyncClient() as client:
                    check_resp = await client.get(
                        f"https://cosmeya.dev-klick.cyou/api/v1/videos/?link={reel_url}",
                        timeout=20.0,
                    )

                    video_id = None
                    is_new = False

                    if check_resp.status_code == 200:
                        result = check_resp.json()
                        videos = result.get("videos", [])
                        if videos:
                            existing_video = videos[0]
                            video_id = existing_video["id"]
                            update_payload = {
                                "amount_views": play_count,
                                "amount_likes": amount_likes,
                                "amount_comments": amount_comments,
                            }
                            if date_published and not existing_video.get("date_published"):
                                update_payload["date_published"] = date_published
                            update_payload["history_created_at"] = history_created_at_iso
                            update_resp = await client.patch(
                                f"https://cosmeya.dev-klick.cyou/api/v1/videos/{video_id}",
                                json=update_payload,
                                timeout=20.0,
                            )
                            update_resp.raise_for_status()
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        resp = await client.post(
                            "https://cosmeya.dev-klick.cyou/api/v1/videos/",
                            json=video_data,
                            timeout=20.0,
                        )
                        resp.raise_for_status()
                        created_video = resp.json()
                        video_id = created_video["id"]
                        print(f"📦 Создано видео {video_id} ({reel_url})")

                    if video_id and is_new and image_url:
                        image_tasks.append((video_id, image_url))
                        print(f"Добавлено в очередь {video_id}: {image_url}")

            except Exception as exc:
                print(f"❌ Ошибка сохранения видео {reel_url}: {exc}")

        processed = 0
        total_candidates = len(reel_sequence)
        seen_shortcodes: set[str] = set()
        for idx, media in enumerate(reel_sequence, start=1):
            if media.get("product_type") not in ("clips", "clip", "reel"):
                continue
            shortcode = media.get("code") or media.get("pk")
            if not shortcode or shortcode in seen_shortcodes:
                continue
            seen_shortcodes.add(shortcode)
            print(f"➡️ Обработка рила {shortcode} ({idx}/{total_candidates})")
            try:
                play_count = media.get("play_count") or media.get("video_view_count") or 0
                like_count = media.get("like_count") or 0
                comment_count = media.get("comment_count") or 0
                caption_data = media.get("caption") or {}
                if isinstance(caption_data, dict):
                    caption_text = caption_data.get("text", "") or ""
                else:
                    caption_text = str(caption_data or "")
                article = self.extract_article_tag(caption_text)
                image_url = None
                candidates = media.get("image_versions2", {}).get("candidates", [])
                if candidates:
                    image_url = candidates[0].get("url")
                taken_at = media.get("taken_at")
                published_at = None
                if isinstance(taken_at, (int, float)):
                    try:
                        published_at = datetime.fromtimestamp(int(taken_at), tz=timezone.utc).strftime("%Y-%m-%d")
                    except (ValueError, OSError, OverflowError):
                        published_at = None
                if not published_at and isinstance(caption_data, dict):
                    created_at = caption_data.get("created_at")
                    if isinstance(created_at, (int, float)):
                        try:
                            published_at = datetime.fromtimestamp(int(created_at), tz=timezone.utc).strftime("%Y-%m-%d")
                        except (ValueError, OSError, OverflowError):
                            published_at = None

                reel_url = f"https://www.instagram.com/reel/{shortcode}/"
                await save_video_and_image(
                    channel_id,
                    shortcode,
                    reel_url,
                    int(play_count or 0),
                    int(like_count or 0),
                    int(comment_count or 0),
                    image_url,
                    published_at,
                    article,
                    caption_text,
                )
                processed += 1
                total_views += int(play_count or 0)
                await asyncio.sleep(0.5)
            except Exception as exc:
                print(f"❌ Ошибка обработки рила {shortcode}: {exc}")

        if image_tasks:
            print(f"📸 Начинаем загрузку {len(image_tasks)} изображений...")
            for idx, (video_id, img_url) in enumerate(image_tasks):
                print(f"🖼️ Загрузка {idx + 1}/{len(image_tasks)} для видео {video_id}...")
                await upload_image(video_id, img_url)
                if idx < len(image_tasks) - 1:
                    await asyncio.sleep(2.0)

        print(f"✅ Обработано {processed} рилов для @{username}")
        return True, processed, total_views

    async def parse_channel(
        self,
        url: str,
        channel_id: int,
        user_id: int,
        max_retries: Optional[int] = None,
        accounts: Optional[list[str]] = None,
        proxy_list: Optional[list[str]] = None,
        parse_started_at: Optional[Union[str, datetime]] = None,
    ):
        run_started_at = self._parse_started_at(parse_started_at)
        history_created_at_iso = run_started_at.isoformat()

        if not self.configure_proxy_list(proxy_list):
            self._log_summary(url, channel_id, 0, 0, run_started_at, datetime.now(timezone.utc), False)
            return

        accounts = accounts or []
        if not accounts:
            print("⚠️ Список аккаунтов пуст, невозможно авторизоваться.")
            self._log_summary(url, channel_id, 0, 0, run_started_at, datetime.now(timezone.utc), False)
            return

        username = self.extract_username_from_url(url)
        if not username:
            print(f"❌ Не удалось определить username из URL {url}")
            self._log_summary(url, channel_id, 0, 0, run_started_at, datetime.now(timezone.utc), False)
            return

        target_items = max_retries if max_retries and max_retries > 0 else None
        max_attempts_collect = 3

        async def session_provider() -> Dict[str, Dict[str, Any]]:
            return await self.ensure_initial_cookies(accounts)

        success, processed_count, total_views = await self._run_channel_with_session_provider(
            url=url,
            username=username,
            channel_id=channel_id,
            user_id=user_id,
            target_items=target_items,
            session_provider=session_provider,
            max_attempts_collect=max_attempts_collect,
            history_created_at_iso=history_created_at_iso,
        )
        self._log_summary(url, channel_id, processed_count, total_views, run_started_at, datetime.now(timezone.utc), success)

    async def parse_channel_with_sessions(
        self,
        *,
        url: str,
        channel_id: int,
        user_id: int,
        sessions: Dict[str, Dict[str, Any]],
        proxy_list: Optional[list[str]] = None,
        max_retries: Optional[int] = None,
        max_attempts_collect: int = 1,
        parse_started_at: Optional[Union[str, datetime]] = None,
    ) -> bool:
        run_started_at = self._parse_started_at(parse_started_at)
        history_created_at_iso = run_started_at.isoformat()

        if proxy_list is not None and not self.configure_proxy_list(proxy_list):
            self._log_summary(url, channel_id, 0, 0, run_started_at, datetime.now(timezone.utc), False)
            return False

        if not sessions:
            print("⚠️ Не переданы подготовленные сессии для batch-парсинга.")
            self._log_summary(url, channel_id, 0, 0, run_started_at, datetime.now(timezone.utc), False)
            return False

        username = self.extract_username_from_url(url)
        if not username:
            print(f"❌ Не удалось определить username из URL {url}")
            self._log_summary(url, channel_id, 0, 0, run_started_at, datetime.now(timezone.utc), False)
            return False

        target_items = max_retries if max_retries and max_retries > 0 else None

        async def session_provider() -> Dict[str, Dict[str, Any]]:
            return sessions

        success, processed_count, total_views = await self._run_channel_with_session_provider(
            url=url,
            username=username,
            channel_id=channel_id,
            user_id=user_id,
            target_items=target_items,
            session_provider=session_provider,
            max_attempts_collect=max_attempts_collect,
            history_created_at_iso=history_created_at_iso,
        )
        self._log_summary(url, channel_id, processed_count, total_views, run_started_at, datetime.now(timezone.utc), success)
        return success


async def main():
    proxy_list = [
        "suQs3N:j30sT6@170.246.55.146:9314",
        "DWtvBb:M1uRTE@181.177.87.15:9725",
        "DWtvBb:M1uRTE@181.177.84.185:9254",
        "DWtvBb:M1uRTE@94.131.54.252:9746",
        "DWtvBb:M1uRTE@95.164.200.121:9155",
        "DWtvBb:M1uRTE@45.237.85.119:9458",
        "MecAgR:v5fbu6@186.65.118.237:9808",
        "MecAgR:v5fbu6@186.65.115.230:9065",
        "MecAgR:v5fbu6@186.65.115.105:9825",
    ]
    parser = InstagramParser()
    url = "https://www.instagram.com/skin.scout/"
    user_id = 13
    accounts = [
        "juan.itaandersen:fsm8f5tb:FOJ2E2475FRD3UR5NY2E45YPTEJK5APH",
        "jodyrhodes74:Kr2V3bxS:2KYNTJCUL74SKSNTVGFENBL6DOAJ65X6",
        "Jeannetteosley12:7nYEEexK:SVTLSGQZVWLNB3ID2PCB5TR7C4VWWPES",
        "hild.amoody:6FL9Jg2j:FW26JAKMNNLP2U5BLQQF6L4ABMMMB4DC",
        "eliseowolf95:CuNAryR3Ly:VF442BGSAVQK3TBMGKM3SAN2U75EKMRG",
        "biancapeixotox577:cHanCroids05:LZNNNJYEYTPETIGT5AEIR5Z2FU47I65J",
        "jaquelinesiqueirayz922:ryBa7lBme:WT2DCIT2OVN5UE7GP5PHCYGPI32BHXKN",
        "ribeirobiatrizax784:x3OgxGA02PM:WMOL7EW3TUSGUWRCKQWLZS3DW3TVDA7K",
        "figueiredorosanaangelina:ufyqvzpel:FPYWZH4CS6EEIXGJRS57BCDZEEGD22CZ",
        # "emanuellasap325:barware2*!:MGUVERU2OWNNZCR5SKGZS7WGTHXXJ63W",
        # "barbaradacruzp460:zaNilY51:ULKDMXA6E5JCJ5BHCPPYWAN2J65LBA34",
        # "biancaleaoo212:genT73@*:TPW7CF4YDHG7G5C7YYAFQ2W4L2A7YUSV",
        # "isisramosbm108:Leadwork996@:YWE7IWEZYOGGNNVRLZ4FW5QVTIAQ4QNZ",
        # "sabrinapimentaut150:bOttOmed0!@:ODTDIB5IEZG6REB3RROMBW3JHR6G6PWP",
        # "liviadamotaj814:zoophiles5:XLMIX3HUL3N3YSHK7NY6HQBTW5TOPXPC",
        # "rezendesuelizn674:TwVHHXku6p:UI6C3HO4CWX2F36KXMLYDM7YVYU5PCY2",
        # "taylorvega968:FqR2RBQckZ:USEVPAIL5TQTVIT6N4YZQP6TMS6N6WFL",
        # "danielle_stafford:QbR86VfEud:YSKAUQROK633XKXT5M2GJZPGEEJSPGJ3",
        # "frasheri8498:NzPAAX5xqC:SJZ3D5XWEZYWHOIYXANTZZQTQ34BE47D",
        # "bonilla.scout:KNWKdS3Gew:J33P5656TMAH7R55WUKML3TEA7RGSFQG",
        # "lizamarks974:cEprBdwR:4LAJODJX6QBH3UGMTINIIATEV5LIMALH",
        # "ednastamm889:h5JrHw8j:SHMSJZULXUBEY2DXSY35MTVHBEN4QNDN",
        # "ihaldare381:c22BC6cY:6CHNKT2Z5VC2IWPHDLP2KP5CEOM5PVNQ",
        # "gerrylind948:AZYGpACe:IQZC4GVAAL66CIRSNGLK22OSELQ5BZ33",
        # "kanekutch913:v5yprTC5:63FWYHZHIYUD7YVTPDO3LJV5TYX2PX7L",
        # "alecryan795:T7xJ6euZ:3W4224N56AO7K5LBXKLPLUWHQZJZRRMB",
        # "lonzokoch385:C5cF5u4v:ESSSG7QBBKA2J2ZZZM2ZKAJDMC7MKXFK",
        # "connerhoffman8:rA2JVsXJ:5FH7UM5DB5QW4TZMCN6Q5RWBSQCZKQ6M",
    ]
    await parser.parse_channel(url, channel_id=75,
                               user_id=user_id, accounts=accounts, proxy_list=proxy_list)

if __name__ == "__main__":
    asyncio.run(main())
