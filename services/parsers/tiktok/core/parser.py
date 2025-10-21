import asyncio
from datetime import datetime, timezone
import re
from urllib.parse import urlparse, urlunparse
import httpx
import random
from typing import Union, Optional
from playwright.async_api import async_playwright

try:
    from playwright_stealth.async_api import stealth_async as apply_stealth  # Playwright Stealth >= 2.0
except ImportError:
    try:
        from playwright_stealth import stealth_async as apply_stealth  # Playwright Stealth 1.1+
    except ImportError:
        from playwright_stealth import Stealth  # Very old versions expose only the class API

        async def apply_stealth(page):
            stealth = Stealth()
            await stealth.apply_stealth_async(page)

from utils.logger import TCPLogger


class TikTokParser:
    def __init__(self, logger: TCPLogger):
        self.logger = logger

    async def scroll_until(self, page, url: str, selector: str, delay: float = 3.0, max_idle_rounds: int = 5):
        prev_count = 0
        idle_rounds = 0
        max_scroll_attempts = 3
        final_count = 0

        for attempt in range(max_scroll_attempts):
            self.logger.send("INFO",  f"Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

            while True:
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

                refresh_button = await page.query_selector('button.emuynwa3.css-z9i4la-Button-StyledButton.ehk74z00')
                if refresh_button:
                    self.logger.send("INFO",  "Обнаружена кнопка 'Refresh'. Кликаем для перезагрузки страницы.")
                    await refresh_button.click()
                    await page.wait_for_timeout(3000)

                current_count = await page.eval_on_selector_all(selector, "els => els.length")
                self.logger.send("INFO",  f"Текущее количество элементов: {current_count}")

                if current_count == prev_count:
                    idle_rounds += 1
                    if idle_rounds >= max_idle_rounds:
                        self.logger.send("INFO",  f"Достигнут конец списка видео профиля {url}")
                        self.logger.send("INFO",  f"Спарсил все видео в количестве {current_count}")
                        final_count = current_count
                        break
                else:
                    idle_rounds = 0
                    prev_count = current_count

                is_at_bottom = await page.evaluate("""
                    () => (window.innerHeight + window.scrollY) >= document.body.scrollHeight;
                """)
                if is_at_bottom and idle_rounds >= max_idle_rounds:
                    self.logger.send("INFO",  f"Достигнут конец страницы для {url}")
                    final_count = current_count
                    break

        # 🔍 Проверка: если после всех попыток количество видео не выросло — сохраняем HTML
        if final_count == 0:
            # На всякий случай получим текущее количество
            final_count = await page.eval_on_selector_all(selector, "els => els.length")

        if final_count == prev_count and final_count > 0:
            self.logger.send("INFO",  "ℹ️ Количество видео не изменилось после всех попыток прокрутки. Сохраняем HTML страницы.")
            try:
                html_content = await page.content()
                # Генерируем имя файла: безопасное из URL
                parsed = urlparse(url)
                safe_name = parsed.path.strip("/").replace("@", "_").replace("/", "_")
                filename = f"tiktok_profile_{safe_name}_{int(asyncio.get_event_loop().time())}.html"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(html_content)
                self.logger.send("INFO",  f"✅ HTML сохранён в файл: {filename}")
            except Exception as e:
                self.logger.send("INFO",  f"❌ Ошибка при сохранении HTML: {e}")

        return final_count

    async def get_proxy_config(self, proxy_str: str) -> Optional[dict]:
        try:
            if "@" in proxy_str:
                auth, host_port = proxy_str.split("@")
                username, password = auth.split(":")
                host, port = host_port.split(":")
                return {
                    "server": f"http://{host}:{port}",
                    "username": username,
                    "password": password
                }
            else:
                host, port = proxy_str.split(":")
                return {"server": f"http://{host}:{port}"}
        except Exception as e:
            self.logger.send("INFO",  f"Неверный формат прокси '{proxy_str}': {e}")
            return None

    async def download_image(self, url: str, proxy: str = None) -> Union[bytes, None]:
        try:
            if proxy and not proxy.startswith(("http://", "https://")):
                proxy = "http://" + proxy
            async with httpx.AsyncClient(proxy=proxy, timeout=20.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
        except Exception as e:
            self.logger.send("INFO",  f"❌ Ошибка загрузки изображения {url}: {e}")
            return None

    async def upload_image(self, video_id: int, image_url: str, proxy: str = None):
        image_bytes = await self.download_image(image_url, proxy=proxy)
        if not image_bytes:
            return None, "Download failed"

        file_name = image_url.split("/")[-1].split("?")[0] or "cover.jpg"
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": (file_name, image_bytes, "image/jpeg")}
            try:
                resp = await client.post(
                    f"https://cosmeya.dev-klick.cyou/api/v1/videos/{video_id}/upload-image/",
                    files=files,
                )
                resp.raise_for_status()
                return resp.status_code, resp.text
            except Exception as e:
                self.logger.send("INFO",  f"⚠️ Ошибка загрузки фото для видео {video_id}: {e}")
                return None, str(e)

    def clean_tiktok_profile_url(self, url: str) -> str:
        """
        Очищает URL профиля TikTok от всех параметров, кроме пути.
        Пример:
            Вход: https://www.tiktok.com/@mil.beoma?_r=1&_d=...&utm_source=copy...
            Выход: https://www.tiktok.com/@mil.beoma
        """
        parsed = urlparse(url)
        # Разрешаем только домен tiktok.com и путь вида /@username
        if "tiktok.com" not in parsed.netloc:
            raise ValueError("URL не принадлежит TikTok")

        # Путь должен начинаться с /@ — это профиль
        if not parsed.path.startswith("/@"):
            raise ValueError("URL не является профилем TikTok")

        # Собираем чистый URL: схема + домен + путь
        clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        return clean

    def generate_short_title(self, full_title: str, max_length: int = 30) -> str:
        if not full_title:
            return ""
        if len(full_title) <= max_length:
            return full_title
        truncated = full_title[:max_length]
        last_space = truncated.rfind(' ')
        if last_space != -1:
            return truncated[:last_space]
        return truncated

    def extract_article_tag(self, caption: str) -> str | None:
        """Возвращает строку со ВСЕМИ найденными артикулами (#sv, #jw и т.д.) через запятую или None."""
        if not caption:
            return None

        allowed_tags = ["#sv", "#jw", "#qz", "#sr", "#fg"]
        found_tags = []

        caption_lower = caption.lower()
        original_caption = caption  # сохраняем оригинальный регистр для точного извлечения

        for tag in allowed_tags:
            if tag in caption_lower:
                # Ищем позицию в нижнем регистре
                start = caption_lower.find(tag)
                if start != -1:
                    # Берём точное написание из оригинала (на случай если кто-то написал #SV)
                    exact_tag = original_caption[start:start + len(tag)]
                    found_tags.append(exact_tag)

        # Убираем дубли и сортируем для консистентности (опционально)
        found_tags = sorted(set(found_tags))

        return ",".join(found_tags) if found_tags else None

    async def parse_channel(self, url: str, channel_id: int, user_id: int, max_retries: int = 3, proxy_list: list = None):

        # --- ОЧИСТКА URL ---
        try:
            clean_url = self.clean_tiktok_profile_url(url)
            self.logger.send("INFO",  f"🧹 Очищенный URL профиля: {clean_url}")
        except Exception as e:
            self.logger.send("INFO",  f"Неверный URL TikTok профиля: {url} | Ошибка: {e}")
            raise ValueError(f"Некорректный URL профиля TikTok: {e}")

        # Далее используем clean_url вместо url
        url = clean_url

        proxy_list = proxy_list or []
        current_proxy_index = 0
        url = url.strip()
        match = re.search(r"@([a-zA-Z0-9_.-]+)", url)
        if not match:
            raise ValueError(f"Не удалось извлечь username из URL: {url}")
        username = match.group(1)

        proxy = random.choice(proxy_list) if proxy_list else None
        proxy_config = await self.get_proxy_config(proxy) if proxy else None

        playwright = None
        browser = None
        context = None
        page = None

        all_videos_data = []
        seen_ids = set()

        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=False,
                args=[
                    "--headless=new",
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--window-size=1920,1080"
                ],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                proxy=proxy_config
            )
            page = await context.new_page()
            await apply_stealth(page)

            self.logger.send("INFO",  f"🌐 Открываем профиль: {url} (username: {username})")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            try:
                await page.wait_for_selector("div[id^='column-item-video-container-']", timeout=15000)
            except Exception as e:
                self.logger.send("INFO",  f"⚠️ Не удалось дождаться первого видео-элемента: {e}")

            tiktok_responses = []

            async def handle_response(response):
                if "/api/post/item_list/" in response.url:
                    try:
                        data = await response.json()
                        if data.get("itemList"):
                            tiktok_responses.append(data)
                            self.logger.send("INFO",  f"📥 +{len(data['itemList'])} видео (всего: {sum(len(r['itemList']) for r in tiktok_responses)})")
                    except:
                        pass

            page.on("response", handle_response)

            await asyncio.sleep(3)

            # 🚀 Шаг 1. Скроллим до конца
            self.logger.send("INFO",  "⏳ Скроллим страницу до самого низа...")
            total_videos_count = await self.scroll_until(
                page,
                url,
                selector="div[id^='column-item-video-container-']",
                delay=2.5,
                max_idle_rounds=5
            )
            self.logger.send("INFO",  f"✅ Скролл завершён. DOM содержит {total_videos_count} видео. Подгружаем API-ответы...")

            # Теперь скроллим МЕДЛЕННО и ЖДЁМ загрузки
            await self.scroll_until(
                page,
                url,
                selector="div[id^='column-item-video-container-']",
                delay=4.0,
                max_idle_rounds=3
            )

            await asyncio.sleep(10)

            self.logger.send("INFO",  f"✅ Собрано {len(tiktok_responses)} item_list ответов.")

            # 🚀 Шаг 4. Собираем видео из всех ответов
            for response_data in tiktok_responses:
                for item in response_data.get("itemList", []):
                    vid = str(item.get("id"))
                    if vid in seen_ids:
                        continue
                    seen_ids.add(vid)
                    stats = item.get("stats", {})
                    video_info = item.get("video", {})
                    cover = video_info.get("cover") or video_info.get("dynamicCover") or video_info.get("originCover")
                    desc = item.get("desc") or ""
                    articles = self.extract_article_tag(desc)
                    video_title = self.generate_short_title(desc, 30)
                    link = f"https://www.tiktok.com/@{username}/video/{vid}"

                    ts = item.get("createTime")
                    date_published = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT00:00:00") if ts else None

                    all_videos_data.append({
                        "link": link,
                        "type": "tiktok",
                        "name": video_title,
                        "image": cover,
                        "articles": articles,
                        "channel_id": channel_id,
                        "amount_views": int(stats.get("playCount", 0)),
                        "amount_likes": int(stats.get("diggCount", 0)),
                        "amount_comments": int(stats.get("commentCount", 0)),
                        "date_published": date_published
                    })

            self.logger.send("INFO",  f"🎯 Всего собрано {len(all_videos_data)} уникальных видео из {len(tiktok_responses)} ответов.")

        except Exception as e:
            self.logger.send("INFO",  f"❌ Критическая ошибка при парсинге {url}: {e}")

        finally:
            # Закрытие ресурсов
            for obj, name in [(page, "page"), (context, "context"), (browser, "browser"), (playwright, "playwright")]:
                if obj:
                    try:
                        await obj.close() if hasattr(obj, "close") else await obj.stop()
                    except Exception as e:
                        self.logger.send("INFO",  f"⚠️ Ошибка при закрытии {name}: {e}")
            self.logger.send("INFO",  "✅ Все ресурсы Playwright закрыты корректно")

        # --- Отправка данных ---
        processed_count = 0
        image_queue = []

        for video_data in all_videos_data:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    # self.logger.send("INFO",  f"🔍 Проверка видео: {video_data['link']}")
                    check_resp = await client.get(f"https://cosmeya.dev-klick.cyou/api/v1/videos/?link={video_data['link']}")
                    is_new = False
                    video_id = None

                    if check_resp.status_code == 200:
                        res = check_resp.json()
                        vids = res.get("videos", [])
                        if vids:
                            video_id = vids[0]['id']
                            await client.patch(
                                f"https://cosmeya.dev-klick.cyou/api/v1/videos/{video_id}",
                                json={
                                    "amount_views": video_data["amount_views"],
                                    "amount_likes": video_data["amount_likes"],
                                    "amount_comments": video_data["amount_comments"],
                                    "date_published": video_data["date_published"],
                                    "articles": video_data["articles"],
                                }
                            )
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        resp = await client.post("https://cosmeya.dev-klick.cyou/api/v1/videos/", json=video_data)
                        resp.raise_for_status()
                        video_id = resp.json()["id"]
                        # self.logger.send("INFO",  f"✅ Создано новое видео {video_id}")
                        if video_data.get("image"):
                            image_queue.append((video_id, video_data["image"]))
                processed_count += 1
            except Exception as e:
                self.logger.send("INFO",  f"⚠️ Ошибка при обработке {video_data.get('link')}: {e}")

        self.logger.send("INFO",  f"📦 Всего обработано {processed_count} видео, ожидают загрузки {len(image_queue)} обложек.")

        # --- Загрузка изображений ---
        idx = 0
        while idx < len(image_queue):
            proxy = proxy_list[current_proxy_index] if proxy_list else None
            current_proxy_index = (current_proxy_index + 1) % len(proxy_list) if proxy_list else 0
            batch = image_queue[idx:idx + 15]
            self.logger.send("INFO",  f"🖼️ Загружаем {len(batch)} изображений через {proxy or 'без прокси'}")

            for vid, img_url in batch:
                try:
                    status, _ = await self.upload_image(vid, img_url, proxy=proxy)
                    self.logger.send("INFO",  f"{'✅' if status == 200 else '⚠️'} Фото для видео {vid} → статус {status}")
                except Exception as e:
                    self.logger.send("INFO",  f"❌ Ошибка загрузки фото {vid}: {e}")
                await asyncio.sleep(3.0)
            idx += 15

        self.logger.send("INFO",  f"🎉 Парсинг завершён: {processed_count} видео обработано.")


# # ----------------------- Пример запуска -----------------------

# async def main():
#     proxy_list = [
#         "g3dmsMyYST:B9BegRNRzi@45.150.35.224:28898",
#         "Weh1oXn82b:dUYiJZ5w7T@45.150.35.129:31801",
#         "gnmPrWSMJ4:tbHyXTwWdx@45.150.35.114:54943",
#         "15ObFJmCP5:a0rog6kGgT@45.150.35.113:24242",
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
#     await parser.parse_channel(url, channel_id=3, user_id=user_id, proxy_list=proxy_list)

# if __name__ == "__main__":
#     asyncio.run(main())
