import asyncio
from datetime import datetime, timezone
import random
import re
from typing import Optional, Union
from playwright.async_api import async_playwright
import httpx


class TikTokParser:
    def __init__(self):
        pass

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

        async with async_playwright() as p:
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

            # === Перехват API-ответов ===
            tiktok_responses = []

            async def handle_response(response):
                if "api/post/item_list/" in response.url and response.status == 200:
                    try:
                        data = await response.json()
                        if data.get("itemList") is not None:
                            print(f"📌 Захвачен API-ответ с {len(data['itemList'])} видео")
                            tiktok_responses.append(data)
                    except Exception as e:
                        print(f"❌ Ошибка парсинга ответа: {e}")

            page.on("response", handle_response)

            print(f"🌐 Открываем профиль: {url} (username: {username})")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Проверка: не закрыт ли TikTok в регионе (например, Гонконг)
            page_content = await page.content()
            if "discontinued operating TikTok in Hong Kong" in page_content:
                print("❌ TikTok недоступен в этом регионе (например, Гонконг). Пропускаем профиль.")
                await browser.close()
                return

            # Ждём появления первого видео-элемента
            try:
                await page.wait_for_selector("div[id^='column-item-video-container-']", timeout=15000)
            except Exception as e:
                print(f"⚠️ Не удалось дождаться первого видео-элемента: {e}. Продолжаем без скролла.")
            
            await asyncio.sleep(3)

            # 🚀 Скроллим до конца, чтобы загрузить все видео
            print("⏳ Начинаем прокрутку страницы для загрузки всех видео...")
            total_videos_count = await self.scroll_until(
                page,
                url,
                selector="div[id^='column-item-video-container-']",
                delay=2.5,
                max_idle_rounds=4
            )
            print(f"✅ Прокрутка завершена. Обнаружено {total_videos_count} видео на странице.")

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

                    if create_time:
                        dt_utc = datetime.fromtimestamp(create_time, tz=timezone.utc)
                        date_published = dt_utc.strftime('%Y-%m-%dT00:00:00')
                    else:
                        date_published = None

                    # Исправлено: убраны лишние пробелы в ссылке
                    link = f"https://www.tiktok.com/@{username}/video/{video_id_str}"

                    all_videos_data.append({
                        "type": "tiktok",
                        "channel_id": channel_id,
                        "link": link,
                        "name": f"Video {video_id_str}",
                        "amount_views": int(stats.get("playCount", 0)),
                        "amount_likes": int(stats.get("diggCount", 0)),
                        "amount_comments": int(stats.get("commentCount", 0)),
                        "image_url": cover,
                        "date_published": date_published
                    })

            print(f"✅ Всего собрано {len(all_videos_data)} видео из {len(tiktok_responses)} API-запросов.")

            await browser.close()

        # --- Этап 2: Отправка данных в API ---
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

        # --- Этап 3: Загрузка изображений с ротацией прокси ---
        idx = 0
        while idx < len(image_queue):
            if not proxy_list:
                proxy = None
            else:
                proxy = proxy_list[current_proxy_index]
                current_proxy_index = (current_proxy_index + 1) % len(proxy_list)

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

            if idx < len(image_queue) and current_proxy_index == 0 and proxy_list:
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
    parser = TikTokParser()
    url = "https://www.tiktok.com/@nastya.beomaa?_t=ZN-8zpTn99jMve&_r=1"
    user_id = 1
    await parser.parse_channel(url, channel_id=9, user_id=user_id,
                               proxy_list=proxy_list)

if __name__ == "__main__":
    asyncio.run(main())
