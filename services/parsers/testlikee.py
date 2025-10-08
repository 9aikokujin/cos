import asyncio
import re
import random
import json
from typing import List, Dict, Optional, Union
from playwright.async_api import async_playwright
import httpx


class LikeeParser:
    def __init__(self,):
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
            print(f"Неверный формат прокси '{proxy_str}': {str(e)}")
            return None

    async def get_uid_from_profile_page(self, short_id: str, proxy_list: List[str], max_retries: int = 3) -> Optional[str]:
        profile_url = f"https://likee.video/p/{short_id}"
        print(f"➡️ Открываем профиль: {profile_url}")

        for attempt in range(1, max_retries + 1):
            proxy = random.choice(proxy_list) if proxy_list else None
            proxy_config = await self.get_proxy_config(proxy) if proxy else None

            try:
                async with async_playwright() as p:
                    print(f"[DEBUG] Запускаем браузер, прокси={proxy_config}")
                    browser = await p.chromium.launch(headless=False)
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
                        proxy=proxy_config
                    )
                    page = await context.new_page()

                    # Ловим сам запрос (url + postData), но не берём body у response
                    video_request: Optional[str] = None
                    payload_data: Optional[str] = None

                    def on_request(req):
                        nonlocal video_request, payload_data
                        if "getUserVideo" in req.url and req.method == "POST":
                            print(f"[HOOK] Пойман запрос → {req.url}")
                            video_request = req.url
                            payload_data = req.post_data

                    page.on("request", on_request)

                    await page.goto(profile_url, wait_until="domcontentloaded", timeout=40000)
                    await asyncio.sleep(5)  # ждём, чтобы точно ушёл XHR

                    if not video_request:
                        print("⚠️ Не поймали запрос getUserVideo")
                        await browser.close()
                        continue

                    # Теперь сами делаем тот же запрос повторно
                    print(f"[DEBUG] Дублируем запрос вручную: {video_request}")
                    resp = await page.request.post(video_request, data=payload_data, headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
                        "Referer": "https://likee.video/"
                    })

                    text_data = await resp.text()
                    print(f"[DEBUG] Ответ API (500 симв): {text_data[:500]}")

                    try:
                        data = json.loads(text_data)
                    except Exception as je:
                        print(f"[ERROR] JSON parse error: {je}")
                        data = {}

                    if data.get("code") == 0 and data.get("data", {}).get("videoList"):
                        uid = data["data"]["videoList"][0].get("posterUid")
                        if uid:
                            print(f"✅ Найден posterUid: {uid}")
                            await browser.close()
                            return str(uid)

                    print("⚠️ UID не найден")
                    await browser.close()

            except Exception as e:
                print(f"Попытка {attempt} не удалась: {e}")
                if attempt == max_retries:
                    return None
                await asyncio.sleep(5)

        return None

    async def get_all_videos_by_uid(self, uid: str, proxy_list: List[str]) -> List[Dict]:
        all_videos = []
        last_post_id = ""
        max_per_request = 100

        proxy = random.choice(proxy_list) if proxy_list else None
        proxy_config = await self.get_proxy_config(proxy) if proxy else None
        print(f"[DEBUG] Используем прокси для сбора видео: {proxy_config}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
                proxy=proxy_config
            )
            page = await context.new_page()

            while True:
                print(f"🔍 Запрашиваем до {max_per_request} видео (после postId: {last_post_id or 'начала'})...")
                api_url = "https://api.like-video.com/likee-activity-flow-micro/videoApi/getUserVideo"
                payload = {
                    "uid": uid,
                    "count": max_per_request,
                    "tabType": 0,
                    "lastPostId": last_post_id
                }
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
                    "Referer": "https://likee.video/",
                    "Origin": "https://likee.video"
                }

                try:
                    print(f"[DEBUG] Делаем POST {api_url} c payload={payload}")
                    resp = await page.request.post(api_url, data=json.dumps(payload), headers=headers)
                    print(f"[DEBUG] HTTP статус: {resp.status}")
                    text_data = await resp.text()
                    print(f"[DEBUG] Ответ API (первые 500 символов): {text_data[:500]}")

                    if resp.status == 200:
                        try:
                            data = json.loads(text_data)
                        except Exception as je:
                            print(f"[ERROR] JSON parse error: {je}")
                            data = {}

                        if data.get("code") == 0:
                            videos = data["data"].get("videoList", [])
                            print(f"→ Получено {len(videos)} видео")
                            if not videos:
                                print("→ Больше нет видео. Завершаем.")
                                break
                            all_videos.extend(videos)
                            if len(videos) < max_per_request:
                                print("→ Достигнут конец профиля.")
                                break
                            last_post_id = videos[-1].get("postId", "")
                            if not last_post_id:
                                print("→ Нет lastPostId — завершаем.")
                                break
                        else:
                            print(f"→ API ошибка: code={data.get('code')}")
                            break
                    else:
                        print(f"→ HTTP ошибка: {resp.status}")
                        break

                    await asyncio.sleep(10)

                except Exception as e:
                    print(f"→ Ошибка при запросе видео: {e}")
                    break

            await browser.close()
            print(f"📦 Всего собрано видео: {len(all_videos)}")
            return all_videos

    async def download_image(self, url: str, proxy: str = None) -> Union[bytes, None]:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                print(f"Успешно загружено изображение: {url}")
                return resp.content
        except Exception as e:
            print(f"❌ Ошибка загрузки {url}: {e}")
            return None

    async def upload_image(self, video_id: int, image_url: str, proxy: str = None):
        image_bytes = await self.download_image(image_url, proxy=proxy)
        if not image_bytes:
            print(f"Не удалось скачать изображение для видео {video_id}")
            return None, "Download failed"

        file_name = image_url.split("/")[-1].split("?")[0]
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": (file_name, image_bytes, "image/jpeg")}
            try:
                resp = await client.post(
                    f"http://127.0.0.1:8000/api/v1/videos/{video_id}/upload-image/",
                    files=files,
                )
                resp.raise_for_status()
                print(f"✅ Фото для видео {video_id} загружено")
                return resp.status_code, resp.text
            except Exception as e:
                print(f"⚠️ Ошибка загрузки фото для видео {video_id}: {e}")
                return None, str(e)

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

    async def parse_channel(self, profile_url: str, channel_id: int, user_id: int, proxy_list: List[str] = None, max_retries: int = 3):
        profile_url = profile_url.strip()
        match = re.search(r"/p/([a-zA-Z0-9]+)", profile_url)
        if not match:
            raise ValueError(f"Неверный формат URL: {profile_url}")

        short_id = match.group(1)
        print(f"🔍 Извлечен short_id: {short_id}")

        uid = await self.get_uid_from_profile_page(short_id, proxy_list, max_retries)
        if not uid:
            raise RuntimeError("Не удалось получить uid.")

        print(f"🔑 Получен uid: {uid}. Собираем максимум видео...")
        videos = await self.get_all_videos_by_uid(uid, proxy_list)

        # Этап: отправка видео в API
        all_videos_data = []
        for video in videos:
            link = f"https://likee.video/v/{video['postId']}"

            # Формируем name из msgText
            msg_text = video.get("msgText", "").strip()
            if msg_text:
                preview = msg_text[:20]
                # Обрезаем по последнему пробелу, чтобы не резать слово
                if " " in preview:
                    name = preview[:preview.rfind(" ")]
                else:
                    name = preview
                # Убираем начальные/конечные пунктуационные символы
                name = name.strip(".,!?:;\"'«»()[]{}")
            else:
                name = f"Video {video['postId']}"

            article = self.extract_article_tag(msg_text)
            amount_views = int(video.get("playCount", 0))
            amount_likes = int(video.get("likeCount", 0))
            amount_comments = int(video.get("commentCount", 0))
            image_url = video.get("coverUrl")

            all_videos_data.append({
                "type": "likee",
                "channel_id": channel_id,
                "link": link,
                "name": name,
                "article": article,
                "amount_views": amount_views,
                "amount_likes": amount_likes,
                "amount_comments": amount_comments,
                "image_url": image_url
            })

        # Отправка метаданных в API
        processed_count = 0
        image_queue = []

        for video_data in all_videos_data:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    print(f"Проверка видео по ссылке: {video_data['link']}")
                    check_resp = await client.get(
                        f"http://127.0.0.1:8000/api/v1/videos/?link={video_data['link']}"
                    )
                    video_id = None
                    is_new = False

                    if check_resp.status_code == 200:
                        result = check_resp.json()
                        videos_api = result.get("videos", [])
                        if videos_api:
                            video_id = videos_api[0]['id']
                            print(f"Видео уже существует, ID: {video_id}, обновляем статистику")
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
                        print(f"Создано видео с ID: {video_id}")
                        if video_data.get("image_url"):
                            image_queue.append((video_id, video_data["image_url"]))
                            print(f"Добавлено изображение в очередь: {video_data['image_url']}")
                processed_count += 1
            except Exception as e:
                print(f"Ошибка при обработке {video_data.get('link')}: {e}")
                continue

        # Загрузка изображений с ротацией прокси
        idx = 0
        while idx < len(image_queue):
            if not proxy_list:
                proxy = None
            else:
                proxy = proxy_list[self.current_proxy_index]
                self.current_proxy_index = (self.current_proxy_index + 1) % len(proxy_list)

            batch = image_queue[idx: idx + 15]
            print(f"🌐 Прокси {proxy}: качаем {len(batch)} фото")

            for video_id, image_url in batch:
                try:
                    status, resp_text = await self.upload_image(video_id, image_url, proxy=proxy)
                    if status == 200:
                        print(f"✅ Фото для видео {video_id} загружено")
                    else:
                        print(f"⚠️ Фото для видео {video_id} ошибка {status}")
                except Exception as e:
                    print(f"❌ Ошибка загрузки фото для {video_id}: {e}")
                await asyncio.sleep(5.0)

            idx += 15

            if idx < len(image_queue) and self.current_proxy_index == 0 and proxy_list:
                print("⏳ Все прокси использованы, ждём 1 минуту...")
                await asyncio.sleep(60)

        print(f"✅ Успешно обработано {processed_count} видео")


async def main():
    proxy_list = [
        "1hnxSSHRLG:uFC7o3eBzg@103.82.103.21:22417",
        "JdW8YzAK0z:sIKJIMBdpS@109.120.147.59:31509",
        "SpxjooIilm:CjBtOOtgkY@109.120.147.96:39525",
    ]
    parser = LikeeParser()
    url = "https://likee.video/p/BE4Uku"
    user_id = 1
    await parser.parse_channel(url, channel_id=4,
                               proxy_list=proxy_list, user_id=user_id)

if __name__ == "__main__":
    asyncio.run(main())
