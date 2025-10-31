import asyncio
import json
import random
import re
from collections import deque
from datetime import datetime, timezone
from typing import Union, Optional, Tuple, Callable, Awaitable, Dict, List, Set
from urllib.parse import urlparse, urlunparse, urljoin

import httpx
import requests
from playwright.async_api import async_playwright, Page, Response, TimeoutError as PlaywrightTimeoutError

# try:
#     from playwright_stealth.async_api import stealth_async as apply_stealth  # Playwright Stealth >=2
# except ImportError:
#     try:
#         from playwright_stealth import stealth_async as apply_stealth  # Playwright Stealth 1.x
#     except ImportError:

#         async def apply_stealth(page):
#             try:
#                 import playwright_stealth as stealth  # type: ignore
#             except ImportError:
#                 return
#             await stealth.apply_stealth_async(page)  # type: ignore

from utils.logger import TCPLogger


ARTICLE_PREFIXES = ("#sv", "#jw", "#qz", "#sr", "#fg")

# Небольшой пул заголовков, чтобы брокировать User-Agent и Accept-Language.
HEADERS_POOL = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/117.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.7",
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) "
        "Gecko/20100101 Firefox/118.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    },
]


class ProxySwitchRequired(RuntimeError):
    """Special exception to signal that we should switch to the next proxy."""


