import re
import asyncio
import httpx
from typing import Union
from urllib.parse import urlparse
from playwright.async_api import async_playwright
import random


class ShortsParser:
    def __init__(self, proxy_list: list = None):
        self.proxy_list = proxy_list or []
        self.current_proxy_index = 0

    def parse_views(self, text: str) -> int:
        """Преобразует текст просмотров в число"""
        if not text:
            print("DEBUG: Текст просмотров пустой")
            print("Текст просмотров пустой")
            return 0
        text = text.strip().upper().replace("VIEWS", "").replace(",", "").replace(" ", "")
        print(f"DEBUG: Парсинг просмотров, текст: {text}")
        print(f"Парсинг просмотров, текст: {text}")
        if text.endswith("K"):
            return int(float(text[:-1]) * 1_000)
        elif text.endswith("M"):
            return int(float(text[:-1]) * 1_000_000)
        else:
            return int(re.sub(r"[^\d]", "", text))

    async def scroll_until(self, page, url: str, selector: str, delay: float = 5.0, max_idle_rounds: int = 5):
        """Скроллит страницу, пока не загрузятся все видео"""
        prev_count = 0
        idle_rounds = 0
        max_scroll_attempts = 3

        for attempt in range(max_scroll_attempts):
            print(f"INFO: Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")
            print(f"Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

            while True:
                scroll_height = await page.evaluate("document.body.scrollHeight")
                scroll_y = await page.evaluate("window.scrollY")
                window_height = await page.evaluate("window.innerHeight")
                print(f"DEBUG: Высота страницы: {scroll_height}, Прокрутка: {scroll_y}, Высота окна: {window_height}")
                print(f"Высота страницы: {scroll_height}, Прокрутка: {scroll_y}, Высота окна: {window_height}")

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
                    print("ERROR: Обнаружена CAPTCHA на странице")
                    print("Обнаружена CAPTCHA на странице")
                    break

                page_content = await page.content()
                print(f"DEBUG: Длина содержимого страницы: {len(page_content)} символов")
                print(f"Длина содержимого страницы: {len(page_content)} символов")
                with open(f"page_attempt_{attempt + 1}.html", "w", encoding="utf-8") as f:
                    f.write(page_content)
                print(f"DEBUG: Сохранено содержимое страницы в page_attempt_{attempt + 1}.html")
                print(f"Сохранено содержимое страницы в page_attempt_{attempt + 1}.html")

                current_count = await page.eval_on_selector_all(selector, "els => els.length")
                print(f"INFO: Текущее количество элементов по селектору '{selector}': {current_count}")
                print(f"Текущее количество элементов по селектору '{selector}': {current_count}")

                if current_count == prev_count:
                    idle_rounds += 1
                    if idle_rounds >= max_idle_rounds:
                        print(f"INFO: Достигнут конец списка видео профиля {url}")
                        print(f"Достигнут конец списка видео профиля {url}")
                        print(f"INFO: Спарсил все видео в количестве {current_count}")
                        print(f"Спарсил все видео в количестве {current_count}")
                        break
                else:
                    idle_rounds = 0
                    prev_count = current_count

                is_at_bottom = await page.evaluate("""
                    () => (window.innerHeight + window.scrollY) >= document.body.scrollHeight;
                """)
                print(f"DEBUG: Находится ли внизу страницы: {is_at_bottom}")
                print(f"Находится ли внизу страницы: {is_at_bottom}")
                if is_at_bottom and idle_rounds >= max_idle_rounds:
                    print(f"INFO: Достигнут конец страницы для {url}")
                    print(f"Достигнут конец страницы для {url}")
                    break

        return prev_count

    async def parse_channel(self, url: str, channel_id: int, user_id: int, max_retries: int = 3):
        """Парсит канал YouTube Shorts"""
        if not url.endswith('/shorts'):
            if url.endswith('/'):
                url = url + 'shorts'
            else:
                url = url + '/shorts'
        print(f"INFO: Переход на канал {url}")
        print(f"Переход на канал {url}")

        # --- Утилиты для Playwright ---
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
                print(f"ERROR: Неверный формат прокси '{proxy_str}': {str(e)}")
                print(f"Неверный формат прокси '{proxy_str}': {str(e)}")
                return None

        async def create_browser_with_proxy(proxy_str):
            proxy_config = await get_proxy_config(proxy_str) if proxy_str else None
            p = await async_playwright().start()
            browser = await p.chromium.launch(
                headless=False,  # Для отладки
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized"
                ],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                # proxy=proxy_config
            )
            page = await context.new_page()
            # Логируем HTTP-запросы
            async def log_request(request):
                print(f"DEBUG: HTTP Request: {request.method} {request.url}")
                print(f"HTTP Request: {request.method} {request.url}")
            async def log_response(response):
                print(f"DEBUG: HTTP Response: {response.url} Status: {response.status}")
                print(f"HTTP Response: {response.url} Status: {response.status}")
            page.on("request", log_request)
            page.on("response", log_response)
            return browser, page

        # --- Этап 1: собираем список видео ---
        current_proxy = random.choice(self.proxy_list) if self.proxy_list else None
        print(f"DEBUG: Используемый прокси: {current_proxy}")
        print(f"Используемый прокси: {current_proxy}")
        browser, page = await create_browser_with_proxy(current_proxy)
        if not browser:
            print("ERROR: Не удалось создать браузер даже для первой прокси")
            print("Не удалось создать браузер даже для первой прокси")
            raise Exception("Не удалось создать браузер даже для первой прокси")

        all_videos_data = []
        try:
            for attempt in range(1, max_retries + 1):
                try:
                    print(f"DEBUG: Попытка загрузки страницы {url}, попытка {attempt}/{max_retries}")
                    print(f"Попытка загрузки страницы {url}, попытка {attempt}/{max_retries}")
                    await page.goto(url, wait_until="networkidle", timeout=60000)
                    print(f"INFO: 🌐 Открыл профиль {url} через прокси {current_proxy}")
                    print(f"🌐 Открыл профиль {url} через прокси {current_proxy}")

                    # Сохраняем начальное содержимое страницы
                    page_content = await page.content()
                    print(f"DEBUG: Длина начального содержимого страницы: {len(page_content)} символов")
                    print(f"Длина начального содержимого страницы: {len(page_content)} символов")
                    with open(f"page_initial_{attempt}.html", "w", encoding="utf-8") as f:
                        f.write(page_content)
                    print(f"DEBUG: Сохранено начальное содержимое страницы в page_initial_{attempt}.html")
                    print(f"Сохранено начальное содержимое страницы в page_initial_{attempt}.html")

                    # Проверяем разные селекторы
                    selectors = [
                        "ytm-shorts-lockup-view-model",  # Мобильная версия
                        "ytd-rich-item-renderer",  # Десктопная версия
                        "div#items ytm-shorts-lockup-view-model-v2",  # Полный путь для мобильной
                        "ytd-grid-video-renderer"  # Альтернатива для десктопной версии
                    ]

                    for selector in selectors:
                        try:
                            print(f"DEBUG: Ожидание селектора '{selector}'")
                            print(f"Ожидание селектора '{selector}'")
                            await page.wait_for_selector(selector, timeout=10000)
                            count = await page.eval_on_selector_all(selector, "els => els.length")
                            print(f"INFO: Найдено {count} элементов по селектору '{selector}'")
                            print(f"Найдено {count} элементов по селектору '{selector}'")
                        except Exception as e:
                            print(f"WARNING: Селектор '{selector}' не найден: {e}")
                            print(f"Селектор '{selector}' не найден: {e}")

                    # Используем основной селектор для прокрутки и парсинга
                    selector = "ytm-shorts-lockup-view-model"
                    await self.scroll_until(page, url, selector=selector, delay=5.0)
                    videos = await page.query_selector_all(selector)
                    print(f"INFO: 🎬 Найдено {len(videos)} видео в профиле {url} по селектору '{selector}'")
                    print(f"🎬 Найдено {len(videos)} видео в профиле {url} по селектору '{selector}'")

                    for video in videos:
                        try:
                            link_el = await video.query_selector("a.shortsLockupViewModelHostEndpoint")
                            video_url = await link_el.get_attribute("href") if link_el else None
                            full_url = f"https://www.youtube.com{video_url}" if video_url else ""
                            print(f"DEBUG: URL видео: {full_url}")
                            print(f"URL видео: {full_url}")

                            title_el = await video.query_selector("h3 a")
                            title = await title_el.get_attribute("title") if title_el else ""
                            video_title = title[:30].rsplit(" ", 1)[0] if len(title) > 30 else title
                            print(f"DEBUG: Название видео: {video_title}")
                            print(f"Название видео: {video_title}")

                            views_el = await video.query_selector(".shortsLockupViewModelHostOutsideMetadataSubhead span")
                            views_text = await views_el.inner_text() if views_el else "0"
                            views = self.parse_views(views_text)
                            print(f"DEBUG: Просмотры: {views_text} -> {views}")
                            print(f"Просмотры: {views_text} -> {views}")

                            img_el = await video.query_selector("img.ytCoreImageHost")
                            img_url = await img_el.get_attribute("src") if img_el else None
                            print(f"DEBUG: URL изображения: {img_url}")
                            print(f"URL изображения: {img_url}")

                            if not full_url:
                                print("WARNING: Пропущено видео без URL")
                                print("Пропущено видео без URL")
                                continue

                            all_videos_data.append({
                                "type": "youtube",
                                "channel_id": channel_id,
                                "link": full_url,
                                "name": video_title,
                                "amount_views": views,
                                "image_url": img_url
                            })
                            print(f"DEBUG: Добавлено видео в список: {video_title} ({full_url})")
                            print(f"Добавлено видео в список: {video_title} ({full_url})")
                        except Exception as e:
                            print(f"ERROR: Ошибка парсинга видео: {e}")
                            print(f"Ошибка парсинга видео: {e}")
                            continue
                    break
                except Exception as e:
                    print(f"ERROR: Попытка {attempt} не удалась: {e}")
                    print(f"Попытка {attempt} не удалась: {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(5)
                    else:
                        raise
        finally:
            await browser.close()
            print("DEBUG: Браузер закрыт")
            print("Браузер закрыт")

        # --- Этап 2: обработка видео + качаем картинки с каруселью прокси ---
        async def download_image(url: str, proxy: str = None) -> Union[bytes, None]:
            try:
                async with httpx.AsyncClient(proxy=proxy, timeout=20.0) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    print(f"DEBUG: Успешно загружено изображение: {url}")
                    print(f"Успешно загружено изображение: {url}")
                    return resp.content
            except Exception as e:
                print(f"ERROR: ❌ Ошибка загрузки {url}: {e}")
                print(f"❌ Ошибка загрузки {url}: {e}")
                return None

        async def upload_image(video_id: int, image_url: str, proxy: str = None):
            image_bytes = await download_image(image_url, proxy=proxy)
            if not image_bytes:
                print(f"ERROR: Не удалось скачать изображение для видео {video_id}")
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
                    print(f"INFO: ✅ Фото для видео {video_id} загружено")
                    print(f"✅ Фото для видео {video_id} загружено")
                    return resp.status_code, resp.text
                except Exception as e:
                    print(f"ERROR: ⚠️ Ошибка загрузки фото для видео {video_id}: {e}")
                    print(f"⚠️ Ошибка загрузки фото для видео {video_id}: {e}")
                    return None, str(e)

        processed_count = 0
        image_queue = []

        # Шаг 1: отправляем метаданные видео в API
        for video_data in all_videos_data:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    print(f"DEBUG: Проверка видео по ссылке: {video_data['link']}")
                    print(f"Проверка видео по ссылке: {video_data['link']}")
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
                            print(f"DEBUG: Видео уже существует, ID: {video_id}, обновляем просмотры")
                            print(f"Видео уже существует, ID: {video_id}, обновляем просмотры")
                            update_resp = await client.patch(
                                f"http://127.0.0.1:8000/api/v1/videos/{video_id}",
                                json={"amount_views": video_data["amount_views"]}
                            )
                            update_resp.raise_for_status()
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        print(f"DEBUG: Создаём новое видео: {video_data['name']}")
                        print(f"Создаём новое видео: {video_data['name']}")
                        create_resp = await client.post(
                            "http://127.0.0.1:8000/api/v1/videos/",
                            json=video_data
                        )
                        create_resp.raise_for_status()
                        video_id = create_resp.json()['id']
                        print(f"DEBUG: Создано видео с ID: {video_id}")
                        print(f"Создано видео с ID: {video_id}")
                        if video_data.get("image_url"):
                            image_queue.append((video_id, video_data["image_url"]))
                            print(f"DEBUG: Добавлено изображение в очередь: {video_data['image_url']}")
                            print(f"Добавлено изображение в очередь: {video_data['image_url']}")
                processed_count += 1
            except Exception as e:
                print(f"ERROR: Ошибка при обработке {video_data.get('link')}: {e}")
                print(f"Ошибка при обработке {video_data.get('link')}: {e}")
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
            print(f"INFO: 🌐 Прокси {proxy}: качаем {len(batch)} фото")
            print(f"🌐 Прокси {proxy}: качаем {len(batch)} фото")

            for video_id, image_url in batch:
                try:
                    status, resp_text = await upload_image(video_id, image_url, proxy=proxy)
                    if status == 200:
                        print(f"INFO: ✅ Фото для видео {video_id} загружено")
                        print(f"✅ Фото для видео {video_id} загружено")
                    else:
                        print(f"ERROR: ⚠️ Фото для видео {video_id} ошибка {status}")
                        print(f"⚠️ Фото для видео {video_id} ошибка {status}")
                except Exception as e:
                    print(f"ERROR: ❌ Ошибка загрузки фото для {video_id}: {e}")
                    print(f"❌ Ошибка загрузки фото для {video_id}: {e}")
                await asyncio.sleep(4.0)

            idx += 15

            if idx < len(image_queue) and self.current_proxy_index == 0 and self.proxy_list:
                print("INFO: ⏳ Все прокси использованы, ждём 1 минуту...")
                print("⏳ Все прокси использованы, ждём 1 минуту...")
                await asyncio.sleep(60)

        print(f"INFO: ✅ Успешно обработано {processed_count} видео")
        print(f"✅ Успешно обработано {processed_count} видео")


async def main():
    proxy_list = [
        "fR86VBRE:ykkuKaTD@192.177.18.99:62258",
        "J7hnPSWjfS:DMNa7O7ZhS@103.127.76.132:34259",
    ]
    parser = ShortsParser(proxy_list=proxy_list)
    url = "https://www.youtube.com/@Interesnyemomenty"
    user_id = 1
    await parser.parse_channel(url, channel_id=24, user_id=user_id)


if __name__ == "__main__":
    asyncio.run(main())
