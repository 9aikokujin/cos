import re
import asyncio
import httpx
from typing import Union, List, Dict, Optional
from playwright.async_api import async_playwright
import random
import json


class ShortsParser:
    def __init__(self):
        self.current_proxy_index = 0
        self.processed_video_ids = set()

    def parse_number(self, text: str) -> int:
        if not text:
            return 0
        original = text
        text = text.strip().replace("\u00A0", " ").replace("&nbsp;", " ")
        # Арабские
        arabic_patterns = [(r"([\d,.]+)\s*ألف", 1_000), (r"([\d,.]+)\s*مليون", 1_000_000)]
        for pattern, mult in arabic_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    num = float(match.group(1).replace(",", "").replace(" ", ""))
                    return int(num * mult)
                except (ValueError, TypeError):
                    continue
        # Русские
        russian_patterns = [(r"([\d,.]+)\s*(?:тыс|тысяч)", 1_000), (r"([\d,.]+)\s*(?:млн|миллион)", 1_000_000)]
        for pattern, mult in russian_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    num_str = match.group(1).replace(",", ".").replace(" ", "")
                    num = float(num_str)
                    return int(num * mult)
                except (ValueError, TypeError):
                    continue
        # Английские
        clean = re.sub(r"[^\d.KMkm,]", "", text.upper().replace(",", ""))
        if clean.endswith("K"):
            try:
                return int(float(clean[:-1]) * 1_000)
            except (ValueError, TypeError):
                pass
        elif clean.endswith("M"):
            try:
                return int(float(clean[:-1]) * 1_000_000)
            except (ValueError, TypeError):
                pass
        digits_only = re.sub(r"[^\d.]", "", text.replace(" ", ""))
        if digits_only:
            try:
                return int(float(digits_only))
            except (ValueError, TypeError):
                pass
        return 0

    def extract_article_tag(self, caption: str) -> Optional[str]:
        if not caption:
            return None
        caption_lower = caption.lower()
        for tag in ["#sv", "#jw", "#qz", "#sr", "#fg"]:
            if tag in caption_lower:
                start = caption_lower.find(tag)
                if start != -1:
                    return caption[start:start + len(tag)]
        return None

    async def get_proxy_config(self, proxy_str: str):
        try:
            if "@" in proxy_str:
                auth, host_port = proxy_str.split("@")
                username, password = auth.split(":")
                host, port = host_port.split(":")
                return {"server": f"http://{host}:{port}", "username": username, "password": password}
            else:
                host, port = proxy_str.split(":")
                return {"server": f"http://{host}:{port}"}
        except Exception as e:
            print(f"Неверный формат прокси '{proxy_str}': {str(e)}")
            return None

    async def create_context_with_proxy(self, proxy_str: Optional[str]):
        proxy_config = await self.get_proxy_config(proxy_str) if proxy_str else None
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-features=IsolateOrigins,site-per-process",
                "--lang=en-US,en",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            proxy=proxy_config
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)
        return browser, context

    async def download_image(self, url: str) -> Optional[bytes]:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content
        except Exception as e:
            print(f"❌ Ошибка загрузки изображения {url}: {e}")
            return None

    async def upload_image(self, video_id: int, image_url: str):
        image_bytes = await self.download_image(image_url)
        if not image_bytes:
            return
        file_name = image_url.split("/")[-1].split("?")[0] or "thumb.jpg"
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": (file_name, image_bytes, "image/jpeg")}
            try:
                resp = await client.post(
                    f"https://cosmeya.dev-klick.cyou/api/v1/videos/{video_id}/upload-image/",
                    files=files,
                )
                resp.raise_for_status()
                print(f"✅ Фото для видео {video_id} загружено")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки фото для видео {video_id}: {e}")

    async def send_to_api(self, data: dict, channel_id: int):
        link = data["link"]
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                check_resp = await client.get(f"https://cosmeya.dev-klick.cyou/api/v1/videos/?link={link}")
                video_id = None
                exists = False
                if check_resp.status_code == 200:
                    result = check_resp.json()
                    if result.get("videos"):
                        video_id = result["videos"][0]["id"]
                        exists = True

                payload = {
                    "type": "youtube",
                    "channel_id": channel_id,
                    "link": link,
                    "article": data["article"],
                    "amount_views": data["views"],
                    "likes": data["likes"],
                    "comments": data["comments"],
                    "name": data["title"]
                }

                if exists:
                    await client.patch(f"https://cosmeya.dev-klick.cyou/api/v1/videos/{video_id}/", json=payload)
                    print(f"Обновлено видео {video_id}")
                else:
                    resp = await client.post("https://cosmeya.dev-klick.cyou/api/v1/videos/", json=payload)
                    video_id = resp.json().get("id")
                    print(f"Создано новое видео: {video_id}")

                if video_id and data.get("image_url"):
                    await self.upload_image(video_id, data["image_url"])

            except Exception as e:
                print(f"Ошибка отправки в API для {link}: {e}")

    async def parse_channel(self, url: str, channel_id: int, user_id: int, max_retries: int = 3, proxy_list: list = None):
        clean_base_url = url.strip().rstrip('/')
        if not clean_base_url.endswith('/shorts'):
            clean_base_url += '/shorts'
        print(f"Начало парсинга канала: {clean_base_url}")

        proxy = random.choice(proxy_list) if proxy_list else None
        browser, context = await self.create_context_with_proxy(proxy)
        page = await context.new_page()

        try:
            print(f"Открываем: {clean_base_url}")
            await page.goto(clean_base_url, wait_until="networkidle", timeout=60000)

            # Принимаем куки
            accept_btn = await page.query_selector('button[jsname="b3VHJd"]')
            if accept_btn:
                try:
                    await accept_btn.click()
                    print("✅ Куки приняты")
                    await page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"⚠️ Ошибка клика по кукам: {e}")

            # Словарь для хранения данных по videoId
            video_data = {}

            # Перехватываем ответы от YouTube API
            def handle_response(response):
                if "/youtubei/v1/player" in response.url:
                    asyncio.create_task(self.handle_player_response(response, video_data))
                elif "/youtubei/v1/next" in response.url:
                    asyncio.create_task(self.handle_next_response(response, video_data))

            page.on("response", handle_response)

            # Прокручиваем ленту шортсов
            processed = 0
            for _ in range(50):  # максимум 50 шортсов
                await page.keyboard.press("ArrowDown")
                await page.wait_for_timeout(2500)

                # Проверяем URL на наличие videoId
                current_url = page.url
                video_id_match = re.search(r"/shorts/([a-zA-Z0-9_-]+)", current_url)
                if video_id_match:
                    vid = video_id_match.group(1)
                    if vid not in self.processed_video_ids:
                        self.processed_video_ids.add(vid)
                        # Ждём, пока данные подгрузятся
                        await asyncio.sleep(1)

                        # Проверяем, есть ли данные
                        if vid in video_data:
                            data = video_data[vid]
                            await self.send_to_api(data, channel_id)
                            processed += 1
                            print(f"✅ Обработано видео #{processed}: {data['link']}")
                        else:
                            print(f"⚠️ Нет данных для видео {vid} (возможно, заблокировано)")

            print("✅ Парсинг завершён")

        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
        finally:
            await browser.close()

    async def handle_player_response(self, response, video_data: dict):
        try:
            json_data = await response.json()
            video_id = json_data.get("videoDetails", {}).get("videoId")
            if not video_id:
                return

            title = json_data.get("videoDetails", {}).get("title", "")
            view_count = int(json_data.get("videoDetails", {}).get("viewCount", 0))
            like_count = int(json_data.get("videoDetails", {}).get("likeCount", 0))
            thumbnails = json_data.get("videoDetails", {}).get("thumbnail", {}).get("thumbnails", [])
            image_url = None
            if thumbnails:
                image_url = max(thumbnails, key=lambda x: x.get("width", 0)).get("url", "").split("?")[0]

            article = self.extract_article_tag(title)

            video_data[video_id] = {
                "link": f"https://www.youtube.com/shorts/{video_id}",
                "title": title,
                "views": view_count,
                "likes": like_count,
                "comments": 0,  # будет обновлено из /next
                "article": article,
                "image_url": image_url
            }
        except Exception as e:
            print(f"Ошибка обработки player response: {e}")

    async def handle_next_response(self, response, video_data: dict):
        try:
            json_data = await response.json()
            video_id = None

            # Извлекаем videoId из контекста
            contents = json_data.get("contents", {}).get("singleColumnWatchNextResults", {}).get("contents", {})
            for key, val in contents.items():
                if isinstance(val, dict):
                    video_id = val.get("videoId")
                    if video_id:
                        break

            if not video_id or video_id not in video_data:
                return

            # Ищем количество комментариев
            def find_comment_count(obj):
                if isinstance(obj, dict):
                    if "commentCount" in obj:
                        count_text = obj["commentCount"].get("simpleText", "0")
                        return self.parse_number(count_text)
                    for v in obj.values():
                        res = find_comment_count(v)
                        if res is not None:
                            return res
                elif isinstance(obj, list):
                    for item in obj:
                        res = find_comment_count(item)
                        if res is not None:
                            return res
                return None

            comment_count = find_comment_count(json_data)
            if comment_count is not None:
                video_data[video_id]["comments"] = comment_count

        except Exception as e:
            print(f"Ошибка обработки next response: {e}")


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
    parser = ShortsParser()
    url = "https://www.youtube.com/@kotokrabs"
    await parser.parse_channel(url, channel_id=1, user_id=1, proxy_list=proxy_list)


if __name__ == "__main__":
    asyncio.run(main())