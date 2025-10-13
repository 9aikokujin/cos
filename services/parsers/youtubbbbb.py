import re
import asyncio
import httpx
from typing import Union, List, Dict, Optional
from playwright.async_api import async_playwright
import random
import json

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
            # Получаем полный HTML
            content = await page.content()

            # Ищем ytInitialPlayerResponse
            match = re.search(r'var ytInitialPlayerResponse\s*=\s*({.*?});', content, re.DOTALL)
            if not match:
                print("⚠️ ytInitialPlayerResponse не найден")
                return metrics

            player_response = json.loads(match.group(1))
            video_details = player_response.get("videoDetails", {})

            # Название
            full_title = video_details.get("title", "")
            metrics["name"] = full_title
            print("название:", repr(full_title))

            # Артикулы
            if full_title:
                found_tags = []
                caption_lower = full_title.lower()
                for tag in ["#sv", "#jw", "#qz", "#sr", "#fg"]:
                    if tag in caption_lower:
                        start = full_title.lower().find(tag)
                        if start != -1:
                            original_tag = full_title[start:start + len(tag)]
                            found_tags.append(original_tag)
                metrics["article"] = ",".join(found_tags) if found_tags else None
            print("артикулы:", metrics["article"])

            # Просмотры и лайки
            try:
                metrics["views"] = int(video_details.get("viewCount", "0"))
            except (ValueError, TypeError):
                metrics["views"] = 0

            try:
                metrics["likes"] = int(video_details.get("likeCount", "0"))
            except (ValueError, TypeError):
                metrics["likes"] = 0

            print("просмотры:", metrics["views"])
            print("лайки:", metrics["likes"])

            # Комментарии — ищем в ytInitialData
            comments_match = re.search(r'var ytInitialData\s*=\s*({.*?});', content, re.DOTALL)
            if comments_match:
                try:
                    initial_data = json.loads(comments_match.group(1))
                    # Путь к комментариям может быть разным, но часто:
                    # contents.twoColumnWatchNextResults.results.results.contents[2].itemSectionRenderer.contents[0].commentsEntryPointHeaderRenderer.commentCount
                    
                    def find_comment_count(obj):
                        if isinstance(obj, dict):
                            if "commentCount" in obj and isinstance(obj["commentCount"], dict):
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

                    comment_count = find_comment_count(initial_data)
                    if comment_count is not None:
                        metrics["comments"] = comment_count
                except Exception as e:
                    print(f"Ошибка при поиске комментариев в ytInitialData: {e}")

            print("комментарии:", metrics["comments"])

            # Изображение
            thumbnail = video_details.get("thumbnail", {}).get("thumbnails")
            if thumbnail and isinstance(thumbnail, list):
                # Берём самый большой
                img_url = max(thumbnail, key=lambda x: x.get("width", 0)).get("url")
                if img_url:
                    metrics["image_url"] = img_url.split("?")[0]
            else:
                # fallback на стандартный URL
                video_id = video_details.get("videoId", "")
                if video_id:
                    metrics["image_url"] = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

            print("изображение:", metrics["image_url"])

        except Exception as e:
            print(f"❌ Ошибка извлечения из JSON: {e}")

        return metrics

    # async def collect_short_urls(self, url: str, proxy: Optional[str]) -> List[str]:
    #     browser, context = await self.create_context_with_proxy(proxy)
    #     page = await context.new_page()
    #     short_urls = []
    #     try:
    #         clean_url = url.rstrip()
    #         if not clean_url.endswith('/shorts'):
    #             clean_url = clean_url.rstrip('/') + '/shorts'
    #         await page.goto(clean_url, wait_until="networkidle", timeout=60000)

    #         # Куки
    #         try:
    #             await page.evaluate("""
    #                 async () => {
    #                     return new Promise((resolve) => {
    #                         const distance = 1000;
    #                         const timer = setInterval(() => {
    #                             window.scrollBy(0, distance);
    #                             if (document.body.scrollHeight - window.scrollY <= window.innerHeight + 100) {
    #                                 clearInterval(timer);
    #                                 resolve();
    #                             }
    #                         }, 100);
    #                     });
    #                 }
    #             """)
    #             accept_btn = await page.query_selector('button[jsname="b3VHJd"]')
    #             if accept_btn:
    #                 try:
    #                     # Принудительный клик через JS
    #                     await page.evaluate("button => button.click()", accept_btn)
    #                     print("✅ Куки приняты через JavaScript")
    #                     await page.wait_for_timeout(2000)
    #                 except Exception as e:
    #                     print(f"⚠️ Ошибка JS-клика: {e}")
    #             else:
    #                 print("ℹ️ Кнопка 'Accept all' не найдена в DOM")
    #         except Exception as e:
    #             print(f"❌ Ошибка при принятии кук: {e}")

    #         selector = "ytm-shorts-lockup-view-model"
    #         await self.scroll_until(page, clean_url, selector=selector, delay=4.0)

    #         videos = await page.query_selector_all(selector)
    #         for video in videos:
    #             link_el = await video.query_selector("a.shortsLockupViewModelHostEndpoint")
    #             href = await link_el.get_attribute("href") if link_el else None
    #             if href:
    #                 full_url = f"https://www.youtube.com{href}"
    #                 short_urls.append(full_url)
    #                 print(f"Собран URL: {full_url}")
    #     finally:
    #         await browser.close()
    #     return short_urls

    # async def process_short_pair(self, urls: List[str], proxy: Optional[str]) -> List[Dict]:
    #     browser, context = await self.create_context_with_proxy(proxy)
    #     results = []
    #     try:
    #         pages = []
    #         for url in urls[:2]:
    #             page = await context.new_page()
    #             await page.goto(url, wait_until="networkidle", timeout=30000)

    #             # >>> ДОБАВЛЕНО: Принятие кук на странице шортса <<<
    #             accept_btn = await page.query_selector('button[jsname="b3VHJd"]')
    #             if accept_btn:
    #                 try:
    #                     await page.evaluate("button => button.click()", accept_btn)
    #                     print("✅ Куки на шортсе приняты через JavaScript")
    #                     await page.wait_for_timeout(2000)
    #                 except Exception as e:
    #                     print(f"⚠️ Ошибка JS-клика на шортсе: {e}")
    #             else:
    #                 print("ℹ️ Баннер кук на шортсе не обнаружен")

    #             pages.append((page, url))

    #         for page, url in pages:
    #             metrics = await self.extract_metrics_from_short_page(page)
    #             results.append({
    #                 "link": url,
    #                 "amount_views": metrics["views"],
    #                 "likes": metrics["likes"],
    #                 "comments": metrics["comments"],
    #                 "article": metrics["article"],
    #                 "image_url": metrics["image_url"],
    #                 "name": metrics["name"]
    #             })
    #             print(f"Метрики для {url}: {metrics}")
    #     except Exception as e:
    #         print(f"Ошибка при обработке пары {urls}: {e}")
    #         results = []
    #     finally:
    #         await context.close()
    #     return results

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

    async def parse_shorts_by_scrolling(self, base_url: str, channel_id: int, proxy: Optional[str]):
        browser, context = await self.create_context_with_proxy(proxy)
        page = await context.new_page()

        try:
            clean_url = base_url.rstrip('/')
            if not clean_url.endswith('/shorts'):
                clean_url += '/shorts'
            print(f"Открываем: {clean_url}")
            await page.goto(clean_url, wait_until="networkidle", timeout=60000)

            # Принимаем куки
            accept_btn = await page.query_selector('button[jsname="b3VHJd"]')
            if accept_btn:
                try:
                    await page.evaluate("button => button.click()", accept_btn)
                    print("✅ Куки приняты")
                    await page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"⚠️ Ошибка клика по кукам: {e}")

            processed = 0
            while True:
                # Ждём загрузки текущего шортса
                await page.wait_for_timeout(3000)

                # Извлекаем данные из HTML
                metrics = await self.extract_metrics_from_short_page(page)
                current_url = await page.url()
                if metrics["name"]:
                    data = {
                        "link": current_url,
                        "amount_views": metrics["views"],
                        "likes": metrics["likes"],
                        "comments": metrics["comments"],
                        "article": metrics["article"],
                        "image_url": metrics["image_url"],
                        "name": metrics["name"]
                    }
                    await self.send_to_api(data, channel_id)
                    processed += 1
                    print(f"✅ Обработано видео #{processed}")

                # Ждём 10 секунд перед листанием
                await page.wait_for_timeout(10000)

                # Проверяем, есть ли кнопка "следующее видео"
                next_button = await page.query_selector('yt-spec-button-shape-next[aria-label*="next"], yt-spec-button-shape-next[aria-label*="следующ"]')
                if not next_button:
                    print("❌ Кнопка 'следующее видео' не найдена — достигнут конец")
                    break

                # Листаем вниз (имитация свайпа)
                try:
                    await page.mouse.wheel(0, 500)  # прокрутка колёсиком
                    # ИЛИ:
                    # await page.keyboard.press("ArrowDown")
                except Exception as e:
                    print(f"⚠️ Ошибка при листании: {e}")
                    break

                # Ждём загрузки следующего видео
                await page.wait_for_timeout(2000)

        except Exception as e:
            print(f"❌ Ошибка при листании: {e}")
        finally:
            await browser.close()

    # async def parse_channel(self, url: str, channel_id: int, user_id: int, max_retries: int = 3, proxy_list: list = None):
    #     self.proxy_list = proxy_list or []
    #     clean_base_url = url.strip().rstrip('/')
    #     if not clean_base_url.endswith('/shorts'):
    #         clean_base_url += '/shorts'
    #     print(f"Начало парсинга канала: {clean_base_url}")

    #     # Шаг 1: Сбор URL
    #     initial_proxy = random.choice(self.proxy_list) if self.proxy_list else None
    #     short_urls = await self.collect_short_urls(clean_base_url, initial_proxy)
    #     print(f"Всего собрано Shorts: {len(short_urls)}")

    #     if not short_urls:
    #         print("Не найдено ни одного Shorts")
    #         return

    #     # Шаг 2: Обработка парами
    #     for i in range(0, len(short_urls), 2):
    #         batch = short_urls[i:i+2]
    #         success = False

    #         for attempt in range(max_retries):
    #             current_proxy = self.proxy_list[self.current_proxy_index] if self.proxy_list else None
    #             print(f"Обработка пары {i//2 + 1}: {batch} через прокси {current_proxy} (попытка {attempt+1})")

    #             metrics_list = await self.process_short_pair(batch, current_proxy)
    #             if metrics_list:
    #                 success = True
    #                 for data in metrics_list:
    #                     await self.send_to_api(data, channel_id)
    #                 break
    #             else:
    #                 if self.proxy_list:
    #                     self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
    #                 await asyncio.sleep(2)

    #         if not success:
    #             print(f"Не удалось обработать пару: {batch}")

    #         # Смена прокси после обработки (даже успешной)
    #         if self.proxy_list:
    #             self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)

    #     print("✅ Парсинг завершён")

    async def parse_channel(self, url: str, channel_id: int, user_id: int, max_retries: int = 3, proxy_list: list = None):
        self.proxy_list = proxy_list or []
        clean_base_url = url.strip().rstrip('/')
        print(f"Начало парсинга канала: {clean_base_url}")

        proxy = random.choice(self.proxy_list) if self.proxy_list else None
        await self.parse_shorts_by_scrolling(clean_base_url, channel_id, proxy)

        print("✅ Парсинг завершён")


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
    user_id = 1
    await parser.parse_channel(url, channel_id=1, user_id=user_id,
                               proxy_list=proxy_list)


if __name__ == "__main__":
    asyncio.run(main())
