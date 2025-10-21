import re
import random
import time
import httpx
import asyncio
from datetime import datetime
from typing import Union, Optional, Tuple
from urllib.parse import urlparse, urlunparse, urljoin

from playwright.async_api import async_playwright, Page, Response

from utils.logger import TCPLogger


class TikTokParser:
    def __init__(self, logger: TCPLogger):
        self.logger = logger

    # ----------------------- УТИЛИТЫ -----------------------

    def parse_views(self, views_text: Optional[str]) -> int:
        if not views_text:
            return 0
        txt = views_text.replace(",", "").strip().upper()
        if txt.endswith("K"):
            return int(float(txt[:-1]) * 1_000)
        if txt.endswith("M"):
            return int(float(txt[:-1]) * 1_000_000)
        return int(re.sub(r"[^\d]", "", txt) or 0)

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
            self.logger.send("INFO",  f"Неверный формат прокси '{proxy_str}': {e}")
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
        return browser, context, page

    # ----------------------- ПЕРЕХВАТ СЧЕТЧИКА -----------------------

    async def _safe_click(self, page: Page, locator_expr: str, timeout_ms: int = 1200):
        """Не-блокирующий клик: не валит сценарий и не ждёт 30с."""
        try:
            loc = page.locator(locator_expr)
            if await loc.count() > 0:
                await loc.first.click(timeout=timeout_ms)
                await page.wait_for_timeout(500)
                return True
        except Exception:
            pass
        return False

    async def wait_video_count_from_api(self, page: Page, timeout_ms: int = 20000) -> Optional[int]:
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()

        async def on_response(resp: Response):
            try:
                if "/api/post/item_list/" not in resp.url or not resp.ok:
                    return
                data = await resp.json()
                item_list = data.get("itemList") if isinstance(data, dict) else None
                if not isinstance(item_list, list) or not item_list:
                    return
                first = item_list[0]
                stats_v2 = first.get("authorStatsV2") or {}
                stats_v1 = first.get("authorStats") or {}
                val = stats_v2.get("videoCount", stats_v1.get("videoCount"))
                if val is None:
                    return
                count_val = int(val) if isinstance(val, (int, str)) else None
                if count_val is not None and not future.done():
                    future.set_result(count_val)
            except Exception:
                return

        page.on("response", on_response)
        try:
            return await asyncio.wait_for(future, timeout=timeout_ms / 1000)
        except asyncio.TimeoutError:
            self.logger.send("INFO",  "⏱️ Не дождались /api/post/item_list/ → videoCount")
            return None
        finally:
            try:
                page.off("response", on_response)
            except Exception:
                pass

    # ----------------------- СКРОЛЛ С ДОПУСКОМ -----------------------

    @staticmethod
    def _within_tolerance(current: int, target: int, tol_low: int, tol_high: int) -> bool:
        """true, если target - tol_low <= current <= target + tol_high."""
        return (current >= max(0, int(target) - int(tol_low))) and (current <= int(target) + int(tol_high))

    async def scroll_to_target_precise(
        self,
        page: Page,
        selector: str,
        target_count: int,
        step_delay_s: float = 1.2,
        max_unchanged_cycles: int = 3,
        tol_low: int = 3,
        tol_high: int = 3,
    ) -> Tuple[int, bool]:
        """
        Скроллим, пока количество карточек не окажется в допуске относительно target_count.
        Успех: target - tol_low <= current <= target + tol_high.
        Ошибка: current не растёт max_unchanged_cycles подряд и при этом всё ещё вне допуска.
        Возвращает (final_count, reached).
        """
        prev = -1
        unchanged = 0
        tol_str = f"±{max(tol_low, tol_high)}" if tol_low == tol_high else f"-{tol_low}/+{tol_high}"

        while True:
            # 1) серия scrollBy; ранний выход, если дальше не скроллится
            await page.evaluate(
                """
                async () => new Promise((resolve) => {
                    let total = 0;
                    const distance = 1600;
                    const tick = setInterval(() => {
                        const before = window.scrollY;
                        window.scrollBy(0, distance);
                        total += distance;
                        if (window.scrollY === before || total > 20000) {
                            clearInterval(tick);
                            resolve();
                        }
                    }, 80);
                })
                """
            )

            # 2) пауза на подгрузку
            await page.wait_for_timeout(int(step_delay_s * 1000))

            # 3) «тихие» попытки снять помехи
            await self._safe_click(page, 'button:has-text("Skip")')
            await self._safe_click(page, 'button:has-text("Refresh")')
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass

            # 4) считаем карточки
            current = await page.eval_on_selector_all(selector, "els => els.length")
            self.logger.send("INFO",  f"📊 Элементов на странице: {current} / {target_count} (допуск {tol_str})")

            # 5) успех по допуску
            if self._within_tolerance(current, target_count, tol_low, tol_high):
                self.logger.send("INFO",  f"✅ Достаточно: {current} в допуске относительно {target_count} ({tol_str})")
                return current, True

            # 6) контроль застревания
            if current == prev:
                unchanged += 1
                self.logger.send("INFO",  f"…число не изменилось (серия {unchanged}/{max_unchanged_cycles})")
                if unchanged >= max_unchanged_cycles:
                    # финальная проверка допусков перед признанием неуспеха
                    if self._within_tolerance(current, target_count, tol_low, tol_high):
                        self.logger.send("INFO",  f"✅ Завершаем по допуску после стагнации: {current} vs {target_count} ({tol_str})")
                        return current, True
                    return current, False
            else:
                unchanged = 0
                prev = current

    # ----------------------- ОСНОВНОЙ -----------------------

    async def parse_channel(self, url: str, channel_id: int, user_id: int, max_retries: int = 3, proxy_list: list = None):
        self.proxy_list = proxy_list or []
        self.current_proxy_index = 0
        if not self.proxy_list:
            self.logger.send("INFO",  "ℹ️ Список прокси пуст — работаем без прокси")

        url = self.clean_tiktok_profile_url(url)
        username = urlparse(url).path.strip("/").lstrip("@") or "tiktok_profile"

        all_videos_data = []
        last_html_snapshot: Optional[str] = None
        success = False

        proxies_to_try = self.proxy_list[:] if self.proxy_list else [None]
        random.shuffle(proxies_to_try)

        playwright = await async_playwright().start()
        try:
            for idx, current_proxy in enumerate(proxies_to_try, start=1):
                self.logger.send("INFO",  f"\n🌐 Прокси {idx}/{len(proxies_to_try)}: {current_proxy or 'без прокси'}")
                browser = context = page = None

                try:
                    browser, context, page = await self._create_browser_with_proxy(playwright, current_proxy)

                    # обработчик ответа — ДО навигации
                    count_task = asyncio.create_task(self.wait_video_count_from_api(page, timeout_ms=20000))

                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    self.logger.send("INFO",  f"🔎 Открыт профиль {url}")
                    self.logger.send("INFO",  f" Текущая страница {page.url}")

                    try:
                        await page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass

                    expected_video_count = await count_task
                    if expected_video_count is None:
                        self.logger.send("INFO",  "⚠️ Не получили videoCount — меняем прокси.")
                        last_html_snapshot = await page.content()
                        await page.close(); await context.close(); await browser.close()
                        continue

                    self.logger.send("INFO",  f"🎯 videoCount с API: {expected_video_count}")
                    self.logger.send("INFO",  f" Текущая страница {page.url}")
                    # скроллим с учётом допуска
                    final_count, reached = await self.scroll_to_target_precise(
                        page,
                        selector='div[data-e2e="user-post-item"]',
                        target_count=expected_video_count,
                        step_delay_s=1.2,
                        max_unchanged_cycles=3,
                        tol_low=3,
                        tol_high=3,
                    )
                    self.logger.send("INFO",  f" Текущая страница {page.url}")
                    last_html_snapshot = await page.content()

                    if not reached:
                        self.logger.send("INFO",  f"❌ Застряли на {final_count}/{expected_video_count} (вне допуска). Меняем прокси.")
                        await page.close(); await context.close(); await browser.close()
                        time.sleep(10)
                        continue

                    self.logger.send("INFO",  f"✅ Достигли цели с допуском: {final_count} ~ {expected_video_count}")
                    success = True

                    # -------- Сбор карточек --------
                    videos = await page.query_selector_all('div[data-e2e="user-post-item"]')
                    self.logger.send("INFO",  f"🎬 Карточек на странице: {len(videos)}")

                    for video in videos:
                        try:
                            link_el = await video.query_selector('a[href*="/video/"]')
                            video_url = await link_el.get_attribute('href') if link_el else None
                            if not video_url:
                                continue
                            if video_url.startswith("/"):
                                video_url = urljoin("https://www.tiktok.com", video_url)

                            view_el = await video.query_selector('strong[data-e2e="video-views"]')
                            views_text = await view_el.inner_text() if view_el else "0"
                            views = self.parse_views(views_text)

                            img_el = await video.query_selector('img')
                            description = await img_el.get_attribute('alt') if img_el else ""
                            img_url = await img_el.get_attribute('src') if img_el else None

                            title = description[:30].rsplit(" ", 1)[0] if len(description or "") > 30 else (description or "")
                            all_videos_data.append({
                                "type": "tiktok",
                                "channel_id": channel_id,
                                "link": video_url,
                                "name": title,
                                "amount_views": views,
                                "image_url": img_url
                            })
                        except Exception as e:
                            self.logger.send("INFO",  f"Ошибка парсинга карточки: {e}")
                            continue

                    await page.close()
                    await context.close()
                    await browser.close()
                    break  # успех -> выходим из цикла прокси

                except Exception as e:
                    self.logger.send("INFO",  f"🚫 Ошибка на прокси {current_proxy or 'без прокси'}: {e}")
                    try:
                        last_html_snapshot = await page.content() if page else last_html_snapshot
                    except Exception:
                        pass
                    finally:
                        for obj in (page, context, browser):
                            try:
                                if obj:
                                    await obj.close()
                                    self.logger.send("INFO",  f"🧹 Закрыто объект {obj}")
                            except Exception:
                                pass
                    continue  # к следующей прокси

        finally:
            try:
                await playwright.stop()
            except Exception:
                pass

        # если не удалось ни на одной прокси — сохраняем HTML
        if not success:
            fname = f"tiktok_profile_{username}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.html"
            try:
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(last_html_snapshot or "<!-- empty -->")
                self.logger.send("INFO",  f"📄 Все прокси исчерпаны. HTML сохранён: {fname}")
            except Exception as e:
                self.logger.send("INFO",  f"⚠️ Не удалось сохранить HTML: {e}")

        # ---------- Этап 2: API + загрузка изображений ----------

        async def download_image(img_url: str, proxy: Optional[str] = None) -> Union[bytes, None]:
            try:
                if proxy and not proxy.startswith(("http://", "https://")):
                    proxy = "http://" + proxy
                async with httpx.AsyncClient(proxy=proxy, timeout=20.0) as client:
                    r = await client.get(img_url)
                    r.raise_for_status()
                    return r.content
            except Exception as e:
                self.logger.send("INFO",  f"❌ Ошибка загрузки {img_url}: {e}")
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
                            upd = await client.patch(
                                f"https://sn.dev-klick.cyou/api/v1/videos/{video_id}",
                                json={"amount_views": video_data["amount_views"]},
                            )
                            upd.raise_for_status()
                        else:
                            is_new = True
                    else:
                        self.logger.send("INFO",  f"Проверка существования не удалась ({check.status_code}): {check.text}")
                        is_new = True

                    if is_new:
                        create = await client.post("https://sn.dev-klick.cyou/api/v1/videos/", json=video_data)
                        create.raise_for_status()
                        video_id = create.json()["id"]
                        # self.logger.send("INFO",  f"🆕 Создано видео ID={video_id}")
                        if video_data.get("image_url"):
                            image_queue.append((video_id, video_data["image_url"]))

                processed_count += 1

            except Exception as e:
                self.logger.send("INFO",  f"Критическая ошибка при обработке {link}: {e}")
                continue

        # загрузка изображений пакетами по 15/прокси
        idx = 0
        proxy_list = self.proxy_list or []
        while idx < len(image_queue):
            proxy = None
            if proxy_list:
                if len(proxy_list) == 1:
                    proxy = proxy_list[0]
                else:
                    candidates = [p for p in proxy_list if p != last_proxy_for_images]
                    proxy = random.choice(candidates)
            else:
                proxy = None
            last_proxy_for_images = proxy

            batch = image_queue[idx: idx + 15]
            self.logger.send("INFO",  f"🖼️ Прокси {proxy or 'без прокси'}: загружаем {len(batch)} фото")

            for video_id, image_url in batch:
                try:
                    status, _ = await upload_image(video_id, image_url, proxy=proxy)
                    if status == 200:
                        self.logger.send("INFO",  f"✅ Фото загружено для видео {video_id}")
                    else:
                        self.logger.send("INFO",  f"⚠️ Фото: код {status} для видео {video_id}")
                except Exception as e:
                    self.logger.send("INFO",  f"❌ Ошибка загрузки фото для {video_id}: {e}")
                await asyncio.sleep(4.0)

            idx += 15
            if idx < len(image_queue) and proxy_list:
                # (при желании можно оставить паузу — зависит от лимитов)
                pass

        self.logger.send("INFO",  f"✅ Успешно обработано {processed_count} видео")


