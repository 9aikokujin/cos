import asyncio
import re
import random
from urllib.parse import urlparse, urlunparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth
import httpx


class InstagramParser:
    def __init__(self, proxy_list: list = None):
        self.proxy_list = proxy_list or []

    async def save_html_on_error(self, page, url: str, error_message: str):
        """Save page HTML on error for debugging"""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.replace(".", "_")
            path = parsed_url.path.replace("/", "_").strip("_")
            filename = f"error_{domain}_{path}_{timestamp}.html"
            html_content = await page.content()
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"HTML saved to {filename} due to error: {error_message}")
        except Exception as save_error:
            print(f"Failed to save HTML: {str(save_error)}")

    async def get_2fa_code(self, page, two_factor_code):
        two_factor_page = await page.context.new_page()
        try:
            await two_factor_page.goto(
                f"https://2fa.fb.rip/{two_factor_code}", timeout=60000)
            await two_factor_page.wait_for_selector(
                "div#verifyCode", timeout=60000)
            two_factor_code_element = await two_factor_page.query_selector(
                "div#verifyCode")
            if two_factor_code_element:
                code = await two_factor_code_element.inner_text()
                code = re.sub(r"\D", "", code)
                if len(code) == 6 and code.isdigit():
                    print(f"2FA код успешно получен: {code}")
                    return code
                else:
                    print(f"Неверный формат 2FA кода: {code}")
                    return None
            else:
                print("Элемент 2FA кода не найден")
                return None
        except Exception as e:
            await self.save_html_on_error(
                two_factor_page,
                f"https://2fa.fb.rip/{two_factor_code}", str(e))
            print(f"Не удалось получить 2FA код: {e}")
            return None
        finally:
            await two_factor_page.close()

    async def login_to_instagram(self, page, username, password, two_factor_code):
        # Сбор ошибок API
        api_errors = []

        async def log_response(response):
            if "www.instagram.com/api/v1" in response.url or "i.instagram.com/api" in response.url:
                try:
                    status = response.status
                    if status >= 400:
                        body = await response.text()
                        print(f"API Error {status} from {response.url}: {body[:500]}")
                        api_errors.append({"url": response.url, "status": status, "body": body})
                except Exception as e:
                    print(f"Не удалось прочитать тело ответа API: {e}")

        page.on("response", log_response)

        try:
            print(f"Начало авторизации для пользователя {username}")

            # Логируем среду
            user_agent = await page.evaluate("navigator.userAgent")
            language = await page.evaluate("navigator.language")
            timezone = await page.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone")
            try:
                ip = await page.evaluate("await (await fetch('https://api.ipify.org?format=json')).json().then(r => r.ip)")
            except:
                ip = "unknown"
            print(f"User-Agent: {user_agent}")
            print(f"Language: {language}, Timezone: {timezone}, IP: {ip}")

            await page.goto("https://www.instagram.com", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=60000)
            print("Страница загружена")

            # Обработка баннера cookies
            print("Проверка наличия баннера cookies")
            cookie_found = False
            cookie_selectors = [
                'button:has-text("Allow all cookies")',
                'button:has-text("Decline optional cookies")',
            ]
            for selector in cookie_selectors:
                print(f"Поиск кнопки cookies: {selector}")
                try:
                    await page.wait_for_selector(selector, timeout=15000)
                    btn = await page.query_selector(selector)
                    if btn and await btn.is_visible() and await btn.is_enabled():
                        print(f"Клик по кнопке cookies: {selector}")
                        await btn.click()
                        await page.wait_for_timeout(3000)
                        cookie_found = True
                        break
                except Exception as e:
                    print(f"Селектор {selector} не сработал: {e}")

            if not cookie_found:
                print("Баннер cookies не найден или не обработан — продолжаем")

            # === КНОПКА "Log in" на главной ===
            print("Поиск начальной кнопки Log in")
            login_button = await page.query_selector('button:has-text("Log in")')
            if not login_button:
                await self.save_html_on_error(page, page.url, "Кнопка Log in не найдена")
                print("Кнопка Log in не найдена")
                return False

            is_visible = await login_button.is_visible()
            is_enabled = await login_button.is_enabled()
            print(f"Кнопка Log in видима: {is_visible}, активна: {is_enabled}")
            if not (is_visible and is_enabled):
                await self.save_html_on_error(page, page.url, "Кнопка Log in неактивна")
                return False

            print("Клик по кнопке Log in")
            await login_button.click(timeout=30000)
            await page.wait_for_timeout(4000)

            # === ПРОВЕРКА ОШИБОК НА ФОРМЕ ===
            print("Проверка сообщений об ошибке после перехода на форму")
            error_selectors = [
                'p:has-text("Sorry, your password was incorrect")',
                'p:has-text("We couldn\'t find an account with that username")',
                'span:has-text("Incorrect username or password")',
                'div:has-text("There was a problem logging you into Instagram")',
                'div[role="alert"]',
            ]
            for sel in error_selectors:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    err_text = (await el.text_content()).strip()
                    print(f"Ошибка на форме: {err_text}")
                    await self.save_html_on_error(page, page.url, f"Ошибка входа: {err_text}")
                    return False

            # === ОЖИДАНИЕ ФОРМЫ ===
            print("Ожидание поля username")
            try:
                await page.wait_for_selector('input[name="username"]', timeout=20000)
            except PlaywrightTimeoutError:
                await self.save_html_on_error(page, page.url, "Форма входа не загрузилась")
                print("Форма входа не появилась")
                return False

            # === ЗАПОЛНЕНИЕ USERNAME ===
            username_field = await page.query_selector('input[name="username"]')
            if not username_field:
                await self.save_html_on_error(page, page.url, "Поле username отсутствует")
                return False

            await username_field.fill(username)
            actual_user = await username_field.input_value()
            print(f"Введён username: '{username}', фактическое значение: '{actual_user}'")
            if actual_user != username:
                print("Поле username не сохранило значение")
                return False

            # === ЗАПОЛНЕНИЕ PASSWORD ===
            password_field = await page.query_selector('input[name="password"]')
            if not password_field:
                await self.save_html_on_error(page, page.url, "Поле password отсутствует")
                return False

            await password_field.fill(password)
            print("Пароль введён")

            # === КНОПКА ВХОДА НА ФОРМЕ ===
            final_login_button = await page.query_selector('button[type="submit"]')
            if not final_login_button:
                # fallback: иногда это div с aria-label
                final_login_button = await page.query_selector('div[role="button"][aria-label="Log in"]')

            if not final_login_button:
                await self.save_html_on_error(page, page.url, "Кнопка входа на форме не найдена")
                print("Кнопка входа на форме не найдена")
                return False

            is_vis = await final_login_button.is_visible()
            is_en = await final_login_button.is_enabled()
            print(f"Кнопка входа на форме: видима={is_vis}, активна={is_en}")
            if not (is_vis and is_en):
                await self.save_html_on_error(page, page.url, "Кнопка входа неактивна")
                return False

            print("Клик по финальной кнопке Log in")
            await final_login_button.click(timeout=30000)
            await page.wait_for_timeout(6000)

            # === ПОСЛЕ КЛИКА: ПРОВЕРКА URL И ОШИБОК ===
            current_url = page.url
            title = await page.title()
            print(f"После входа: URL={current_url}, Title={title}")

            # Проверка на challenge / suspended
            if "/challenge/" in current_url:
                await self.save_html_on_error(page, current_url, "Требуется верификация (challenge)")
                print("Обнаружен challenge — требуется ручная верификация")
                return False

            if "/suspended/" in current_url:
                await self.save_html_on_error(page, current_url, "Аккаунт приостановлен")
                print("Аккаунт приостановлен")
                return False

            # Повторная проверка ошибок на форме (иногда появляются позже)
            for sel in error_selectors:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    err_text = (await el.text_content()).strip()
                    print(f"Ошибка после отправки формы: {err_text}")
                    await self.save_html_on_error(page, page.url, f"Ошибка после входа: {err_text}")
                    return False

            # === 2FA ===
            print("Проверка 2FA")
            try:
                await page.wait_for_selector('input[aria-label="Code"]', timeout=15000)
                print("Обнаружено поле 2FA")
                code_field = await page.query_selector('input[aria-label="Code"]')
                if not code_field:
                    raise Exception("Поле кода не найдено")

                verification_code = await self.get_2fa_code(page, two_factor_code)
                if not verification_code:
                    print("Не удалось получить 2FA код")
                    return False

                await code_field.fill(verification_code)
                print(f"2FA код введён: {verification_code}")

                continue_btn = await page.query_selector('div[role="button"][aria-label="Continue"]')
                if continue_btn:
                    await continue_btn.click()
                    await page.wait_for_timeout(3000)

                # Trust device
                trust_checkbox = await page.query_selector('div[role="checkbox"][aria-label*="Trust"]')
                if trust_checkbox:
                    await trust_checkbox.click()
                    print("Устройство помечено как доверенное")

            except PlaywrightTimeoutError:
                print("2FA не требуется")

            # === КНОПКА "Not now" ===
            try:
                # Попробуем найти кнопку по тексту и роли
                not_now_button = page.get_by_role("button", name="Not now")
                if await not_now_button.is_visible(timeout=5000):
                    await not_now_button.click()
                    print("Клик по 'Not now'")
                else:
                    # Попробуем русскую локализацию
                    not_now_button_ru = page.get_by_role("button", name="Не сейчас")
                    if await not_now_button_ru.is_visible(timeout=3000):
                        await not_now_button_ru.click()
                        print("Клик по 'Не сейчас'")
            except Exception as e:
                print(f"'Not now' не найден или не удалось нажать: {e}")

            # === ФИНАЛЬНАЯ ПРОВЕРКА: УСПЕХ ===
            await page.wait_for_timeout(5000)
            if "instagram.com/accounts/login/" in page.url:
                print("Всё ещё на странице входа — вход не удался")
                await self.save_html_on_error(page, page.url, "Вход не удался: остался на login-странице")
                return False

            if "/accounts/onetap/" in page.url or "/accounts/login/" not in page.url:
                print("Успешный вход в Instagram")
                return True

            print("Неясное состояние после входа — возможно, частичный успех")
            return True

        except Exception as e:
            print(f"Исключение в login_to_instagram: {str(e)}")
            await self.save_html_on_error(page, page.url or "https://www.instagram.com", "Необработанная ошибка")
            return False

    async def scroll_until(self, page, url: str, selector: str,
                           delay: float = 5.0, max_idle_rounds: int = 5):
        prev_count = 0
        idle_rounds = 0
        max_scroll_attempts = 3
        reel_data = set()

        for attempt in range(max_scroll_attempts):
            print(f"Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

            while True:
                # Собираем все элементы рилсов
                reel_elements = await page.query_selector_all('a[href*="/reel/"]')
                for element in reel_elements:
                    href = await element.get_attribute('href')
                    if href and href.startswith('/'):
                        full_url = f"https://www.instagram.com{href}"
                        # Ищем элемент с классом x1lvsgvq для получения URL изображения
                        image_element = await element.query_selector('div.x1lvsgvq')
                        image_url = None
                        if image_element:
                            style = await image_element.get_attribute('style')
                            if style and 'background-image: url' in style:
                                # Извлекаем URL из background-image
                                start = style.find('url("') + 5
                                end = style.find('")')
                                if start > 4 and end > start:
                                    image_url = style[start:end]
                        reel_data.add((full_url, image_url))

                # Прокрутка страницы
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
                current_count = await page.eval_on_selector_all(selector, "els => els.length")
                print(f"Текущее количество элементов: {current_count}, URL-ов рилов: {len(reel_data)}")

                if current_count == prev_count:
                    idle_rounds += 1
                    print(f"Количество элементов не изменилось, idle_rounds: {idle_rounds}")
                    if idle_rounds >= max_idle_rounds:
                        print(f"Достигнут конец списка рилов для профиля {url}")
                        print(f"Собрано {len(reel_data)} пар (URL рила, URL изображения)")
                        break
                else:
                    idle_rounds = 0
                    prev_count = current_count

                is_at_bottom = await page.evaluate("""
                    () => {
                        return (window.innerHeight + window.scrollY) >= document.body.scrollHeight;
                    }
                """)
                if is_at_bottom and idle_rounds >= max_idle_rounds:
                    print(f"Достигнут конец страницы для {url}")
                    break

        return list(reel_data)

    def generate_short_title(self, full_title: str, max_length: int = 20) -> str:
        if not full_title:
            return ""
        # Убираем переносы строк и лишние пробелы
        clean_title = " ".join(full_title.split())
        if len(clean_title) <= max_length:
            return clean_title
        truncated = clean_title[:max_length]
        last_space = truncated.rfind(' ')
        if last_space != -1:
            return truncated[:last_space]
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

    async def parse_channel(self, url: str, channel_id: int, user_id: int,
                            max_retries: int = 3, accounts: list = None):
        if not self.proxy_list:
            print("Список прокси пуст, используем без прокси")
        # Инициализация состояния прокси (если ещё не было)
        if not hasattr(self, 'failed_proxies'):
            self.failed_proxies = set()
            self.current_proxy = None
            self.browser = None
            self.page = None

        failed_proxies = self.failed_proxies
        MAX_PROXY_FAILURES = len(self.proxy_list) if self.proxy_list else 0

        image_tasks = []

        # Функции для работы с прокси (скопированы из TikTok-версии)
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
                    return {
                        "server": f"http://{host}:{port}"
                    }
            except Exception as e:
                print(f"Неверный формат прокси '{proxy_str}': {str(e)}")
                return None

        async def get_httpx_proxy_url(proxy_str):
            if not proxy_str:
                return None
            try:
                return f"http://{proxy_str}"
            except Exception as e:
                print(f"Ошибка формата прокси для httpx: {e}")
                return None

        async def create_browser_with_proxy(proxy_str):
            proxy_config = await get_proxy_config(proxy_str)
            if not proxy_config:
                return None, None

            p = await async_playwright().start()
            device = p.devices["iPhone 14 Pro"]
            browser = await p.chromium.launch(
                headless=False,
                args=["--window-size=390,844"]
            )
            context = await browser.new_context(
                **device,
                locale="en-US",
                timezone_id="Europe/Amsterdam",
                proxy=proxy_config
            )
            page = await context.new_page()
            stealth = Stealth()
            await stealth.apply_stealth_async(page)
            return browser, page

        async def switch_proxy():
            nonlocal failed_proxies, MAX_PROXY_FAILURES
            available_proxies = [p for p in (self.proxy_list or [None]) if p not in failed_proxies]

            if len(failed_proxies) >= MAX_PROXY_FAILURES and MAX_PROXY_FAILURES > 0:
                print("⏳ Все прокси временно не работают. Ждём 1 минуту...")
                await asyncio.sleep(60)
                failed_proxies.clear()
                available_proxies = self.proxy_list.copy() if self.proxy_list else [None]
                print("🔁 Список прокси сброшен, начинаем заново.")

            if not available_proxies:
                available_proxies = self.proxy_list.copy() if self.proxy_list else [None]

            if not available_proxies:
                raise Exception("Список прокси пуст — нечего использовать даже после ожидания")

            new_proxy = random.choice(available_proxies)
            print(f"🔁 Переключаемся на прокси: {new_proxy}")

            # Закрываем старый браузер
            if hasattr(self, 'browser') and self.browser:
                await self.browser.close()

            # Создаём новый
            browser, page = await create_browser_with_proxy(new_proxy)
            if not browser:
                failed_proxies.add(new_proxy)
                print(f"❌ Прокси {new_proxy} не работает, пробуем другую...")
                return await switch_proxy()

            # Обновляем состояние
            self.current_proxy = new_proxy
            self.browser = browser
            self.page = page

            if new_proxy in failed_proxies:
                failed_proxies.remove(new_proxy)

        # 👇 Инициализируем первый прокси
        if not self.current_proxy:
            await switch_proxy()

        # 👇 Функции загрузки изображений — с использованием ТЕКУЩЕГО прокси
        async def download_image(url: str) -> bytes:
            proxy_url = await get_httpx_proxy_url(self.current_proxy) if self.current_proxy else None
            async with httpx.AsyncClient(timeout=20.0, proxy=proxy_url) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content

        async def upload_image(video_id: int, image_url: str):
            try:
                image_bytes = await download_image(image_url)
                file_name = image_url.split("/")[-1].split("?")[0] or f"{video_id}.jpg"
                proxy_url = await get_httpx_proxy_url(self.current_proxy) if self.current_proxy else None
                async with httpx.AsyncClient(timeout=30.0) as client:
                    files = {"file": (file_name, image_bytes, "image/jpeg")}
                    resp = await client.post(
                        f"http://127.0.0.1:8000/api/v1/videos/{video_id}/upload-image/",
                        files=files,
                    )
                    resp.raise_for_status()
                    print(f"📸 Загружено превью для видео {video_id}")
            except Exception as e:
                print(f"❌ Ошибка загрузки превью {video_id}: {e}")

        async def save_video_and_image(
            channel_id: int, reel_code: str,
            reel_url: str, play_count: int,
            amount_likes: int, amount_comments: int,
            image_url: str, article: str,
            caption_text: str,
        ):
            video_name = self.generate_short_title(caption_text, max_length=20)

            video_data = {
                "type": "instagram",
                "channel_id": channel_id,
                "link": reel_url,
                "name": video_name,
                "article": article,
                "amount_views": play_count,
                "amount_likes": amount_likes,
                "amount_comments": amount_comments,
                "image_url": image_url,
            }
            try:
                async with httpx.AsyncClient() as client:
                    check_resp = await client.get(
                        f"http://127.0.0.1:8000/api/v1/videos/?link={reel_url}",
                        timeout=20.0
                    )

                    video_id = None
                    is_new = False

                    if check_resp.status_code == 200:
                        result = check_resp.json()
                        videos = result.get("videos", [])
                        if videos:
                            existing_video = videos[0]
                            video_id = existing_video['id']
                            update_resp = await client.patch(
                                f"http://127.0.0.1:8000/api/v1/videos/{video_id}",
                                json={"amount_views": play_count},
                                timeout=20.0
                            )
                            update_resp.raise_for_status()
                            print(f"🔄 Обновлены просмотры для видео {video_id}: {play_count}")
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        resp = await client.post(
                            "http://127.0.0.1:8000/api/v1/videos/",
                            json=video_data,
                            timeout=20.0,
                        )
                        resp.raise_for_status()
                        created_video = resp.json()
                        video_id = created_video["id"]
                        print(f"📦 Создано видео {video_id} ({reel_url})")

                    if is_new and image_url:
                        image_tasks.append((video_id, image_url))
                        print(f"Добавлено в очередь {video_id}: {image_url}")

            except Exception as e:
                print(f"❌ Ошибка сохранения видео {reel_url}: {e}")

        # 🚀 Основной цикл с ротацией прокси и аккаунтов
        collected_queries = []

        async def handle_response(response):
            url = response.url
            if not any(x in url for x in ["graphql/query", "/api/v1/"]):
                return

            try:
                json_resp = await response.json()
            except Exception:
                return

            collected_queries.append(json_resp)

            # Новый формат
            clips_edges = (
                json_resp.get("data", {})
                .get("xdt_api__v1__clips__user__connection_v2", {})
                .get("edges", [])
            )

            for edge in clips_edges:
                media = edge.get("node", {}).get("media", {})
                if media.get("product_type") != "clips":
                    continue

                reel_code = media.get("code")
                reel_url = f"https://www.instagram.com/reel/{reel_code}/"
                play_count = media.get("play_count", 0)
                amount_likes = media.get("like_count", 0)
                amount_comments = media.get("comment_count", 0)
                image_url = (
                    media.get("image_versions2", {})
                    .get("candidates", [{}])[0]
                    .get("url")
                )
                caption_text = (
                    media.get("caption", {})
                    .get("text", "")
                )

                article = self.extract_article_tag(caption_text)
                await save_video_and_image(
                    channel_id, reel_code, reel_url, play_count,
                    amount_likes, amount_comments, image_url, article, caption_text
                )

            # Старый формат
            media_edges = (
                json_resp.get("user", {})
                .get("edge_owner_to_timeline_media", {})
                .get("edges", [])
            )

            for edge in media_edges:
                node = edge.get("node", {})
                if node.get("product_type") != "clips":
                    continue

                reel_code = node.get("shortcode")
                caption_text = node.get("accessibility_caption") or node.get("edge_media_to_caption", {}).get("edges", [{}])[0].get("node", {}).get("text", "")
                reel_url = f"https://www.instagram.com/reel/{reel_code}/"
                play_count = node.get("video_play_count", 0)
                play_count = node.get("play_count", 0)
                amount_likes = node.get("like_count", 0)
                image_url = node.get("display_url")
                article = self.extract_article_tag(caption_text)

                await save_video_and_image(
                    channel_id, reel_code, reel_url, play_count,
                    amount_likes, amount_comments, image_url, article, caption_text
                )

            if "play_count" in str(json_resp):
                print(f"🎯 Нашли play_count в {url}")

        # 🔄 Основной цикл аккаунтов
        used_accounts = set()
        print(f"Используемые аккаунты: {accounts}")
        max_account_retries = len(accounts)

        for account_attempt in range(max_account_retries):
            available_accounts = [acc for acc in accounts if acc not in used_accounts]
            if not available_accounts:
                print("Все аккаунты использованы, парсинг невозможен")
                break

            account = random.choice(available_accounts)
            used_accounts.add(account)
            username, password, two_factor_code = account.split(":")
            print(f"Попытка {account_attempt + 1}/{max_account_retries} с аккаунтом {username}")

            # 🔁 Переключаем прокси ПРИ СМЕНЕ АККАУНТА
            await switch_proxy()

            # Используем текущий браузер и страницу
            page = self.page
            page.on("response", handle_response)

            # Логинимся
            login_success = await self.login_to_instagram(page, username, password, two_factor_code)
            if not login_success:
                print(f"Не удалось войти с {username}, пробуем другой прокси и аккаунт")
                failed_proxies.add(self.current_proxy)  # помечаем прокси как нерабочий
                continue  # → автоматически переключится на следующем аккаунте

            try:
                parsed_url = urlparse(url)
                clean_url = urlunparse(
                    (parsed_url.scheme, parsed_url.netloc, parsed_url.path.rstrip('/'), '', '', '')
                )
                reels_url = f"{clean_url}/reels/"
                print(f"Открытие профиля {reels_url}")

                await page.goto(reels_url, wait_until="networkidle")
                await page.wait_for_timeout(3000)
                print(f"✅ Перешли на {reels_url}")
                # === ПОПЫТКА ЗАКРЫТЬ МОДАЛКУ "Save your login info?" ===
                try:
                    print("Проверка наличия модального окна 'Save login info'...")
                    # Ждём появления заголовка модалки (до 10 секунд)
                    await page.wait_for_function(
                        '() => document.querySelector(\'[role="dialog"]\')?.innerText?.includes("Save your login info?")',
                        timeout=10000
                    )
                    print("✅ Модальное окно 'Save your login info?' обнаружено")

                    # Ищем кнопку "Not now" внутри модалки
                    not_now_button = page.get_by_role("button", name="Not now").first
                    if await not_now_button.is_visible(timeout=5000):
                        await not_now_button.click()
                        print("✅ Успешно нажата кнопка 'Not now'")
                        await page.wait_for_timeout(2000)  # дать время исчезнуть
                    else:
                        # Попробуем русскую версию
                        not_now_ru = page.get_by_role("button", name="Не сейчас").first
                        if await not_now_ru.is_visible(timeout=3000):
                            await not_now_ru.click()
                            print("✅ Успешно нажата кнопка 'Не сейчас'")
                            await page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"ℹ️ Модальное окно 'Save info' не найдено или уже закрыто: {e}")

                await self.scroll_until(page, reels_url, selector="div._aajy")

                # Закрываем браузер перед загрузкой изображений (если нужно)
                if hasattr(self, 'browser') and self.browser:
                    await self.browser.close()
                    self.browser = None
                    self.page = None

                # Загружаем изображения
                if image_tasks:
                    print(f"📸 Начинаем загрузку {len(image_tasks)} изображений...")
                    for idx, (video_id, img_url) in enumerate(image_tasks):
                        print(f"🖼️ Загрузка {idx + 1}/{len(image_tasks)} для видео {video_id}...")
                        await upload_image(video_id, img_url)

                        if idx < len(image_tasks) - 1:
                            await asyncio.sleep(4.0)

                print(f"✅ Успешно обработано {len(image_tasks)} новых видео")
                return

            except PlaywrightTimeoutError as e:
                await self.save_html_on_error(page, reels_url, f"Таймаут: {str(e)}")
                print(f"Таймаут для {reels_url}: {e}")
                failed_proxies.add(self.current_proxy)  # помечаем прокси как нерабочий
                continue  # → переключится на следующем аккаунте
            except Exception as e:
                await self.save_html_on_error(
                    page, reels_url, f"Ошибка: {str(e)}")
                print(f"Ошибка парсинга {reels_url}: {e}")
                failed_proxies.add(self.current_proxy)
                continue

        print("❌ Не удалось спарсить профиль")
        if hasattr(self, 'browser') and self.browser:
            await self.browser.close()
        return


