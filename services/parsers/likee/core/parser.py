import asyncio
from collections import deque
from datetime import datetime, timezone
import httpx
import json
import os
import random
import re
from typing import List, Dict, Optional, Union
from playwright.async_api import async_playwright
from utils.logger import TCPLogger



class LikeeParser:
    def __init__(
            self,
            logger: TCPLogger
    ):
        self.logger = logger
        self.current_proxy_index = 0

    @staticmethod
    def _parse_started_at(value: Optional[Union[str, datetime]]) -> datetime:
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str) and value.strip():
            text = value.strip()
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(text)
            except ValueError:
                dt = datetime.now(timezone.utc)
        else:
            dt = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def _log_summary(
        self,
        url: str,
        channel_id: int,
        video_count: int,
        total_views: int,
        started_at: datetime,
        ended_at: datetime,
        success: bool,
    ) -> None:
        status_icon = "✅" if success else "⚠️"
        status_text = "Успешно спарсили" if success else "Не удалось спарсить"
        self.logger.send(
            "INFO",
            f"{status_icon} {status_text} {url} с {channel_id} "
            f"кол-во видео - {video_count}, кол-во просмотров - {total_views}, "
            f"время начала парсинга - {started_at.isoformat()}, конец парсинга - {ended_at.isoformat()}",
        )

    async def _start_playwright(self):
        try:
            return await async_playwright().start()
        except Exception as exc:
            self.logger.send("INFO", f"❌ Не удалось запустить Playwright: {exc}")
            return None

    async def _safe_close(self, obj, label: str, method: str = "close"):
        if not obj:
            return
        closer = getattr(obj, method, None)
        if not closer:
            return
        try:
            result = closer()
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            self.logger.send("INFO", f"⚠️ Ошибка закрытия {label}: {exc}")

    async def _cleanup_browser_stack(self, page=None, context=None, browser=None):
        await self._safe_close(page, "page")
        await self._safe_close(context, "context")
        await self._safe_close(browser, "browser")

    def _format_proxy(self, proxy: Optional[str]) -> Optional[str]:
        if not proxy:
            return None
        proxy = proxy.strip()
        if not proxy:
            return None
        if proxy.startswith(("http://", "https://")):
            return proxy
        if "@" in proxy:
            auth, host_port = proxy.split("@", 1)
            host, port = host_port.split(":", 1)
            return f"http://{auth}@{host}:{port}"
        if ":" in proxy:
            host, port = proxy.split(":", 1)
            return f"http://{host}:{port}"
        return proxy

    def _select_next_proxy(self, proxies: List[Optional[str]], last_proxy: Optional[str]) -> Optional[str]:
        if not proxies:
            return None
        if len(proxies) == 1:
            return proxies[0]
        candidates = [p for p in proxies if p != last_proxy]
        return random.choice(candidates) if candidates else proxies[0]

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
            self.logger.send("INFO", f"Неверный формат прокси '{proxy_str}': {str(e)}")
            return None

    async def get_uid_from_profile_page(
        self,
        short_id: str,
        proxy_list: List[str],
        playwright,
        max_retries: int = 3,
        proxy_override: Optional[str] = None,
    ) -> Optional[str]:
        try:
            retries = int(max_retries)
            if retries < 1:
                retries = 1
        except (TypeError, ValueError):
            self.logger.send(
                "WARNING",
                f"Получен некорректный max_retries={max_retries}, использую 3",
            )
            retries = 3

        profile_url = f"https://likee.video/p/{short_id}"
        self.logger.send("INFO", f"➡️ Открываем профиль: {profile_url}")

        for attempt in range(1, retries + 1):
            proxy = proxy_override or (random.choice(proxy_list) if proxy_list else None)
            proxy_config = await self.get_proxy_config(proxy) if proxy else None

            browser = context = page = None
            try:
                self.logger.send("INFO", f"Запускаем браузер, прокси={proxy_config or 'без прокси'} (попытка {attempt}/{max_retries})",)
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-gpu",
                        "--no-sandbox",
                        "--window-size=1280,720",
                        "--headless=new",
                    ]

                )  # headless=True в продакшене
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
                    proxy=proxy_config
                )
                page = await context.new_page()

                video_request: Optional[str] = None
                payload_data: Optional[str] = None

                def on_request(req):
                    nonlocal video_request, payload_data
                    if "getUserVideo" in req.url and req.method == "POST":
                        self.logger.send("INFO", f"[HOOK] Пойман запрос → {req.url}")
                        video_request = req.url
                        payload_data = req.post_data

                page.on("request", on_request)

                await page.goto(profile_url, wait_until="domcontentloaded", timeout=40000)
                await asyncio.sleep(5)

                if not video_request:
                    self.logger.send("INFO", "⚠️ Не поймали запрос getUserVideo")
                    continue

                request_uid: Optional[Union[str, int]] = None
                if payload_data:
                    try:
                        payload_json = json.loads(payload_data)
                    except json.JSONDecodeError as je:
                        self.logger.send(
                            "INFO",
                            f"Не удалось распарсить тело запроса getUserVideo: {je}",
                        )
                    else:
                        request_uid = payload_json.get("uid") or payload_json.get("posterUid")
                        if request_uid:
                            self.logger.send("INFO", f"✅ Найден uid в теле запроса: {request_uid}")
                            return str(request_uid)

                # Повторяем запрос вручную
                self.logger.send("INFO", f"Дублируем запрос вручную: {video_request}")
                resp = await page.request.post(
                    video_request,
                    data=payload_data,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
                        "Referer": "https://likee.video/"
                    }
                )

                text_data = await resp.text()
                try:
                    data = json.loads(text_data)
                except Exception as je:
                    self.logger.send("INFO", f"JSON parse error: {je}")
                    data = {}

                if data.get("code") == 0 and data.get("data", {}).get("videoList"):
                    uid = data["data"]["videoList"][0].get("posterUid")
                    if uid:
                        self.logger.send("INFO", f"✅ Найден posterUid: {uid}")
                        return str(uid)

                self.logger.send("INFO", "⚠️ UID не найден")

            except Exception as e:
                self.logger.send("INFO", f"Попытка {attempt} не удалась: {e}")
                if attempt == max_retries:
                    return None
                await asyncio.sleep(5)

            finally:
                await self._cleanup_browser_stack(page, context, browser)

        return None

    async def get_all_videos_by_uid(
        self,
        uid: str,
        proxy_list: List[str],
        playwright,
        proxy_override: Optional[str] = None,
    ) -> List[Dict]:
        all_videos = []
        last_post_id = ""
        max_per_request = 100

        proxy = proxy_override or (random.choice(proxy_list) if proxy_list else None)
        proxy_config = await self.get_proxy_config(proxy) if proxy else None
        self.logger.send("INFO", f"Используем прокси для сбора видео: {proxy_config or 'без прокси'}",)

        browser = context = page = None
        try:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
                proxy=proxy_config
            )
            page = await context.new_page()

            while True:
                self.logger.send("INFO", f"🔍 Запрашиваем до {max_per_request} видео (после postId: {last_post_id or 'начала'})...")
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
                    resp = await page.request.post(api_url, data=json.dumps(payload), headers=headers)
                    self.logger.send("INFO", f"HTTP статус: {resp.status}")
                    text_data = await resp.text()

                    if resp.status == 200:
                        try:
                            data = json.loads(text_data)
                        except Exception as je:
                            self.logger.send("INFO", f"JSON parse error: {je}")
                            data = {}

                        if data.get("code") == 0:
                            videos = data["data"].get("videoList", [])
                            self.logger.send("INFO", f"→ Получено {len(videos)} видео")
                            if not videos:
                                break
                            all_videos.extend(videos)
                            if len(videos) < max_per_request:
                                break
                            last_post_id = videos[-1].get("postId", "")
                            if not last_post_id:
                                break
                        else:
                            self.logger.send("INFO", f"→ API ошибка: code={data.get('code')}")
                            break
                    else:
                        self.logger.send("INFO", f"→ HTTP ошибка: {resp.status}")
                        break

                    await asyncio.sleep(10)

                except Exception as e:
                    self.logger.send("INFO", f"→ Ошибка при запросе видео: {e}")
                    break

        finally:
            await self._cleanup_browser_stack(page, context, browser)

        self.logger.send("INFO", f"📦 Всего собрано видео: {len(all_videos)}")
        return all_videos

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

    def extract_article_tag(self, caption: str) -> Optional[str]:
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

    async def download_image(self, url: str, proxy: Optional[str] = None) -> Union[bytes, None]:
        formatted_proxy = self._format_proxy(proxy)
        try:
            async with httpx.AsyncClient(timeout=20.0, proxy=formatted_proxy) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                self.logger.send("INFO", f"Успешно загружено изображение: {url}")
                return resp.content
        except Exception as e:
            self.logger.send("INFO", f"❌ Ошибка загрузки {url}: {e}")
            return None

    async def upload_image(self, video_id: int, image_url: str, proxy: Optional[str] = None):
        image_bytes = await self.download_image(image_url, proxy=proxy)
        if not image_bytes:
            self.logger.send("INFO", f"Не удалось скачать изображение для видео {video_id}")
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
                try:
                    payload = resp.json()
                except ValueError:
                    payload = {}

                image_path = None
                if isinstance(payload, dict):
                    image_path = payload.get("image")
                    if image_path and not image_path.startswith(("http://", "https://", "/")):
                        image_path = f"/{image_path}"

                self.logger.send("INFO", f"✅ Фото для видео {video_id} загружено")
                return resp.status_code, image_path or payload or resp.text
            except Exception as e:
                self.logger.send("INFO", f"⚠️ Ошибка загрузки фото для видео {video_id}: {e}")
                return None, str(e)

    # --- Основной метод с централизованным управлением Playwright ---
    async def parse_channel(
        self,
        profile_url: str,
        channel_id: int,
        user_id: int,
        proxy_list: List[str] = None,
        max_retries: int = 3,
        parse_started_at: Optional[Union[str, datetime]] = None,
    ):
        profile_url = profile_url.strip()
        match = re.search(r"/p/([a-zA-Z0-9]+)", profile_url)
        if not match:
            raise ValueError(f"Неверный формат URL: {profile_url}")

        short_id = match.group(1)
        self.logger.send("INFO", f"🔍 Извлечен short_id: {short_id}")

        run_started_at = self._parse_started_at(parse_started_at)
        history_created_at_iso = run_started_at.isoformat()
        processed_count = 0
        total_views = 0

        def log_final(success: bool) -> None:
            ended_at = datetime.now(timezone.utc)
            self._log_summary(
                profile_url,
                channel_id,
                processed_count,
                total_views,
                run_started_at,
                ended_at,
                success and processed_count > 0,
            )

        playwright = await self._start_playwright()
        if not playwright:
            return

        try:
            if proxy_list is None:
                proxy_list = []
            elif not isinstance(proxy_list, list):
                self.logger.send(
                    "WARNING",
                    f"Получен proxy_list некорректного типа ({type(proxy_list)}): {proxy_list}. "
                    "Преобразую в список.",
                )
                proxy_list = [proxy_list]

            proxy_list = [p for p in proxy_list if p]
            proxies_cycle = proxy_list if proxy_list else [None]
            self.logger.send(
                "INFO",
                f"🔁 Подготовлено прокси для перебора: {proxies_cycle}",
            )

            uid = None
            videos: List[Dict] = []

            for attempt, current_proxy in enumerate(proxies_cycle, start=1):
                self.logger.send(
                    "INFO",
                    f"🧪 Попытка {attempt}/{len(proxies_cycle)} с прокси "
                    f"{current_proxy or 'без прокси'}",
                )
                uid = await self.get_uid_from_profile_page(
                    short_id,
                    proxy_list,
                    playwright,
                    max_retries,
                    proxy_override=current_proxy,
                )
                if not uid:
                    self.logger.send("INFO", "Не удалось получить uid, переключаемся на следующий прокси",)
                    await asyncio.sleep(3)
                    continue

                self.logger.send("INFO", f"🔑 Получен uid: {uid}. Собираем максимум видео (попытка {attempt})",)
                videos = await self.get_all_videos_by_uid(
                    uid,
                    proxy_list,
                    playwright,
                    proxy_override=current_proxy,
                )
                if videos:
                    break

                self.logger.send("INFO", "Видео не получены на этом прокси, пробуем следующий...",)
                await asyncio.sleep(3)

            if not uid:
                raise RuntimeError("Не удалось получить uid ни с одного прокси.")

            if not videos:
                self.logger.send("INFO", "Завершили перебор прокси, видео не собраны. Продолжаем без данных.",)

            # --- Этап: отправка видео в API (без Playwright) ---
            all_videos_data = []
            for video in videos:
                link = f"https://likee.video/v/{video['postId']}"
                amount_views = int(video.get("playCount", 0))
                amount_likes = int(video.get("likeCount", 0))
                amount_comments = int(video.get("commentCount", 0))
                image_url = video.get("coverUrl")
                description = (video.get("postLongDesc") or video.get("msgText") or "").strip()
                name = self.generate_short_title(description, 30)
                articles = self.extract_article_tag(description)
                post_time = video.get("postTime")
                published_at = None
                if post_time is not None:
                    try:
                        # Безопасное преобразование
                        dt = datetime.fromtimestamp(int(post_time), tz=timezone.utc)
                        published_at = dt.strftime('%Y-%m-%d')
                    except (ValueError, OSError, TypeError, OverflowError) as e:
                        self.logger.send("INFO", f"Ошибка при конвертации postTime {post_time}: {e}")

                all_videos_data.append({
                    "link": link,
                    "type": "likee",
                    "name": name,
                    "image_url": image_url,
                    "articles": articles,
                    "channel_id": channel_id,
                    "amount_views": amount_views,
                    "amount_likes": amount_likes,
                    "amount_comments": amount_comments,
                    "date_published": published_at,
                    "history_created_at": history_created_at_iso,
                })

            total_views = sum(int(item.get("amount_views", 0) or 0) for item in all_videos_data)
            image_queue = []

            for video_data in all_videos_data:
                try:
                    async with httpx.AsyncClient(timeout=20.0) as client:
                        check_resp = await client.get(
                            f"https://cosmeya.dev-klick.cyou/api/v1/videos/?link={video_data['link']}"
                        )
                        video_id = None
                        is_new = False

                        if check_resp.status_code == 200:
                            result = check_resp.json()
                            videos_api = result.get("videos", [])
                            if videos_api:
                                video_id = videos_api[0]['id']
                                update_resp = await client.patch(
                                    f"https://cosmeya.dev-klick.cyou/api/v1/videos/{video_id}",
                                    json={
                                        "amount_views": video_data["amount_views"],
                                        "amount_likes": video_data["amount_likes"],
                                        "amount_comments": video_data["amount_comments"],
                                        "history_created_at": history_created_at_iso,
                                    }
                                )
                                update_resp.raise_for_status()
                            else:
                                is_new = True
                        else:
                            is_new = True

                        if is_new:
                            create_resp = await client.post(
                                "https://cosmeya.dev-klick.cyou/api/v1/videos/",
                                json=video_data
                            )
                            create_resp.raise_for_status()
                            video_id = create_resp.json()['id']
                            if video_data.get("image_url"):
                                image_queue.append((video_id, video_data["image_url"]))
                    processed_count += 1
                except Exception as e:
                    self.logger.send("INFO", f"Ошибка при обработке {video_data.get('link')}: {e}")
                    continue

            proxy_candidates: List[Optional[str]] = list(proxy_list) if proxy_list else [None]
            pending_images = deque((video_id, image_url, None) for video_id, image_url in image_queue)

            while pending_images:
                video_id, image_url, last_proxy_used = pending_images.popleft()
                proxy = self._select_next_proxy(proxy_candidates, last_proxy_used)
                self.logger.send("INFO", f"🌐 Прокси {proxy or 'без прокси'}: качаем фото для видео {video_id}")

                try:
                    status, resp_text = await self.upload_image(video_id, image_url, proxy=proxy)
                    if status == 200:
                        self.logger.send("INFO", f"✅ Фото для видео {video_id} загружено")
                        await asyncio.sleep(5.0)
                        continue
                    self.logger.send("INFO", f"⚠️ Фото для видео {video_id} ошибка {status}")
                except Exception as e:
                    self.logger.send("INFO", f"❌ Ошибка загрузки фото для {video_id}: {e}")

                self.logger.send("INFO", f"🔄 Повторим загрузку фото для {video_id} через 1 минуту на другой прокси")
                pending_images.append((video_id, image_url, proxy))
                await asyncio.sleep(60.0)

            self.logger.send("INFO", f"✅ Успешно обработано {processed_count} видео")

        finally:
            # Централизованное закрытие Playwright
            await self._safe_close(playwright, "playwright", method="stop")
            log_final(processed_count > 0)


# async def main():
#     proxy_list = [
#         "gYCnZWZrgi:iexdZdvSeN@193.168.224.25:50524",
#         "ndtvwtXQh7:Acg5amEuK7@103.82.103.34:48319",
#         "ZVaGoMrHmt:fLA2FnapWs@109.120.147.248:55710",
#         "YWpuNCTEcf:9J5UHLn2ha@45.132.252.137:20472",
#         "ThI4AlnYc8:cC6IiARsnD@109.120.147.221:60860",
#         "weTPSmpjHB:OPBSIuub2t@193.168.224.125:31635",
#         "frvEXoGF2v:nIbEnIuD26@45.132.252.60:43121",
#         "7dtzp90Dsr:DaDxgASS3d@45.132.252.89:24550",
#         "gzQZLQNslU:7wYp8R5UU9@103.82.103.150:51428",
#         "qI6mCjoRDV:aArrfm6cGH@109.120.147.208:32907",
#     ]
#     parser = LikeeParser()
#     url = "https://l.likee.video/p/IVOeZT"
#     user_id = 1
#     await parser.parse_channel(url, channel_id=4,
#                                proxy_list=proxy_list, user_id=user_id)

# if __name__ == "__main__":
#     asyncio.run(main())
