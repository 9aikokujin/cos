import re
import asyncio
import time
from typing import Optional, Dict, List, Union
import httpx
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import random
from datetime import datetime


class ShortsParser:
    def __init__(self):
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

    async def extract_images_from_dom(self, page, url: str):
        """Извлекает ссылки на изображения из DOM и подсчитывает общее количество видео"""
        print("🔍 Извлекаем изображения из DOM...")

        selectors = [
            "ytm-shorts-lockup-view-model img.ytCoreImageHost",  # Мобильная
            "ytd-rich-item-renderer img.yt-img-shadow",          # Десктопная
            "ytd-reel-item-renderer img",                        # Reel items
            "ytd-grid-video-renderer img"                        # Grid renderer
        ]

        total_videos = 0
        dom_images = {}

        for selector in selectors:
            try:
                img_elements = await page.query_selector_all(selector)
                print(f"Найдено {len(img_elements)} изображений по селектору: {selector}")

                for i, img_el in enumerate(img_elements[:50]):  # Берем первые 50 для надежности
                    try:
                        img_url = await img_el.get_attribute("src")
                        if img_url and "ytimg.com" in img_url:
                            # Извлекаем video_id из URL изображения (обычно в формате /vi/VIDEO_ID/)
                            video_id_match = re.search(r'/vi/([a-zA-Z0-9_-]{11})/', img_url)
                            if video_id_match:
                                video_id = video_id_match.group(1)
                                dom_images[video_id] = img_url
                                total_videos += 1
                                print(f"📸 Видео ID: {video_id} -> {img_url[:100]}...")
                    except Exception as e:
                        continue

                if total_videos > 0:
                    break  # Если нашли изображения, используем этот селектор
            except Exception as e:
                print(f"Ошибка при поиске по селектору {selector}: {e}")
                continue

        # Если не нашли по основным селекторам, пробуем общий поиск всех img
        if not dom_images:
            try:
                all_imgs = await page.query_selector_all("img[src*='ytimg.com']")
                print(f"Общий поиск: найдено {len(all_imgs)} изображений ytimg")
                for i, img_el in enumerate(all_imgs[:30]):
                    img_url = await img_el.get_attribute("src")
                    video_id_match = re.search(r'/vi/([a-zA-Z0-9_-]{11})/', img_url)
                    if video_id_match:
                        video_id = video_id_match.group(1)
                        if video_id not in dom_images:
                            dom_images[video_id] = img_url
                            total_videos += 1
            except Exception as e:
                print(f"Ошибка общего поиска изображений: {e}")

        self.dom_images = dom_images
        print(f"✅ Из DOM извлечено {len(dom_images)} изображений, общее видео: {total_videos}")
        return total_videos

    async def scroll_until(self, page, url: str, selector: str, delay: float = 4.0, max_idle_rounds: int = 5):
        """Модифицированный скролл - теперь также извлекаем изображения из DOM"""
        prev_count = 0
        idle_rounds = 0
        max_scroll_attempts = 3

        for attempt in range(max_scroll_attempts):
            print(f"Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

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
                    print("Обнаружена CAPTCHA на странице")
                    return 0

                # ИЗВЛЕКАЕМ ИЗОБРАЖЕНИЯ ИЗ DOM ПОКА СКРОЛЛИМ
                await self.extract_images_from_dom(page, url)

                try:
                    current_count = await page.eval_on_selector_all(selector, "els => els.length")
                    print(f"Текущее количество элементов по селектору '{selector}': {current_count}")

                    if current_count == prev_count:
                        idle_rounds += 1
                        if idle_rounds >= max_idle_rounds:
                            print(f"Достигнут конец списка видео профиля {url}")
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
                    print("Timeout при оценке элементов, продолжаем...")
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

            like_renderer = overlay.get("likeButton", {}).get("likeButtonRenderer", {})
            video_id = like_renderer.get("target", {}).get("videoId")
            if not video_id:
                print("Нет video_id в reel_item_watch")
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
            publish_date = None
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
                        # Извлечение описания
                        # desc_item = item.get("expandableVideoDescriptionBodyRenderer", {})
                        # desc_runs = desc_item.get("descriptionBodyText", {}).get("runs", [])
                        # if desc_runs:
                        #     description = " ".join(run.get("text", "") for run in desc_runs)
                        #     print(f"Описание: {description}")

                    break
            articles = self.extract_article_tag(title)

            # image_url = data.get("background", {}).get("cinematicContainerRenderer", {}).get("thumbnails", [{}])[0].get("url", None)

            return {
                "video_id": video_id,
                "link": f"https://www.youtube.com/shorts/{video_id}",
                "name": name,
                "amount_views": views,
                "likes": likes,
                "comments": comments,
                "publish_date": publish_date,
                "articles": articles,
                "image_url": image_url
            }
        except Exception as e:
            print(f"Ошибка извлечения из reel_item_watch: {e}")
            return None

    async def process_reel_item_watch(self, response):
        try:
            json_data = await response.json()
            video = self.extract_video_from_reel_item_watch(json_data)
            if video and video["video_id"] not in self.seen_video_ids:
                self.seen_video_ids.add(video["video_id"])
                self.collected_videos.append(video)
                print("\n🟢 Получено видео из reel_item_watch:")
                print(f"   ID: {video['video_id']}")
                print(f"   Название: {video['name']}")
                print(f"   Лайки: {video['likes']}")
                print(f"   Комментарии: {video['comments']}")
                print(f"   Просмотры: {video['amount_views']}")
                print(f"   Дата: {video['publish_date']}")
                print(f"   Ссылка: {video['link']}")
                print(f"   Изображение: {video['image_url']}")
        except Exception as e:
            print(f"Ошибка обработки reel_item_watch: {e}")

    async def wait_for_reel_item_watch(self, timeout: int = 10):
        """Ждём появления ответа reel_item_watch."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            found = any(
                "youtubei/v1/reel/reel_item_watch" in r.url
                for r in getattr(self, "_recent_responses", [])
            )
            if found:
                print("📡 Получен ответ reel_item_watch")
                return True
            await asyncio.sleep(0.5)
        print("⚠️ Не дождались reel_item_watch (возможно капча, но API всё равно работает)")
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
            print(f"Ошибка в handle_response: {e}")

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
        """Скачивает изображение (с прокси), но отправляет на сервер БЕЗ прокси."""
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
        """
        Полный цикл парсинга канала по новой логике:
        - скроллим ленту, считаем total_videos
        - кликаем на 1-й (сбор reel_item_watch)
        - закрываем, кликаем на 2-й (сбор)
        - открываем 1-й снова, кликаем вниз 2 раза -> получаем 3-й
        - далее кликаем вниз последовательно и собираем все оставшиеся
        ВАЖНО: НИКАКИХ page.reload(), никаких переходов по ссылкам.
        """
        self.proxy_list = proxy_list or []
        current_proxy_index = 0
        if not url.endswith('/shorts'):
            url = url.rstrip('/') + '/shorts'
        print(f"Переход на канал: {url}")

        playwright = None
        browser = None
        context = None
        page = None

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
        print(f"Используемый прокси: {current_proxy}")

        all_videos_data = []

        try:
            playwright = await async_playwright().start()
            browser, context, page = await create_browser_with_proxy(current_proxy, playwright)

            # ШАГ 1: Открываем страницу и скроллим
            print("🔍 Загружаем страницу Shorts…")
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Закрыть куки если есть
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
            print(f"📊 Из DOM найдено {total_videos_from_dom} видео/изображений")

            if total_videos_from_dom == 0:
                print("⚠️ Нет видео для парсинга")
                return []

            print("Пропускаем reload, чтобы сохранить ленту Shorts")

            # Сброс состояния парсера
            self.seen_video_ids.clear()
            self.collected_videos.clear()
            self.response_tasks.clear()

            # Регистрируем перехватчик ответов
            page.on("response", lambda response: asyncio.create_task(self.handle_response(response)))

            item_locator = page.locator("ytd-rich-item-renderer, ytd-reel-item-renderer")
            # проверим, что есть минимум 1 и 2 элемента
            count = await item_locator.count()
            print(f"Локаторов в DOM: {count}")

            if count < 1:
                print("⚠️ Не найден ни один элемент ленты")
                return []

            # --- ШАГ A: Открываем первое видео и собираем reel_item_watch ---
            try:
                await item_locator.nth(0).locator("a[href*='/shorts/']").click()
            except Exception:
                await item_locator.nth(0).click()
            print("✅ Клик по первому рилсу выполнен")
            await asyncio.sleep(5)
            await asyncio.gather(*self.response_tasks, return_exceptions=True)
            self.response_tasks.clear()

            # --- ВОЗВРАТ В ПРОФИЛЬ --- вместо Escape
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(1000)  # небольшая пауза
            item_locator = page.locator("ytd-rich-item-renderer, ytd-reel-item-renderer")
            count = await item_locator.count()

            # --- ШАГ B: Открываем второе видео ---
            if count >= 2:
                try:
                    await item_locator.nth(1).locator("a[href*='/shorts/']").click()
                except Exception:
                    await item_locator.nth(1).click()
                print("✅ Клик по второму рилсу выполнен")
                await asyncio.sleep(5)
                await asyncio.gather(*self.response_tasks, return_exceptions=True)
                self.response_tasks.clear()

                # --- ВОЗВРАТ В ПРОФИЛЬ ---
                await page.goto(url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(1000)
                item_locator = page.locator("ytd-rich-item-renderer, ytd-reel-item-renderer")
                count = await item_locator.count()
            else:
                print("ℹ️ Нет второго видео в ленте")

            # Если всего 2 видео — всё, иначе продолжаем по описанной схеме
            if total_videos_from_dom <= 2:
                print("📌 Всего 1-2 видео — сбор завершён.")
            else:
                # --- ШАГ C: Открываем первое снова, чтобы "установить" контекст, затем кликаем вниз 2 раза (чтобы попасть на 3-е)
                print("🔁 Открываем первое видео снова и переходим вниз до 3-го")
                try:
                    await item_locator.nth(0).locator("a[href*='/shorts/']").click()
                except Exception:
                    await item_locator.nth(0).click()
                await asyncio.sleep(1)  # короткая пауза
                # два клика вниз, чтобы пропустить 2-е
                for down_click in range(2):
                    # на странице плеера кнопка вниз:
                    next_btn = await page.query_selector("#navigation-button-down button")
                    if not next_btn:
                        try:
                            await page.keyboard.press("ArrowDown")
                        except:
                            pass
                    else:
                        try:
                            await next_btn.click()
                        except:
                            try:
                                await page.keyboard.press("ArrowDown")
                            except:
                                pass
                    await asyncio.sleep(3)  # ждём API ответ
                    await asyncio.gather(*self.response_tasks, return_exceptions=True)
                    self.response_tasks.clear()

                remaining_to_collect = total_videos_from_dom - len(self.collected_videos)
                print(f"⏭️ Будем щёлкать вниз и собирать ещё примерно {remaining_to_collect} видео")

                while len(self.collected_videos) < total_videos_from_dom:
                    next_btn = await page.query_selector("#navigation-button-down button")
                    if not next_btn:
                        try:
                            await page.keyboard.press("ArrowDown")
                        except:
                            print("⏭️ Не получилось нажать вниз, выходим")
                            break
                    else:
                        try:
                            await next_btn.click()
                        except:
                            try:
                                await page.keyboard.press("ArrowDown")
                            except:
                                print("⏭️ Не получилось нажать вниз, выходим")
                                break

                    # дождёмся ответа
                    await asyncio.sleep(3.0)
                    await asyncio.gather(*self.response_tasks, return_exceptions=True)
                    self.response_tasks.clear()

                    if len(self.collected_videos) >= total_videos_from_dom:
                        break

                # закрываем плеер в конце
                try:
                    await page.keyboard.press("Escape")
                except:
                    pass
                await page.wait_for_timeout(500)

            # Собираем финальный список
            all_videos_data = [
                {
                    "link": v["link"],
                    "type": "youtube",
                    "name": v["name"],
                    "image": v["image_url"],
                    "articles": v["articles"],
                    "channel_id": channel_id,
                    "amount_views": v["amount_views"],
                    "amount_likes": v["likes"],
                    "amount_comments": v["comments"],
                    "date_published": v["publish_date"]
                }
                for v in self.collected_videos
            ]

            print(f"✅ Собрано {len(all_videos_data)} из {total_videos_from_dom} видео")

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

        processed_count = 0
        image_queue = []
        for video_data in all_videos_data:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    print("INFO", f"🔍 Проверка видео: {video_data['link']}")
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
                                    "link": video_data["link"],
                                    "type": "youtube",
                                    "name": video_data["name"],
                                    "image": video_data["image"],
                                    "articles": video_data["articles"],
                                    "channel_id": channel_id,
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
                        print("INFO", f"✅ Создано новое видео {video_id}")
                        if video_data.get("image"):
                            image_queue.append((video_id, video_data["image"]))
                processed_count += 1
            except Exception as e:
                print("ERROR", f"⚠️ Ошибка при обработке {video_data.get('link')}: {e}")

        print("INFO", f"📦 Всего обработано {processed_count} видео, ожидают загрузки {len(image_queue)} обложек.")

        # --- Загрузка изображений ---
        idx = 0
        while idx < len(image_queue):
            proxy = proxy_list[current_proxy_index] if proxy_list else None
            current_proxy_index = (current_proxy_index + 1) % len(proxy_list) if proxy_list else 0
            batch = image_queue[idx:idx + 15]
            print("INFO", f"🖼️ Загружаем {len(batch)} изображений через {proxy or 'без прокси'}")

            for vid, img_url in batch:
                try:
                    status, _ = await self.upload_image(vid, img_url, proxy=proxy)
                    print("INFO", f"{'✅' if status == 200 else '⚠️'} Фото для видео {vid} → статус {status}")
                except Exception as e:
                    print("ERROR", f"❌ Ошибка загрузки фото {vid}: {e}")
                await asyncio.sleep(3.0)
            idx += 15

        print("INFO", f"🎉 Парсинг завершён: {processed_count} видео обработано.")


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
        # "cpeFm6Dh5x:bQXTp4e1gf@45.150.35.111:22684",
        "K6dlqo2Xbn:KJ7TE9kPO7@45.150.35.51:49586",
        "db2JltFuja:8MItiT5T12@45.150.35.10:58894",
        # "79zEDvbAVA:xJBsip0IQK@45.150.35.4:58129",
        "mBQnv9UCPd:e3VkzkB9p5@45.150.35.74:55101",
        "IDWsfoHdf1:z6d3r0tnzM@45.150.35.244:42679",
    ]
    parser = ShortsParser()
    url = "https://www.youtube.com/@nastya.beomaa"
    await parser.parse_channel(url, channel_id=12, user_id=1,
                               proxy_list=proxy_list)

if __name__ == "__main__":
    asyncio.run(main())
