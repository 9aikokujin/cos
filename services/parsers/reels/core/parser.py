import os
import asyncio
import re
import random
from urllib.parse import urlparse, urlunparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth
import httpx

from dotenv import load_dotenv
from utils.logger import TCPLogger
load_dotenv()


class InstagramParser:
    def __init__(self, logger: TCPLogger):
        self.logger = logger

    async def deactivate_account_by_username(self, username: str):
        """Деактивирует аккаунт в локальной БД по username через API."""
        api_base = f"https://{os.environ['PROD_DOMEN']}/api/v1/accounts"

        async with httpx.AsyncClient() as client:
            try:
                # 1. Поиск аккаунта по username
                search_resp = await client.get(
                    f"{api_base}/search",
                    params={"query": username},
                    timeout=10.0
                )
                search_resp.raise_for_status()
                accounts = search_resp.json()

                # Ищем точное совпадение (account_str == username)
                target_account = None
                for acc in accounts:
                    account_str = acc.get("account_str", "")
                    if account_str.startswith(username + ":"):
                        target_account = acc
                        break

                if not target_account:
                    self.logger.send("WARNING", f"Аккаунт с username '{username}' не найден в БД для деактивации")
                    return False

                account_id = target_account["id"]

                # 2. Деактивация через PATCH
                update_resp = await client.patch(
                    f"{api_base}/{account_id}",
                    json={"is_active": False},
                    timeout=10.0
                )
                update_resp.raise_for_status()

                self.logger.send("INFO", f"🔒 Аккаунт {username} (ID: {account_id}) успешно деактивирован в БД")
                return True

            except Exception as e:
                self.logger.send("ERROR", f"❌ Ошибка при деактивации аккаунта {username}: {str(e)}")
                return False

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
            self.logger.send("WARNING", f"HTML сохранен в {filename} из-за ошибки: {error_message}")
        except Exception as save_error:
            self.logger.send("ERROR", f"Ошибка при сохранении HTML: {str(save_error)}")

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
                    self.logger.send("INFO", f"2FA код успешно получен: {code}")
                    return code
                else:
                    self.logger.send("ERROR", f"Неверный формат 2FA кода: {code}")
                    return None
            else:
                self.logger.send("ERROR", "Элемент 2FA кода не найден")
                return None
        except Exception as e:
            await self.save_html_on_error(
                two_factor_page,
                f"https://2fa.fb.rip/{two_factor_code}", str(e))
            self.logger.send("ERROR", f"Не удалось получить 2FA код: {e}")
            return None
        finally:
            await two_factor_page.close()

    async def login_to_instagram(self, page, username, password, two_factor_code):
        try:
            self.logger.send("INFO", f"Начало авторизации для пользователя {username}")
            await page.goto("https://www.instagram.com", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=60000)
            self.logger.send("INFO", "Страница загружена")

            # Обработка баннера cookies
            self.logger.send("INFO", "Проверка наличия баннера cookies")
            try:
                cookie_selectors = [
                    'button:has-text("Allow all cookies")',
                    'div[role="dialog"] button:has-text("Allow all cookies")',
                    'button:has-text("Decline optional cookies")'
                ]
                accept_cookies_button = None
                for selector in cookie_selectors:
                    try:
                        btn = await page.query_selector(selector)
                        if btn:
                            accept_cookies_button = btn
                            self.logger.send("INFO", f"Нашли кнопку cookies: {selector}")
                            break
                    except Exception as e:
                        self.logger.send("DEBUG", f"Селектор {selector} не найден: {e}")

                if accept_cookies_button:
                    try:
                        await accept_cookies_button.click()
                        self.logger.send("INFO", "Клик по кнопке cookies")
                        await page.wait_for_timeout(3000)
                    except Exception as e:
                        self.logger.send("WARNING", f"Не удалось кликнуть по кнопке cookies: {e}")
                else:
                    self.logger.send("INFO", "Баннер cookies не найден, продолжаем")
            except Exception as e:
                self.logger.send("ERROR", f"Ошибка при обработке cookies: {e}")

            # Кнопка Log in на главной
            self.logger.send("INFO", "Поиск начальной кнопки Log in")
            login_button = await page.query_selector('button:has-text("Log in"), div[role="button"]:has-text("Log in")')
            if login_button:
                try:
                    await login_button.click()
                    self.logger.send("INFO", "Клик по кнопке Log in")
                    await page.wait_for_timeout(4000)
                except Exception as e:
                    self.logger.send("WARNING", f"Не удалось кликнуть Log in: {e}")
            else:
                self.logger.send("ERROR", "Кнопка Log in не найдена")
                await self.save_html_on_error(page, page.url, "Кнопка Log in не найдена")
                return False

            # Проверка ошибок формы
            error_selectors = [
                'p:has-text("Sorry, your password was incorrect")',
                'p:has-text("We couldn\'t find an account with that username")',
                'span:has-text("Incorrect username or password")',
                'div:has-text("There was a problem logging you into Instagram")',
                'div[role="alert"]'
            ]
            for sel in error_selectors:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    err_text = (await el.text_content()).strip()
                    self.logger.send("ERROR", f"Ошибка на форме: {err_text}")
                    await self.save_html_on_error(page, page.url, f"Ошибка входа: {err_text}")
                    return False

            # Ожидание формы логина
            self.logger.send("INFO", "Ожидание формы логина")
            try:
                await page.wait_for_selector('input[name="username"]', timeout=20000)
            except Exception:
                self.logger.send("ERROR", "Форма логина не появилась")
                await self.save_html_on_error(page, page.url, "Форма логина не появилась")
                return False

            username_field = await page.query_selector('input[name="username"]')
            password_field = await page.query_selector('input[name="password"]')
            if not username_field or not password_field:
                self.logger.send("ERROR", "Не найдены поля username/password")
                await self.save_html_on_error(page, page.url, "Нет полей username/password")
                return False

            await username_field.fill(username)
            self.logger.send("INFO", f"Введён username: {username}")
            await password_field.fill(password)
            self.logger.send("INFO", "Введён пароль")

            # Финальная кнопка входа
            final_login_button = await page.query_selector('button[type="submit"], div[role="button"][aria-label="Log in"]')
            if final_login_button:
                try:
                    await final_login_button.click()
                    self.logger.send("INFO", "Клик по финальной кнопке Log in")
                    await page.wait_for_timeout(6000)
                except Exception as e:
                    self.logger.send("ERROR", f"Не удалось кликнуть финальную кнопку входа: {e}")
                    return False
            else:
                self.logger.send("ERROR", "Финальная кнопка входа не найдена")
                await self.save_html_on_error(page, page.url, "Финальная кнопка входа не найдена")
                return False

            # Проверка challenge/suspended
            current_url = page.url
            if "/challenge/" in current_url:
                self.logger.send("ERROR", "Обнаружен challenge — требуется верификация")
                await self.save_html_on_error(page, current_url, "Challenge")
                return False
            if "/suspended/" in current_url:
                self.logger.send("ERROR", "Аккаунт приостановлен")
                await self.save_html_on_error(page, current_url, "Suspended")
                return False

            # 2FA
            try:
                code_field = await page.wait_for_selector('input[aria-label="Code"]', timeout=15000)
                if code_field:
                    code = await self.get_2fa_code(page, two_factor_code)
                    if not code:
                        self.logger.send("ERROR", "Не удалось получить 2FA код")
                        return False
                    await code_field.fill(code)
                    self.logger.send("INFO", f"Введён 2FA код: {code}")
                    continue_btn = await page.query_selector('div[role="button"][aria-label="Continue"]')
                    if continue_btn:
                        try:
                            await continue_btn.click()
                            self.logger.send("INFO", "Клик по кнопке Continue")
                            await page.wait_for_timeout(3000)
                        except Exception as e:
                            self.logger.send("WARNING", f"Не удалось кликнуть Continue: {e}")
            except Exception:
                self.logger.send("INFO", "2FA не требуется")

            # Кнопка Not now
            not_now = await page.query_selector(
                'div[role="button"]:has-text("Not now"), div[role="button"]:has-text("Не сейчас"), button:has-text("Dismiss")'
            )
            if not_now:
                try:
                    await not_now.click()
                    self.logger.send("INFO", "Клик по кнопке 'Not now'")
                except Exception as e:
                    self.logger.send("WARNING", f"Не удалось кликнуть 'Not now': {e}")

            # Проверка финального состояния
            await page.wait_for_timeout(5000)
            if "instagram.com/accounts/login/" in page.url:
                self.logger.send("ERROR", "Остались на login-странице — вход не удался")
                await self.save_html_on_error(page, page.url, "Неудачный вход")
                return False

            self.logger.send("INFO", "Успешный вход в Instagram")
            return True
        except Exception as e:
            await self.save_html_on_error(page, page.url or "https://www.instagram.com", f"Ошибка при входе: {e}")
            self.logger.send("ERROR", f"Исключение при входе {username}: {e}")
            return False

    async def scroll_until(self, page, url: str, selector: str,
                           delay: float = 5.0, max_idle_rounds: int = 5):
        prev_count = 0
        idle_rounds = 0
        max_scroll_attempts = 3
        reel_data = set()

        for attempt in range(max_scroll_attempts):
            self.logger.send("INFO", f"Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

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
                self.logger.send("INFO", f"Текущее количество элементов: {current_count}, URL-ов рилов: {len(reel_data)}")

                if current_count == prev_count:
                    idle_rounds += 1
                    self.logger.send("INFO", f"Количество элементов не изменилось, idle_rounds: {idle_rounds}")
                    if idle_rounds >= max_idle_rounds:
                        self.logger.send("INFO", f"Достигнут конец списка рилов для профиля {url}")
                        self.logger.send("INFO", f"Собрано {len(reel_data)} пар (URL рила, URL изображения)")
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
                    self.logger.send("INFO", f"Достигнут конец страницы для {url}")
                    break

        return list(reel_data)

    async def parse_channel(self, url: str, channel_id: int, user_id: int,
                            max_retries: int = 3, proxy_list: list = None,
                            accounts: list = None,):
        self.proxy_list = proxy_list or []
        if not self.proxy_list:
            self.logger.send("WARNING", "Список прокси пуст, используем без прокси")
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
                self.logger.send("ERROR", f"Неверный формат прокси '{proxy_str}': {str(e)}")
                return None

        async def get_httpx_proxy_url(proxy_str):
            if not proxy_str:
                return None
            try:
                return f"http://{proxy_str}"
            except Exception as e:
                self.logger.send("ERROR", f"Ошибка формата прокси для httpx: {e}")
                return None

        async def create_browser_with_proxy(proxy_str):
            proxy_config = await get_proxy_config(proxy_str)
            if not proxy_config:
                return None, None

            p = await async_playwright().start()
            device = p.devices["iPhone 14 Pro"]
            browser = await p.chromium.launch(
                headless=True,
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

        # 🔁 Функция переключения прокси — как в TikTok-версии
        async def switch_proxy():
            nonlocal failed_proxies, MAX_PROXY_FAILURES
            available_proxies = [p for p in (self.proxy_list or [None]) if p not in failed_proxies]

            if len(failed_proxies) >= MAX_PROXY_FAILURES and MAX_PROXY_FAILURES > 0:
                self.logger.send("WARNING", "⏳ Все прокси временно не работают. Ждём 1 минуту...")
                await asyncio.sleep(60)
                failed_proxies.clear()
                available_proxies = self.proxy_list.copy() if self.proxy_list else [None]
                self.logger.send("INFO", "🔁 Список прокси сброшен, начинаем заново.")

            if not available_proxies:
                available_proxies = self.proxy_list.copy() if self.proxy_list else [None]

            if not available_proxies:
                raise Exception("Список прокси пуст — нечего использовать даже после ожидания")

            new_proxy = random.choice(available_proxies)
            self.logger.send("WARNING", f"🔁 Переключаемся на прокси: {new_proxy}")

            # Закрываем старый браузер
            if hasattr(self, 'browser') and self.browser:
                await self.browser.close()

            # Создаём новый
            browser, page = await create_browser_with_proxy(new_proxy)
            if not browser:
                failed_proxies.add(new_proxy)
                self.logger.send("WARNING", f"❌ Прокси {new_proxy} не работает, пробуем другую...")
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
            async with httpx.AsyncClient(proxy=proxy_url, timeout=20.0) as client:
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
                        f"http://{os.environ['PROD_DOMEN']}/api/v1/videos/{video_id}/upload-image/",
                        files=files,
                    )
                    resp.raise_for_status()
                    self.logger.send("INFO", f"📸 Загружено превью для видео {video_id}")
            except Exception as e:
                self.logger.send("ERROR", f"❌ Ошибка загрузки превью {video_id}: {e}")

        async def save_video_and_image(
                channel_id: int, reel_code: str,
                reel_url: str, play_count: int,
                amount_likes: int, amount_comments: int,
                image_url: str
        ):
            video_data = {
                "type": "instagram",
                "channel_id": channel_id,
                "link": reel_url,
                "name": reel_code,
                "amount_views": play_count,
                "amount_likes": amount_likes,
                "amount_comments": amount_comments,
                "image_url": image_url,
            }
            try:
                async with httpx.AsyncClient() as client:
                    check_resp = await client.get(
                        f"https://{os.environ['PROD_DOMEN']}/api/v1/videos/?link={reel_url}",
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
                                f"https://{os.environ['PROD_DOMEN']}/api/v1/videos/{video_id}",
                                json={"amount_views": play_count},
                                timeout=20.0
                            )
                            update_resp.raise_for_status()
                            self.logger.send("INFO", f"🔄 Обновлены просмотры для видео {video_id}: {play_count}")
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        resp = await client.post(
                            f"https://{os.environ['PROD_DOMEN']}/api/v1/videos/",
                            json=video_data,
                            timeout=20.0,
                        )
                        resp.raise_for_status()
                        created_video = resp.json()
                        video_id = created_video["id"]
                        self.logger.send("INFO", f"📦 Создано видео {video_id} ({reel_url})")

                    if is_new and image_url:
                        image_tasks.append((video_id, image_url))
                        self.logger.send("INFO", f"Добавлено в очередь {video_id}: {image_url}")

            except Exception as e:
                self.logger.send("ERROR", f"❌ Ошибка сохранения видео {reel_url}: {e}")

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
                await save_video_and_image(channel_id, reel_code, reel_url, play_count, amount_likes, amount_comments, image_url)

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
                reel_url = f"https://www.instagram.com/reel/{reel_code}/"  # ← Исправлено
                play_count = node.get("video_play_count", 0)
                amount_likes = node.get("like_count", 0)
                amount_comments = node.get("comment_count", 0)
                image_url = node.get("display_url")
                await save_video_and_image(channel_id, reel_code, reel_url, play_count, amount_likes, amount_comments, image_url)

            if "play_count" in str(json_resp):
                self.logger.send("INFO", f"🎯 Нашли play_count в {url}")

        # 🔄 Основной цикл аккаунтов
        used_accounts = set()
        self.logger.send("INFO", f"Используемые аккаунты: {accounts}")
        max_account_retries = len(accounts)

        for account_attempt in range(max_account_retries):
            available_accounts = [acc for acc in accounts if acc not in used_accounts]
            if not available_accounts:
                self.logger.send("CRITICAL", "Все аккаунты использованы, парсинг невозможен")
                break

            account = random.choice(available_accounts)
            used_accounts.add(account)
            username, password, two_factor_code = account.split(":")
            self.logger.send("INFO", f"Попытка {account_attempt + 1}/{max_account_retries} с аккаунтом {username}")

            # 🔁 Переключаем прокси ПРИ СМЕНЕ АККАУНТА
            await switch_proxy()

            # Используем текущий браузер и страницу
            page = self.page
            page.on("response", handle_response)

            # Логинимся
            login_success = await self.login_to_instagram(page, username, password, two_factor_code)
            if not login_success:
                self.logger.send("ERROR", f"Не удалось войти с {username}, пробуем другой прокси и аккаунт")
                # Деактивируем аккаунт в БД
                await self.deactivate_account_by_username(username)

                failed_proxies.add(self.current_proxy)  # помечаем прокси как нерабочий
                continue

            try:
                parsed_url = urlparse(url)
                clean_url = urlunparse(
                    (parsed_url.scheme, parsed_url.netloc, parsed_url.path.rstrip('/'), '', '', '')
                )
                reels_url = f"{clean_url}/reels/"
                self.logger.send("INFO", f"Открытие профиля {reels_url}")

                await page.goto(reels_url, wait_until="networkidle")
                await page.wait_for_timeout(3000)
                self.logger.send("INFO", f"✅ Перешли на {reels_url}")

                await self.scroll_until(page, reels_url, selector="div._aajy")

                # Закрываем браузер перед загрузкой изображений (если нужно)
                if hasattr(self, 'browser') and self.browser:
                    await self.browser.close()
                    self.browser = None
                    self.page = None

                # Загружаем изображения
                if image_tasks:
                    self.logger.send("INFO", f"📸 Начинаем загрузку {len(image_tasks)} изображений...")
                    for idx, (video_id, img_url) in enumerate(image_tasks):
                        self.logger.send("INFO", f"🖼️ Загрузка {idx + 1}/{len(image_tasks)} для видео {video_id}...")
                        await upload_image(video_id, img_url)

                        if idx < len(image_tasks) - 1:
                            await asyncio.sleep(4.0)

                self.logger.send("INFO", f"✅ Успешно обработано {len(image_tasks)} новых видео")
                return

            except PlaywrightTimeoutError as e:
                await self.save_html_on_error(page, reels_url, f"Таймаут: {str(e)}")
                self.logger.send("ERROR", f"Таймаут для {reels_url}: {e}")
                failed_proxies.add(self.current_proxy)  # помечаем прокси как нерабочий
                continue  # → переключится на следующем аккаунте
            except Exception as e:
                await self.save_html_on_error(
                    page, reels_url, f"Ошибка: {str(e)}")
                self.logger.send("ERROR", f"Ошибка парсинга {reels_url}: {e}")
                failed_proxies.add(self.current_proxy)
                continue

        self.logger.send("CRITICAL", "❌ Не удалось спарсить профиль")
        if hasattr(self, 'browser') and self.browser:
            await self.browser.close()
        return
