import asyncio
import json
import random
import re
from datetime import datetime, timezone
from typing import Union, Optional, Tuple, Callable, Awaitable, Dict, List
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

# from utils.logger import TCPLogger


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
            # logger: TCPLogger
    ):
        # self.logger = logger
        self.dom_video_links: Dict[str, str] = {}
        self.dom_images: Dict[str, str] = {}
        self.dom_order: List[str] = []
        self.proxy_list: List[Optional[str]] = []

    # ----------------------- УТИЛИТЫ -----------------------

    def reset_dom_state(self):
        self.dom_video_links = {}
        self.dom_images = {}
        self.dom_order = []

    # def _log(self, level: str, message: str):
    #     if self.logger:
    #         try:
    #             self.logger.send(level, message)
    #         except Exception:
    #             pass
    #     print(message)

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
            print(f"Неверный формат прокси '{proxy_str}': {e}")
            return None

    async def _create_browser_with_proxy(self, playwright, proxy_str: Optional[str]):
        proxy_config = await self._get_proxy_config(proxy_str)
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
                "--no-sandbox",                # если в контейнере/CI
                # "--disable-dev-shm-usage",     # если мало /dev/shm
                "--disable-infobars",
                "--lang=en-US,en;q=0.9",
                "--window-size=1920,1080",
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

                img_el = await card.query_selector("img")
                image_url = await img_el.get_attribute("src") if img_el else None
                if image_url and video_id not in self.dom_images:
                    self.dom_images[video_id] = image_url
            except Exception:
                continue

        return added

    async def _shake_scroll(self, page: Page, delay: float) -> bool:
        """
        Делаем несколько коротких скроллов вверх-вниз, чтобы подтолкнуть ленту.
        Возвращает True, если число собранных карточек увеличилось.
        """
        baseline = len(self.dom_order)
        print("↕️  Нет прогресса — пробуем короткие скроллы")

        for jiggle in range(1, 4):
            print(f"   ↕️ Попытка мини-скролла {jiggle}/3")
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
            print(f"   🔄 После мини-скролла собрано {current_total} карточек")

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

        acceptable_total: Optional[int] = None
        if target_count is not None:
            acceptable_total = max(0, target_count - max(tolerance, 0))

        for cycle in range(1, max_cycles + 1):
            if target_count and len(self.dom_order) >= target_count:
                break

            print(f"Прокрутка страницы, цикл {cycle}/{max_cycles}")

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
            print(f"🔢 Собрано {current_total} уникальных видео (цель: {target_info})")

            if acceptable_total is not None and current_total >= acceptable_total:
                if target_count and current_total < target_count:
                    print(
                        f"⚠️ Собрано {current_total}/{target_count}, допускаем недобор в {tolerance} видео."
                    )
                else:
                    print("🎯 Достигнуто требуемое количество видео из шапки.")
                break

            try:
                current_count = await page.eval_on_selector_all(selector, "els => els.length")
                print(f"Текущее количество элементов по селектору '{selector}': {current_count}")
            except PlaywrightTimeoutError:
                print("Timeout при оценке элементов, продолжаем...")
            except Exception:
                pass

            if current_total == prev_total:
                print("🔁 Новых карточек нет, ждём и пробуем мини-скролл")
                if acceptable_total is not None and current_total >= acceptable_total:
                    if target_count and current_total < target_count:
                        print(
                            f"⚠️ Собрано {current_total}/{target_count}, допускаем недобор в {tolerance} видео."
                        )
                    break

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
                print(
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
                    print(f"⚠️ Для видео {video_id} нет URL, пропускаем")
                    continue

                html = await self.fetch_video_html(video_url, proxy, max_retries=1)
                if html:
                    parsed = self.parse_video_html(html)
                    if parsed:
                        results[video_id] = parsed
                        continue

                if attempts_per_id[video_id] < max_retries:
                    print(f"🔁 Повторим видео {video_id} через 5 секунд (попытка {attempts_per_id[video_id]}/{max_retries})",)
                    await asyncio.sleep(5)
                    queue.append(video_id)
                else:
                    print(f"⛔️ Не удалось получить данные видео {video_id} после {max_retries} попыток",)

            if queue:
                print("⏳ Пауза 5 секунд перед следующим проходом по прокси")
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
                print(f"🌐 Прокси {idx}/{len(proxies_for_browser)}: {current_proxy or 'без прокси'}")

                success_on_proxy = False
                switch_proxy = False
                browser = context = page = None
                response_handler: Optional[Callable[[Response], Awaitable[None]]] = None

                try:
                    for attempt in range(1, max_attempts_per_proxy + 1):
                        print(f"   Попытка {attempt}/{max_attempts_per_proxy} на этой прокси")
                        browser = context = page = None
                        response_handler = None
                        video_count_current: Optional[int] = None

                        try:
                            browser, context, page = await self._create_browser_with_proxy(playwright, current_proxy)
                            feed_future, response_handler, timeout_s = self.attach_video_count_listener(page)

                            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                            print(f"🔎 Открыт профиль {url}")

                            current_url = page.url or ""
                            lowered_url = current_url.lower()
                            if "page-not-available" in lowered_url or "verify" in lowered_url:
                                raise RuntimeError(f"Страница недоступна или требует проверку: {current_url}")

                            try:
                                await page.wait_for_load_state("networkidle", timeout=15000)
                            except Exception:
                                pass

                            try:
                                video_count_current = await asyncio.wait_for(feed_future, timeout=timeout_s)
                                print(f"📥 Получен videoCount: {video_count_current}")
                            except asyncio.TimeoutError:
                                print("⏱️ Не получили videoCount в отведённое время")
                                video_count_current = None

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
                                    print(f"⚠️ Собрано {collected_now}/{effective_target}, принимаем результат с допуском {tolerance}.")
                                success = True
                                break

                            print(
                                f"⚠️ На прокси {current_proxy or 'без прокси'} собрано только "
                                f"{collected_now}/{effective_target if effective_target is not None else '—'} — повторяем."
                            )
                            await asyncio.sleep(3)
                        except ProxySwitchRequired as switch_exc:
                            print(f"   {switch_exc}")
                            switch_proxy = True
                            success_on_proxy = False
                            break
                        except Exception as inner_exc:
                            print(f"   Ошибка попытки {attempt}/{max_attempts_per_proxy}: {inner_exc}")
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
                        print("   Переходим к следующей прокси — нет прогресса по скроллу")
                        await asyncio.sleep(3)
                        continue

                    if not success_on_proxy:
                        print("   Переходим к следующей прокси")
                        await asyncio.sleep(5)
                        continue

                except Exception as e:
                    print(f"🚫 Ошибка на прокси {current_proxy or 'без прокси'}: {e}")
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
        print(
            f"🎯 Собрано {total_collected} ссылок (videoCount: {target_video_count if target_video_count is not None else '—'})",
        )

        if not success:
            fname = f"tiktok_profile_{username}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.html"
            try:
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(last_html_snapshot or "<!-- empty -->")
                print(f"📄 Не удалось собрать видео — HTML сохранён: {fname}")
            except Exception as e:
                print(f"⚠️ Не удалось сохранить HTML: {e}")
            return

        video_ids = self.dom_order[: target_video_count] if target_video_count else self.dom_order
        metadata = await self.fetch_metadata_for_videos(video_ids, proxies_for_requests, max_retries=max_retries)

        all_videos_data: List[Dict[str, Union[str, int]]] = []
        for video_id in video_ids:
            link = self.dom_video_links.get(video_id)
            if not link:
                print(f"⚠️ Нет ссылки для видео {video_id}, пропускаем")
                continue

            parsed = metadata.get(video_id)
            if not parsed:
                print(f"⚠️ Нет данных по запросу для {video_id}, пропускаем")
                continue

            description = parsed.get("description") or ""
            title = self.generate_short_title(description or video_id)
            image_url = self.dom_images.get(video_id)

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
                }
            )

        if not all_videos_data:
            print("⚠️ После запросов не осталось данных для отправки")
            return

        async def download_image(img_url: str, proxy: Optional[str] = None) -> Union[bytes, None]:
            try:
                if proxy and not proxy.startswith(("http://", "https://")):
                    proxy = "http://" + proxy
                async with httpx.AsyncClient(proxy=proxy, timeout=20.0) as client:
                    r = await client.get(img_url)
                    r.raise_for_status()
                    return r.content
            except Exception as e:
                print(f"❌ Ошибка загрузки {img_url}: {e}")
                return None

        async def upload_image(video_id: int, image_url: str, proxy: Optional[str] = None):
            img = await download_image(image_url, proxy=proxy)
            if not img:
                return None, "Download failed"
            file_name = image_url.split("/")[-1].split("?")[0] or f"{video_id}.jpg"
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {"file": (file_name, img, "image/jpeg")}
                resp = await client.post(
                    f"https://sn.dev-klick.cyou/api/v1/videos/{video_id}/upload-image/",
                    files=files,
                )
                resp.raise_for_status()
                return resp.status_code, resp.text

        processed_count = 0
        image_queue = []

        for video_data in all_videos_data:
            link = video_data.get("link", "UNKNOWN_LINK")
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    check = await client.get(f"https://sn.dev-klick.cyou/api/v1/videos/?link={link}")
                    video_id = None
                    is_new = False

                    if check.status_code == 200:
                        payload = check.json()
                        vids = payload.get("videos", [])
                        if vids:
                            video_id = vids[0]["id"]
                            update_payload = {
                                "amount_views": video_data.get("amount_views", 0),
                                "amount_likes": video_data.get("amount_likes", 0),
                                "amount_comments": video_data.get("amount_comments", 0),
                                "date_published": video_data.get("date_published"),
                                "articles": video_data.get("articles"),
                                "description": video_data.get("description"),
                            }
                            upd = await client.patch(
                                f"https://sn.dev-klick.cyou/api/v1/videos/{video_id}",
                                json=update_payload,
                            )
                            upd.raise_for_status()
                        else:
                            is_new = True
                    else:
                        print(f"Проверка существования не удалась ({check.status_code}): {check.text}")
                        is_new = True

                    if is_new:
                        create_payload = {
                            key: value
                            for key, value in video_data.items()
                            if key != "video_id" and value is not None
                        }
                        create = await client.post("https://sn.dev-klick.cyou/api/v1/videos/", json=create_payload)
                        create.raise_for_status()
                        video_id = create.json()["id"]
                        if video_data.get("image_url"):
                            image_queue.append((video_id, video_data["image_url"]))

                processed_count += 1

            except Exception as e:
                print(f"Критическая ошибка при обработке {link}: {e}")
                continue

        last_proxy_for_images: Optional[str] = None
        idx = 0
        proxy_list = self.proxy_list or []
        while idx < len(image_queue):
            proxy = None
            if proxy_list:
                if len(proxy_list) == 1:
                    proxy = proxy_list[0]
                else:
                    candidates = [p for p in proxy_list if p != last_proxy_for_images]
                    proxy = random.choice(candidates) if candidates else proxy_list[0]
            last_proxy_for_images = proxy

            batch = image_queue[idx: idx + 15]
            print(f"🖼️ Прокси {proxy or 'без прокси'}: загружаем {len(batch)} фото")

            for video_id, image_url in batch:
                try:
                    status, _ = await upload_image(video_id, image_url, proxy=proxy)
                    if status == 200:
                        print(f"✅ Фото загружено для видео {video_id}")
                    else:
                        print(f"⚠️ Фото: код {status} для видео {video_id}")
                except Exception as e:
                    print(f"❌ Ошибка загрузки фото для {video_id}: {e}")
                await asyncio.sleep(4.0)

            idx += 15

        print(f"✅ Успешно обработано {processed_count} видео")


# ----------------------- Пример запуска -----------------------

async def main():
    proxy_list = [
        "2p9UY4YAxP:O9Mru1m26m@109.120.131.161:34945",
        "LgSCXw:UCNpHx@138.219.120.153:9466",
    ]
    parser = TikTokParser()
    url = "https://www.tiktok.com/@nastya.beomaa"
    user_id = 1
    await parser.parse_channel(url, channel_id=1, user_id=user_id, proxy_list=proxy_list)


if __name__ == "__main__":
    asyncio.run(main())