async def main():
    proxy_list = [
        "DOsSb4De74:gcoOPWqUAE@109.120.131.147:26209",
        "bd4v82PuNJ:fIbH8cOYn9@109.120.131.178:56127",
        "EWQAQZdvRX:RfBJ5g7XCu@45.150.35.251:42181",
        "DXF9lzZUmM:tHzHG71cSJ@109.120.131.180:49057",
    ]
    parser = InstagramParser(proxy_list=proxy_list)
    url = "https://www.instagram.com/shd.tattoo"
    user_id = 1
    accounts = [
        "juan.itaandersen:fsm8f5tb:FOJ2E2475FRD3UR5NY2E45YPTEJK5APH",
        "jodyrhodes74:Kr2V3bxS:2KYNTJCUL74SKSNTVGFENBL6DOAJ65X6",
        "Jeannetteosley12:7nYEEexK:SVTLSGQZVWLNB3ID2PCB5TR7C4VWWPES",
        "hild.amoody:6FL9Jg2j:FW26JAKMNNLP2U5BLQQF6L4ABMMMB4DC",
        "eliseowolf95:CuNAryR3Ly:VF442BGSAVQK3TBMGKM3SAN2U75EKMRG",
        "jolenemccoy650:KQ9GsFqzHy:GI2NPPGSYMTFZD4F75XMOVIAB4GFWSP4",
        "taylorvega968:FqR2RBQckZ:USEVPAIL5TQTVIT6N4YZQP6TMS6N6WFL",
        "danielle_stafford:QbR86VfEud:YSKAUQROK633XKXT5M2GJZPGEEJSPGJ3",
        "frasheri8498:NzPAAX5xqC:SJZ3D5XWEZYWHOIYXANTZZQTQ34BE47D",
        "bonilla.scout:KNWKdS3Gew:J33P5656TMAH7R55WUKML3TEA7RGSFQG",
    ]
    await parser.parse_channel(url, channel_id=1,
                               user_id=user_id, accounts=accounts)

