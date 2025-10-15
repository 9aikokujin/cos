import asyncio
from datetime import datetime, timezone
import re
from urllib.parse import urlparse
import httpx
import random
from typing import Union, Optional
from playwright.async_api import async_playwright
# from urllib.parse import urlparse


class TikTokParser:
    def __init__(self):
        pass

    async def scroll_until(self, page, url: str, selector: str, delay: float = 3.0, max_idle_rounds: int = 5):
        prev_count = 0
        idle_rounds = 0
        max_scroll_attempts = 3
        final_count = 0

        for attempt in range(max_scroll_attempts):
            print(f"Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

            while True:
                # Плавная прокрутка вниз
                await page.evaluate("""
                    () => {
                        const distance = 1000;
                        const scrollStep = () => {
                            if (window.scrollY + window.innerHeight < document.body.scrollHeight) {
                                window.scrollBy(0, distance);
                                setTimeout(scrollStep, 100);
                            }
                        };
                        scrollStep();
                    }
                """)

                await page.wait_for_timeout(int(delay * 1000))

                # Проверка кнопки обновления (на случай ошибки сети)
                refresh_button = await page.query_selector('button[data-e2e="feed-refresh-btn"]') or await page.query_selector('button:has-text("Refresh")') or await page.query_selector('button.emuynwa3.css-z9i4la-Button-StyledButton.ehk74z00')
                if refresh_button:
                    print("Обнаружена кнопка 'Refresh'. Кликаем для перезагрузки страницы.")
                    await refresh_button.click()
                    await page.wait_for_timeout(3000)

                # Подсчёт текущего количества элементов
                try:
                    current_count = await page.eval_on_selector_all(selector, "els => els.length")
                except Exception as e:
                    print(f"⚠️ Ошибка при подсчёте элементов по селектору '{selector}': {e}")
                    current_count = prev_count

                print(f"Текущее количество элементов: {current_count}")

                if current_count == prev_count:
                    idle_rounds += 1
                    if idle_rounds >= max_idle_rounds:
                        print(f"Достигнут конец списка видео профиля {url}")
                        print(f"Спарсил все видео в количестве {current_count}")
                        final_count = current_count
                        break
                else:
                    idle_rounds = 0
                    prev_count = current_count

                # Дополнительная проверка: достигли ли конца страницы
                is_at_bottom = await page.evaluate("""
                    () => (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 100;
                """)
                if is_at_bottom and idle_rounds >= max_idle_rounds:
                    print(f"Достигнут конец страницы для {url}")
                    final_count = current_count
                    break

        # Если по какой-то причине final_count не установлен — получаем актуальное значение
        if final_count == 0:
            try:
                final_count = await page.eval_on_selector_all(selector, "els => els.length")
            except:
                final_count = 0

        # Сохраняем HTML, если есть элементы
        if final_count > 0:
            print("ℹ️ Количество видео не изменилось после всех попыток прокрутки. Сохраняем HTML страницы.")
            try:
                html_content = await page.content()
                from urllib.parse import urlparse
                parsed = urlparse(url)
                safe_name = parsed.path.strip("/").replace("@", "_").replace("/", "_")
                filename = f"tiktok_profile_{safe_name}_{int(asyncio.get_event_loop().time())}.html"
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(html_content)
                print(f"✅ HTML сохранён в файл: {filename}")
            except Exception as e:
                print(f"❌ Ошибка при сохранении HTML: {e}")

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
            print(f"PROXYYYYYYYYY {proxy_config}")
            page = await context.new_page()
            from playwright_stealth import stealth_sync
            stealth_sync(page)

            print(f"🌐 Открываем профиль: {url} (username: {username})")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            try:
                await page.wait_for_selector("div[id^='column-item-video-container-']", timeout=15000)
            except Exception as e:
                print(f"⚠️ Не удалось дождаться первого видео-элемента: {e}")

            await asyncio.sleep(3)

            # 🚀 Шаг 2. Перехватываем API после прогрузки контента
            tiktok_responses = []

            async def handle_response(response):
                if "/api/post/item_list/" in response.url:
                    try:
                        data = await response.json()
                        if data.get("itemList"):
                            print(f"📥 +{len(data['itemList'])} видео (всего: {sum(len(r['itemList']) for r in tiktok_responses)})")
                            tiktok_responses.append(data)
                    except Exception as e:
                        print(f"⚠️ Ошибка парсинга ответа: {e}")

            page.on("response", handle_response)

            # 🚀 Шаг 2. Скроллим — и во время скролла будут ловиться все API-запросы
            print("⏳ Скроллим страницу до самого низа...")
            total_videos_count = await self.scroll_until(
                page,
                url,
                selector="div[id^='column-item-video-container-']",
                delay=3.0,
                max_idle_rounds=5
            )
            await asyncio.sleep(5)

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

            print(f"🎯 Всего собрано {len(all_videos_data)} уникальных видео из {len(tiktok_responses)} ответов.")

        except Exception as e:
            print(f"❌ Критическая ошибка при парсинге {url}: {e}")

        finally:
            # Закрытие ресурсов
            for obj, name in [(page, "page"), (context, "context"), (browser, "browser"), (playwright, "playwright")]:
                if obj:
                    try:
                        await obj.close() if hasattr(obj, "close") else await obj.stop()
                    except Exception as e:
                        print(f"⚠️ Ошибка при закрытии {name}: {e}")
            print("✅ Все ресурсы Playwright закрыты корректно")

        # --- Отправка данных ---
        processed_count = 0
        image_queue = []

        for video_data in all_videos_data:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    print(f"🔍 Проверка видео: {video_data['link']}")
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
                        print(f"✅ Создано новое видео {video_id}")
                        if video_data.get("image_url"):
                            image_queue.append((video_id, video_data["image_url"]))
                processed_count += 1
            except Exception as e:
                print(f"⚠️ Ошибка при обработке {video_data.get('link')}: {e}")

        print(f"📦 Всего обработано {processed_count} видео, ожидают загрузки {len(image_queue)} обложек.")

        # --- Загрузка изображений ---
        idx = 0
        while idx < len(image_queue):
            proxy = proxy_list[current_proxy_index] if proxy_list else None
            current_proxy_index = (current_proxy_index + 1) % len(proxy_list) if proxy_list else 0
            batch = image_queue[idx:idx + 15]
            print(f"🖼️ Загружаем {len(batch)} изображений через {proxy or 'без прокси'}")

            for vid, img_url in batch:
                try:
                    status, _ = await self.upload_image(vid, img_url, proxy=proxy)
                    print(f"{'✅' if status == 200 else '⚠️'} Фото для видео {vid} → статус {status}")
                except Exception as e:
                    print(f"❌ Ошибка загрузки фото {vid}: {e}")
                await asyncio.sleep(3.0)
            idx += 15

        print(f"🎉 Парсинг завершён: {processed_count} видео обработано.")


async def main():
    proxy_list = [
        "iuZKi4BGyp:vHKtDTzA0z@45.150.35.98:24730",
        "QgSnMzKNDg:rQR6PpWyH6@45.150.35.140:37495",
        "nGzc2Uw9o1:IOEIP5yqHF@45.150.35.72:30523",
        "ljpOi6p4wE:AzWMnGcwT9@45.150.35.75:56674",
        "mpiv4PCpJG:oFct8hLGU3@109.120.131.51:52137",
        "BnpDZPR6sd:dIciqNGo7d@45.150.35.97:51776",
        "3fNux7Ul42:pkfkTaLi9D@109.120.131.31:59895",
        "dnyqkeZB92:y38H1PzPef@45.150.35.28:27472",
        "udWhRyA0GU:laqpdeslpC@45.150.35.225:22532",
        "qMGdKOcu0w:MfeGgg0Dh9@45.150.35.205:23070",
        "cpeFm6Dh5x:bQXTp4e1gf@45.150.35.111:22684",
        "K6dlqo2Xbn:KJ7TE9kPO7@45.150.35.51:49586",
        "db2JltFuja:8MItiT5T12@45.150.35.10:58894",
        "79zEDvbAVA:xJBsip0IQK@45.150.35.4:58129",
        "mBQnv9UCPd:e3VkzkB9p5@45.150.35.74:55101",
        "IDWsfoHdf1:z6d3r0tnzM@45.150.35.244:42679",
    ]
    parser = TikTokParser()
    url = "https://www.tiktok.com/@nastya.beomaa?_t=ZN-8zpTn99jMve&_r=1"
    user_id = 1
    await parser.parse_channel(url, channel_id=10, user_id=user_id,
                               proxy_list=proxy_list)

if __name__ == "__main__":
    asyncio.run(main())
