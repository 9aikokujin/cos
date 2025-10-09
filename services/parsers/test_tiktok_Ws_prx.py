import asyncio
import httpx
import random
from typing import Union
from playwright.async_api import async_playwright
# from urllib.parse import urlparse


# fR86VBRE:ykkuKaTD@192.177.18.99:62258

class TikTokParser:
    def __init__(self, proxy_list: list = None):
        self.proxy_list = proxy_list or []
        self.current_proxy_index = 0  # для карусели прокси

    def parse_views(self, views_text):
        """Преобразует текст просмотров в число"""
        if not views_text:
            return 0
        views_text = views_text.replace(",", "").strip()
        if views_text.endswith("K"):
            return int(float(views_text[:-1]) * 1000)
        elif views_text.endswith("M"):
            return int(float(views_text[:-1]) * 1000000)
        return int(views_text)

    def generate_short_title(self, full_title: str, max_length: int = 20) -> str:
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

    async def scroll_until(self, page, url: str, selector: str, delay: float = 3.0, max_idle_rounds: int = 5):
        prev_count = 0
        idle_rounds = 0
        max_scroll_attempts = 3

        for attempt in range(max_scroll_attempts):
            print(f"INFO: Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

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
                    print("INFO: Обнаружена кнопка 'Refresh'. Кликаем для перезагрузки страницы.")
                    await refresh_button.click()
                    await page.wait_for_timeout(3000)

                current_count = await page.eval_on_selector_all(selector, "els => els.length")
                print(f"INFO: Текущее количество элементов: {current_count}")

                if current_count == prev_count:
                    idle_rounds += 1
                    if idle_rounds >= max_idle_rounds:
                        print(f"INFO: Достигнут конец списка видео профиля {url}")
                        print(f"INFO: Спарсил все видео в количестве {current_count}")
                        break
                else:
                    idle_rounds = 0
                    prev_count = current_count

                is_at_bottom = await page.evaluate("""
                    () => (window.innerHeight + window.scrollY) >= document.body.scrollHeight;
                """)
                if is_at_bottom and idle_rounds >= max_idle_rounds:
                    print(f"INFO: Достигнут конец страницы для {url}")
                    break

        return prev_count

    async def parse_channel(self, url: str, channel_id: int, user_id: int, max_retries: int = 3):
        if not self.proxy_list:
            print("Список прокси пуст, используем без прокси")

        # --- утилиты для Playwright ---
        async def get_proxy_config(proxy_str):
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
                print(f"Неверный формат прокси '{proxy_str}': {str(e)}")
                return None

        async def create_browser_with_proxy(proxy_str):
            proxy_config = await get_proxy_config(proxy_str) if proxy_str else None
            p = await async_playwright().start()
            browser = await p.chromium.launch(
                headless=False,
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
            return browser, page

        # --- Этап 1: собираем список видео ---
        current_proxy = random.choice(self.proxy_list) if self.proxy_list else None
        browser, page = await create_browser_with_proxy(current_proxy)
        if not browser:
            raise Exception("Не удалось создать браузер даже для первой прокси")

        all_videos_data = []
        try:
            for attempt in range(1, max_retries + 1):
                try:
                    await page.goto(url, wait_until="networkidle", timeout=60000)
                    print(f"🌐 Открыл профиль {url} через прокси {current_proxy}")

                    await self.scroll_until(page, url, selector='div[data-e2e="user-post-item"]')
                    videos = await page.query_selector_all('div[data-e2e="user-post-item"]')
                    print(f"🎬 Найдено {len(videos)} видео в профиле {url}")

                    for video in videos:
                        try:
                            link_element = await video.query_selector('a[href*="/video/"]')
                            video_url = await link_element.get_attribute('href') if link_element else None

                            view_element = await video.query_selector('strong[data-e2e="video-views"]')
                            views_text = await view_element.inner_text() if view_element else "0"
                            views = self.parse_views(views_text)

                            img_element = await video.query_selector('img')
                            description = await img_element.get_attribute('alt') if img_element else ""
                            img_url = await img_element.get_attribute('src') if img_element else None

                            if not video_url:
                                continue

                            video_title = self.generate_short_title(description, max_length=20)
                            article = self.extract_article_tag(description)

                            all_videos_data.append({
                                "type": "tiktok",
                                "channel_id": channel_id,
                                "link": video_url,
                                "name": video_title,
                                "article": article,
                                "amount_views": views,
                                "image_url": img_url
                            })
                        except Exception as e:
                            print(f"Ошибка парсинга видео: {e}")
                            continue
                    break
                except Exception as e:
                    print(f"Попытка {attempt} не удалась: {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(5)
                    else:
                        raise
        finally:
            await browser.close()

        # --- Этап 2: обработка видео + качаем картинки с каруселью прокси ---
        async def download_image(url: str,
                                 proxy: str = None) -> Union[bytes, None]:
            try:
                # Добавляем схему, если прокси задан и не содержит её
                if proxy and not proxy.startswith(("http://", "https://")):
                    proxy = "http://" + proxy

                async with httpx.AsyncClient(proxy=proxy, timeout=20.0) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    return resp.content
            except Exception as e:
                print(f"❌ Ошибка загрузки {url}: {e}")
                return None

        async def upload_image(video_id: int, image_url: str,
                               proxy: str = None):
            image_bytes = await download_image(image_url, proxy=proxy)
            if not image_bytes:
                return None, "Download failed"

            file_name = image_url.split("/")[-1].split("?")[0]
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {"file": (file_name, image_bytes, "image/jpeg")}
                resp = await client.post(
                    f"http://127.0.0.1:8000/api/v1/videos/{video_id}/upload-image/",
                    files=files,
                )
                resp.raise_for_status()
                return resp.status_code, resp.text

        processed_count = 0
        image_queue = []

        # шаг 1: отправляем метаданные видео в API
        for video_data in all_videos_data:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    check_resp = await client.get(
                        f"http://127.0.0.1:8000/api/v1/videos/?link={video_data['link']}"
                    )
                    video_id = None
                    is_new = False

                    if check_resp.status_code == 200:
                        result = check_resp.json()
                        videos = result.get("videos", [])
                        if videos:
                            video_id = videos[0]['id']
                            update_resp = await client.patch(
                                f"http://127.0.0.1:8000/api/v1/videos/{video_id}",
                                json={"amount_views": video_data["amount_views"]}
                            )
                            update_resp.raise_for_status()
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        create_resp = await client.post(
                            "http://127.0.0.1:8000/api/v1/videos/",
                            json=video_data
                        )
                        create_resp.raise_for_status()
                        video_id = create_resp.json()['id']
                        if video_data.get("image_url"):
                            image_queue.append(
                                (video_id, video_data["image_url"]))
                processed_count += 1
            except Exception as e:
                print(f"Ошибка при обработке {video_data.get('link')}: {e}")
                continue

        # шаг 2: качаем фото пакетами по 15/прокси
        idx = 0
        while idx < len(image_queue):
            if not self.proxy_list:
                proxy = None
            else:
                proxy = self.proxy_list[self.current_proxy_index]
                self.current_proxy_index = (
                    self.current_proxy_index + 1) % len(self.proxy_list)

            batch = image_queue[idx: idx + 15]
            print(f"🌐 Прокси {proxy}: качаем {len(batch)} фото")

            for video_id, image_url in batch:
                try:
                    status, resp_text = await upload_image(video_id, image_url,
                                                           proxy=proxy)
                    if status == 200:
                        print(f"✅ Фото для видео {video_id} загружено")
                    else:
                        print(f"⚠️ Фото для видео {video_id} ошибка {status}")
                except Exception as e:
                    print(f"❌ Ошибка загрузки фото для {video_id}: {e}")
                await asyncio.sleep(4.0)

            idx += 15

            # если прошли все прокси и фото ещё остались → ждём минуту
            if idx < len(image_queue) and self.current_proxy_index == 0 and self.proxy_list:
                print("⏳ Все прокси использованы, ждём 1 минуту...")
                await asyncio.sleep(60)

        print(f"✅ Успешно обработано {processed_count} видео")


async def main():
    proxy_list = [
        "mGACNmVTQp:xcdWpe44dU@77.221.150.170:63969",
        "sAH2j6St9i:qdImpC6Lum@77.221.150.171:31388",
        "cP1EN6Kf8l:A7tZYPTOYF@77.221.150.31:26441",
        "0VREPcE2A4:eHe9c7lQ76@77.221.150.190:60507",
        "RrBtY9EOET:NW311l4sNb@77.221.150.61:35966",
    ]
    parser = TikTokParser(proxy_list=proxy_list)
    url = "https://www.tiktok.com/@nastya.beomaa?_t=ZN-8zpTn99jMve&_r=1"
    user_id = 1
    await parser.parse_channel(url, channel_id=5, user_id=user_id)

if __name__ == "__main__":
    asyncio.run(main())
