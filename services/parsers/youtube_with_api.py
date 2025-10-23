# --- ИМПОРТЫ ДОПОЛНИТЕЛЬНО ---
import os
import asyncio
import random
import re
import httpx
from typing import List, Dict, Optional, Union
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# from utils.logger import TCPLogger


# ====== ИЗМЕНЁННЫЙ __init__ ======
class ShortsParser:
    def __init__(
            self,
            # logger: TCPLogger,
            youtube_api_key: str | None = None,
            api_base: str = "https://cosmeya.dev-klick.cyou/api/v1",
            yt_quota_sleep: float = 0.25
    ):
        # self.logger = logger
        self.current_proxy_index = 0
        self.seen_video_ids: set = set()
        self.collected_videos: List[Dict] = []
        self.response_tasks: List[asyncio.Task] = []
        self.dom_images = {}
        # NEW:
        self.youtube_api_key = youtube_api_key or os.getenv("YT_API_KEY")
        self.api_base = api_base.rstrip("/")
        self.yt_quota_sleep = yt_quota_sleep

    # ====== УТИЛИТА РАЗБИВКИ НА БАТЧИ ======
    def _chunked(self, seq, n):
        for i in range(0, len(seq), n):
            yield seq[i:i+n]

    async def extract_images_from_dom(self, page, url: str):
        """Как в коде 2: идём по карточкам, берём href -> video_id и img.src/srcset.
        Аккумулируем в self.dom_images (не перезаписываем). Возвращаем общее кол-во картинок."""
        print("🔍 Извлекаем изображения из DOM (по карточкам, как в коде 2)...")

        item_selectors = [
            "ytm-shorts-lockup-view-model",   # мобильная
            "ytd-rich-item-renderer",         # десктопная
            "ytd-reel-item-renderer",         # reel items
            "ytd-grid-video-renderer"         # сетка
        ]

        added = 0
        total_cards_seen = 0

        for selector in item_selectors:
            try:
                items = await page.query_selector_all(selector)
                total_cards_seen += len(items)
                print(f"Карточек по '{selector}': {len(items)}")

                for el in items:
                    try:
                        # 1) ссылка на шорт — достаём video_id из href
                        link_el = await el.query_selector("a[href*='/shorts/']") \
                                or await el.query_selector("a.shortsLockupViewModelHostEndpoint")
                        href = await link_el.get_attribute("href") if link_el else None
                        if not href:
                            continue
                        m = re.search(r"/shorts/([a-zA-Z0-9_-]{11})", href)
                        if not m:
                            continue
                        video_id = m.group(1)

                        img_el = await el.query_selector("img.ytCoreImageHost, img.yt-img-shadow, img")
                        img_url = None
                        if img_el:
                            src = await img_el.get_attribute("src")
                            if src and src.strip() and not src.startswith("data:"):
                                img_url = src
                            else:
                                # бывает, что только srcset
                                srcset = await img_el.get_attribute("srcset")
                                if srcset:
                                    parts = [p.strip().split(" ")[0] for p in srcset.split(",") if p.strip()]
                                    if parts:
                                        img_url = parts[-1]

                        if not img_url:
                            img_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                        if video_id not in self.dom_images:
                            self.dom_images[video_id] = img_url
                            added += 1

                    except Exception:
                        continue

            except Exception as e:
                print(f"Ошибка при обходе '{selector}': {e}")
                continue

        print(f"✅ self.dom_images пополнен: +{added}, всего: {len(self.dom_images)}; карточек просмотрено: {total_cards_seen}")
        return len(self.dom_images)

    async def scroll_until(
            self,
            page,
            url: str,
            selector: str,
            delay: float = 4.0,
            max_idle_rounds: int = 5,
            max_total_scrolls: int = 60,
    ):
        """
        Прокручивает страницу, пока не перестанут появляться новые карточки.
        Добавлен верхний потолок по общему числу прокруток, чтобы не зациклиться.
        """
        max_scroll_attempts = 3
        total_scrolls = 0
        idle_rounds = 0

        try:
            prev_count = await page.eval_on_selector_all(selector, "els => els.length")
        except PlaywrightTimeoutError:
            prev_count = 0

        # Снимаем первый срез DOM до начала активного скролла
        await self.extract_images_from_dom(page, url)

        reached_bottom = False

        for attempt in range(1, max_scroll_attempts + 1):
            print(f"Прокрутка страницы, попытка {attempt}/{max_scroll_attempts}")

            while total_scrolls < max_total_scrolls:
                total_scrolls += 1

                # Имитация прокрутки колесом мыши помогает YouTube подгружать новые карточки
                try:
                    await page.mouse.wheel(0, random.randint(600, 900))
                except Exception as e:
                    print(f"⚠️ Не удалось прокрутить колесом мыши: {e}. Пробуем scrollBy.")
                    await page.evaluate("distance => window.scrollBy(0, distance)", 1000)

                await page.wait_for_timeout(int(delay * 1000))

                captcha = await page.query_selector("text=CAPTCHA")
                if captcha:
                    print("Обнаружена CAPTCHA на странице")
                    return 0

                try:
                    current_count = await page.eval_on_selector_all(selector, "els => els.length")
                    print(f"Текущее количество элементов по селектору '{selector}': {current_count}")
                except PlaywrightTimeoutError:
                    print("Timeout при оценке количества элементов, повторяем попытку...")
                    break

                if current_count > prev_count:
                    prev_count = current_count
                    idle_rounds = 0
                    await self.extract_images_from_dom(page, url)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=int(delay * 1000))
                    except PlaywrightTimeoutError:
                        pass
                else:
                    idle_rounds += 1
                    if idle_rounds >= max_idle_rounds:
                        print(f"Достигнут конец списка видео профиля {url}")
                        reached_bottom = True
                        break

                is_at_bottom = await page.evaluate(
                    "() => (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 100"
                )
                if is_at_bottom:
                    reached_bottom = True
                    break

            if reached_bottom:
                break

            if total_scrolls >= max_total_scrolls:
                print("⚠️ Превышено максимальное число прокруток, останавливаемся.")
                break

            # Небольшая пауза перед следующей попыткой: иногда YouTube догружает контент с задержкой
            idle_rounds = 0
            await page.wait_for_timeout(1500)

        # Финальное извлечение изображений после скролла
        await self.extract_images_from_dom(page, url)
        return len(self.dom_images)

    # ====== НОВОЕ: запрос к YouTube Data API по собранным ID ======
    async def fetch_youtube_meta(self, video_ids: List[str]) -> Dict[str, dict]:
        """
        Берёт батчами по 50 ID и возвращает {id: item} из videos.list
        part=snippet,statistics => title, description, publishedAt, viewCount, likeCount, commentCount
        """
        if not self.youtube_api_key:
            raise RuntimeError("YouTube API ключ не задан (youtube_api_key или переменная YT_API_KEY).")

        out = {}
        fields = (
            "items("
            "id,"
            "snippet/publishedAt,"
            "snippet/title,"
            "snippet/description,"
            "statistics/viewCount,"
            "statistics/likeCount,"
            "statistics/commentCount)"
        )
        params_base = {
            "part": "snippet,statistics",
            "key": self.youtube_api_key,
            "fields": fields
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            for batch in self._chunked(video_ids, 50):
                try:
                    params = params_base | {"id": ",".join(batch)}
                    r = await client.get("https://www.googleapis.com/youtube/v3/videos", params=params)
                    if r.status_code != 200:
                        print(f"⚠️ videos.list {r.status_code}: {r.text[:200]}")
                        await asyncio.sleep(self.yt_quota_sleep)
                        continue
                    data = r.json()
                    for it in data.get("items", []):
                        out[it["id"]] = it
                except Exception as e:
                    print(f"⚠️ Ошибка videos.list: {e}")
                await asyncio.sleep(self.yt_quota_sleep)  # бережём квоту
        return out

    # ====== ИЗМЕНЁННЫЙ upload_image: используем api_base ======

    async def download_image(self, url: str, proxy: str = None) -> Union[bytes, None]:
        """Скачивает изображение с YouTube (можно с прокси)."""
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
                    f"{self.api_base}/videos/{video_id}/upload-image/",
                    files=files,
                )
                resp.raise_for_status()
                return resp.status_code, resp.text
            except Exception as e:
                print(f"⚠️ Ошибка загрузки фото для видео {video_id}: {e}")
                return None, str(e)

    # ====== NEW: сбор финального payload из API и отправка в ваш бэкенд ======
    async def upsert_videos_to_backend(self, payloads: List[Dict], proxy_list: list | None = None) -> tuple[int, List[tuple[int, str]]]:
        """
        Создаём/обновляем записи на ваших эндпоинтах.
        Возвращает (processed_count, image_queue), где image_queue = [(video_id, image_url), ...]
        """
        processed_count = 0
        image_queue: List[tuple[int, str]] = []

        async with httpx.AsyncClient(timeout=20.0) as client:
            for video_data in payloads:
                try:
                    # проверяем, есть ли уже такая запись по link
                    check_resp = await client.get(f"{self.api_base}/videos/", params={"link": video_data["link"]})
                    is_new = False
                    video_id = None

                    if check_resp.status_code == 200:
                        res = check_resp.json()
                        vids = res.get("videos", [])
                        if vids:
                            video_id = vids[0]["id"]
                            # Пакет частичного обновления
                            patch_data = {
                                "amount_views": video_data["amount_views"],
                                "amount_likes": video_data["amount_likes"],
                                "amount_comments": video_data["amount_comments"],
                                "date_published": video_data["date_published"],
                            }
                            # Попробуем пробросить description, если бэкенд это поддерживает
                            if video_data.get("description") is not None:
                                patch_data["description"] = video_data["description"]
                            try:
                                await client.patch(f"{self.api_base}/videos/{video_id}", json=patch_data)
                            except httpx.HTTPStatusError as e:
                                # если 4xx из-за неизвестного поля, повторим без description
                                if e.response is not None and e.response.status_code in (400, 422) and "description" in patch_data:
                                    patch_data.pop("description", None)
                                    await client.patch(f"{self.api_base}/videos/{video_id}", json=patch_data)
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        # Полное создание
                        create_data = video_data.copy()
                        try:
                            resp = await client.post(f"{self.api_base}/videos/", json=create_data)
                            resp.raise_for_status()
                            video_id = resp.json()["id"]
                        except httpx.HTTPStatusError as e:
                            # fallback без description, если поле не поддерживается
                            if e.response is not None and e.response.status_code in (400, 422) and "description" in create_data:
                                create_data.pop("description", None)
                                resp = await client.post(f"{self.api_base}/videos/", json=create_data)
                                resp.raise_for_status()
                                video_id = resp.json()["id"]
                            else:
                                raise

                        # планируем загрузку обложки
                        if video_data.get("image"):
                            image_queue.append((video_id, video_data["image"]))

                    processed_count += 1

                except Exception as e:
                    print(f"⚠️ Ошибка при обработке {video_data.get('link')}: {e}")

        return processed_count, image_queue

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

    # ====== ГЛАВНЫЙ МЕТОД: скроллим /shorts → собираем DOM → YouTube API → бэкенд ======
    async def parse_channel(self, url: str, channel_id: int, user_id: int,
                            max_retries: int = 3, proxy_list: list = None):
        """
        Новая логика: только DOM + YouTube API.
        - Скроллим /shorts, собираем {video_id: image_url}
        - Батчами дергаем YouTube Data API
        - Формируем payload и отправляем на ваши эндпоинты
        - Загружаем обложки
        """
        self.proxy_list = proxy_list or []
        current_proxy_index = 0
        if not url.endswith("/shorts"):
            url = url.rstrip("/") + "/shorts"
        print(f"Переход на вкладку Shorts: {url}")

        playwright = browser = context = page = None

        async def get_proxy_config(proxy_str):
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
                print(f"Неверный формат прокси: {e}")
                return None

        async def create_browser_with_proxy(proxy_str, playwright):
            proxy_config = await get_proxy_config(proxy_str) if proxy_str else None
            browser = await playwright.chromium.launch(
                headless=False,
                args=["--headless=new", "--disable-blink-features=AutomationControlled", "--start-maximized"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/138.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                proxy=proxy_config
            )
            page = await context.new_page()
            return browser, context, page

        current_proxy = random.choice(self.proxy_list) if self.proxy_list else None
        print(f"Используемый прокси: {current_proxy}")

        try:
            playwright = await async_playwright().start()
            browser, context, page = await create_browser_with_proxy(current_proxy, playwright)

            # 1) Открываем /shorts и скроллим, попутно собирая карточки
            await page.goto(url, wait_until="networkidle", timeout=60000)

            try:
                accept_btn = await page.query_selector("button[aria-label='Accept all']")
                if accept_btn:
                    await accept_btn.click()
                    await page.wait_for_timeout(1200)
                    print("Закрыта модалка с куки")
            except:
                pass

            selector = "ytd-rich-item-renderer, ytd-reel-item-renderer, ytm-shorts-lockup-view-model"
            total_videos_from_dom = await self.scroll_until(page, url, selector=selector, delay=4.0)
            if total_videos_from_dom == 0:
                print("⚠️ На вкладке /shorts не найдено карточек")
                return []

            print(f"📊 В DOM найдено {total_videos_from_dom} карточек Shorts")

            # 2) Собираем ID (ключи словаря) и вызываем YouTube API
            video_ids = list(self.dom_images.keys())
            meta = await self.fetch_youtube_meta(video_ids)

            # 3) Формируем итоговый payload
            #    (описание, лайки, просмотры, комменты, publishedAt — всё из API)
            all_videos_data = []
            for vid in video_ids:
                it = meta.get(vid)
                if not it:
                    continue
                sn = it.get("snippet", {}) or {}
                st = it.get("statistics", {}) or {}

                title = sn.get("title") or ""
                description = sn.get("description") or ""
                published_at = (sn.get("publishedAt") or "")[:10]  # YYYY-MM-DD
                view_count = int(st.get("viewCount")) if st.get("viewCount") is not None else 0
                like_count = int(st.get("likeCount")) if st.get("likeCount") is not None else 0
                comment_count = int(st.get("commentCount")) if st.get("commentCount") is not None else 0

                all_videos_data.append({
                    "link": f"https://www.youtube.com/shorts/{vid}",
                    "type": "youtube",
                    "name": self.generate_short_title(title),
                    "description": description,   # NEW
                    "image": self.dom_images.get(vid) or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                    "articles": self.extract_article_tag(title),
                    "channel_id": channel_id,
                    "amount_views": view_count,
                    "amount_likes": like_count,
                    "amount_comments": comment_count,
                    "date_published": published_at
                })

            print(f"✅ Сформирован payload по {len(all_videos_data)} видео")

        except Exception as main_error:
            print(f"Критическая ошибка: {main_error}")
            raise
        finally:
            for obj, name in [(page, "page"), (context, "context"), (browser, "browser"), (playwright, "playwright")]:
                if obj:
                    try:
                        if name == "playwright":
                            await obj.stop()
                        else:
                            await obj.close()
                    except Exception as e:
                        print(f"Ошибка закрытия {name}: {e}")

        # 4) Отправляем в ваш бэкенд и планируем загрузку обложек
        processed_count, image_queue = await self.upsert_videos_to_backend(all_videos_data, proxy_list=proxy_list)
        print(f"📦 Всего обработано {processed_count} видео, ожидают загрузки {len(image_queue)} обложек.")

        # 5) Загрузка изображений (как у вас, только base берётся из self.api_base)
        idx = 0
        while idx < len(image_queue):
            proxy = proxy_list[current_proxy_index] if proxy_list else None
            current_proxy_index = (current_proxy_index + 1) % len(proxy_list) if proxy_list else 0
            batch = image_queue[idx:idx + 15]
            print(f"🖼️ Загружаем {len(batch)} изображений через {proxy or 'без прокси'}")

            for vid, img_url in batch:
                try:
                    await self.upload_image(vid, img_url, proxy=proxy)
                except Exception as e:
                    print(f"❌ Ошибка загрузки фото {vid}: {e}")
                await asyncio.sleep(5.0)
            idx += 15

        print(f"🎉 Парсинг завершён: {processed_count} видео обработано.")
        # Возвращаем итоговый список, если нужно как результат
        return all_videos_data


# # ----------------------- Пример запуска -----------------------

async def main():
    proxy_list = [
        "g3dmsMyYST:B9BegRNRzi@45.150.35.224:28898",
        "Weh1oXn82b:dUYiJZ5w7T@45.150.35.129:31801",
        "gnmPrWSMJ4:tbHyXTwWdx@45.150.35.114:54943",
        "15ObFJmCP5:a0rog6kGgT@45.150.35.113:24242",
        "Z7mGFwrT6N:5wLFFO5v3S@109.120.131.5:34707",
        "HCtCUxQYnj:GM9pjQ8J8T@109.120.131.229:39202",
        "dBY505zGKK:8gqxiwpjvg@45.150.35.44:40281",
        "zhH47betn3:J8eC3qaOrs@109.120.131.175:38411",
        "KX32alVE51:ZVD0CsjFhJ@109.120.131.27:47449",
        "KTdw9aNBl7:MI45E5jVnB@45.150.35.233:57281",
        "7bZbeHwcNI:fFs1cUXfbN@109.120.131.219:29286",
        "F1Y0BvrqNo:HKPbfMGtJw@45.150.35.31:41247",
        "WfkB8GfYts:vXdJAVXCSI@45.150.35.133:35460",
        "yr3Xib8LYo:FzS9t4PGro@45.150.35.3:50283",
        "exOL0CR6TN:oj0BGarhAk@45.150.35.143:32354",
        "CbZ35SQIZb:OO4ddjBRiK@45.150.35.99:28985",
        "JRGI3q6Zo9:LJpcFpCgU2@45.150.35.30:32381",
        "NTPvsl77eN:wagp6GmWNk@109.120.131.41:55509",
        "SBqj98lU9c:ktxTU1ZOid@45.150.35.138:55350",
        "3El7Uvg1TY:1DZVyrdMPs@45.150.35.231:51842",
        "dBqOOqGczg:d2xKkdc3Re@45.150.35.156:38617",
        "fz91O4ury3:ZBCW6s8d7E@45.150.35.132:47712",
        "RLFUp7vicq:X1TTYhQYWs@45.150.35.34:40674",
        "3dQxPpHkj4:o12oWKn5Lg@45.150.35.201:42897",
        "iRArjOVFVr:0vXB48RsTf@45.150.35.200:42312",
    ]
    parser = ShortsParser()
    url = "https://www.youtube.com/@nastya.beomaa"
    user_id = 1
    await parser.parse_channel(url, channel_id=4, user_id=user_id,
                               proxy_list=proxy_list)


if __name__ == "__main__":
    asyncio.run(main())