class TikTokParser:
    def __init__(
            self,
            logger: TCPLogger
    ):
        self.logger = logger
        self.dom_video_links: Dict[str, str] = {}
        self.dom_images: Dict[str, List[str]] = {}
        self.dom_order: List[str] = []
        self.proxy_list: List[Optional[str]] = []

    # ----------------------- УТИЛИТЫ -----------------------

    def reset_dom_state(self):
        self.dom_video_links = {}
        self.dom_images = {}
        self.dom_order = []

    @staticmethod
    def _has_uploaded_image(image_field) -> bool:
        """Определяем, есть ли у видео уже загруженное изображение."""
        if image_field is None:
            return False
        if isinstance(image_field, str):
            return bool(image_field.strip())
        if isinstance(image_field, dict):
            candidate = image_field.get("url") or image_field.get("image") or image_field.get("path")
            if isinstance(candidate, str):
                return bool(candidate.strip())
            return bool(image_field)
        if isinstance(image_field, (list, tuple, set)):
            return any(
                TikTokParser._has_uploaded_image(item)
                for item in image_field
            )
        return bool(image_field)

    def _select_next_proxy(self, proxies: List[Optional[str]], last_proxy: Optional[str]) -> Optional[str]:
        if not proxies:
            return None
        if len(proxies) == 1:
            return proxies[0]
        candidates = [p for p in proxies if p != last_proxy]
        return random.choice(candidates) if candidates else proxies[0]

    # def _log(self, level: str, message: str):
    #     if self.logger:
    #         try:
    #             self.logger.send(level, message)
    #         except Exception:
    #             pass
    #     self.logger.send("INFO", message)

    def clean_tiktok_profile_url(self, url: str) -> str:
        parsed = urlparse(url)
        if "tiktok.com" not in parsed.netloc:
            raise ValueError("URL не принадлежит TikTok")
        if not parsed.path.startswith("/@"):
            raise ValueError("URL не является профилем TikTok")
        return urlunparse((parsed.scheme or "https", parsed.netloc, parsed.path.rstrip("/"), "", "", ""))

    async def _get_proxy_config(self, proxy_str: Optional[str]):
        if not proxy_str:
            return None
        try:
            if "@" in proxy_str:
                auth, host_port = proxy_str.split("@", 1)
                username, password = auth.split(":", 1)
                host, port = host_port.split(":", 1)
                return {"server": f"http://{host}:{port}", "username": username, "password": password}
            host, port = proxy_str.split(":", 1)
            return {"server": f"http://{host}:{port}"}
        except Exception as e:
            self.logger.send("INFO", f"Неверный формат прокси '{proxy_str}': {e}")
            return None

    async def _create_browser_with_proxy(self, playwright, proxy_str: Optional[str]):
        proxy_config = await self._get_proxy_config(proxy_str)
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox",                # если в контейнере/CI
                # "--disable-dev-shm-usage",     # если мало /dev/shm
                "--disable-infobars",
                "--lang=en-US,en;q=0.9",
                "--window-size=1920,1080",
                "--headless=new"
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            timezone_id="America/New_York",
            proxy=proxy_config,
            locale="en-US",
        )
        page = await context.new_page()
        # try:
        #     await apply_stealth(page)
        # except Exception:
        #     pass
        return browser, context, page

    # ----------------------- API-ПЕРЕХВАТЧИК -----------------------

    def attach_video_count_listener(
        self,
        page: Page,
        timeout_ms: int = 20000,
    ) -> Tuple[asyncio.Future, Callable[[Response], Awaitable[None]], float]:
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        timeout_s = timeout_ms / 1000

        async def on_response(resp: Response):
            if "/api/post/item_list/" not in resp.url or not resp.ok:
                return
            try:
                data = await resp.json()
            except Exception:
                return

            if not isinstance(data, dict):
                return

            total = data.get("extra", {}).get("total")
            item_list = data.get("itemList")

            if total is None and isinstance(item_list, list) and item_list:
                first = item_list[0]
                if isinstance(first, dict):
                    stats_v2 = first.get("authorStatsV2") or {}
                    stats_v1 = first.get("authorStats") or {}
                    total = stats_v2.get("videoCount") or stats_v1.get("videoCount")

            try:
                count_val = int(total) if total is not None else None
            except (TypeError, ValueError):
                count_val = None

            if count_val is not None and not future.done():
                future.set_result(count_val)

        page.on("response", on_response)
        return future, on_response, timeout_s

    async def _click_refresh_button(self, page: Page) -> bool:
        """
        Пытаемся нажать кнопку Refresh и ждём 5 секунд, чтобы страницы успела обновиться.
        Возвращает True, если клик выполнен и ожидание прошло.
        """
        try:
            refresh_locator = page.locator('button:has-text("Refresh")')
            if await refresh_locator.count() == 0:
                self.logger.send("INFO", "🔄 Кнопка Refresh не найдена на странице профиля")
                return False

            self.logger.send("INFO", "🔄 Нажимаем кнопку Refresh и ждём ответ")
            await refresh_locator.first.scroll_into_view_if_needed()
            await refresh_locator.first.click(timeout=5000)
            await page.wait_for_timeout(5000)
            return True
        except Exception as exc:
            self.logger.send("INFO", f"⚠️ Не удалось нажать кнопку Refresh: {exc}")
            return False

    # ----------------------- СБОР DOM -----------------------

    async def extract_videos_from_dom(self, page: Page) -> int:
        """Собираем ссылки и превью из карточек пользователя."""
        cards = await page.query_selector_all('div[data-e2e="user-post-item"]')
        added = 0

        for card in cards:
            try:
                link_el = await card.query_selector('a[href*="/video/"]')
                video_url = await link_el.get_attribute("href") if link_el else None
                if not video_url:
                    continue

                if video_url.startswith("/"):
                    video_url = urljoin("https://www.tiktok.com", video_url)

                match = re.search(r"/video/(\d+)", video_url)
                if not match:
                    continue

                video_id = match.group(1)
                if video_id not in self.dom_video_links:
                    self.dom_video_links[video_id] = video_url
                    self.dom_order.append(video_id)
                    added += 1

                img_elements = await card.query_selector_all("img")
                for img_el in img_elements:
                    try:
                        raw_urls = await img_el.evaluate(
                            """
                            (img) => {
                                const collected = [];
                                const push = (value) => {
                                    if (!value || typeof value !== "string") {
                                        return;
                                    }
                                    const trimmed = value.trim();
                                    if (!trimmed || collected.includes(trimmed)) {
                                        return;
                                    }
                                    collected.push(trimmed);
                                };
                                push(img.currentSrc);
                                push(img.src);
                                const srcAttr = img.getAttribute("src");
                                if (srcAttr) {
                                    push(srcAttr);
                                }
                                const dataSrc = img.getAttribute("data-src");
                                if (dataSrc) {
                                    push(dataSrc);
                                }
                                const dataUrl = img.getAttribute("data-url");
                                if (dataUrl) {
                                    push(dataUrl);
                                }
                                const srcset = img.getAttribute("srcset");
                                if (srcset) {
                                    for (const part of srcset.split(",")) {
                                        const candidate = part.trim().split(" ")[0];
                                        if (candidate) {
                                            push(candidate);
                                        }
                                    }
                                }
                                return collected;
                            }
                            """
                        )
                    except Exception:
                        raw_urls = None

                    if not raw_urls:
                        continue

                    normalized: List[str] = []
                    for raw in raw_urls:
                        if not isinstance(raw, str):
                            continue
                        candidate = raw.strip()
                        if not candidate:
                            continue
                        if candidate.startswith("//"):
                            candidate = "https:" + candidate
                        if not candidate.startswith(("http://", "https://")):
                            continue
                        if candidate not in normalized:
                            normalized.append(candidate)

                    if not normalized:
                        continue

                    stored = self.dom_images.setdefault(video_id, [])
                    for candidate in normalized:
                        if candidate not in stored:
                            stored.append(candidate)
                    if stored:
                        break
            except Exception:
                continue

        return added

    async def _shake_scroll(self, page: Page, delay: float) -> bool:
        """
        Делаем несколько коротких скроллов вверх-вниз, чтобы подтолкнуть ленту.
        Возвращает True, если число собранных карточек увеличилось.
        """
        baseline = len(self.dom_order)
        self.logger.send("INFO", "↕️  Нет прогресса — пробуем короткие скроллы")

        for jiggle in range(1, 4):
            self.logger.send("INFO", f"   ↕️ Попытка мини-скролла {jiggle}/3")
            try:
                await page.evaluate("() => window.scrollBy({ top: -window.innerHeight * 0.5, behavior: 'instant' })")
            except Exception:
                try:
                    await page.mouse.wheel(0, -1200)
                except Exception:
                    pass

            await page.wait_for_timeout(600)

            try:
                await page.evaluate("() => window.scrollBy({ top: window.innerHeight * 0.8, behavior: 'smooth' })")
            except Exception:
                try:
                    await page.mouse.wheel(0, 1400)
                except Exception:
                    pass

            await page.wait_for_timeout(int((delay + 0.4) * 1000))
            await self.extract_videos_from_dom(page)
            current_total = len(self.dom_order)
            self.logger.send("INFO", f"   🔄 После мини-скролла собрано {current_total} карточек")

            if current_total > baseline:
                return True

        return False

    async def scroll_and_collect(
        self,
        page: Page,
        target_count: Optional[int],
        url: str,
        selector: str = 'div[data-e2e="user-post-item"]',
        delay: float = 2.0,
        max_cycles: int = 20,
        tolerance: int = 0,
    ) -> int:
        """
        Плавно скроллим вниз, пока не достигнем нужного количества карточек.
        Если прогресс останавливается, пробуем короткие скроллы и при неудаче, не покрытой допуском, сигнализируем о смене прокси.
        """
        prev_total = len(self.dom_order)
        start_total = prev_total

        acceptable_total: Optional[int] = None
        if target_count is not None:
            acceptable_total = max(0, target_count - max(tolerance, 0))

        for cycle in range(1, max_cycles + 1):
            if target_count and len(self.dom_order) >= target_count:
                break

            self.logger.send("INFO", f"Прокрутка страницы, цикл {cycle}/{max_cycles}")

            try:
                await page.evaluate(
                    """
                    async () => {
                        const distance = 720;
                        const steps = 6;
                        for (let i = 0; i < steps; i += 1) {
                            window.scrollBy({ top: distance, behavior: 'smooth' });
                            await new Promise((resolve) => setTimeout(resolve, 180));
                        }
                    }
                    """
                )
            except Exception:
                try:
                    await page.mouse.wheel(0, 2200)
                except Exception:
                    pass

            await page.wait_for_timeout(int(delay * 1000))

            await self.extract_videos_from_dom(page)

            current_total = len(self.dom_order)
            target_info = target_count if target_count is not None else "?"
            self.logger.send("INFO", f"🔢 Собрано {current_total} уникальных видео (цель: {target_info})")

            if acceptable_total is not None and current_total >= acceptable_total:
                if target_count and current_total < target_count:
                    self.logger.send(
                        "INFO",
                        f"⚠️ Собрано {current_total}/{target_count}, допускаем недобор в {tolerance} видео."
                    )
                else:
                    self.logger.send("INFO", "🎯 Достигнуто требуемое количество видео из шапки.")
                break

            try:
                current_count = await page.eval_on_selector_all(selector, "els => els.length")
                self.logger.send("INFO", f"Текущее количество элементов по селектору '{selector}': {current_count}")
            except PlaywrightTimeoutError:
                self.logger.send("INFO", "Timeout при оценке элементов, продолжаем...")
            except Exception:
                pass

            if current_total == prev_total:
                self.logger.send("INFO", "🔁 Новых карточек нет, ждём и пробуем мини-скролл")
                if acceptable_total is not None and current_total >= acceptable_total:
                    if target_count and current_total < target_count:
                        self.logger.send(
                            "INFO",
                            f"⚠️ Собрано {current_total}/{target_count}, допускаем недобор в {tolerance} видео."
                        )
                    break

                if len(self.dom_order) == start_total:
                    self.logger.send(
                        "INFO",
                        "   ⌛️ Пока нет новых уникальных карточек по сравнению с началом прохода — продолжаем основной скролл."
                    )
                    continue

                adjusted = await self._shake_scroll(page, delay)
                if adjusted:
                    prev_total = len(self.dom_order)
                    continue

                raise ProxySwitchRequired("Нет прогресса после 3 дополнительных прокруток — переключаем прокси.")
            else:
                prev_total = current_total

        await self.extract_videos_from_dom(page)
        return len(self.dom_order)

    # ----------------------- ПАРСИНГ HTML -----------------------

    def _prepare_requests_proxy(self, proxy: Optional[str]) -> Optional[Dict[str, str]]:
        if not proxy:
            return None
        if proxy.startswith("http://") or proxy.startswith("https://"):
            proxy_url = proxy
        else:
            proxy_url = f"http://{proxy}"
        return {"http": proxy_url, "https": proxy_url}

    def _random_headers(self) -> Dict[str, str]:
        template = random.choice(HEADERS_POOL)
        # копируем, чтобы можно было добавлять per-request заголовки
        return dict(template)

    def _extract_universal_data(self, html: str) -> Optional[Dict]:
        marker = '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
        start = html.find(marker)
        if start == -1:
            return None
        start += len(marker)
        end = html.find("</script>", start)
        if end == -1:
            return None
        data_chunk = html[start:end]
        try:
            return json.loads(data_chunk)
        except json.JSONDecodeError:
            return None

    def _normalize_article(self, tag: str) -> Optional[str]:
        if not tag:
            return None
        if not tag.startswith("#"):
            tag = "#" + tag
        lower_tag = tag.lower()
        for prefix in ARTICLE_PREFIXES:
            if lower_tag.startswith(prefix):
                return tag
        return None

    def extract_articles(self, description: str, text_extra: Optional[List[dict]]) -> Optional[str]:
        found: set[str] = set()

        if description:
            for match in re.findall(r"#[\w-]+", description):
                normalized = self._normalize_article(match)
                if normalized:
                    found.add(normalized)

        if isinstance(text_extra, list):
            for block in text_extra:
                if not isinstance(block, dict):
                    continue
                name = block.get("hashtagName")
                if isinstance(name, str):
                    normalized = self._normalize_article(name)
                    if normalized:
                        found.add(normalized)

        if not found:
            return None

        # сохраняем порядок для детерминированности
        return ", ".join(sorted(found, key=lambda x: x.lower()))

    def _select_cover_url(self, video_data: Dict) -> Optional[str]:
        candidates = [
            video_data.get("originCover"),
            video_data.get("cover"),
            video_data.get("dynamicCover"),
            video_data.get("poster"),  # fallback if присутствует
        ]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                return candidate
        return None

    def parse_video_html(self, html: str) -> Optional[Dict[str, Union[str, int]]]:
        data = self._extract_universal_data(html)
        if not data:
            return None

        scope = data.get("__DEFAULT_SCOPE__", {})
        detail = scope.get("webapp.video-detail", {})
        item_info = detail.get("itemInfo", {})
        item_struct = item_info.get("itemStruct", {})
        if not item_struct:
            return None

        video_data = item_struct.get("video") or {}
        cover_url = self._select_cover_url(video_data if isinstance(video_data, dict) else {})

        stats = item_struct.get("stats", {})
        desc = item_struct.get("desc") or ""
        create_time = item_struct.get("createTime")
        text_extra = item_struct.get("textExtra")

        def to_int(val) -> int:
            try:
                return int(val)
            except (TypeError, ValueError):
                return 0

        published_at = None
        if isinstance(create_time, (int, str)) and str(create_time).isdigit():
            try:
                dt = datetime.fromtimestamp(int(create_time), tz=timezone.utc)
                published_at = dt.strftime("%Y-%m-%d")
            except (ValueError, OSError, OverflowError):
                published_at = None

        articles = self.extract_articles(desc, text_extra)

        return {
            "description": desc.strip(),
            "amount_views": to_int(stats.get("playCount")),
            "amount_likes": to_int(stats.get("diggCount")),
            "amount_comments": to_int(stats.get("commentCount")),
            "date_published": published_at,
            "articles": articles,
            "cover_url": cover_url,
        }

    def generate_short_title(self, full_text: str, max_length: int = 30) -> str:
        text = full_text.strip()
        if not text:
            return ""
        if len(text) <= max_length:
            return text
        truncated = text[:max_length]
        last_space = truncated.rfind(" ")
        return truncated[:last_space] if last_space > 0 else truncated

    async def fetch_video_html(
        self,
        video_url: str,
        proxy: Optional[str],
        max_retries: int = 3,
    ) -> Optional[str]:
        proxies = self._prepare_requests_proxy(proxy)
        for attempt in range(1, max_retries + 1):
            headers = self._random_headers()
            try:
                response = await asyncio.to_thread(
                    requests.get,
                    video_url,
                    headers=headers,
                    proxies=proxies,
                    timeout=30,
                )
                response.raise_for_status()
                return response.text
            except Exception as exc:
                self.logger.send(
                    "INFO",
                    f"⚠️ Ошибка при запросе {video_url} через {proxy or 'без прокси'} "
                    f"(попытка {attempt}/{max_retries}): {exc}",
                )
                if attempt < max_retries:
                    await asyncio.sleep(5)
        return None

    async def fetch_metadata_for_videos(
        self,
        video_ids: List[str],
        proxies: List[Optional[str]],
        max_retries: int = 3,
    ) -> Dict[str, Dict[str, Union[str, int]]]:
        results: Dict[str, Dict[str, Union[str, int]]] = {}
        attempts_per_id: Dict[str, int] = {vid: 0 for vid in video_ids}
        queue = list(video_ids)
        proxy_cycle = proxies if proxies else [None]

        while queue:
            for proxy in proxy_cycle:
                if not queue:
                    break

                video_id = queue.pop(0)
                video_url = self.dom_video_links.get(video_id)
                attempts_per_id[video_id] += 1

                if not video_url:
                    self.logger.send("INFO", f"⚠️ Для видео {video_id} нет URL, пропускаем")
                    continue

                html = await self.fetch_video_html(video_url, proxy, max_retries=1)
                if html:
                    parsed = self.parse_video_html(html)
                    if parsed:
                        results[video_id] = parsed
                        continue

                if attempts_per_id[video_id] < max_retries:
                    self.logger.send("INFO", f"🔁 Повторим видео {video_id} через 5 секунд (попытка {attempts_per_id[video_id]}/{max_retries})",)
                    await asyncio.sleep(5)
                    queue.append(video_id)
                else:
                    self.logger.send("INFO", f"⛔️ Не удалось получить данные видео {video_id} после {max_retries} попыток",)

            if queue:
                self.logger.send("INFO", "⏳ Пауза 5 секунд перед следующим проходом по прокси")
                await asyncio.sleep(5)

        return results

    # ----------------------- ОСНОВНОЙ МЕТОД -----------------------

    async def parse_channel(
        self,
        url: str,
        channel_id: int,
        user_id: int,
        max_retries: int = 3,
        proxy_list: Optional[List[str]] = None,
    ):
        self.proxy_list = [p for p in (proxy_list or []) if p]
        proxies_for_requests = self.proxy_list or [None]

        self.reset_dom_state()

        url = self.clean_tiktok_profile_url(url)
        username = urlparse(url).path.strip("/").lstrip("@") or "tiktok_profile"

        target_video_count: Optional[int] = None
        last_html_snapshot: Optional[str] = None
        success = False

        playwright = await async_playwright().start()
        try:
            proxies_for_browser = self.proxy_list or [None]
            random.shuffle(proxies_for_browser)

            max_attempts_per_proxy = 3
            for idx, current_proxy in enumerate(proxies_for_browser, start=1):
                self.logger.send("INFO", f"🌐 Прокси {idx}/{len(proxies_for_browser)}: {current_proxy or 'без прокси'}")

                success_on_proxy = False
                switch_proxy = False
                browser = context = page = None
                response_handler: Optional[Callable[[Response], Awaitable[None]]] = None

                try:
                    for attempt in range(1, max_attempts_per_proxy + 1):
                        self.logger.send("INFO", f"   Попытка {attempt}/{max_attempts_per_proxy} на этой прокси")
                        browser = context = page = None
                        response_handler = None
                        video_count_current: Optional[int] = None

                        try:
                            browser, context, page = await self._create_browser_with_proxy(playwright, current_proxy)
                            feed_future, response_handler, timeout_s = self.attach_video_count_listener(page)
                            refresh_attempted = False

                            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                            self.logger.send("INFO", f"🔎 Открыт профиль {url}")

                            current_url = page.url or ""
                            lowered_url = current_url.lower()
                            if "page-not-available" in lowered_url or "verify" in lowered_url:
                                raise RuntimeError(f"Страница недоступна или требует проверку: {current_url}")

                            try:
                                await page.wait_for_load_state("networkidle", timeout=15000)
                            except Exception:
                                pass

                            try:
                                video_count_current = await asyncio.wait_for(
                                    asyncio.shield(feed_future),
                                    timeout=timeout_s,
                                )
                                self.logger.send("INFO", f"📥 Получен videoCount: {video_count_current}")
                            except asyncio.TimeoutError:
                                self.logger.send("INFO", "⏱️ Не получили videoCount в отведённое время")
                                video_count_current = None
                                if not refresh_attempted:
                                    refresh_attempted = True
                                    clicked = await self._click_refresh_button(page)
                                    if clicked:
                                        if feed_future.done() and not feed_future.cancelled():
                                            try:
                                                video_count_current = feed_future.result()
                                                self.logger.send("INFO", f"📥 Получен videoCount после Refresh: {video_count_current}")
                                            except Exception as result_exc:
                                                self.logger.send("INFO", f"⚠️ Ошибка при получении videoCount после Refresh: {result_exc}")
                                                video_count_current = None
                                        else:
                                            self.logger.send("INFO", "⏱️ Ответ от API не пришёл после Refresh")
                                    else:
                                        self.logger.send("INFO", "🔄 Пропускаем Refresh-попытку")

                            await self.extract_videos_from_dom(page)
                            await self.scroll_and_collect(
                                page,
                                video_count_current or target_video_count,
                                url,
                                tolerance=1,
                            )

                            if len(self.dom_order) == 0:
                                raise RuntimeError("Не удалось собрать карточки на этой прокси.")

                            last_html_snapshot = await page.content()

                            if video_count_current is not None:
                                target_video_count = video_count_current

                            effective_target = target_video_count
                            tolerance = 1 if effective_target else 0
                            required_total = (
                                max(0, (effective_target or 0) - tolerance) if effective_target else None
                            )
                            collected_now = len(self.dom_order)
                            if effective_target is None:
                                enough_cards = collected_now > 0
                            else:
                                enough_cards = collected_now >= (
                                    required_total if required_total is not None else collected_now
                                )

                            success_on_proxy = collected_now > 0

                            if enough_cards:
                                if effective_target and collected_now < effective_target:
                                    self.logger.send("INFO", f"⚠️ Собрано {collected_now}/{effective_target}, принимаем результат с допуском {tolerance}.")
                                success = True
                                break

                            self.logger.send(
                                "INFO",
                                f"⚠️ На прокси {current_proxy or 'без прокси'} собрано только "
                                f"{collected_now}/{effective_target if effective_target is not None else '—'} — повторяем."
                            )
                            await asyncio.sleep(3)
                        except ProxySwitchRequired as switch_exc:
                            self.logger.send("INFO", f"   {switch_exc}")
                            switch_proxy = True
                            success_on_proxy = False
                            break
                        except Exception as inner_exc:
                            self.logger.send("INFO", f"   Ошибка попытки {attempt}/{max_attempts_per_proxy}: {inner_exc}")
                            await asyncio.sleep(3)
                        finally:
                            if response_handler and page:
                                try:
                                    page.off("response", response_handler)
                                except Exception:
                                    pass
                            for obj in (page, context, browser):
                                try:
                                    if obj:
                                        await obj.close()
                                except Exception:
                                    pass

                        if success:
                            break

                    if success:
                        break

                    if switch_proxy:
                        self.logger.send("INFO", "   Переходим к следующей прокси — нет прогресса по скроллу")
                        await asyncio.sleep(3)
                        continue

                    if not success_on_proxy:
                        self.logger.send("INFO", "   Переходим к следующей прокси")
                        await asyncio.sleep(5)
                        continue

                except Exception as e:
                    self.logger.send("INFO", f"🚫 Ошибка на прокси {current_proxy or 'без прокси'}: {e}")
                    try:
                        last_html_snapshot = await page.content() if page else last_html_snapshot
                    except Exception:
                        pass
                    finally:
                        if response_handler and page:
                            try:
                                page.off("response", response_handler)
                            except Exception:
                                pass
                        for obj in (page, context, browser):
                            try:
                                if obj:
                                    await obj.close()
                            except Exception:
                                pass

                    await asyncio.sleep(5)

        finally:
            try:
                await playwright.stop()
            except Exception:
                pass

        total_collected = len(self.dom_order)
        self.logger.send(
            "INFO",
            f"🎯 Собрано {total_collected} ссылок (videoCount: {target_video_count if target_video_count is not None else '—'})",
        )

        if not success:
            fname = f"tiktok_profile_{username}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.html"
            try:
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(last_html_snapshot or "<!-- empty -->")
                self.logger.send("INFO", f"📄 Не удалось собрать видео — HTML сохранён: {fname}")
            except Exception as e:
                self.logger.send("INFO", f"⚠️ Не удалось сохранить HTML: {e}")
            return

        video_ids = self.dom_order[: target_video_count] if target_video_count else self.dom_order
        metadata = await self.fetch_metadata_for_videos(video_ids, proxies_for_requests, max_retries=max_retries)

        all_videos_data: List[Dict[str, Union[str, int]]] = []
        for video_id in video_ids:
            link = self.dom_video_links.get(video_id)
            if not link:
                self.logger.send("INFO", f"⚠️ Нет ссылки для видео {video_id}, пропускаем")
                continue

            parsed = metadata.get(video_id)
            if not parsed:
                self.logger.send("INFO", f"⚠️ Нет данных по запросу для {video_id}, пропускаем")
                continue

            description = parsed.get("description") or ""
            title = self.generate_short_title(description or video_id)
            dom_candidates = self.dom_images.get(video_id) or []
            if isinstance(dom_candidates, str):
                dom_candidates = [dom_candidates]
            elif isinstance(dom_candidates, (tuple, set)):
                dom_candidates = list(dom_candidates)

            image_candidates: List[str] = []
            for candidate in dom_candidates:
                if not isinstance(candidate, str):
                    continue
                cleaned = candidate.strip()
                if not cleaned:
                    continue
                if cleaned.startswith("//"):
                    cleaned = "https:" + cleaned
                if cleaned.startswith(("http://", "https://")) and cleaned not in image_candidates:
                    image_candidates.append(cleaned)

            cover_url = parsed.get("cover_url")
            if isinstance(cover_url, str):
                cleaned_cover = cover_url.strip()
                if cleaned_cover.startswith("//"):
                    cleaned_cover = "https:" + cleaned_cover
                if cleaned_cover.startswith(("http://", "https://")) and cleaned_cover not in image_candidates:
                    image_candidates.append(cleaned_cover)

            image_url = image_candidates[0] if image_candidates else None

            all_videos_data.append(
                {
                    "type": "tiktok",
                    "channel_id": channel_id,
                    "link": link,
                    "name": title,
                    "description": description,
                    "amount_views": parsed.get("amount_views", 0),
                    "amount_likes": parsed.get("amount_likes", 0),
                    "amount_comments": parsed.get("amount_comments", 0),
                    "date_published": parsed.get("date_published"),
                    "image_url": image_url,
                    "articles": parsed.get("articles"),
                    "image_candidates": image_candidates,
                }
            )

        if not all_videos_data:
            self.logger.send("INFO", "⚠️ После запросов не осталось данных для отправки")
            return

        async def download_image(img_url: str, proxy: Optional[str] = None) -> Union[bytes, None]:
            try:
                normalized_proxy = proxy
                if normalized_proxy and not normalized_proxy.startswith(("http://", "https://")):
                    normalized_proxy = "http://" + normalized_proxy

                headers = self._random_headers()
                headers.setdefault("Accept", "image/avif,image/webp,image/*,*/*;q=0.8")
                headers.setdefault("Referer", "https://www.tiktok.com/")

                async with httpx.AsyncClient(
                    proxy=normalized_proxy,
                    timeout=httpx.Timeout(20.0),
                    headers=headers,
                    follow_redirects=True,
                    trust_env=False,
                ) as client:
                    response = await client.get(img_url)
                    response.raise_for_status()
                    return response.content
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                reason = exc.response.reason_phrase or ""
                self.logger.send("INFO", f"❌ Ошибка загрузки {img_url}: HTTP {status} {reason}".rstrip())
            except httpx.RequestError as exc:
                self.logger.send("INFO", f"❌ Ошибка загрузки {img_url}: {type(exc).__name__}: {exc}")
            except Exception as exc:
                self.logger.send("INFO", f"❌ Ошибка загрузки {img_url}: {exc}")
            return None

        async def upload_image(video_id: int, image_url: str, proxy: Optional[str] = None):
            img = await download_image(image_url, proxy=proxy)
            if not img:
                return None, "Download failed"
            file_name = image_url.split("/")[-1].split("?")[0] or f"{video_id}.jpg"
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {"file": (file_name, img, "image/jpeg")}
                resp = await client.post(
                    f"https://cosmeya.dev-klick.cyou/api/v1/videos/{video_id}/upload-image/",
                    files=files,
                )
                resp.raise_for_status()
                return resp.status_code, resp.text

        processed_count = 0
        image_queue: List[Tuple[int, List[str]]] = []
        queued_video_ids: Set[int] = set()

        for video_data in all_videos_data:
            link = video_data.get("link", "UNKNOWN_LINK")
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    check = await client.get(f"https://cosmeya.dev-klick.cyou/api/v1/videos/?link={link}")
                    video_id = None
                    is_new = False

                    if check.status_code == 200:
                        payload = check.json()
                        vids = payload.get("videos", [])
                        if vids:
                            existing_video = vids[0]
                            video_id = existing_video["id"]
                            update_payload = {
                                "amount_views": video_data.get("amount_views", 0),
                                "amount_likes": video_data.get("amount_likes", 0),
                                "amount_comments": video_data.get("amount_comments", 0),
                                # "date_published": video_data.get("date_published"),
                                "articles": video_data.get("articles"),
                                # "description": video_data.get("description"),
                            }
                            upd = await client.patch(
                                f"https://cosmeya.dev-klick.cyou/api/v1/videos/{video_id}",
                                json=update_payload,
                            )
                            upd.raise_for_status()
                            existing_image = existing_video.get("image")
                            image_missing = not self._has_uploaded_image(existing_image)
                            image_candidates = [
                                candidate
                                for candidate in video_data.get("image_candidates", [])
                                if isinstance(candidate, str) and candidate.startswith(("http://", "https://"))
                            ]
                            if image_missing and image_candidates and video_id not in queued_video_ids:
                                image_queue.append((video_id, image_candidates))
                                queued_video_ids.add(video_id)
                        else:
                            is_new = True
                    else:
                        self.logger.send("INFO", f"Проверка существования не удалась ({check.status_code}): {check.text}")
                        is_new = True

                    if is_new:
                        create_payload = {
                            key: value
                            for key, value in video_data.items()
                            if key not in {"video_id", "image_candidates"} and value is not None
                        }
                        create = await client.post("https://cosmeya.dev-klick.cyou/api/v1/videos/", json=create_payload)
                        create.raise_for_status()
                        created_video = create.json()
                        video_id = created_video["id"]
                        created_image = created_video.get("image")
                        image_missing = not self._has_uploaded_image(created_image)
                        image_candidates = [
                            candidate
                            for candidate in video_data.get("image_candidates", [])
                            if isinstance(candidate, str) and candidate.startswith(("http://", "https://"))
                        ]
                        if image_missing and image_candidates and video_id not in queued_video_ids:
                            image_queue.append((video_id, image_candidates))
                            queued_video_ids.add(video_id)

                processed_count += 1

            except Exception as e:
                self.logger.send("INFO", f"Критическая ошибка при обработке {link}: {e}")
                continue

        proxy_candidates: List[Optional[str]] = list(self.proxy_list) if self.proxy_list else [None]
        pending_images = deque((video_id, urls, None, 0, 0) for video_id, urls in image_queue)
        max_attempts_per_video = max(5, len(proxy_candidates) * 2)

        while pending_images:
            video_id, urls, last_proxy_used, url_index, attempts = pending_images.popleft()

            if not urls:
                self.logger.send("INFO", f"⚠️ Нет ссылок на обложки для видео {video_id}, пропускаем загрузку")
                continue

            if url_index >= len(urls):
                url_index = 0

            proxy = self._select_next_proxy(proxy_candidates, last_proxy_used)
            candidate_url = urls[url_index]
            candidate_position = f"{url_index + 1}/{len(urls)}"
            self.logger.send("INFO", f"🖼️ Прокси {proxy or 'без прокси'}: загружаем фото для видео {video_id} ({candidate_position})")

            try:
                status, _ = await upload_image(video_id, candidate_url, proxy=proxy)
                if status == 200:
                    self.logger.send("INFO", f"✅ Фото загружено для видео {video_id}")
                    await asyncio.sleep(4.0)
                    continue
                self.logger.send("INFO", f"⚠️ Фото: код {status} для видео {video_id} ({candidate_position})")
            except Exception as exc:
                self.logger.send("INFO", f"❌ Ошибка загрузки фото для {video_id} ({candidate_position}): {exc}")

            attempts += 1
            if attempts >= max_attempts_per_video:
                self.logger.send("INFO", f"⛔️ Превышено число попыток загрузки фото для видео {video_id}, пропускаем")
                continue

            if len(urls) > 1:
                next_index = (url_index + 1) % len(urls)
                if next_index != url_index:
                    self.logger.send("INFO", f"🔄 Попробуем альтернативный URL для видео {video_id} ({next_index + 1}/{len(urls)})")
                    pending_images.append((video_id, urls, None, next_index, attempts))
                    await asyncio.sleep(5.0)
                    continue

            self.logger.send("INFO", f"🔄 Повторим попытку для видео {video_id} через 30 секунд на другой прокси")
            pending_images.append((video_id, urls, proxy, url_index, attempts))
            await asyncio.sleep(30.0)

        self.logger.send("INFO", f"✅ Успешно обработано {processed_count} видео")


