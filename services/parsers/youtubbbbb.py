import re
import asyncio
import httpx
from typing import Union, List, Dict, Optional
from playwright.async_api import async_playwright
import random

# переписать без логгера


class ShortsParser:
    def __init__(self):
        self.current_proxy_index = 0

    def parse_number(self, text: str) -> int:
        """Универсальный парсер чисел: поддержка английских, арабских и русских обозначений"""
        if not text:
            return 0
        original = text
        # Заменяем неразрывные пробелы (YouTube использует \u00A0)
        text = text.strip().replace("\u00A0", " ").replace("&nbsp;", " ")
        print(f"Парсинг числа из текста: '{original}'")

        # Арабские
        arabic_patterns = [
            (r"([\d,.]+)\s*ألف", 1_000),
            (r"([\d,.]+)\s*مليون", 1_000_000),
        ]
        for pattern, mult in arabic_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    num = float(match.group(1).replace(",", "").replace(" ", ""))
                    return int(num * mult)
                except (ValueError, TypeError):
                    continue

        # Русские
        russian_patterns = [
            (r"([\d,.]+)\s*(?:тыс|тысяч)", 1_000),
            (r"([\d,.]+)\s*(?:млн|миллион)", 1_000_000),
        ]
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

        # Чистое число (например: "105 331" → 105331)
        digits_only = re.sub(r"[^\d.]", "", text.replace(" ", ""))
        if digits_only:
            try:
                return int(float(digits_only))
            except (ValueError, TypeError):
                pass

        print(f"Не удалось распарсить число: '{original}'")
        return 0

    async def scroll_until(self, page, url: str, selector: str, delay: float = 4.0, max_idle_rounds: int = 5):
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
                    break

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

        return prev_count

    def generate_short_title(self, full_title: str, max_length: int = 20) -> str:
        if not full_title:
            return ""

        # Берём максимум первые max_length символов
        truncated = full_title[:max_length]

        # Если длина <= max_length и нет обрезки — возвращаем как есть
        if len(full_title) <= max_length:
            return full_title

        # Ищем последний пробел в обрезанной части
        last_space = truncated.rfind(' ')
        if last_space != -1:
            return truncated[:last_space]
        else:
            # Если пробелов нет — возвращаем всё, даже если это обрывает слово
            return truncated

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
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Mobile Safari/537.36",
            viewport={"width": 390, "height": 844},
            proxy=proxy_config
        )
        return browser, context

    async def extract_metrics_from_short_page(self, page) -> Dict[str, Union[int, str, None]]:
        metrics = {
            "views": 0,
            "likes": 0,
            "comments": 0,
            "image_url": None,
            "article": None,
            "name": None
        }

        try:
            # Лайки
            like_el = await page.query_selector('factoid-renderer:has-text("Отметки \\"Нравится\\"") .ytwFactoidRendererValue .yt-core-attributed-string')
            likes_text = await like_el.inner_text() if like_el else "0"
            metrics["likes"] = self.parse_number(likes_text)

            # Название
            title_el = await page.query_selector('#title yt-formatted-string')
            full_title = await title_el.inner_text() if title_el else ""
            metrics["name"] = self.generate_short_title(full_title)

            # Артикул
            article = self.extract_article_tag(full_title)
            metrics["article"] = article

            # Просмотры
            view_el = await page.query_selector('view-count-factoid-renderer .ytwFactoidRendererValue .yt-core-attributed-string')
            views_text = await view_el.inner_text() if view_el else "0"
            metrics["views"] = self.parse_number(views_text)

            # Комментарии
            comment_el = await page.query_selector('#comments-button .yt-spec-button-shape-with-label__label .yt-core-attributed-string')
            comments_text = await comment_el.inner_text() if comment_el else "0"
            metrics["comments"] = self.parse_number(comments_text)

            # Превью
            img_el = await page.query_selector("ytm-reel-player-renderer img[src*='http']")
            if img_el:
                src = await img_el.get_attribute("src")
                if src:
                    metrics["image_url"] = src.split("?")[0]

        except Exception as e:
            print(f"Ошибка извлечения метрик и изображения: {e}")

        return metrics

    async def collect_short_urls(self, url: str, proxy: Optional[str]) -> List[str]:
        browser, context = await self.create_context_with_proxy(proxy)
        page = await context.new_page()
        short_urls = []
        try:
            clean_url = url.rstrip()
            if not clean_url.endswith('/shorts'):
                clean_url = clean_url.rstrip('/') + '/shorts'
            await page.goto(clean_url, wait_until="networkidle", timeout=60000)

            # Куки
            try:
                accept_btn = await page.query_selector("button[aria-label='Accept all']")
                if accept_btn:
                    await accept_btn.click()
                    await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"Ошибка принятия куки: {e}")

            selector = "ytm-shorts-lockup-view-model"
            await self.scroll_until(page, clean_url, selector=selector, delay=4.0)

            videos = await page.query_selector_all(selector)
            for video in videos:
                link_el = await video.query_selector("a.shortsLockupViewModelHostEndpoint")
                href = await link_el.get_attribute("href") if link_el else None
                if href:
                    full_url = f"https://www.youtube.com{href}"
                    short_urls.append(full_url)
                    print(f"Собран URL: {full_url}")
        finally:
            await browser.close()
        return short_urls

    async def process_short_pair(self, urls: List[str], proxy: Optional[str]) -> List[Dict]:
        browser, context = await self.create_context_with_proxy(proxy)
        results = []
        try:
            pages = []
            for url in urls[:2]:
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30000)
                pages.append((page, url))

            for page, url in pages:
                metrics = await self.extract_metrics_from_short_page(page)
                results.append({
                    "link": url,
                    "amount_views": metrics["views"],
                    "likes": metrics["likes"],
                    "comments": metrics["comments"],
                    "article": metrics["article"],
                    "image_url": metrics["image_url"],
                    "name": metrics["name"]
                })
                print(f"Метрики для {url}: {metrics}")
        except Exception as e:
            print(f"Ошибка при обработке пары {urls}: {e}")
            results = []
        finally:
            await context.close()
        return results

    async def download_image(self, url: str) -> Optional[bytes]:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                print(f"Успешно загружено изображение: {url}")
                return resp.content
        except Exception as e:
            print(f"❌ Ошибка загрузки изображения {url}: {e}")
            return None

    async def upload_image(self, video_id: int, image_url: str):
        image_bytes = await self.download_image(image_url)
        if not image_bytes:
            print(f"Не удалось скачать изображение для видео {video_id}")
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
                    "amount_views": data["amount_views"],
                    "likes": data["likes"],
                    "comments": data["comments"],
                    "name": data["name"]
                }

                if exists:
                    await client.patch(f"https://cosmeya.dev-klick.cyou/api/v1/videos/{video_id}/", json=payload)
                    print(f"Обновлено видео {video_id}")
                else:
                    resp = await client.post("https://cosmeya.dev-klick.cyou/api/v1/videos/", json=payload)
                    video_id = resp.json().get("id")
                    print(f"Создано новое видео: {video_id}")

                # Загрузка изображения, если есть
                if video_id and data.get("image_url"):
                    await self.upload_image(video_id, data["image_url"])

            except Exception as e:
                print(f"Ошибка отправки в API для {link}: {e}")

    async def parse_channel(self, url: str, channel_id: int, user_id: int, max_retries: int = 3, proxy_list: list = None):
        self.proxy_list = proxy_list or []
        clean_base_url = url.strip().rstrip('/')
        if not clean_base_url.endswith('/shorts'):
            clean_base_url += '/shorts'
        print(f"Начало парсинга канала: {clean_base_url}")

        # Шаг 1: Сбор URL
        initial_proxy = random.choice(self.proxy_list) if self.proxy_list else None
        short_urls = await self.collect_short_urls(clean_base_url, initial_proxy)
        print(f"Всего собрано Shorts: {len(short_urls)}")

        if not short_urls:
            print("Не найдено ни одного Shorts")
            return

        # Шаг 2: Обработка парами
        for i in range(0, len(short_urls), 2):
            batch = short_urls[i:i+2]
            success = False

            for attempt in range(max_retries):
                current_proxy = self.proxy_list[self.current_proxy_index] if self.proxy_list else None
                print(f"Обработка пары {i//2 + 1}: {batch} через прокси {current_proxy} (попытка {attempt+1})")

                metrics_list = await self.process_short_pair(batch, current_proxy)
                if metrics_list:
                    success = True
                    for data in metrics_list:
                        await self.send_to_api(data, channel_id)
                    break
                else:
                    if self.proxy_list:
                        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
                    await asyncio.sleep(2)

            if not success:
                print(f"Не удалось обработать пару: {batch}")

            # Смена прокси после обработки (даже успешной)
            if self.proxy_list:
                self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)

        print("✅ Парсинг завершён")


async def main():
    proxy_list = [
        "dCO5hGtkW5:fasW1uvQ7l@45.150.35.46:55676",
        "Q75n20a1UE:47t7aEhBfc@45.150.35.81:53274",
        "Q1uPaCjVjZ:fbAyEPHr2H@45.150.35.31:52694",
        "tiBQYiUvbR:eMEejf37Ah@45.150.35.160:58245",
        "99GbD8h45V:j8wANJPW91@109.120.131.167:26928",
        "Kwmxx66N8A:9X8rVKfoGy@45.150.35.244:28304",
        "XN1u5Cj7QT:7KsZyBgXFx@45.150.35.37:32891"
    ]
    parser = ShortsParser()
    url = "https://www.youtube.com/@kotokrabs"
    user_id = 1
    await parser.parse_channel(url, channel_id=1, user_id=user_id,
                               proxy_list=proxy_list)


if __name__ == "__main__":
    asyncio.run(main())
