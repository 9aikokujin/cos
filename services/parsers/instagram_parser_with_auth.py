"""
InstagramParser with authentication storage and reel data sending.

This module defines a class ``InstagramParser`` that can log into
Instagram using Playwright (if installed), save authentication
cookies/local storage to a JSON file, reuse those for subsequent
requests, and extract reels information from a given profile.  It
includes methods to send collected reel data to a REST API.

The actual network and browser interactions require a working
Playwright installation and access to Instagram.  In this environment,
Playwright is not available, so the class demonstrates the
structure needed to implement the workflow on your own machine.

Usage::

    from instagram_parser_with_auth import InstagramParser
    parser = InstagramParser(logger)
    accounts = ["user:pass:2fa", ...]
    # Use parser.ensure_authorized_context(...) inside your flow
    # to login or reuse cookies.

You can run this script directly as a placeholder; it will simply
inform you that Playwright is not available.
"""

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Any, List

# Attempt to import Playwright; may not be installed in this environment.
try:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth
    PLAYWRIGHT_AVAILABLE = True
except Exception:
    PLAYWRIGHT_AVAILABLE = False


INSTAGRAM_APP_ID = "936619743392459"
IG_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

# Directory where auth JSON files are stored
AUTH_DIR = Path("auth_store")
AUTH_DIR.mkdir(parents=True, exist_ok=True)


def now() -> int:
    return int(time.time())


def _auth_file(username: str) -> Path:
    safe = username.strip().lower()
    return AUTH_DIR / f"{safe}.json"