# ----------------------- Пример запуска -----------------------

# async def main():
#     proxy_list = [
        # "msEHZ8:tYomUE@138.219.122.128:9584",
        # "msEHZ8:tYomUE@138.219.123.22:9205",
        # "msEHZ8:tYomUE@138.59.5.46:9559",
        # "msEHZ8:tYomUE@152.232.68.147:9269",
        # "msEHZ8:tYomUE@152.232.67.18:9241",
        # "msEHZ8:tYomUE@152.232.68.149:9212",
        # "msEHZ8:tYomUE@152.232.66.152:9388",
        # "msEHZ8:tYomUE@152.232.65.53:9461",
        # "msEHZ8:tYomUE@190.185.108.103:9335",
        # "PvJVn6:jr8EvS@38.148.133.33:8000",
        # "PvJVn6:jr8EvS@38.148.142.71:8000",
        # "PvJVn6:jr8EvS@38.148.133.69:8000",
        # "PvJVn6:jr8EvS@38.148.138.48:8000",
        # "msEHZ8:tYomUE@168.196.239.222:9211",
        # "msEHZ8:tYomUE@168.196.237.44:9129",
        # "msEHZ8:tYomUE@168.196.237.99:9160",
        # "msEHZ8:tYomUE@138.219.122.56:9409",
        # "msEHZ8:tYomUE@138.99.37.16:9622",
        # "msEHZ8:tYomUE@138.99.37.136:9248",
        # "msEHZ8:tYomUE@152.232.72.124:9057",
        # "msEHZ8:tYomUE@23.229.49.135:9511",
        # "msEHZ8:tYomUE@209.127.8.189:9281",
        # "msEHZ8:tYomUE@152.232.72.235:9966",
        # "msEHZ8:tYomUE@152.232.74.34:9043",

        # "2p9UY4YAxP:O9Mru1m26m@109.120.131.161:34945",
        # "pA7b4DkZVm:8yv1LzTa82@109.120.131.6:53046",
        # "fPdEeT67zF:AkrSIiWZRN@109.120.131.124:61827",
        # "Pujlnq340D:lZXechQsfm@109.120.131.40:56974",
        # "F0AIJxsjsK:0KaDLg5uES@109.120.131.169:31162",
        # "iYvNraz4Qo:CtXfUQFIm6@109.120.131.25:36592",
        # "XAQrpqMDWw:IokI8mYSKf@109.120.131.129:43852",
        # "CCgYrPgXPY:KA3apNGhbN@109.120.131.229:27100",
        # "7ImUgttUz5:PlcstoApnp@109.120.131.196:56618",
        # "glyxP8tEya:HPhM9wjQGM@109.120.131.114:31838",

