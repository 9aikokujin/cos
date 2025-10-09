import asyncio
from datetime import datetime, timezone
import re
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

        for attempt in range(max_scroll_attempts):
            self.logger.send("INFO", f"INFO: Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

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
                    self.logger.send("INFO", "INFO: Обнаружена кнопка 'Refresh'. Кликаем для перезагрузки страницы.")
                    await refresh_button.click()
                    await page.wait_for_timeout(3000)

                current_count = await page.eval_on_selector_all(selector, "els => els.length")
                self.logger.send("INFO", f"INFO: Текущее количество элементов: {current_count}")

                if current_count == prev_count:
                    idle_rounds += 1
                    if idle_rounds >= max_idle_rounds:
                        self.logger.send("INFO", f"INFO: Достигнут конец списка видео профиля {url}")
                        self.logger.send("INFO", f"INFO: Спарсил все видео в количестве {current_count}")
                        break
                else:
                    idle_rounds = 0
                    prev_count = current_count

                is_at_bottom = await page.evaluate("""
                    () => (window.innerHeight + window.scrollY) >= document.body.scrollHeight;
                """)
                if is_at_bottom and idle_rounds >= max_idle_rounds:
                    self.logger.send("INFO", f"INFO: Достигнут конец страницы для {url}")
                    break

        return prev_count

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
                    f"https://sn.dev-klick.cyou/api/v1/videos/{video_id}/upload-image/",
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

        # === Объявляем ресурсы заранее для корректного закрытия ===
        playwright = None
        browser = None
        context = None
        page = None

        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized"
                ],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                proxy=proxy_config
            )
            page = await context.new_page()

            # === Перехват API-ответов ===
            tiktok_responses = []

            async def handle_response(response):
                if "api/post/item_list/" in response.url and response.status == 200:
                    try:
                        data = await response.json()
                        if data.get("itemList") is not None:
                            self.logger.send("INFO", f"📌 Захвачен API-ответ с {len(data['itemList'])} видео")
                            tiktok_responses.append(data)
                    except Exception as e:
                        self.logger.send("ERROR", f"❌ Ошибка парсинга ответа: {e}")

            page.on("response", handle_response)

            self.logger.send("INFO", f"🌐 Открываем профиль: {url} (username: {username})")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Ждём появления первого видео-элемента
            try:
                await page.wait_for_selector("div[id^='column-item-video-container-']", timeout=15000)
            except Exception as e:
                self.logger.send("ERROR", f"⚠️ Не удалось дождаться первого видео-элемента: {e}. Продолжаем без скролла.")

            await asyncio.sleep(3)

            # 🚀 Скроллим до конца, чтобы загрузить все видео
            self.logger.send("INFO", "⏳ Начинаем прокрутку страницы для загрузки всех видео...")
            total_videos_count = await self.scroll_until(
                page,
                url,
                selector="div[id^='column-item-video-container-']",
                delay=2.5,
                max_idle_rounds=4
            )
            self.logger.send("INFO", f"✅ Прокрутка завершена. Обнаружено {total_videos_count} видео на странице.")

            # Даём время на завершение последних API-запросов
            await asyncio.sleep(3)

            # === Сбор всех видео из всех API-ответов ===
            all_videos_data = []

            for response_data in tiktok_responses:
                item_list = response_data.get("itemList", [])
                for item in item_list:
                    video_id_str = str(item.get("id"))
                    stats = item.get("stats", {})
                    video_info = item.get("video", {})
                    cover = video_info.get("cover") or video_info.get("dynamicCover") or video_info.get("originCover")
                    create_time = item.get("createTime")
                    description = video_info.get("desc")
                    video_title = self.generate_short_title(description, max_length=30)

                    if create_time:
                        dt_utc = datetime.fromtimestamp(create_time, tz=timezone.utc)
                        date_published = dt_utc.strftime('%Y-%m-%dT00:00:00')
                    else:
                        date_published = None

                    link = f"https://www.tiktok.com/@{username}/video/{video_id_str}"

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

            self.logger.send("INFO", f"✅ Всего собрано {len(all_videos_data)} видео из {len(tiktok_responses)} API-запросов.")

        except Exception as main_error:
            self.logger.send("ERROR", f"Критическая ошибка при парсинге профиля {url}: {main_error}")
            raise

        finally:
            # === Корректное закрытие ресурсов ===
            close_errors = []
            if page:
                try:
                    await page.close()
                except Exception as e:
                    close_errors.append(f"page.close(): {e}")
            if context:
                try:
                    await context.close()
                except Exception as e:
                    close_errors.append(f"context.close(): {e}")
            if browser:
                try:
                    await browser.close()
                except Exception as e:
                    close_errors.append(f"browser.close(): {e}")
            if playwright:
                try:
                    await playwright.stop()
                except Exception as e:
                    close_errors.append(f"playwright.stop(): {e}")

            if close_errors:
                self.logger.send("WARNING", f"Ошибки при закрытии ресурсов Playwright: {close_errors}")
            else:
                self.logger.send("INFO", "✅ Все ресурсы Playwright корректно закрыты")

        # --- Этап 2: Отправка данных в API ---
        processed_count = 0
        image_queue = []

        for video_data in all_videos_data:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    self.logger.send("INFO", f"Проверка видео: {video_data['link']}")
                    check_resp = await client.get(
                        f"https://sn.dev-klick.cyou/api/v1/videos/?link={video_data['link']}"
                    )
                    video_id = None
                    is_new = False

                    if check_resp.status_code == 200:
                        result = check_resp.json()
                        videos = result.get("videos", [])
                        if videos:
                            video_id = videos[0]['id']
                            self.logger.send("INFO", f"Видео уже существует (ID: {video_id}), обновляем статистику")
                            update_resp = await client.patch(
                                f"https://sn.dev-klick.cyou/api/v1/videos/{video_id}",
                                json={
                                    "amount_views": video_data["amount_views"],
                                    "amount_likes": video_data["amount_likes"],
                                    "amount_comments": video_data["amount_comments"],
                                    "date_published": video_data["date_published"]
                                }
                            )
                            update_resp.raise_for_status()
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        self.logger.send("INFO", f"Создаём новое видео: {video_data['name']}")
                        create_resp = await client.post(
                            "https://sn.dev-klick.cyou/api/v1/videos/",
                            json=video_data
                        )
                        create_resp.raise_for_status()
                        video_id = create_resp.json()['id']
                        self.logger.send("INFO", f"✅ Создано видео с ID: {video_id}")
                        if video_data.get("image_url"):
                            image_queue.append((video_id, video_data["image_url"]))
                            self.logger.send("INFO", f"🖼️ Добавлено изображение в очередь: {video_data['image_url']}")
                processed_count += 1
            except Exception as e:
                self.logger.send("ERROR", f"❌ Ошибка при обработке {video_data.get('link')}: {e}")
                continue

        # --- Этап 3: Загрузка изображений с ротацией прокси ---
        idx = 0
        while idx < len(image_queue):
            if not proxy_list:
                proxy = None
            else:
                proxy = proxy_list[current_proxy_index]
                current_proxy_index = (current_proxy_index + 1) % len(proxy_list)

            batch = image_queue[idx: idx + 15]
            self.logger.send("INFO", f"🌐 Прокси {proxy}: загружаем {len(batch)} изображений")

            for video_id, image_url in batch:
                try:
                    status, resp_text = await self.upload_image(video_id, image_url, proxy=proxy)
                    if status == 200:
                        self.logger.send("INFO", f"✅ Фото для видео {video_id} загружено")
                    else:
                        self.logger.send("ERROR", f"⚠️ Ошибка загрузки фото для видео {video_id}: статус {status}")
                except Exception as e:
                    self.logger.send("ERROR", f"❌ Исключение при загрузке фото для {video_id}: {e}")
                await asyncio.sleep(4.0)

            idx += 15

            if idx < len(image_queue) and current_proxy_index == 0 and proxy_list:
                self.logger.send("WARNING", "⏳ Все прокси исчерпаны. Ждём 60 секунд...")
                await asyncio.sleep(60)

        self.logger.send("INFO", f"✅ Успешно обработано {processed_count} видео")