class InstagramParser:
    """A parser that handles Instagram login and reel extraction.

    This class is a simplified placeholder that shows how you can
    integrate cookie storage and reuse into your existing parser.  In
    this environment, Playwright is not installed, so methods that
    depend on it will log a message instead of performing actions.
    """

    def __init__(self, logger: Any):
        self.logger = logger
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    # ------------------------------------------------------------------
    # Helper methods for authentication storage
    # ------------------------------------------------------------------

    def _load_auth(self, username: str) -> Optional[Dict[str, Any]]:
        f = _auth_file(username)
        if not f.exists():
            return None
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            self.logger.send("ERROR", f"Ошибка чтения auth {f}: {e}")
            return None

    async def _save_auth(self, page, username: str):
        if not PLAYWRIGHT_AVAILABLE:
            self.logger.send("ERROR", "Playwright не доступен, не могу сохранить auth")
            return
        try:
            context = page.context
            cookies = await context.cookies()
            # Collect localStorage for each origin
            origins = ["https://www.instagram.com", "https://i.instagram.com"]
            local_storage: Dict[str, Dict[str, str]] = {}
            for origin in origins:
                try:
                    ls = await page.evaluate(
                        """
                        (origin) => {
                            return new Promise((res) => {
                                try {
                                    const a = document.createElement('a'); a.href = origin;
                                    if (location.origin !== a.origin) {res({}); return;}
                                    const out = {};
                                    for (let i = 0; i < localStorage.length; i++) {
                                        const k = localStorage.key(i);
                                        out[k] = localStorage.getItem(k);
                                    }
                                    res(out);
                                } catch (e) { res({}); }
                            });
                        }
                        """,
                        origin,
                    )
                except Exception:
                    ls = {}
                if ls:
                    local_storage[origin] = ls
            data = {
                "username": username,
                "created_at": now(),
                "last_validated_at": now(),
                "user_agent": IG_UA,
                "x_ig_app_id": INSTAGRAM_APP_ID,
                "cookies": cookies,
                "local_storage": local_storage,
            }
            _auth_file(username).write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self.logger.send("INFO", f"auth сохранён в {str(_auth_file(username))}")
        except Exception as e:
            self.logger.send("ERROR", f"Не удалось сохранить auth для {username}: {e}")

    async def _apply_auth_to_context(self, context, username: str) -> bool:
        if not PLAYWRIGHT_AVAILABLE:
            self.logger.send("ERROR", "Playwright не доступен, не могу применить auth")
            return False
        data = self._load_auth(username)
        if not data:
            return False
        try:
            # Set cookies
            await context.add_cookies(data.get("cookies", []))
            # Set localStorage by visiting each origin
            page = await context.new_page()
            await page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
            ls_map: Dict[str, Dict[str, str]] = data.get("local_storage", {})
            for origin, kv in ls_map.items():
                try:
                    await page.evaluate(
                        """
                        (payload) => {
                            const { origin, kv } = payload;
                            const a = document.createElement('a'); a.href = origin;
                            if (location.origin !== a.origin) return;
                            for (const [k, v] of Object.entries(kv || {})) {
                                localStorage.setItem(k, v);
                            }
                        }
                        """,
                        {"origin": origin, "kv": kv},
                    )
                except Exception:
                    pass
            await page.close()
            return True
        except Exception as e:
            self.logger.send("ERROR", f"Не удалось применить auth: {e}")
            return False

    async def _validate_auth_httpx(self, username: str, proxy: Optional[str]) -> bool:
        """Validate whether stored cookies are still valid using httpx.

        Returns True if the cookies can fetch the profile info, False
        otherwise.  This function requires httpx installed.
        """
        try:
            import httpx
        except Exception:
            self.logger.send(
                "WARNING", "httpx не доступен, пропускаю валидацию cookie"
            )
            return False
        data = self._load_auth(username)
        if not data:
            return False
        cookies = {
            c["name"]: c["value"]
            for c in data.get("cookies", [])
            if "name" in c and "value" in c
        }
        if not cookies.get("sessionid"):
            return False
        headers = {
            "x-ig-app-id": data.get("x_ig_app_id", INSTAGRAM_APP_ID),
            "User-Agent": data.get("user_agent", IG_UA),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        proxy_url = None
        if proxy:
            proxy_url = proxy if proxy.startswith("http") else f"http://{proxy}"
        url = (
            "https://i.instagram.com/api/v1/users/web_profile_info/?username="
            + username
        )
        try:
            async with httpx.AsyncClient(timeout=20.0, proxy=proxy_url, headers=headers) as client:
                r = await client.get(url, cookies=cookies)
                if r.status_code == 200 and "\"user\"" in r.text:
                    data["last_validated_at"] = now()
                    _auth_file(username).write_text(
                        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    return True
                self.logger.send(
                    "WARNING",
                    f"auth валидация {username} HTTP {r.status_code}: {r.text[:160]}",
                )
                return False
        except Exception as e:
            self.logger.send(
                "WARNING", f"auth валидация {username} ошибка: {e}"
            )
            return False

    # ------------------------------------------------------------------
    # Methods requiring Playwright to login and create context
    # ------------------------------------------------------------------

    async def _create_browser_ctx_with_proxy(self, proxy_str: Optional[str]):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright не установлен; установка невозможна в этой среде.")
        # This method configures an iPhone browser context with proxy settings.
        browser = await self.playwright.chromium.launch(
            headless=True, args=["--window-size=390,844"]
        )
        # Parse proxy
        proxy_cfg = None
        if proxy_str:
            if "@" in proxy_str:
                auth, host_port = proxy_str.split("@", 1)
                username, password = auth.split(":", 1)
                host, port = host_port.split(":", 1)
                proxy_cfg = {
                    "server": f"http://{host}:{port}",
                    "username": username,
                    "password": password,
                }
            else:
                host, port = proxy_str.split(":", 1)
                proxy_cfg = {"server": f"http://{host}:{port}"}
        context = await browser.new_context(
            **self.playwright.devices["iPhone 14 Pro"],
            locale="en-US",
            timezone_id="Europe/Amsterdam",
            proxy=proxy_cfg,
        )
        page = await context.new_page()
        stealth = Stealth()
        await stealth.apply_stealth_async(page)
        return browser, context, page

    async def ensure_authorized_context(
        self, account: str, proxy_str: Optional[str]
    ):
        """Ensure that a Playwright context is authenticated.

        If stored cookies exist and are valid, reuse them to create
        a context.  Otherwise, log in with the provided account
        credentials and save the cookies.  Returns a tuple
        ``(browser, context, page, used_login)`` where
        ``used_login`` is True if a new login was performed.
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright не установлен; выполнение невозможно в этой среде."
            )
        username, password, twofa_seed = account.split(":", 2)
        # Validate existing auth via HTTP call
        valid = await self._validate_auth_httpx(username, proxy_str)
        if valid:
            self.logger.send("INFO", f"Используем сохранённые куки для {username}")
            browser, context, page = await self._create_browser_ctx_with_proxy(proxy_str)
            await self._apply_auth_to_context(context, username)
            return browser, context, page, False
        # Otherwise perform login
        self.logger.send("INFO", f"Выполняем вход для {username}")
        browser, context, page = await self._create_browser_ctx_with_proxy(proxy_str)
        # At this point you would call your login routine here.  It is
        # left unimplemented in this environment.  After logging in,
        # call ``await self._save_auth(page, username)``.
        raise RuntimeError(
            "Login routine is not implemented in this demonstration module."
        )

    # ------------------------------------------------------------------
    # Reel data extraction placeholder
    # ------------------------------------------------------------------

    async def fetch_reels_data(self, username: str) -> List[Dict[str, Any]]:
        """Fetch reel data from a profile.

        This placeholder returns a static example.  Replace the body
        with code that uses GraphQL to fetch real data when running
        locally with network access.
        """
        # Example of a single reel
        example_reel = {
            "shortcode": "DQNAdGCj5S4",
            "likes": 2679,
            "comments": 21,
            "views": 71407,
            "timestamp": 1761333125,
            "caption": "Пример описания",
            "preview_image": "https://example.com/preview.jpg",
            "video_url": "https://example.com/video.mp4",
        }
        return [example_reel]

    async def send_reels_to_api(self, reels: List[Dict[str, Any]], channel_id: int, api_base: str):
        """Send each reel as a video to the API endpoint.

        This method demonstrates posting JSON to an API.  The
        environment must have a reachable API at ``api_base``.  The
        payload format should match your backend expectations.
        """
        import httpx
        for reel in reels:
            payload = {
                "type": "instagram",
                "channel_id": channel_id,
                "link": f"https://www.instagram.com/reel/{reel['shortcode']}/",
                "name": reel["shortcode"],
                "amount_views": reel["views"],
                "amount_likes": reel["likes"],
                "amount_comments": reel["comments"],
                "image_url": reel["preview_image"],
                "articles": None,  # optional field if you extract articles from caption
            }
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(api_base, json=payload)
                    resp.raise_for_status()
                    self.logger.send(
                        "INFO",
                        f"Отправлено видео {reel['shortcode']} (status {resp.status_code})",
                    )
            except Exception as e:
                self.logger.send(
                    "ERROR",
                    f"Не удалось отправить видео {reel['shortcode']} на API: {e}",
                )


if __name__ == "__main__":
    # Simple command-line demonstration
    class DummyLogger:
        def send(self, level: str, msg: str):
            print(f"[{level}] {msg}")

    parser = InstagramParser(DummyLogger())
    if not PLAYWRIGHT_AVAILABLE:
        print(
            "Playwright не установлен в этой среде. "
            "Запустить полноценно логин/парсинг нельзя."
        )
    else:
        print(
            "Playwright доступен. Здесь вы могли бы вызвать ensure_authorized_context()"
        )