#         "d8mAnk3QEW:mJCDjUZQXt@45.150.35.133:20894",
#         "quUqYxfzsN:IVsnELV4fT@45.150.35.246:46257",
#         "RfbRo1W0gz:Rk5fwJnepP@45.150.35.131:63024",
#         "jcB7GBuBdw:wnOUcC6uC2@45.150.35.40:52284",
#         "rJexYOOn6O:tjd4Q4SgTN@45.150.35.194:57330",
#         "ZoA3aDjewp:lgRGWxPzR5@45.150.35.117:35941",
#         "PSKbldOuol:YRinsMQpQB@45.150.35.74:42121",
#         "aNpriSRLmG:RVEBaYMSnq@45.150.35.145:27900",
#         "um2y7QWzne:3NVuS7S93n@45.150.35.180:58611",
#         "gkmSRIalTf:xGROjfA2LF@45.150.35.154:39073",
#         "hejdZusT4h:BJYdsmEZKI@45.150.35.10:36612",
#         "nbyr75VACh:I5WWfT2oLt@45.150.35.215:48124",
#         "fgOfy2ylm9:9fKs4syWBG@45.150.35.48:47557",
#     ]
#     parser = TikTokParser()
#     url = "https://www.tiktok.com/@bestbeautydeal"
#     user_id = 13
#     await parser.parse_channel(url, channel_id=33, user_id=user_id, proxy_list=proxy_list)


# if __name__ == "__main__":
#     asyncio.run(main())