if __name__ == "__main__":
    asyncio.run(main())


# juan.itaandersen:fsm8f5tb:FOJ2E2475FRD3UR5NY2E45YPTEJK5APH

# jodyrhodes74:Kr2V3bxS:2KYNTJCUL74SKSNTVGFENBL6DOAJ65X6

# Jeannetteosley12:7nYEEexK:SVTLSGQZVWLNB3ID2PCB5TR7C4VWWPES

# hild.amoody:6FL9Jg2j:FW26JAKMNNLP2U5BLQQF6L4ABMMMB4DC

# eliseowolf95:CuNAryR3Ly:VF442BGSAVQK3TBMGKM3SAN2U75EKMRG

# jolenemccoy650:KQ9GsFqzHy:GI2NPPGSYMTFZD4F75XMOVIAB4GFWSP4

# taylorvega968:FqR2RBQckZ:USEVPAIL5TQTVIT6N4YZQP6TMS6N6WFL

# danielle_stafford:QbR86VfEud:YSKAUQROK633XKXT5M2GJZPGEEJSPGJ3

# frasheri8498:NzPAAX5xqC:SJZ3D5XWEZYWHOIYXANTZZQTQ34BE47D

# bonilla.scout:KNWKdS3Gew:J33P5656TMAH7R55WUKML3TEA7RGSFQG
