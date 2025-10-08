import asyncio
import random
import re
from typing import List, Dict, Optional, Union
from playwright.async_api import async_playwright
import httpx


class TikTokParser:
    def __init__(self, proxy_list: list = None):
        self.proxy_list = proxy_list or []
        self.current_proxy_index = 0

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
            print(f"Неверный формат прокси '{proxy_str}': {e}")
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
            print(f"❌ Ошибка загрузки изображения {url}: {e}")
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
                print(f"⚠️ Ошибка загрузки фото для видео {video_id}: {e}")
                return None, str(e)

    async def parse_channel(self, url: str, channel_id: int, user_id: int, max_retries: int = 3):
        # Извлекаем username из URL и убираем лишние пробелы
        url = url.strip()
        match = re.search(r"@([a-zA-Z0-9_.-]+)", url)
        if not match:
            raise ValueError(f"Не удалось извлечь username из URL: {url}")
        username = match.group(1)

        proxy = random.choice(self.proxy_list) if self.proxy_list else None
        proxy_config = await self.get_proxy_config(proxy) if proxy else None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
                viewport={"width": 390, "height": 844},
                proxy=proxy_config
            )
            page = await context.new_page()

            # === Эвазия от детекта автоматизации ===
            try:
                from playwright_stealth import stealth_async
                await stealth_async(page)
            except ImportError:
                print("⚠️ playwright_stealth не установлен. Рекомендуется установить: pip install playwright-stealth")

            # === Сбор всех ответов от TikTok API ===
            tiktok_responses = []

            async def handle_response(response):
                if "api/post/item_list/" in response.url and response.status == 200:
                    try:
                        data = await response.json()
                        if data.get("itemList") is not None:
                            tiktok_responses.append(data)
                    except Exception as e:
                        print(f"❌ Ошибка парсинга ответа: {e}")

            page.on("response", handle_response)

            print(f"🌐 Открываем профиль: {url} (username: {username})")
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Даём немного времени на завершение фоновых запросов
            await asyncio.sleep(5)

            # === Извлекаем данные из собранных ответов ===
            all_videos_data = []
            has_more = False
            cursor = "0"

            if tiktok_responses:
                # Берём последний (самый свежий) ответ
                data = tiktok_responses[-1]
                item_list = data.get("itemList", [])
                has_more = data.get("hasMore", False)
                cursor = data.get("cursor", "0")

                print(f"📥 Получено {len(item_list)} видео (cursor={cursor}, hasMore={has_more})")

                for item in item_list:
                    video_id_str = str(item.get("id"))
                    stats = item.get("stats", {})
                    # Обратите внимание: в вашем JSON cover находится в video.cover
                    video_info = item.get("video", {})
                    cover = video_info.get("cover") or video_info.get("dynamicCover") or video_info.get("originCover")

                    link = f"https://www.tiktok.com/@{username}/video/{video_id_str}"

                    all_videos_data.append({
                        "type": "tiktok",
                        "channel_id": channel_id,
                        "link": link,
                        "name": f"Video {video_id_str}",
                        "amount_views": int(stats.get("playCount", 0)),
                        "amount_likes": int(stats.get("diggCount", 0)),
                        "amount_comments": int(stats.get("commentCount", 0)),
                        "image_url": cover
                    })
            else:
                print("⚠️ Не найдено ни одного ответа от api/post/item_list/")

            await browser.close()

        # --- Этап 2 и 3 остаются без изменений ---
        processed_count = 0
        image_queue = []

        for video_data in all_videos_data:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    print(f"Проверка видео: {video_data['link']}")
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
                            print(f"Видео уже существует (ID: {video_id}), обновляем статистику")
                            update_resp = await client.patch(
                                f"http://127.0.0.1:8000/api/v1/videos/{video_id}",
                                json={
                                    "amount_views": video_data["amount_views"],
                                    "amount_likes": video_data["amount_likes"],
                                    "amount_comments": video_data["amount_comments"]
                                }
                            )
                            update_resp.raise_for_status()
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        print(f"Создаём новое видео: {video_data['name']}")
                        create_resp = await client.post(
                            "http://127.0.0.1:8000/api/v1/videos/",
                            json=video_data
                        )
                        create_resp.raise_for_status()
                        video_id = create_resp.json()['id']
                        print(f"✅ Создано видео с ID: {video_id}")
                        if video_data.get("image_url"):
                            image_queue.append((video_id, video_data["image_url"]))
                            print(f"🖼️ Добавлено изображение в очередь: {video_data['image_url']}")
                processed_count += 1
            except Exception as e:
                print(f"❌ Ошибка при обработке {video_data.get('link')}: {e}")
                continue

        # --- Этап 3: загрузка изображений с ротацией прокси ---
        idx = 0
        while idx < len(image_queue):
            if not self.proxy_list:
                proxy = None
            else:
                proxy = self.proxy_list[self.current_proxy_index]
                self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)

            batch = image_queue[idx: idx + 15]
            print(f"🌐 Прокси {proxy}: загружаем {len(batch)} изображений")

            for video_id, image_url in batch:
                try:
                    status, resp_text = await self.upload_image(video_id, image_url, proxy=proxy)
                    if status == 200:
                        print(f"✅ Фото для видео {video_id} загружено")
                    else:
                        print(f"⚠️ Ошибка загрузки фото для видео {video_id}: статус {status}")
                except Exception as e:
                    print(f"❌ Исключение при загрузке фото для {video_id}: {e}")
                await asyncio.sleep(4.0)

            idx += 15

            if idx < len(image_queue) and self.current_proxy_index == 0 and self.proxy_list:
                print("⏳ Все прокси исчерпаны. Ждём 60 секунд...")
                await asyncio.sleep(60)

        print(f"✅ Успешно обработано {processed_count} видео")

async def main():
    proxy_list = [
        "DOsSb4De74:gcoOPWqUAE@109.120.131.147:26209",
        "bd4v82PuNJ:fIbH8cOYn9@109.120.131.178:56127",
        "EWQAQZdvRX:RfBJ5g7XCu@45.150.35.251:42181",
        "DXF9lzZUmM:tHzHG71cSJ@109.120.131.180:49057",
    ]
    parser = TikTokParser(proxy_list=proxy_list)
    url = "https://www.tiktok.com/@shura_urassai"
    user_id = 1
    await parser.parse_channel(url, channel_id=1, user_id=user_id)

if __name__ == "__main__":
    asyncio.run(main())
