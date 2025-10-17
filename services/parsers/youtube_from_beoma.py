import re
import asyncio
import time
from typing import Optional, Dict, List, Union
import httpx
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import random
from datetime import datetime

from utils.logger import TCPLogger


class ShortsParser:
    def __init__(self, logger: TCPLogger):
        self.logger = logger
        self.current_proxy_index = 0
        self.seen_video_ids: set = set()
        self.collected_videos: List[Dict] = []
        self.response_tasks: List[asyncio.Task] = []
        self.dom_images = {}

    def parse_views(self, text: str) -> int:
        if not text:
            return 0
        match = re.search(r"([\d,]+)", text)
        return int(match.group(1).replace(",", "")) if match else 0

    def _parse_compact_number(self, text: str) -> int | None:
        if not text:
            return None
        # убираем NBSP и лишние пробелы
        s = text.replace("\u00a0", " ").strip()

        # Ищем число + необязательный суффикс (K/M/К/М)
        m = re.search(r"([\d\s.,]+)\s*([kKmMкКмМ])?", s)
        if not m:
            return None

        num = m.group(1)
        # "1 234,5" -> "1234.5"
        num = num.replace(" ", "").replace(",", ".")
        try:
            n = float(num)
        except ValueError:
            return None

        suff = (m.group(2) or "").lower()
        if suff in ("k", "к"):
            n *= 1_000
        elif suff in ("m", "м"):
            n *= 1_000_000

        return int(round(n))

    async def get_video_count_from_header(self, page, timeout: int = 15000) -> int | None:
        """
        Ищет в шапке канала блок метаданных и достаёт число из текста вида '229 videos' / '229 видео'.
        Возвращает int или None.
        """
        try:
            # ждём появление шапки
            await page.wait_for_selector("ytd-tabbed-page-header", timeout=timeout)
        except Exception:
            return None

        # 1) собираем все фрагменты метаданных шапки
        try:
            texts = await page.eval_on_selector_all(
                "ytd-tabbed-page-header yt-content-metadata-view-model .yt-content-metadata-view-model__metadata-text",
                "els => els.map(e => (e.textContent || '').trim())"
            )
        except Exception:
            texts = []

        # 1a) ищем те, где явно встречается 'videos/видео/відео'
        for t in texts:
            if re.search(r"\b(videos?|видео|відео)\b", t, flags=re.I):
                num = self._parse_compact_number(t)
                if num is not None:
                    return num

        # 2) эвристика: во втором ряду последний span — как правило "N videos"
        try:
            last_text = await page.eval_on_selector(
                "ytd-tabbed-page-header yt-content-metadata-view-model .yt-content-metadata-view-model__metadata-row:nth-of-type(2) .yt-content-metadata-view-model__metadata-text:last-of-type",
                "el => (el && el.textContent || '').trim()"
            )
            if last_text:
                num = self._parse_compact_number(last_text)
                if num is not None:
                    return num
        except Exception:
            pass

        return None

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

    async def scroll_until(self, page, url: str, selector: str, delay: float = 4.0, max_idle_rounds: int = 5):
        """Модифицированный скролл - теперь также извлекаем изображения из DOM"""
        prev_count = 0
        idle_rounds = 0
        max_scroll_attempts = 3

        for attempt in range(max_scroll_attempts):
            self.logger.send("INFO", f"Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

            while True:
                await page.evaluate("""
                    async () => {
                        return new Promise((resolve) => {
                            const distance = 1000;
                            const timer = setInterval(() => {
                                window.scrollBy(0, distance);
                                if (document.body.scrollHeight - window.scrollY <= window.innerHeight + 100) {
                                    clearInterval(timer);
                                    resolve();
                                }
                            }, 100);
                        });
                    }
                """)

                await page.wait_for_timeout(int(delay * 1000))

                captcha = await page.query_selector("text=CAPTCHA")
                if captcha:
                    self.logger.send("ERROR", "Обнаружена CAPTCHA на странице")
                    return 0

                # ИЗВЛЕКАЕМ ИЗОБРАЖЕНИЯ ИЗ DOM ПОКА СКРОЛЛИМ
                await self.extract_images_from_dom(page, url)

                try:
                    current_count = await page.eval_on_selector_all(selector, "els => els.length")
                    self.logger.send("INFO", f"Текущее количество элементов по селектору '{selector}': {current_count}")

                    if current_count == prev_count:
                        idle_rounds += 1
                        if idle_rounds >= max_idle_rounds:
                            self.logger.send("INFO", f"Достигнут конец списка видео профиля {url}")
                            break
                    else:
                        idle_rounds = 0
                        prev_count = current_count

                    is_at_bottom = await page.evaluate(
                        "() => (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 100"
                    )
                    if is_at_bottom:
                        break
                except PlaywrightTimeoutError:
                    self.logger.send("ERROR", "Timeout при оценке элементов, продолжаем...")
                    break

        # Финальное извлечение изображений после скролла
        await self.extract_images_from_dom(page, url)
        return len(self.dom_images)

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

    def extract_article_tag(self, caption: str) -> str | None:
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

    def extract_video_from_reel_item_watch(self, data: dict) -> Optional[Dict]:
        try:
            overlay = data.get("overlay", {}).get("reelPlayerOverlayRenderer", {})

            metapanel = overlay.get("metapanel", {}).get("reelMetapanelViewModel", {})
            title_items = metapanel.get("metadataItems", [])
            title = next(
                (item.get("shortsVideoTitleViewModel", {}).get("text", {}).get(
                    "content", "") for item in title_items if "shortsVideoTitleViewModel" in item),
                overlay.get("reelPlayerHeaderSupportedRenderers", {})
                .get("reelPlayerHeaderRenderer", {})
                .get("accessibility", {})
                .get("accessibilityData", {})
                .get("label", "")
                .split("@")[0]
                .strip()
            )
            name = self.generate_short_title(title)
            article = self.extract_article_tag(title)

            like_renderer = overlay.get("likeButton", {}).get("likeButtonRenderer", {})
            video_id = like_renderer.get("target", {}).get("videoId")
            if not video_id:
                self.logger.send("ERROR", "Нет video_id в reel_item_watch")
                return None
            image_url = self.dom_images.get(video_id)
            like_label = like_renderer.get("likeCountWithLikeText", {}).get("accessibility", {}).get("accessibilityData", {}).get("label", "")
            likes = int(re.search(r"([\d,]+)", like_label).group(1).replace(
                ",", "")) if re.search(r"([\d,]+)", like_label) else 0

            comment_btn = overlay.get("viewCommentsButton", {}).get("buttonRenderer", {})
            comment_label = comment_btn.get("accessibility", {}).get(
                "label", "") or comment_btn.get("text", {}).get("simpleText", "")
            comment_match = re.search(r"(\d+)", comment_label)
            comments = int(comment_match.group(1)) if comment_match else 0

            views = 0
            # publish_date = None
            engagement_panels = data.get("engagementPanels", [])
            for panel in engagement_panels:
                if panel.get("engagementPanelSectionListRenderer", {}).get("targetId") == "engagement-panel-structured-description":
                    items = panel.get("engagementPanelSectionListRenderer", {}).get("content", {}).get("structuredDescriptionContentRenderer", {}).get("items", [])
                    for item in items:
                        hdr = item.get("videoDescriptionHeaderRenderer", {})
                        views_text = hdr.get("views", {}).get("simpleText", "")
                        date_text = hdr.get("publishDate", {}).get("simpleText", "")
                        if views_text:
                            views = self.parse_views(views_text)
                        if date_text:
                            for fmt in ["%b %d, %Y", "%Y-%m-%d"]:
                                try:
                                    dt = datetime.strptime(date_text, fmt)
                                    publish_date = dt.strftime("%Y-%m-%d")
                                    break
                                except:
                                    continue
                        # # Извлечение описания
                        # desc_item = item.get("expandableVideoDescriptionBodyRenderer", {})
                        # desc_runs = desc_item.get("descriptionBodyText", {}).get("runs", [])
                        # if desc_runs:
                        #     description = " ".join(run.get("text", "") for run in desc_runs)

                    break
            # articles = self.extract_article_tag(title)

            # image_url = data.get("background", {}).get("cinematicContainerRenderer", {}).get("thumbnails", [{}])[0].get("url", None)

            return {
                "video_id": video_id,
                "link": f"https://www.youtube.com/shorts/{video_id}",
                "name": name,
                "amount_views": views,
                # "likes": likes,
                # "comments": comments,
                # "publish_date": publish_date,
                # "articles": articles,
                "image_url": image_url
            }
        except Exception as e:
            self.logger.send("ERROR", f"Ошибка извлечения из reel_item_watch: {e}")
            return None

    async def process_reel_item_watch(self, response):
        try:
            json_data = await response.json()
            video = self.extract_video_from_reel_item_watch(json_data)
            if video and video["video_id"] not in self.seen_video_ids:
                self.seen_video_ids.add(video["video_id"])
                self.collected_videos.append(video)
                # print("\n🟢 Получено видео из reel_item_watch:")
                # print(f"   ID: {video['video_id']}")
                # print(f"   Название: {video['name']}")
                # print(f"   Лайки: {video['likes']}")
                # print(f"   Комментарии: {video['comments']}")
                # print(f"   Просмотры: {video['amount_views']}")
                # print(f"   Дата: {video['publish_date']}")
                # print(f"   Ссылка: {video['link']}")
                # print(f"   Изображение: {video['image_url']}")
        except Exception as e:
            self.logger.send("ERROR", f"Ошибка обработки reel_item_watch: {e}")

    async def wait_for_reel_item_watch(self, timeout: int = 10):
        """Ждём появления ответа reel_item_watch."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            found = any(
                "youtubei/v1/reel/reel_item_watch" in r.url
                for r in getattr(self, "_recent_responses", [])
            )
            if found:
                self.logger.send("INFO", "📡 Получен ответ reel_item_watch")
                return True
            await asyncio.sleep(0.5)
        self.logger.send("ERROR", "⚠️ Не дождались reel_item_watch (возможно капча, но API всё равно работает)")
        return False

    async def handle_response(self, response):
        """
        Перехватываем ответы. Обрабатываем только reel_item_watch POST,
        добавляем задачу на обработку и сохраняем небольшой буфер (response_tasks).
        """
        try:
            url = response.url
            method = response.request.method if response.request else None
            if method != "POST":
                return

            if "youtubei/v1/reel/reel_item_watch" in url:
                task = asyncio.create_task(self.process_reel_item_watch(response))
                self.response_tasks.append(task)

        except Exception as e:
            self.logger.send("ERROR", f"Ошибка в handle_response: {e}")

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
            self.logger.send("ERROR", f"❌ Ошибка загрузки изображения {url}: {e}")
            return None

    async def upload_image(self, video_id: int, image_url: str, proxy: str = None):
        """Скачивает изображение (с прокси), но отправляет на сервер БЕЗ прокси."""
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

    async def parse_channel(self, url: str, channel_id: int, user_id: int, max_retries: int = 3, proxy_list: list = None):
        """
        Полный цикл парсинга канала по новой логике:
        - получаем ожидаемое количество видео из шапки канала (N videos)
        - кликаем первое видео → собираем reel_item_watch
        - возвращаемся на профиль, кликаем второе → собираем
        - снова открываем первое, затем жмём вниз для обхода остальных
        - НЕ используем скролл для подсчёта (только лёгкое извлечение превью с первого экрана)
        """
        self.proxy_list = proxy_list or []
        current_proxy_index = 0
        if not url.endswith('/shorts'):
            url = url.rstrip('/') + '/shorts'
        self.logger.send("INFO", f"Переход на канал: {url}")

        playwright = None
        browser = None
        context = None
        page = None

        async def get_proxy_config(proxy_str):
            try:
                if not proxy_str:
                    return None
                if "@" in proxy_str:
                    auth, host_port = proxy_str.split("@")
                    username, password = auth.split(":")
                    host, port = host_port.split(":")
                    return {"server": f"http://{host}:{port}", "username": username, "password": password}
                else:
                    host, port = proxy_str.split(":")
                    return {"server": f"http://{host}:{port}"}
            except Exception as e:
                self.logger.send("ERROR", f"Неверный формат прокси: {e}")
                return None

        async def create_browser_with_proxy(proxy_str, playwright):
            proxy_config = await get_proxy_config(proxy_str) if proxy_str else None
            browser = await playwright.chromium.launch(
                headless=False,
                args=[
                    "--headless=new",
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
            return browser, context, page

        current_proxy = random.choice(self.proxy_list) if self.proxy_list else None
        self.logger.send("INFO", f"Используемый прокси: {current_proxy}")

        all_videos_data = []

        try:
            playwright = await async_playwright().start()
            browser, context, page = await create_browser_with_proxy(current_proxy, playwright)

            # ШАГ 1: Открываем страницу
            self.logger.send("INFO", "🔍 Загружаем страницу Shorts…")
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Закрыть куки если есть
            try:
                accept_btn = await page.query_selector(
                    "button[aria-label*='Accept'][aria-label*='all'], button:has-text('Accept all'), button:has-text('Согласиться')"
                )
                if accept_btn:
                    await accept_btn.click()
                    await page.wait_for_timeout(1200)
                    self.logger.send("INFO", "Закрыта модалка с куки")
            except Exception:
                pass

            # --- НОВОЕ: читаем количество видео из шапки ---
            total_videos_expected = await self.get_video_count_from_header(page)
            if total_videos_expected is None:
                self.logger.send("WARNING", "Не смогли прочитать число видео из шапки — используем нижнюю оценку по видимым карточкам")
                try:
                    # лёгкий фолбэк: что видно без прокрутки
                    visible_cards = await page.eval_on_selector_all(
                        "ytd-rich-item-renderer, ytd-reel-item-renderer, ytm-shorts-lockup-view-model",
                        "els => els.length"
                    )
                    total_videos_expected = int(visible_cards) if visible_cards else 0
                except Exception:
                    total_videos_expected = 0

            if total_videos_expected == 0:
                self.logger.send("ERROR", "⚠️ Похоже, на канале нет видео или шапка недоступна")
                return []

            self.logger.send("INFO", f"📌 В шапке профиля указано {total_videos_expected} видео")

            # Немного соберём превью с первого экрана (без тяжёлого скролла)
            try:
                await self.extract_images_from_dom(page, url)
            except Exception:
                pass

            # Сброс состояния парсера
            self.seen_video_ids.clear()
            self.collected_videos.clear()
            self.response_tasks.clear()

            # Перехват ответов API
            page.on("response", lambda response: asyncio.create_task(self.handle_response(response)))

            item_locator = page.locator("ytd-rich-item-renderer, ytd-reel-item-renderer")
            count = await item_locator.count()
            self.logger.send("INFO", f"Локаторов в DOM (первый экран): {count}")

            if count < 1:
                self.logger.send("ERROR", "⚠️ Не найден ни один элемент ленты")
                return []

            # --- ШАГ A: Открываем первое видео и собираем reel_item_watch ---
            try:
                await item_locator.nth(0).locator("a[href*='/shorts/']").click()
            except Exception:
                await item_locator.nth(0).click()
            self.logger.send("INFO", "✅ Клик по первому рилсу выполнен")
            await asyncio.sleep(5)
            await asyncio.gather(*self.response_tasks, return_exceptions=True)
            self.response_tasks.clear()

            # --- ВОЗВРАТ В ПРОФИЛЬ ---
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(800)
            item_locator = page.locator("ytd-rich-item-renderer, ytd-reel-item-renderer")
            count = await item_locator.count()

            # --- ШАГ B: Открываем второе видео ---
            if count >= 2:
                try:
                    await item_locator.nth(1).locator("a[href*='/shorts/']").click()
                except Exception:
                    await item_locator.nth(1).click()
                self.logger.send("INFO", "✅ Клик по второму рилсу выполнен")
                await asyncio.sleep(5)
                await asyncio.gather(*self.response_tasks, return_exceptions=True)
                self.response_tasks.clear()

                # --- ВОЗВРАТ В ПРОФИЛЬ ---
                await page.goto(url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(800)
                item_locator = page.locator("ytd-rich-item-renderer, ytd-reel-item-renderer")
                count = await item_locator.count()
            else:
                self.logger.send("WARNING", "ℹ️ Нет второго видео в ленте")

            # Если всего 1–2 видео — сбор завершён
            if total_videos_expected <= 2:
                self.logger.send("INFO", "📌 Всего 1–2 видео — сбор завершён.")
            else:
                # --- ШАГ C: открываем первое снова и дважды жмём вниз (чтобы попасть на 3-й)
                self.logger.send("INFO", "🔁 Открываем первое видео снова и переходим вниз до 3-го")
                try:
                    await item_locator.nth(0).locator("a[href*='/shorts/']").click()
                except Exception:
                    await item_locator.nth(0).click()
                await asyncio.sleep(1)

                for _ in range(2):
                    next_btn = await page.query_selector("#navigation-button-down button")
                    if next_btn:
                        try:
                            await next_btn.click()
                        except Exception:
                            try:
                                await page.keyboard.press("ArrowDown")
                            except Exception:
                                pass
                    else:
                        try:
                            await page.keyboard.press("ArrowDown")
                        except Exception:
                            pass
                    await asyncio.sleep(3)
                    await asyncio.gather(*self.response_tasks, return_exceptions=True)
                    self.response_tasks.clear()

                remaining_to_collect = max(0, total_videos_expected - len(self.collected_videos))
                self.logger.send("INFO", f"⏭️ Будем щёлкать вниз и собирать ещё примерно {remaining_to_collect} видео")

                # --- основной цикл вниз до total_videos_expected ---
                while len(self.collected_videos) < total_videos_expected:
                    next_btn = await page.query_selector("#navigation-button-down button")
                    pressed = False
                    if next_btn:
                        try:
                            await next_btn.click()
                            pressed = True
                        except Exception:
                            pressed = False
                    if not pressed:
                        try:
                            await page.keyboard.press("ArrowDown")
                            pressed = True
                        except Exception:
                            self.logger.send("INFO", "⏭️ Не получилось нажать вниз, выходим")
                            break

                    await asyncio.sleep(3.0)
                    await asyncio.gather(*self.response_tasks, return_exceptions=True)
                    self.response_tasks.clear()

                    # на всякий случай отрубим потенциальный бесконечный цикл
                    if not pressed:
                        break

                    if len(self.collected_videos) >= total_videos_expected:
                        break

                # закрываем плеер
                try:
                    await page.keyboard.press("Escape")
                except Exception:
                    pass
                await page.wait_for_timeout(500)

            # Собираем финальный список с фолбэком для обложек
            all_videos_data = []
            for v in self.collected_videos:
                # фолбэк на случай отсутствия image_url
                try:
                    vid_from_link = v["link"].rstrip("/").rsplit("/", 1)[-1]
                except Exception:
                    vid_from_link = None
                image_url = v.get("image_url") or (f"https://i.ytimg.com/vi/{vid_from_link}/hqdefault.jpg" if vid_from_link else None)

                all_videos_data.append({
                    "link": v["link"],
                    "type": "youtube",
                    "name": v["name"],
                    "image": image_url,
                    "channel_id": channel_id,
                    "amount_views": v["amount_views"],
                })

            self.logger.send("INFO", f"✅ Собрано {len(all_videos_data)} из ожидаемых {total_videos_expected} видео")

        except Exception as main_error:
            self.logger.send("ERROR", f"Критическая ошибка: {main_error}")
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
                        self.logger.send("ERROR", f"Ошибка закрытия {name}: {e}")

        # --- Отправка/обновление на сервере + загрузка обложек ---
        processed_count = 0
        image_queue = []
        for video_data in all_videos_data:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    check_resp = await client.get(f"https://sn.dev-klick.cyou/api/v1/videos/?link={video_data['link']}")
                    is_new = False
                    video_id = None

                    if check_resp.status_code == 200:
                        res = check_resp.json()
                        vids = res.get("videos", [])
                        if vids:
                            video_id = vids[0]['id']
                            await client.patch(
                                f"https://sn.dev-klick.cyou/api/v1/videos/{video_id}",
                                json={
                                    "amount_views": video_data["amount_views"],
                                }
                            )
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        resp = await client.post("https://sn.dev-klick.cyou/api/v1/videos/", json=video_data)
                        resp.raise_for_status()
                        video_id = resp.json()["id"]
                        self.logger.send("INFO", f"✅ Создано новое видео {video_id}")
                        if video_data.get("image"):
                            image_queue.append((video_id, video_data["image"]))
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
                await asyncio.sleep(5.0)
            idx += 15

        self.logger.send("INFO", f"🎉 Парсинг завершён: {processed_count} видео обработано.")
