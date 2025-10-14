import re
import asyncio
import httpx
from typing import Optional, Dict, List
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import random
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class ShortsParser:
    def __init__(self):
        self.current_proxy_index = 0
        self.seen_video_ids: set = set()
        self.collected_videos: List[Dict] = []

    def parse_views(self, text: str) -> int:
        if not text:
            return 0
        match = re.search(r"([\d,]+)", text)
        return int(match.group(1).replace(",", "")) if match else 0

    async def scroll_until(self, page, url: str, selector: str, delay: float = 4.0, max_idle_rounds: int = 5):
        prev_count = 0
        idle_rounds = 0
        max_scroll_attempts = 3

        for attempt in range(max_scroll_attempts):
            logger.info(f"Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

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
                    logger.error("Обнаружена CAPTCHA на странице")
                    return 0

                try:
                    current_count = await page.eval_on_selector_all(selector, "els => els.length")
                    logger.info(f"Текущее количество элементов по селектору '{selector}': {current_count}")

                    if current_count == prev_count:
                        idle_rounds += 1
                        if idle_rounds >= max_idle_rounds:
                            logger.info(f"Достигнут конец списка видео профиля {url}")
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
                    logger.warning("Timeout при оценке элементов, продолжаем...")
                    break

        return prev_count

    def extract_video_from_reel_item_watch(self, data: dict) -> Optional[Dict]:
        try:
            overlay = data.get("overlay", {}).get("reelPlayerOverlayRenderer", {})

            # Title (надёжнее через metapanel, fallback на accessibility)
            metapanel = overlay.get("metapanel", {}).get("reelMetapanelViewModel", {})
            title_items = metapanel.get("metadataItems", [])
            title = next(
                (item.get("shortsVideoTitleViewModel", {}).get("text", {}).get("content", "") for item in title_items if "shortsVideoTitleViewModel" in item),
                overlay.get("reelPlayerHeaderSupportedRenderers", {})
                      .get("reelPlayerHeaderRenderer", {})
                      .get("accessibility", {})
                      .get("accessibilityData", {})
                      .get("label", "")
                      .split("@")[0]
                      .strip()
            )

            # Video ID и Likes
            like_renderer = overlay.get("likeButton", {}).get("likeButtonRenderer", {})
            video_id = like_renderer.get("target", {}).get("videoId")
            if not video_id:
                logger.warning("Нет video_id в reel_item_watch")
                return None
            like_label = like_renderer.get("likeCountWithLikeText", {}).get("accessibility", {}).get("accessibilityData", {}).get("label", "")
            likes = int(re.search(r"([\d,]+)", like_label).group(1).replace(",", "")) if re.search(r"([\d,]+)", like_label) else 0

            # Comments
            comment_btn = overlay.get("viewCommentsButton", {}).get("buttonRenderer", {})
            comment_label = comment_btn.get("accessibility", {}).get("label", "") or comment_btn.get("text", {}).get("simpleText", "")
            comment_match = re.search(r"(\d+)", comment_label)
            comments = int(comment_match.group(1)) if comment_match else 0

            # Views и Date
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
                    break

            # Thumbnail
            image_url = data.get("background", {}).get("cinematicContainerRenderer", {}).get("thumbnails", [{}])[0].get("url", None)

            return {
                "video_id": video_id,
                "link": f"https://www.youtube.com/shorts/{video_id}",
                "name": title,
                "amount_views": views,
                "likes": likes,
                "comments": comments,
                "publish_date": publish_date,
                "image_url": image_url
            }
        except Exception as e:
            logger.error(f"Ошибка извлечения из reel_item_watch: {e}")
            return None

    def extract_video_from_reel_watch_sequence(self, data: dict) -> List[Dict]:
        videos = []
        try:
            entries = data.get("entries", [])
            for entry in entries:
                command = entry.get("command", {})
                endpoint = command.get("reelWatchEndpoint", {})
                video_id = endpoint.get("videoId")
                if not video_id:
                    logger.warning("Нет video_id в entry reel_watch_sequence")
                    continue

                # Thumbnail
                thumbnails = endpoint.get("thumbnail", {}).get("thumbnails", [])
                image_url = thumbnails[0].get("url") if thumbnails else None

                # Defaults
                title = ""
                likes = 0
                views = 0
                comments = 0
                publish_date = None

                # Overlay (обычно для первого)
                overlay = endpoint.get("overlay", {}).get("reelPlayerOverlayRenderer", {})
                if overlay:
                    like_renderer = overlay.get("likeButton", {}).get("likeButtonRenderer", {})
                    likes = like_renderer.get("likeCount", 0)

                    comment_btn = overlay.get("viewCommentsButton", {}).get("buttonRenderer", {})
                    comment_text = comment_btn.get("text", {}).get("simpleText", "") or comment_btn.get("accessibility", {}).get("label", "")
                    comment_match = re.search(r"(\d+)", comment_text)
                    comments = int(comment_match.group(1)) if comment_match else 0

                # Views/Date из prefetch
                prefetch = command.get("unserializedPrefetchData", {})
                watch_response = prefetch.get("reelItemWatchResponse", {})
                engagement_panels = watch_response.get("engagementPanels", [])
                for panel in engagement_panels:
                    if "structuredDescriptionContentRenderer" in panel.get("engagementPanelSectionListRenderer", {}).get("content", {}):
                        items = panel["engagementPanelSectionListRenderer"]["content"]["structuredDescriptionContentRenderer"].get("items", [])
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

                video = {
                    "video_id": video_id,
                    "link": f"https://www.youtube.com/shorts/{video_id}",
                    "name": title,
                    "amount_views": views,
                    "likes": likes,
                    "comments": comments,
                    "publish_date": publish_date,
                    "image_url": image_url
                }
                videos.append(video)

            return videos
        except Exception as e:
            logger.error(f"Ошибка извлечения из reel_watch_sequence: {e}")
            return []

    async def process_reel_item_watch(self, response):
        try:
            json_data = await response.json()
            video = self.extract_video_from_reel_item_watch(json_data)
            if video and video["video_id"] not in self.seen_video_ids:
                self.seen_video_ids.add(video["video_id"])
                self.collected_videos.append(video)
                logger.info("\n🟢 Получено видео из reel_item_watch:")
                logger.info(f"   ID: {video['video_id']}")
                logger.info(f"   Название: {video['name']}")
                logger.info(f"   Лайки: {video['likes']}")
                logger.info(f"   Комментарии: {video['comments']}")
                logger.info(f"   Просмотры: {video['amount_views']}")
                logger.info(f"   Дата: {video['publish_date']}")
                logger.info(f"   Ссылка: {video['link']}")
                logger.info(f"   Изображение: {video['image_url']}")
        except Exception as e:
            logger.error(f"Ошибка обработки reel_item_watch: {e}")

    async def process_reel_watch_sequence(self, response):
        try:
            json_data = await response.json()
            videos = self.extract_video_from_reel_watch_sequence(json_data)
            for video in videos:
                if video["video_id"] not in self.seen_video_ids:
                    self.seen_video_ids.add(video["video_id"])
                    self.collected_videos.append(video)
                    logger.info("\n🟡 Получено видео из reel_watch_sequence:")
                    logger.info(f"   ID: {video['video_id']}")
                    logger.info(f"   Название: {video['name']}")
                    logger.info(f"   Лайки: {video['likes']}")
                    logger.info(f"   Комментарии: {video['comments']}")
                    logger.info(f"   Просмотры: {video['amount_views']}")
                    logger.info(f"   Дата: {video['publish_date']}")
                    logger.info(f"   Ссылка: {video['link']}")
                    logger.info(f"   Изображение: {video['image_url']}")
        except Exception as e:
            logger.error(f"Ошибка обработки reel_watch_sequence: {e}")

    async def handle_response(self, response):
        try:
            url = response.url
            if "youtubei/v1/reel/reel_item_watch" in url and response.request.method == "POST":
                json_data = await response.json()
                if json_data.get("playabilityStatus", {}).get("status") == "LOGIN_REQUIRED":
                    logger.warning("LOGIN_REQUIRED detected in reel_item_watch")
                asyncio.create_task(self.process_reel_item_watch(response))
            elif "youtubei/v1/reel/reel_watch_sequence" in url and response.request.method == "POST":
                json_data = await response.json()
                if json_data.get("playabilityStatus", {}).get("status") == "LOGIN_REQUIRED":
                    logger.warning("LOGIN_REQUIRED detected in reel_watch_sequence")
                asyncio.create_task(self.process_reel_watch_sequence(response))
        except Exception as e:
            logger.error(f"Ошибка в handle_response: {e}")

    async def parse_channel(self, url: str, channel_id: int, user_id: int, max_retries: int = 3, proxy_list: list = None):
        self.proxy_list = proxy_list or []
        if not url.endswith('/shorts'):
            url = url.rstrip('/') + '/shorts'
        logger.info(f"Переход на канал: {url}")

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
                logger.error(f"Неверный формат прокси: {e}")
                return None

        async def create_browser_with_proxy(proxy_str, playwright):
            proxy_config = await get_proxy_config(proxy_str) if proxy_str else None
            browser = await playwright.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                proxy=proxy_config
            )
            page = await context.new_page()
            return browser, context, page

        current_proxy = random.choice(self.proxy_list) if self.proxy_list else None
        logger.info(f"Используемый прокси: {current_proxy}")

        all_videos_data = []

        try:
            playwright = await async_playwright().start()
            browser, context, page = await create_browser_with_proxy(current_proxy, playwright)

            for attempt in range(1, max_retries + 1):
                try:
                    # ШАГ 1: Подсчёт количества видео
                    logger.info("🔍 Считаем количество Shorts на канале...")
                    await page.goto(url, wait_until="networkidle", timeout=60000)

                    # Куки
                    try:
                        accept_btn = await page.query_selector("button[aria-label='Accept all']")
                        if accept_btn:
                            await accept_btn.click()
                            await page.wait_for_timeout(2000)
                    except:
                        pass

                    # Скролл
                    selector = "ytd-rich-item-renderer, ytd-reel-item-renderer"
                    total_videos = await self.scroll_until(page, url, selector=selector, delay=4.0, max_idle_rounds=5)
                    logger.info(f"📊 Найдено {total_videos} Shorts на канале")

                    if total_videos == 0:
                        logger.warning("⚠️ Нет видео для парсинга")
                        all_videos_data = []
                    else:
                        # ШАГ 2: Новая сессия для навигации
                        logger.info("🔄 Открываем новую сессию для навигации по Shorts...")
                        await page.close()
                        await context.close()
                        browser, context, page = await create_browser_with_proxy(current_proxy, playwright)

                        await page.goto(url, wait_until="networkidle", timeout=60000)
                        try:
                            accept_btn = await page.query_selector("button[aria-label='Accept all']")
                            if accept_btn:
                                await accept_btn.click()
                                await page.wait_for_timeout(2000)
                        except:
                            pass

                        # Сброс состояния
                        self.seen_video_ids.clear()
                        self.collected_videos.clear()

                        # Привязка асинхронного обработчика
                        page.on("response", lambda response: asyncio.create_task(self.handle_response(response)))

                        # Клик по первому Shorts
                        first_shorts_sel = "ytd-rich-item-renderer a[href*='/shorts/'], ytd-reel-item-renderer a[href*='/shorts/']"
                        for _ in range(3):
                            try:
                                await page.wait_for_selector(first_shorts_sel, timeout=15000)
                                await page.click(first_shorts_sel)
                                await page.wait_for_selector("#reel-player", timeout=10000)
                                logger.info("✅ Клик по первому Shorts")
                                break
                            except PlaywrightTimeoutError:
                                logger.warning("Timeout при клике на первый Shorts, retry...")
                                continue
                        else:
                            logger.error("Не удалось кликнуть на первый Shorts")
                            break

                        await page.wait_for_timeout(4000)

                        # ШАГ 3: Клик Next
                        clicks_needed = total_videos - 1
                        logger.info(f"⏭️ Будем нажимать Next {clicks_needed} раз(а)")

                        for i in range(clicks_needed):
                            try:
                                next_btn = await page.query_selector("#navigation-button-down button")
                                if not next_btn or await next_btn.is_disabled():
                                    logger.warning("⏭️ Кнопка Next исчезла или неактивна")
                                    break

                                await next_btn.click()
                                logger.info(f"⏭️ Нажат Next ({i + 1}/{clicks_needed})")
                                await page.wait_for_selector("#reel-player", timeout=10000)
                                await asyncio.sleep(2.5)

                                if len(self.collected_videos) >= total_videos:
                                    logger.info("✅ Все видео собраны досрочно")
                                    break

                            except Exception as e:
                                logger.error(f"⚠️ Ошибка при нажатии Next: {e}")
                                break

                        all_videos_data = [
                            {
                                "type": "youtube",
                                "channel_id": channel_id,
                                "link": v["link"],
                                "name": v["name"],
                                "amount_views": v["amount_views"],
                                "likes": v["likes"],
                                "comments": v["comments"],
                                "publish_date": v["publish_date"],
                                "image_url": v["image_url"]
                            }
                            for v in self.collected_videos
                        ]

                        logger.info(f"✅ Собрано {len(all_videos_data)} из {total_videos} видео")
                    break

                except Exception as e:
                    logger.error(f"Попытка {attempt} провалена: {e}")
                    if attempt < max_retries:
                        await asyncio.sleep(5)
                    else:
                        raise

        except Exception as main_error:
            logger.error(f"Критическая ошибка: {main_error}")
            raise

        finally:
            for obj, name in [(page, "page"), (context, "context"), (browser, "browser"), (playwright, "playwright")]:
                if obj:
                    try:
                        if name == "playwright":
                            await obj.stop()
                        elif name == "page" and not obj.is_closed():
                            await obj.close()
                        elif name == "context" and not obj.is_closed():
                            await obj.close()
                        elif name == "browser" and not obj.is_closed():
                            await obj.close()
                    except Exception as e:
                        logger.error(f"Ошибка закрытия {name}: {e}")

        # Отправка в API
        async def download_image(url: str, proxy: str = None) -> bytes | None:
            try:
                async with httpx.AsyncClient(proxies=proxy, timeout=20.0) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    return resp.content
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки {url}: {e}")
                return None

        async def upload_image(video_id: int, image_url: str, proxy: str = None):
            image_bytes = await download_image(image_url, proxy=proxy)
            if not image_bytes:
                return None, "Download failed"
            file_name = image_url.split("/")[-1].split("?")[0]
            async with httpx.AsyncClient(proxies=proxy, timeout=30.0) as client:
                files = {"file": (file_name, image_bytes, "image/jpeg")}
                for _ in range(3):
                    try:
                        resp = await client.post(
                            f"http://127.0.0.1:8000/api/v1/videos/{video_id}/upload-image/",
                            files=files,
                        )
                        resp.raise_for_status()
                        return resp.status_code, resp.text
                    except httpx.HTTPStatusError as e:
                        if e.response.status_code in (429, 503):
                            await asyncio.sleep(2 ** _ * 5)
                            continue
                        raise
                    except Exception as e:
                        return None, str(e)
                return None, "Max retries exceeded"

        processed_count = 0
        image_queue = []

        for video_data in all_videos_data:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    check_resp = await client.get(f"http://127.0.0.1:8000/api/v1/videos/?link={video_data['link']}")
                    video_id = None
                    is_new = False

                    if check_resp.status_code == 200:
                        result = check_resp.json()
                        videos = result.get("videos", [])
                        if videos:
                            video_id = videos[0]['id']
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
                        create_resp = await client.post("http://127.0.0.1:8000/api/v1/videos/", json=video_data)
                        create_resp.raise_for_status()
                        video_id = create_resp.json()['id']
                        if video_data.get("image_url"):
                            image_queue.append((video_id, video_data["image_url"]))
                processed_count += 1
            except Exception as e:
                logger.error(f"Ошибка при обработке {video_data.get('link')}: {e}")
                continue

        idx = 0
        while idx < len(image_queue):
            proxy = self.proxy_list[self.current_proxy_index] if self.proxy_list else None
            if self.proxy_list:
                self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)

            batch = image_queue[idx: idx + 15]
            tasks = [upload_image(video_id, image_url, proxy=proxy) for video_id, image_url in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for (video_id, _), result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Ошибка загрузки фото для {video_id}: {result}")
                elif result[0] is None:
                    logger.error(f"❌ Ошибка загрузки фото для {video_id}: {result[1]}")
            idx += 15
            if idx < len(image_queue) and self.current_proxy_index == 0 and self.proxy_list:
                await asyncio.sleep(30)

        logger.info(f"✅ Успешно обработано {processed_count} видео")
        return all_videos_data


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
    await parser.parse_channel(url, channel_id=11, user_id=1, proxy_list=proxy_list)

if __name__ == "__main__":
    asyncio.run(main())
