import re
import asyncio
import httpx
from typing import Union
# from urllib.parse import urlparse
from playwright.async_api import async_playwright
import random
from utils.logger import TCPLogger


class ShortsParser:
    def __init__(self, logger: TCPLogger):
        self.current_proxy_index = 0
        self.logger = logger

    def parse_views(self, text: str) -> int:
        """Преобразует текст просмотров в число, поддерживает английские и арабские обозначения"""
        if not text:
            self.logger.send("INFO", "Текст просмотров пустой")
            return 0

        original_text = text
        text = text.strip()
        self.logger.send("INFO", f"Парсинг просмотров, исходный текст: {original_text}")

        # Удаляем всё, кроме цифр, точек, пробелов и арабских/латинских суффиксов
        # Сначала попробуем обработать арабские обозначения
        arabic_patterns = [
            (r"([\d,.]+)\s*ألف", 1_000),      # "24 ألف" → 24 * 1000
            (r"([\d,.]+)\s*مليون", 1_000_000), # "1.5 مليون" → 1.5 * 1_000_000
        ]

        for pattern, multiplier in arabic_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                num_str = match.group(1).replace(",", "").replace(" ", "")
                try:
                    num = float(num_str)
                    return int(num * multiplier)
                except ValueError:
                    continue

        # Если арабские шаблоны не сработали — пробуем латинские (как раньше)
        clean_text = (
            text.upper()
            .replace("VIEWS", "")
            .replace("VIEW", "")
            .replace("مشاهدة", "")
            .replace("مشاهدات", "")
            .replace(",", "")
            .replace(" ", "")
        )

        if clean_text.endswith("K"):
            try:
                return int(float(clean_text[:-1]) * 1_000)
            except ValueError:
                pass
        elif clean_text.endswith("M"):
            try:
                return int(float(clean_text[:-1]) * 1_000_000)
            except ValueError:
                pass
        else:
            # Удаляем всё, кроме цифр и точки (на случай, если осталось что-то вроде "1,234")
            digits_only = re.sub(r"[^\d.]", "", clean_text)
            if digits_only:
                try:
                    return int(float(digits_only))
                except ValueError:
                    pass

        self.logger.send("WARNING", f"Не удалось распарсить просмотры из текста: {original_text}")
        return 0

    async def scroll_until(self, page, url: str, selector: str, delay: float = 5.0, max_idle_rounds: int = 5):
        """Скроллит страницу, пока не загрузятся все видео"""
        prev_count = 0
        idle_rounds = 0
        max_scroll_attempts = 3

        for attempt in range(max_scroll_attempts):
            self.logger.send("INFO", f"Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

            while True:
                scroll_height = await page.evaluate("document.body.scrollHeight")
                scroll_y = await page.evaluate("window.scrollY")
                window_height = await page.evaluate("window.innerHeight")

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

                captcha = await page.query_selector("text=CAPTCHA")
                if captcha:
                    self.logger.send("ERROR", "Обнаружена CAPTCHA на странице")
                    break

                page_content = await page.content()
                self.logger.send("INFO", f"Длина содержимого страницы: {len(page_content)} символов")
                with open(f"page_attempt_{attempt + 1}.html", "w", encoding="utf-8") as f:
                    f.write(page_content)
                self.logger.send("INFO", f"Сохранено содержимое страницы в page_attempt_{attempt + 1}.html")

                current_count = await page.eval_on_selector_all(selector, "els => els.length")
                self.logger.send("INFO", f"Текущее количество элементов по селектору '{selector}': {current_count}")

                if current_count == prev_count:
                    idle_rounds += 1
                    if idle_rounds >= max_idle_rounds:
                        self.logger.send("INFO", f"Достигнут конец списка видео профиля {url}")
                        self.logger.send("INFO", f"Спарсил все видео в количестве {current_count}")
                        break
                else:
                    idle_rounds = 0
                    prev_count = current_count

                is_at_bottom = await page.evaluate("""
                    () => (window.innerHeight + window.scrollY) >= document.body.scrollHeight;
                """)
                self.logger.send("INFO", f"Находится ли внизу страницы: {is_at_bottom}")
                if is_at_bottom and idle_rounds >= max_idle_rounds:
                    self.logger.send("INFO", f"Достигнут конец страницы для {url}")
                    break

        return prev_count

    async def parse_channel(self, url: str, channel_id: int, user_id: int, max_retries: int = 3, proxy_list: list = None):
        """Парсит канал YouTube Shorts"""
        self.proxy_list = proxy_list or []
        if not url.endswith('/shorts'):
            if url.endswith('/'):
                url = url + 'shorts'
            else:
                url = url + '/shorts'
        self.logger.send("INFO", f"Переход на канал {url}")

        # Объявляем все ресурсы заранее, чтобы они были доступны в finally
        playwright = None
        browser = None
        context = None
        page = None

        # --- Вспомогательные функции ---
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
                self.logger.send("INFO", f"Неверный формат прокси '{proxy_str}': {str(e)}")
                return None

        async def create_browser_with_proxy(proxy_str, playwright):
            proxy_config = await get_proxy_config(proxy_str) if proxy_str else None
            self.logger.send("INFO", f"Создаём браузер с прокси: {proxy_config}")
            browser = await playwright.chromium.launch(
                headless=True,
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
            return browser, context, page  # ← возвращаем context!

        # --- Основной парсинг ---
        current_proxy = random.choice(self.proxy_list) if self.proxy_list else None
        self.logger.send("INFO", f"Используемый прокси: {current_proxy}")

        all_videos_data = []

        try:
            playwright = await async_playwright().start()
            browser, context, page = await create_browser_with_proxy(current_proxy, playwright)

            for attempt in range(1, max_retries + 1):
                try:
                    self.logger.send("INFO", f"Попытка загрузки страницы {url}, попытка {attempt}/{max_retries}")
                    await page.goto(url, wait_until="networkidle", timeout=60000)
                    self.logger.send("INFO", f"🌐 Открыл профиль {url} через прокси {current_proxy}")

                    # Обработка куки
                    try:
                        cookie_popup = await page.query_selector("div.qqtRac")
                        if cookie_popup:
                            accept_button = await page.query_selector("button[aria-label='Accept all']")
                            if accept_button:
                                await accept_button.click()
                                await page.wait_for_timeout(2000)
                                self.logger.send("INFO", "Нажата кнопка 'Accept all'")
                            else:
                                self.logger.send("WARNING", "Кнопка 'Accept all' не найдена")
                    except Exception as e:
                        self.logger.send("ERROR", f"Ошибка при обработке окна с куки: {e}")

                    # Сохранение HTML для отладки
                    page_content = await page.content()
                    with open(f"page_initial_{attempt}.html", "w", encoding="utf-8") as f:
                        f.write(page_content)
                    self.logger.send("INFO", f"Сохранено начальное содержимое страницы в page_initial_{attempt}.html")

                    # Поиск видео
                    # Проверяем разные селекторы
                    selectors = [
                        "ytm-shorts-lockup-view-model",  # Мобильная версия
                        "ytd-rich-item-renderer",  # Десктопная версия
                        "div#items ytm-shorts-lockup-view-model-v2",  # Полный путь для мобильной
                        "ytd-grid-video-renderer"  # Альтернатива для десктопной версии
                    ]

                    for selector in selectors:
                        try:
                            self.logger.send("INFO", f"Ожидание селектора '{selector}'")
                            await page.wait_for_selector(selector, timeout=10000)
                            count = await page.eval_on_selector_all(selector, "els => els.length")
                            self.logger.send("INFO", f"Найдено {count} элементов по селектору '{selector}'")
                        except Exception as e:
                            self.logger.send("WARNING", f"Селектор '{selector}' не найден: {e}")

                    # Используем основной селектор для прокрутки и парсинга
                    selector = "ytm-shorts-lockup-view-model"
                    await self.scroll_until(page, url, selector=selector, delay=5.0)
                    videos = await page.query_selector_all(selector)
                    self.logger.send("INFO", f"🎬 Найдено {len(videos)} видео в профиле {url} по селектору '{selector}'")

                    for video in videos:
                        try:
                            link_el = await video.query_selector("a.shortsLockupViewModelHostEndpoint")
                            video_url = await link_el.get_attribute("href") if link_el else None
                            full_url = f"https://www.youtube.com{video_url}" if video_url else ""
                            if not full_url or full_url == "https://www.youtube.com":
                                self.logger.send("WARNING", "Пропущено видео без URL")
                                continue

                            title_el = await video.query_selector("h3 a")
                            title = await title_el.get_attribute("title") if title_el else ""
                            video_title = title[:30].rsplit(" ", 1)[0] if len(title) > 30 else title

                            views_el = await video.query_selector(".shortsLockupViewModelHostOutsideMetadataSubhead span")
                            views_text = await views_el.inner_text() if views_el else "0"
                            views = self.parse_views(views_text)

                            img_el = await video.query_selector("img.ytCoreImageHost")
                            img_url = await img_el.get_attribute("src") if img_el else None
                            self.logger.send("INFO", f"URL изображения: {img_url}")

                            all_videos_data.append({
                                "type": "youtube",
                                "channel_id": channel_id,
                                "link": full_url,
                                "name": video_title,
                                "amount_views": views,
                                "image_url": img_url
                            })
                            self.logger.send("INFO", f"Добавлено видео: {video_title} ({full_url})")
                        except Exception as e:
                            self.logger.send("ERROR", f"Ошибка парсинга видео: {e}")
                            continue
                    break  # Успех — выходим из цикла попыток

                except Exception as e:
                    self.logger.send("WARNING", f"Попытка {attempt} не удалась: {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(5)
                    else:
                        raise

        except Exception as main_error:
            self.logger.send("ERROR", f"Критическая ошибка в parse_channel: {main_error}")
            raise

        finally:
            # Закрываем в строгом порядке: page → context → browser → playwright
            close_errors = []
            if page:
                try:
                    await page.close()
                except Exception as e:
                    close_errors.append(f"page.close(): {e}")

            if context:
                try:
                    await context.close()
                except Exception as e:
                    close_errors.append(f"context.close(): {e}")

            if browser:
                try:
                    await browser.close()
                except Exception as e:
                    close_errors.append(f"browser.close(): {e}")

            if playwright:
                try:
                    await playwright.stop()
                except Exception as e:
                    close_errors.append(f"playwright.stop(): {e}")

            if close_errors:
                self.logger.send("WARNING", f"Ошибки при закрытии ресурсов Playwright: {close_errors}")
            else:
                self.logger.send("INFO", "Все ресурсы Playwright успешно закрыты")

        # --- Этап 2: обработка видео + качаем картинки с каруселью прокси ---
        async def download_image(url: str, proxy: str = None) -> Union[bytes, None]:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    self.logger.send("INFO", f"Успешно загружено изображение: {url}")
                    return resp.content
            except Exception as e:
                self.logger.send("ERROR", f"❌ Ошибка загрузки {url}: {e}")
                return None

        async def upload_image(video_id: int, image_url: str, proxy: str = None):
            image_bytes = await download_image(image_url, proxy=proxy)
            if not image_bytes:
                self.logger.send("ERROR", f"Не удалось скачать изображение для видео {video_id}")
                return None, "Download failed"

            file_name = image_url.split("/")[-1].split("?")[0]
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {"file": (file_name, image_bytes, "image/jpeg")}
                try:
                    resp = await client.post(
                        f"https://cosmeya.dev-klick.cyou/api/v1/videos/{video_id}/upload-image/",
                        files=files,
                    )
                    resp.raise_for_status()
                    self.logger.send("INFO", f"✅ Фото для видео {video_id} загружено")
                    return resp.status_code, resp.text
                except Exception as e:
                    self.logger.send("ERROR", f"⚠️ Ошибка загрузки фото для видео {video_id}: {e}")
                    return None, str(e)

        processed_count = 0
        image_queue = []

        # Шаг 1: отправляем метаданные видео в API
        for video_data in all_videos_data:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    self.logger.send("INFO", f"Проверка видео по ссылке: {video_data['link']}")
                    check_resp = await client.get(
                        f"https://cosmeya.dev-klick.cyou/api/v1/videos/?link={video_data['link']}"
                    )
                    video_id = None
                    is_new = False

                    if check_resp.status_code == 200:
                        result = check_resp.json()
                        videos = result.get("videos", [])
                        if videos:
                            video_id = videos[0]['id']
                            self.logger.send("INFO", f"Видео уже существует, ID: {video_id}, обновляем просмотры")
                            update_resp = await client.patch(
                                f"https://cosmeya.dev-klick.cyou/api/v1/videos/{video_id}",
                                json={"amount_views": video_data["amount_views"]}
                            )
                            update_resp.raise_for_status()
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        self.logger.send("INFO", f"Создаём новое видео: {video_data['name']}")
                        create_resp = await client.post(
                            "https://cosmeya.dev-klick.cyou/api/v1/videos/",
                            json=video_data
                        )
                        create_resp.raise_for_status()
                        video_id = create_resp.json()['id']
                        self.logger.send("INFO", f"Создано видео с ID: {video_id}")
                        if video_data.get("image_url"):
                            image_queue.append((video_id, video_data["image_url"]))
                            self.logger.send("INFO", f"Добавлено изображение в очередь: {video_data['image_url']}")
                processed_count += 1
            except Exception as e:
                self.logger.send("ERROR", f"Ошибка при обработке {video_data.get('link')}: {e}")
                continue

        # Шаг 2: качаем фото пакетами по 15/прокси
        idx = 0
        while idx < len(image_queue):
            if not self.proxy_list:
                proxy = None
            else:
                proxy = self.proxy_list[self.current_proxy_index]
                self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)

            batch = image_queue[idx: idx + 15]
            self.logger.send("INFO", f"🌐 Прокси {proxy}: качаем {len(batch)} фото")

            for video_id, image_url in batch:
                try:
                    status, resp_text = await upload_image(video_id, image_url, proxy=proxy)
                    if status == 200:
                        self.logger.send("INFO", f"✅ Фото для видео {video_id} загружено")
                    else:
                        self.logger.send("ERROR", f"⚠️ Фото для видео {video_id} ошибка {status}")
                except Exception as e:
                    self.logger.send("ERROR", f"❌ Ошибка загрузки фото для {video_id}: {e}")
                await asyncio.sleep(5.0)

            idx += 15

            if idx < len(image_queue) and self.current_proxy_index == 0 and self.proxy_list:
                self.logger.send("WARNING", "⏳ Все прокси использованы, ждём 1 минуту...")
                await asyncio.sleep(60)

        self.logger.send("INFO", f"✅ Успешно обработано {processed_count} видео")