# # ----------------------- Пример запуска -----------------------

# async def main():
#     proxy_list = [
#         # "g3dmsMyYST:B9BegRNRzi@45.150.35.224:28898",
#         # "Weh1oXn82b:dUYiJZ5w7T@45.150.35.129:31801",
#         # "gnmPrWSMJ4:tbHyXTwWdx@45.150.35.114:54943",
#         # "15ObFJmCP5:a0rog6kGgT@45.150.35.113:24242",
#         "Z7mGFwrT6N:5wLFFO5v3S@109.120.131.5:34707",
#         "HCtCUxQYnj:GM9pjQ8J8T@109.120.131.229:39202",
#         "dBY505zGKK:8gqxiwpjvg@45.150.35.44:40281",
#         "zhH47betn3:J8eC3qaOrs@109.120.131.175:38411",
#         "KX32alVE51:ZVD0CsjFhJ@109.120.131.27:47449",
#         "KTdw9aNBl7:MI45E5jVnB@45.150.35.233:57281",
#         "7bZbeHwcNI:fFs1cUXfbN@109.120.131.219:29286",
#         "F1Y0BvrqNo:HKPbfMGtJw@45.150.35.31:41247",
#         "WfkB8GfYts:vXdJAVXCSI@45.150.35.133:35460",
#         "yr3Xib8LYo:FzS9t4PGro@45.150.35.3:50283",
#         "exOL0CR6TN:oj0BGarhAk@45.150.35.143:32354",
#         "CbZ35SQIZb:OO4ddjBRiK@45.150.35.99:28985",
#         "JRGI3q6Zo9:LJpcFpCgU2@45.150.35.30:32381",
#         "NTPvsl77eN:wagp6GmWNk@109.120.131.41:55509",
#         "SBqj98lU9c:ktxTU1ZOid@45.150.35.138:55350",
#         "3El7Uvg1TY:1DZVyrdMPs@45.150.35.231:51842",
#         "dBqOOqGczg:d2xKkdc3Re@45.150.35.156:38617",
#         "fz91O4ury3:ZBCW6s8d7E@45.150.35.132:47712",
#         "RLFUp7vicq:X1TTYhQYWs@45.150.35.34:40674",
#         "3dQxPpHkj4:o12oWKn5Lg@45.150.35.201:42897",
#         "iRArjOVFVr:0vXB48RsTf@45.150.35.200:42312",
#     ]
#     parser = TikTokParser()
#     url = "https://www.tiktok.com/@nastya.beomaa"
#     user_id = 1
#     await parser.parse_channel(url, channel_id=1, user_id=user_id, proxy_list=proxy_list)

# if __name__ == "__main__":
#     asyncio.run(main())
