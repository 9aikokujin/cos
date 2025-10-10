import asyncio
from datetime import datetime, timezone
import re
from urllib.parse import urlparse
import httpx
import random
from typing import Union, Optional
from playwright.async_api import async_playwright
# from urllib.parse import urlparse
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
            self.logger.send("INFO", f"Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

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
                    self.logger.send("INFO", "Обнаружена кнопка 'Refresh'. Кликаем для перезагрузки страницы.")
                    await refresh_button.click()
                    await page.wait_for_timeout(3000)

                current_count = await page.eval_on_selector_all(selector, "els => els.length")
                self.logger.send("INFO", f"Текущее количество элементов: {current_count}")

                if current_count == prev_count:
                    idle_rounds += 1
                    if idle_rounds >= max_idle_rounds:
                        self.logger.send("INFO", f"Достигнут конец списка видео профиля {url}")
                        self.logger.send("INFO", f"Спарсил все видео в количестве {current_count}")
                        final_count = current_count
                        break
                else:
                    idle_rounds = 0
                    prev_count = current_count

                is_at_bottom = await page.evaluate("""
                    () => (window.innerHeight + window.scrollY) >= document.body.scrollHeight;
                """)
                if is_at_bottom and idle_rounds >= max_idle_rounds:
                    self.logger.send("INFO", f"Достигнут конец страницы для {url}")
                    final_count = current_count
                    break

        # 🔍 Проверка: если после всех попыток количество видео не выросло — сохраняем HTML
        if final_count == 0:
            # На всякий случай получим текущее количество
            final_count = await page.eval_on_selector_all(selector, "els => els.length")

        if final_count == prev_count and final_count > 0:
            self.logger.send("WARNING", "ℹ️ Количество видео не изменилось после всех попыток прокрутки. Сохраняем HTML страницы.")
            try:
                html_content = await page.content()
                # Генерируем имя файла: безопасное из URL
                parsed = urlparse(url)
                safe_name = parsed.path.strip("/").replace("@", "_").replace("/", "_")
                filename = f"tiktok_profile_{safe_name}_{int(asyncio.get_event_loop().time())}.html"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(html_content)
                self.logger.send("INFO", f"✅ HTML сохранён в файл: {filename}")
            except Exception as e:
                self.logger.send("ERROR", f"❌ Ошибка при сохранении HTML: {e}")

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
            self.logger.send("ERROR", f"Неверный формат прокси '{proxy_str}': {e}")
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
            self.logger.send("ERROR", f"❌ Ошибка загрузки изображения {url}: {e}")
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
                    f"http://127.0.0.1:8000/api/v1/videos/{video_id}/upload-image/",
                    files=files,
                )
                resp.raise_for_status()
                return resp.status_code, resp.text
            except Exception as e:
                self.logger.send("ERROR", f"⚠️ Ошибка загрузки фото для видео {video_id}: {e}")
                return None, str(e)

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

    async def parse_channel(self, url: str, channel_id: int, user_id: int, max_retries: int = 3, proxy_list: list = None):
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
            # print(f"PROXYYYYYYYYY {proxy_config}")
            page = await context.new_page()
            from playwright_stealth import stealth_sync
            stealth_sync(page)

            self.logger.send("INFO", f"🌐 Открываем профиль: {url} (username: {username})")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            try:
                await page.wait_for_selector("div[id^='column-item-video-container-']", timeout=15000)
            except Exception as e:
                self.logger.send("ERROR", f"⚠️ Не удалось дождаться первого видео-элемента: {e}")

            await asyncio.sleep(3)

            # 🚀 Шаг 1. Скроллим до конца
            self.logger.send("INFO", "⏳ Скроллим страницу до самого низа...")
            total_videos_count = await self.scroll_until(
                page,
                url,
                selector="div[id^='column-item-video-container-']",
                delay=2.5,
                max_idle_rounds=5
            )
            self.logger.send("INFO", f"✅ Скролл завершён. DOM содержит {total_videos_count} видео. Подгружаем API-ответы...")

            # 🚀 Шаг 2. Перехватываем API после прогрузки контента
            tiktok_responses = []

            async def handle_response(response):
                if "/api/post/item_list/" in response.url:
                    try:
                        data = await response.json()
                        if data.get("itemList"):
                            tiktok_responses.append(data)
                            self.logger.send("INFO", f"📥 +{len(data['itemList'])} видео (всего: {sum(len(r['itemList']) for r in tiktok_responses)})")
                    except:
                        pass

            page.on("response", handle_response)

            # Теперь скроллим МЕДЛЕННО и ЖДЁМ загрузки
            await self.scroll_until(page, url, selector="...", delay=4.0, max_idle_rounds=3)

            # 🚀 Шаг 3. Мягко обновляем страницу, чтобы TikTok вызвал item_list запросы заново
            # self.logger.send("INFO", "🔄 Обновляем страницу для сбора всех item_list...")
            # await page.reload(wait_until="networkidle", timeout=60000)
            await asyncio.sleep(10)  # подождать пока все lazy-загрузки отработают

            self.logger.send("INFO", f"✅ Собрано {len(tiktok_responses)} item_list ответов.")

            # 🚀 Шаг 4. Собираем видео из всех ответов
            all_videos_data = []
            seen_ids = set()

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
                    video_title = self.generate_short_title(desc, 30)
                    link = f"https://www.tiktok.com/@{username}/video/{vid}"

                    ts = item.get("createTime")
                    date_published = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT00:00:00") if ts else None

                    all_videos_data.append({
                        "type": "tiktok",
                        "channel_id": channel_id,
                        "link": link,
                        "name": video_title,
                        "amount_views": int(stats.get("playCount", 0)),
                        "amount_likes": int(stats.get("diggCount", 0)),
                        "amount_comments": int(stats.get("commentCount", 0)),
                        "image_url": cover,
                        "date_published": date_published
                    })

            self.logger.send("INFO", f"🎯 Всего собрано {len(all_videos_data)} уникальных видео из {len(tiktok_responses)} ответов.")

        except Exception as e:
            self.logger.send("ERROR", f"❌ Критическая ошибка при парсинге {url}: {e}")

        finally:
            # Закрытие ресурсов
            for obj, name in [(page, "page"), (context, "context"), (browser, "browser"), (playwright, "playwright")]:
                if obj:
                    try:
                        await obj.close() if hasattr(obj, "close") else await obj.stop()
                    except Exception as e:
                        self.logger.send("ERROR", f"⚠️ Ошибка при закрытии {name}: {e}")
            self.logger.send("INFO", "✅ Все ресурсы Playwright закрыты корректно")

        # --- Отправка данных ---
        processed_count = 0
        image_queue = []

        for video_data in all_videos_data:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    self.logger.send("INFO", f"🔍 Проверка видео: {video_data['link']}")
                    check_resp = await client.get(f"http://127.0.0.1:8000/api/v1/videos/?link={video_data['link']}")
                    is_new = False
                    video_id = None

                    if check_resp.status_code == 200:
                        res = check_resp.json()
                        vids = res.get("videos", [])
                        if vids:
                            video_id = vids[0]['id']
                            await client.patch(
                                f"http://127.0.0.1:8000/api/v1/videos/{video_id}",
                                json={
                                    "amount_views": video_data["amount_views"],
                                    "amount_likes": video_data["amount_likes"],
                                    "amount_comments": video_data["amount_comments"],
                                    "date_published": video_data["date_published"]
                                }
                            )
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        resp = await client.post("http://127.0.0.1:8000/api/v1/videos/", json=video_data)
                        resp.raise_for_status()
                        video_id = resp.json()["id"]
                        self.logger.send("INFO", f"✅ Создано новое видео {video_id}")
                        if video_data.get("image_url"):
                            image_queue.append((video_id, video_data["image_url"]))
                processed_count += 1
            except Exception as e:
                self.logger.send("ERROR", f"⚠️ Ошибка при обработке {video_data.get('link')}: {e}")

        self.logger.send("INFO", f"📦 Всего обработано {processed_count} видео, ожидают загрузки {len(image_queue)} обложек.")

        # --- Загрузка изображений ---
        idx = 0
        while idx < len(image_queue):
            proxy = proxy_list[current_proxy_index] if proxy_list else None
            current_proxy_index = (current_proxy_index + 1) % len(proxy_list) if proxy_list else 0
            batch = image_queue[idx:idx + 15]
            self.logger.send("INFO", f"🖼️ Загружаем {len(batch)} изображений через {proxy or 'без прокси'}")

            for vid, img_url in batch:
                try:
                    status, _ = await self.upload_image(vid, img_url, proxy=proxy)
                    self.logger.send("INFO", f"{'✅' if status == 200 else '⚠️'} Фото для видео {vid} → статус {status}")
                except Exception as e:
                    self.logger.send("ERROR", f"❌ Ошибка загрузки фото {vid}: {e}")
                await asyncio.sleep(3.0)
            idx += 15

        self.logger.send("INFO", f"🎉 Парсинг завершён: {processed_count} видео обработано.")
