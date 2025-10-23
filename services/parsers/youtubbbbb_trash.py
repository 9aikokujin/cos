import asyncio
import re
import random
import time
import traceback
from datetime import datetime
from typing import Optional, Dict, List
from urllib.parse import urlparse, urlunparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth
import httpx

from utils.logger import TCPLogger


class InstagramParser:
    def __init__(
            self,
            logger: TCPLogger
    ):
        pass
        self.logger = logger

    def _calculate_total_views(self, videos: List[Dict]) -> int:
        total = 0
        for video in videos:
            try:
                total += int(video.get("amount_views") or 0)
            except (TypeError, ValueError):
                continue
        return total

    async def deactivate_account_by_username(self, username: str):
        """Деактивирует аккаунт в локальной БД по username через API."""
        api_base = "https://sn.dev-klick.cyou/api/v1/accounts"

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
                    self.logger.send("INFO", f"Аккаунт с username '{username}' не найден в БД для деактивации")
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

    async def _save_html(self, page, url: str, prefix: str, label: str) -> Optional[str]:
        """
        Internal helper to dump page HTML to disk.
        Returns filename if saved, otherwise None.
        """
        if page is None:
            self.logger.send("INFO", f"Пропуск сохранения HTML ({label}) — page отсутствует")
            return None
        try:
            if hasattr(page, "is_closed") and page.is_closed():
                self.logger.send("INFO", f"Пропуск сохранения HTML ({label}) — страница закрыта")
                return None
        except Exception:
            # If is_closed itself fails, continue with best effort
            pass

        try:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            parsed_url = urlparse(url or "")
            domain = parsed_url.netloc.replace(".", "_") if parsed_url.netloc else "no_domain"
            path = parsed_url.path.replace("/", "_").strip("_") or "root"
            label_slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", label) if label else "snapshot"
            label_slug = label_slug.strip("_") or "snapshot"
            filename = f"{prefix}_{domain}_{path}_{label_slug}_{timestamp}.html"
            html_content = await page.content()
            with open(filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            return filename
        except Exception as save_error:
            raise save_error

    async def save_html_snapshot(self, page, url: str, label: str):
        """Save page HTML snapshot for debugging/analysis purposes."""
        try:
            filename = await self._save_html(page, url, prefix="success", label=label)
            if filename:
                self.logger.send("INFO", f"HTML снапшот сохранён ({label}) в {filename}")
            else:
                self.logger.send("INFO", f"HTML снапшот ({label}) не сохранён (страница недоступна)")
        except Exception as save_error:
            self.logger.send("ERROR", f"Ошибка при сохранении HTML снапшота ({label}): {str(save_error)}")

    async def save_html_on_error(self, page, url: str, error_message: str):
        """Save page HTML on error for debugging"""
        try:
            truncated_label = error_message[:60] if error_message else "error"
            filename = await self._save_html(page, url, prefix="error", label=truncated_label)
            if filename:
                self.logger.send("INFO", f"HTML сохранен в {filename} из-за ошибки: {error_message}")
            else:
                self.logger.send("INFO", f"HTML не сохранен (страница недоступна) из-за ошибки: {error_message}")
        except Exception as save_error:
            self.logger.send("ERROR", f"Ошибка при сохранении HTML: {str(save_error)}")

    async def accept_cookies_if_needed(self, page, prefer_all: bool = True) -> bool:
        """
        Закрывает как полноэкранную страницу consent (GDPR), так и обычный баннер.
        Возвращает True, если что-то нажали/убрали; False иначе.
        """
        try:
            url_now = page.url or ""

            # --- Вариант 1: полноэкранная страница согласия /consent/ ---
            if "/consent/" in url_now or "user_cookie_choice" in url_now:
                self.logger.send("INFO", f"Обнаружена страница consent: {url_now}")

                # сначала пытаемся нажать "Allow all cookies"
                selectors_allow = [
                    'button:has-text("Allow all cookies")',
                    'button:has-text("Allow all")',
                    'button:has-text("Accept all")',
                ]
                selectors_essential = [
                    'button:has-text("Only allow essential cookies")',
                    'button:has-text("Allow essential")',
                    'button:has-text("Only essential")',
                ]

                clicked = False

                if prefer_all:
                    for sel in selectors_allow:
                        btn = await page.query_selector(sel)
                        if btn:
                            await btn.click()
                            clicked = True
                            break

                if not clicked:  # либо prefer_all=False, либо не нашли "Allow all"
                    for sel in (selectors_essential + selectors_allow):
                        btn = await page.query_selector(sel)
                        if btn:
                            await btn.click()
                            clicked = True
                            break

                if not clicked:
                    # фолбэк — жмём первый сабмит на странице
                    cand = await page.query_selector('button[type="submit"], input[type="submit"], button')
                    if cand:
                        await cand.click()
                        clicked = True

                if clicked:
                    # Дождёмся смены URL/перерендера
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception:
                        pass
                    await page.wait_for_timeout(800)
                    self.logger.send("INFO", "✅ Cookie consent закрыт")
                    return True

                self.logger.send("INFO", "Не нашли кнопку на странице consent")
                return False

            # --- Вариант 2: обычный баннер куков на любой странице ---
            banner_selectors = [
                'div[role="dialog"] button:has-text("Allow all cookies")',
                'button:has-text("Allow all cookies")',
                'button:has-text("Accept all")',
                'button:has-text("Accept")'
            ]
            for sel in banner_selectors:
                btn = await page.query_selector(sel)
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(500)
                    self.logger.send("INFO", f"Закрыли cookie баннер: {sel}")
                    return True

            return False

        except Exception as e:
            self.logger.send("INFO", f"Ошибка при принятии cookies: {e}")
            return False

    def is_challenge_url(self, url: str) -> bool:
        """True, если текущий URL указывает на challenge/COIG-редирект."""
        try:
            if not url:
                return False
            return ("/challenge/" in url
                    or "__coig_challenged" in url
                    or "coig_challenged" in url)
        except Exception:
            return False

    async def wait_for_post_login_state(self, page, timeout_ms: int = 90000):
        """
        Аккуратно ждём один из сценариев после клика "Log in":
        - найдено 2FA-поле -> {"state": "2fa", "selector": "..."}
        - challenge URL -> {"state": "challenge"}
        - suspended URL -> {"state": "suspended"}
        - явная ошибка логина -> {"state": "failed", "reason": "..."}
        - похоже, вошли (ушли со /accounts/login) -> {"state": "maybe_logged_in"}
        - таймаут -> {"state": "timeout"}
        """
        import time
        poll = 0.5  # секунды
        deadline = time.monotonic() + (timeout_ms / 1000.0)

        TWO_FA_SELECTORS = [
            'input[aria-label="Code"]',
            'input[aria-label="Security code"]',
            'input[name="verificationCode"]',
            'input[name="security_code"]',
            'input[id="verificationCode"]',
            'input[autocomplete="one-time-code"]',
            'input[name="code"]',
        ]
        ERROR_SELECTORS = [
            '#slfErrorAlert',
            'div:has-text("There was a problem")',
            'p:has-text("incorrect")',
            'div:has-text("Try again later")',
        ]

        while time.monotonic() < deadline:
            if page.is_closed():
                return {"state": "failed", "reason": "page_closed"}

            url = page.url or ""
            # Прямые признаки блоков
            if self.is_challenge_url(url):
                return {"state": "challenge"}
            if "/suspended/" in url:
                return {"state": "suspended"}

            # 2FA поле
            for sel in TWO_FA_SELECTORS:
                el = await page.query_selector(sel)
                if el:
                    self.logger.send("INFO", f"Обнаружено поле 2FA: {sel}")
                    return {"state": "2fa", "selector": sel}

            # Ошибки
            for sel in ERROR_SELECTORS:
                if await page.query_selector(sel):
                    return {"state": "failed", "reason": f"login_error:{sel}"}

            # Ушли со страницы логина — возможно, вошли или открыли модалки
            if "instagram.com/accounts/login" not in url and "instagram.com/accounts" not in url:
                return {"state": "maybe_logged_in"}

            await page.wait_for_timeout(int(poll * 1000))

        return {"state": "timeout"}

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
                    # маскируем код в логах
                    self.logger.send("INFO", f"2FA код успешно получен: ***{code[-2:]}")
                    return code
                else:
                    self.logger.send("INFO", f"Неверный формат 2FA кода: {code}")
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

    async def login_to_instagram(self, page, username, password, two_factor_code) -> str:
        try:
            if page.is_closed():
                self.logger.send("ERROR", f"Страница уже закрыта перед логином {username}")
                return "failed"

            self.logger.send("INFO", f"Начало авторизации для пользователя {username}")
            await page.goto("https://www.instagram.com", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=60000)
            await self.accept_cookies_if_needed(page)

            # --- Cookies banner (best-effort) ---
            # try:
            #     self.logger.send("INFO", "Проверка наличия баннера cookies")
            #     for selector in [
            #         'button:has-text("Allow all cookies")',
            #         'div[role="dialog"] button:has-text("Allow all cookies")',
            #         'button:has-text("Decline optional cookies")'
            #     ]:
            #         if page.is_closed():
            #             return "failed"
            #         btn = await page.query_selector(selector)
            #         if btn:
            #             self.logger.send("INFO", f"Нашли кнопку cookies: {selector}")
            #             await btn.click()
            #             await page.wait_for_timeout(1200)
            #             break
            # except Exception as e:
            #     self.logger.send("INFO", f"Cookie banner err: {e}")

            # --- Landing 'Log in' (если есть) ---
            if page.is_closed():
                return "failed"
            login_button = await page.query_selector('button:has-text("Log in"), div[role="button"]:has-text("Log in")')
            if login_button:
                try:
                    await login_button.click()
                    self.logger.send("INFO", "Клик по кнопке Log in")
                    await page.wait_for_timeout(1000)
                except Exception as e:
                    self.logger.send("INFO", f"Не удалось кликнуть Log in: {e}")

            # --- Форма логина ---
            try:
                await page.wait_for_selector('input[name="username"]', timeout=20000)
            except Exception:
                self.logger.send("INFO", "Форма логина не появилась")
                await self.save_html_on_error(page, page.url, "Форма логина не появилась")
                return "failed"

            username_field = await page.query_selector('input[name="username"]')
            password_field = await page.query_selector('input[name="password"]')
            if not username_field or not password_field:
                self.logger.send("INFO", "Не найдены поля username/password")
                await self.save_html_on_error(page, page.url, "Нет полей username/password")
                return "failed"

            await username_field.fill(username)
            self.logger.send("INFO", f"Введён username: {username}")
            await password_field.fill(password)
            self.logger.send("INFO", "Введён пароль")

            final_login_button = await page.query_selector('button[type="submit"], div[role="button"][aria-label="Log in"]')
            if not final_login_button:
                self.logger.send("INFO", "Финальная кнопка входа не найдена")
                await self.save_html_on_error(page, page.url, "Финальная кнопка входа не найдена")
                return "failed"
            await final_login_button.click()
            self.logger.send("INFO", "Клик по финальной кнопке Log in")

            def _cookies_say_logged_in(cookies_list):
                try:
                    for c in cookies_list:
                        n = c.get("name")
                        d = c.get("domain", "")
                        v = c.get("value", "")
                        if n in ("sessionid", "ds_user_id") and "instagram.com" in d and v:
                            return True
                except Exception:
                    pass
                return False

            async def save_success_snapshot(label: str):
                try:
                    await self.save_html_snapshot(page, page.url or "https://www.instagram.com", label)
                except Exception as snapshot_err:
                    self.logger.send("INFO", f"Не удалось сохранить HTML после успешного входа ({label}): {snapshot_err}")

            TWO_FA_SELECTORS = [
                'input[aria-label="Code"]',
                'input[aria-label="Security code"]',
                'input[name="verificationCode"]',
                'input[name="security_code"]',
                'input[id="verificationCode"]',
                'input[autocomplete="one-time-code"]',
                'input[name="code"]',
            ]

            deadline = time.monotonic() + 120.0
            seen_2fa_selector = None

            while time.monotonic() < deadline:
                if page.is_closed():
                    return "failed"

                url_now = page.url or ""
                if ("/challenge/" in url_now) or ("__coig_challenged" in url_now) or ("coig_challenged" in url_now):
                    self.logger.send("INFO", "Обнаружен challenge — требуется верификация")
                    await self.save_html_on_error(page, url_now, "Challenge")
                    await self.deactivate_account_by_username(username)
                    return "challenge"
                if "/suspended/" in url_now:
                    self.logger.send("INFO", "Аккаунт приостановлен")
                    await self.save_html_on_error(page, url_now, "Suspended")
                    await self.deactivate_account_by_username(username)
                    return "suspended"

                cookies = await page.context.cookies()
                if _cookies_say_logged_in(cookies):
                    await save_success_snapshot("login_success_cookies_initial")
                    self.logger.send("INFO", "✅ Успешный вход в Instagram (по кукам)")
                    return "success"

                if not seen_2fa_selector:
                    for sel in TWO_FA_SELECTORS:
                        if await page.query_selector(sel):
                            seen_2fa_selector = sel
                            self.logger.send("INFO", f"Обнаружено поле 2FA: {sel}")
                            break

                if seen_2fa_selector:
                    break  # переходим к вводу 2FA

                await page.wait_for_timeout(500)

            # --- Если 2FA так и не появилось и куков нет — считаем фейлом ---
            if not seen_2fa_selector:
                await self.save_html_on_error(page, page.url, "Post-login timeout/no-2FA-no-cookies")
                return "failed"

            # --- 2FA: получить код и ввести ---
            code = await self.get_2fa_code(page, two_factor_code)
            if not code:
                self.logger.send("INFO", "Не удалось получить 2FA код")
                return "failed"
            self.logger.send("INFO", f"Вводим 2FA код: ***{code[-2:]}")

            field = await page.query_selector(seen_2fa_selector) or \
                await page.query_selector('input[autocomplete="one-time-code"], input[aria-label="Code"], input[name="verificationCode"], input[name="security_code"], input[name="code"]')
            if not field:
                self.logger.send("INFO", "Поле 2FA исчезло до ввода")
                return "failed"

            try:
                await field.fill("")
                await field.type(code, delay=50)
            except Exception as e:
                self.logger.send("INFO", f"Не удалось ввести 2FA: {e}")
                return "failed"

            cont = await page.query_selector(
                'div[role="button"][aria-label="Continue"], button:has-text("Continue"), button:has-text("Confirm"), button[type="submit"]'
            )
            try:
                if cont:
                    await cont.click()
                else:
                    await page.keyboard.press("Enter")
            except Exception as e:
                self.logger.send("INFO", f"Клик по confirm/enter не удался: {e}")

            # --- После ввода 2FA терпеливо ждём куки/успех (до 90с) ---
            deadline2 = time.monotonic() + 90.0
            while time.monotonic() < deadline2:
                if page.is_closed():
                    return "failed"

                url_now = page.url or ""
                if ("/challenge/" in url_now) or ("__coig_challenged" in url_now) or ("coig_challenged" in url_now):
                    await self.save_html_on_error(page, url_now, "Post-2FA Challenge")
                    await self.deactivate_account_by_username(username)
                    return "challenge"
                if "/suspended/" in url_now:
                    await self.save_html_on_error(page, url_now, "Post-2FA Suspended")
                    await self.deactivate_account_by_username(username)
                    return "suspended"

                cookies = await page.context.cookies()
                if _cookies_say_logged_in(cookies):
                    await save_success_snapshot("login_success_post_2fa")
                    self.logger.send("INFO", "✅ Успешный вход в Instagram")
                    return "success"

                await page.wait_for_timeout(500)

            # Попробуем «толкнуть» SPA: перейти на главную и проверить куки ещё раз
            try:
                await page.goto("https://www.instagram.com/", wait_until="networkidle", timeout=60000)
            except Exception:
                pass
            cookies = await page.context.cookies()
            if _cookies_say_logged_in(cookies):
                await save_success_snapshot("login_success_after_force_nav")
                self.logger.send("INFO", "✅ Успешный вход в Instagram (после принудительной навигации)")
                return "success"

            # Если всё ещё висим на логине — фейл
            if "instagram.com/accounts/login" in (page.url or ""):
                self.logger.send("INFO", "Остались на login-странице — вход не удался")
                await self.save_html_on_error(page, page.url, "Неудачный вход")
                return "failed"

            await save_success_snapshot("login_success_url_check")
            self.logger.send("INFO", "✅ Успешный вход в Instagram (по URL)")
            return "success"

        except Exception as e:
            try:
                if not page.is_closed():
                    await self.save_html_on_error(page, page.url or "https://www.instagram.com", f"Ошибка при входе: {e}")
            except Exception:
                pass
            self.logger.send("INFO", f"Исключение при входе {username}: {e}")
            return "failed"

    async def scroll_until(self, page, url: str, selector: str,
                           delay: float = 5.0, max_idle_rounds: int = 5):
        prev_count = 0
        idle_rounds = 0
        max_scroll_attempts = 3
        reel_data = set()
        prev_reel_count = 0

        if await self.accept_cookies_if_needed(page):
            if "/consent/" in (page.url or ""):
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(500)

        for attempt in range(max_scroll_attempts):
            self.logger.send("INFO", f"Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

            while True:
                new_reels_added = False
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
                        entry = (full_url, image_url)
                        if entry not in reel_data:
                            reel_data.add(entry)
                            new_reels_added = True

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
                current_reel_count = len(reel_data)
                self.logger.send("INFO", f"Текущее количество элементов: {current_count}, URL-ов рилов: {current_reel_count}")

                if not new_reels_added and current_count == prev_count and current_reel_count == prev_reel_count:
                    idle_rounds += 1
                    self.logger.send("INFO", f"Количество элементов не изменилось, idle_rounds: {idle_rounds}")
                else:
                    idle_rounds = 0

                prev_count = current_count
                prev_reel_count = current_reel_count

                if idle_rounds >= max_idle_rounds:
                    self.logger.send("INFO", f"Достигнут конец списка рилов для профиля {url}")
                    self.logger.send("INFO", f"Собрано {current_reel_count} пар (URL рила, URL изображения)")
                    break

                is_at_bottom = await page.evaluate("""
                    () => {
                        return (window.innerHeight + window.scrollY) >= document.body.scrollHeight;
                    }
                """)    
                if is_at_bottom and not new_reels_added:
                    self.logger.send("INFO", f"Достигнут конец страницы для {url}")
                    break

        return list(reel_data)

    async def parse_channel(self, url: str, channel_id: int, user_id: int,
                            max_retries: int = 3, proxy_list: list = None,
                            accounts: list = None):
        parse_started_at = datetime.utcnow()
        self.proxy_list = proxy_list or []
        if not self.proxy_list:
            self.logger.send("INFO", "Список прокси пуст, используем без прокси")

        # Инициализация атрибутов
        if not hasattr(self, 'playwright'):
            self.playwright = None
            self.browser = None
            self.context = None
            self.page = None
            self.current_proxy = None
            self.failed_proxies = set()

        self.is_closing = False
        image_tasks = []
        had_endpoint_interaction = False
        failed_proxies = self.failed_proxies
        MAX_PROXY_FAILURES = len(self.proxy_list) if self.proxy_list else 0
        collected_videos: List[Dict] = []
        collected_index: Dict[str, int] = {}
        processed_counter = 0

        if self.playwright is None:
            self.playwright = await async_playwright().start()

        # --- Прокси и браузер ---
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
                self.logger.send("INFO", f"Неверный формат прокси '{proxy_str}': {str(e)}")
                return None

        async def get_httpx_proxy_url(proxy_str):
            return f"http://{proxy_str}" if proxy_str else None

        async def create_browser_with_proxy(proxy_str):
            proxy_config = await get_proxy_config(proxy_str)
            if not proxy_config:
                return None, None, None
            device = self.playwright.devices["iPhone 14 Pro"]
            browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    "--window-size=390,844",
                    # "--headless=new",
                ]
            )
            context = await browser.new_context(
                **device,
                locale="en-US",
                # timezone_id="Europe/Amsterdam",
                timezone_id="America/New_York",
                proxy=proxy_config,
            )

            # Повышаем таймауты по умолчанию — чтобы «досидеть» поздние элементы
            try:
                context.set_default_timeout(90000)
                context.set_default_navigation_timeout(90000)
            except Exception:
                pass

            page = await context.new_page()
            try:
                page.set_default_timeout(90000)
                page.set_default_navigation_timeout(90000)
            except Exception:
                pass

            stealth = Stealth()
            await stealth.apply_stealth_async(page)
            return browser, context, page

        async def safe_close_all():
            """Безопасное закрытие всех ресурсов (Playwright >= 1.46 совместимо)"""
            self.is_closing = True
            close_errors = []

            # --- Удаляем обработчики событий ---
            try:
                if getattr(self, "page", None):
                    try:
                        self.page.off("response", handle_response)
                    except Exception:
                        pass
            except Exception as e:
                close_errors.append(f"remove_listeners: {e}")

            await asyncio.sleep(0.3)

            # --- Последовательно закрываем page/context/browser ---
            async def safe_close(name, obj, func):
                if not obj:
                    return
                try:
                    if hasattr(obj, "is_closed") and obj.is_closed():
                        return
                    await func()
                except Exception as e:
                    close_errors.append(f"{name}: {e}")

            await safe_close("page", getattr(self, "page", None), lambda: self.page.close())
            await safe_close("context", getattr(self, "context", None), lambda: self.context.close())
            await safe_close("browser", getattr(self, "browser", None), lambda: self.browser.close())

            # --- Завершение Playwright ---
            try:
                if getattr(self, "playwright", None):
                    await self.playwright.stop()
            except Exception as e:
                close_errors.append(f"playwright.stop(): {e}")

            # --- Очистка атрибутов ---
            for attr in ['page', 'context', 'browser', 'playwright', 'current_proxy']:
                if hasattr(self, attr):
                    try:
                        setattr(self, attr, None)
                    except Exception as e:
                        close_errors.append(f"clear_attr_{attr}: {e}")

            if close_errors:
                self.logger.send("INFO", f"Ошибки при закрытии ресурсов: {close_errors}")
            else:
                self.logger.send("INFO", "✅ Все ресурсы Playwright корректно закрыты")

        async def switch_proxy():
            """Переключение прокси"""
            nonlocal failed_proxies, MAX_PROXY_FAILURES
            available_proxies = [p for p in (self.proxy_list or [None]) if p not in failed_proxies]

            if len(failed_proxies) >= MAX_PROXY_FAILURES and MAX_PROXY_FAILURES > 0:
                self.logger.send("INFO", "⏳ Все прокси временно не работают. Ждём 1 минуту...")
                await asyncio.sleep(60)
                failed_proxies.clear()
                available_proxies = self.proxy_list.copy() if self.proxy_list else [None]
                self.logger.send("INFO", "🔁 Список прокси сброшен, начинаем заново.")

            if not available_proxies:
                available_proxies = self.proxy_list.copy() if self.proxy_list else [None]
            if not available_proxies:
                raise Exception("Список прокси пуст")

            new_proxy = random.choice(available_proxies)
            self.logger.send("INFO", f"🔁 Переключаемся на прокси: {new_proxy}")

            if self.browser and not self.is_closing:
                try:
                    await self.browser.close()
                    await asyncio.sleep(0.5)
                except Exception as e:
                    self.logger.send("INFO", f"Ошибка при закрытии старого browser: {e}")

            browser, context, page = await create_browser_with_proxy(new_proxy)
            if not browser:
                failed_proxies.add(new_proxy)
                self.logger.send("INFO", f"❌ Прокси {new_proxy} не работает, пробуем другую...")
                return await switch_proxy()

            self.current_proxy = new_proxy
            self.browser = browser
            self.context = context
            self.page = page
            self.is_closing = False
            if new_proxy in failed_proxies:
                failed_proxies.remove(new_proxy)

        if not self.current_proxy:
            await switch_proxy()

        # --- Работа с изображениями ---
        async def download_image(url: str) -> bytes:
            proxy_url = await get_httpx_proxy_url(self.current_proxy)
            async with httpx.AsyncClient(timeout=20.0, proxy=proxy_url) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return resp.content

        async def upload_image(video_id: int, image_url: str):
            try:
                image_bytes = await download_image(image_url)
                file_name = image_url.split("/")[-1].split("?")[0] or f"{video_id}.jpg"
                async with httpx.AsyncClient(timeout=30.0) as client:
                    files = {"file": (file_name, image_bytes, "image/jpeg")}
                    resp = await client.post(
                        f"https://sn.dev-klick.cyou/api/v1/videos/{video_id}/upload-image/",
                        files=files,
                    )
                    resp.raise_for_status()
                    self.logger.send("INFO", f"📸 Загружено превью для видео {video_id}")
            except Exception as e:
                self.logger.send("INFO", f"❌ Ошибка загрузки превью {video_id}: {e}")

        async def save_video_and_image(channel_id: int, reel_code: str, reel_url: str, play_count: int, image_url: str):
            nonlocal had_endpoint_interaction, processed_counter
            video_data = {
                "type": "instagram",
                "channel_id": channel_id,
                "link": reel_url,
                "name": reel_code,
                "amount_views": play_count,
                "image_url": image_url,
            }
            index = collected_index.get(reel_url)
            if index is None:
                collected_index[reel_url] = len(collected_videos)
                collected_videos.append(video_data)
            else:
                existing = collected_videos[index]
                existing["amount_views"] = play_count
                if image_url and not existing.get("image_url"):
                    existing["image_url"] = image_url
            try:
                async with httpx.AsyncClient() as client:
                    check_resp = await client.get(
                        f"https://sn.dev-klick.cyou/api/v1/videos/?link={reel_url}", timeout=20.0
                    )
                    had_endpoint_interaction = True
                    video_id = None
                    is_new = False

                    if check_resp.status_code == 200:
                        result = check_resp.json()
                        videos = result.get("videos", [])
                        if videos:
                            existing_video = videos[0]
                            video_id = existing_video['id']

                            # Если у видео нет картинки — обновим просмотры и добавим задачу на загрузку
                            if existing_video.get('image') is None:
                                update_resp = await client.patch(
                                    f"https://sn.dev-klick.cyou/api/v1/videos/{video_id}",
                                    json={"amount_views": play_count},
                                    timeout=20.0
                                )
                                update_resp.raise_for_status()
                                if image_url:
                                    image_tasks.append((video_id, image_url))
                                    self.logger.send("INFO", f"📸 Добавлено в очередь для скачивания фото {video_id}: {image_url}")
                            else:
                                # Фото уже есть — только обновим просмотры
                                update_resp = await client.patch(
                                    f"https://sn.dev-klick.cyou/api/v1/videos/{video_id}",
                                    json={"amount_views": play_count},
                                    timeout=20.0
                                )
                                update_resp.raise_for_status()
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        resp = await client.post(
                            "https://sn.dev-klick.cyou/api/v1/videos/",
                            json=video_data,
                            timeout=20.0,
                        )
                        resp.raise_for_status()
                        created_video = resp.json()
                        video_id = created_video["id"]
                        # self.logger.send("INFO", f"📦 Создано видео {video_id} ({reel_url})")
                        if image_url:
                            image_tasks.append((video_id, image_url))
                            self.logger.send("INFO", f"📸 Добавлено в очередь фото {video_id}")
                processed_counter += 1
            except Exception as e:
                self.logger.send("INFO", f"❌ Ошибка сохранения видео {reel_url}: {e}")

        collected_queries = []

        async def handle_response(response):
            if self.is_closing:
                return
            url_resp = str(response.url)
            if not any(x in url_resp for x in ["graphql/query", "/api/v1/"]):
                return
            try:
                json_resp = await response.json()
            except Exception as e:
                self.logger.send("INFO", f"Ошибка JSON в handle_response: {e}")
                return
            collected_queries.append(json_resp)

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
                image_url = (
                    media.get("image_versions2", {}).get("candidates", [{}])[0].get("url")
                )
                await save_video_and_image(channel_id, reel_code, reel_url, play_count, image_url)

            media_edges = (
                json_resp.get("user", {}).get("edge_owner_to_timeline_media", {}).get("edges", [])
            )
            for edge in media_edges:
                node = edge.get("node", {})
                if node.get("product_type") != "clips":
                    continue
                reel_code = node.get("shortcode")
                reel_url = f"https://www.instagram.com/reel/{reel_code}/"
                play_count = node.get("video_play_count", 0)
                image_url = node.get("display_url")
                await save_video_and_image(channel_id, reel_code, reel_url, play_count, image_url)

        used_accounts = set()
        self.logger.send("INFO", f"Используемые аккаунты: {accounts}")
        max_account_retries = len(accounts) if accounts else 0
        success = False

        try:
            for account_attempt in range(max_account_retries):
                available_accounts = [acc for acc in accounts if acc not in used_accounts]
                if not available_accounts:
                    break

                account = random.choice(available_accounts)
                used_accounts.add(account)
                had_endpoint_interaction = False
                username, password, two_factor_code = account.split(":")
                self.logger.send("INFO", f"Попытка {account_attempt + 1}/{max_account_retries} с аккаунтом {username}")

                if not self.current_proxy or self.current_proxy in failed_proxies:
                    await switch_proxy()
                else:
                    self.logger.send("INFO", f"Используем текущий прокси: {self.current_proxy}")

                # избегаем дублирующих подписок на событие
                try:
                    if self.page:
                        self.page.off("response", handle_response)
                except Exception:
                    pass
                self.page.on("response", handle_response)

                status = await self.login_to_instagram(self.page, username, password, two_factor_code)
                if status == "challenge":
                    failed_proxies.add(self.current_proxy)
                    self.logger.send("INFO", "⚠️ Challenge: деактивировал аккаунт, переключаю прокси и пробую другой аккаунт")
                    continue
                if status == "suspended":
                    failed_proxies.add(self.current_proxy)
                    self.logger.send("INFO", "⚠️ Аккаунт приостановлен: переключаю прокси и пробую другой аккаунт")
                    continue
                if status != "success":
                    failed_proxies.add(self.current_proxy)
                    self.logger.send("INFO", f"⚠️ Логин неуспешен (status={status}), пробуем другой прокси/аккаунт")
                    continue

                # --- Навигация в профиль (reels) ---
                parsed_url = urlparse(url)
                clean_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path.rstrip('/'), '', '', ''))
                reels_url = f"{clean_url}/reels/"
                self.logger.send("INFO", f"Открытие профиля {reels_url}")

                try:
                    await self.page.goto(reels_url, wait_until="networkidle")
                    await asyncio.sleep(3)

                    # Важная повторная проверка на challenge после перехода в профиль
                    if self.is_challenge_url(self.page.url):
                        self.logger.send("INFO", f"Challenge после перехода в профиль: {self.page.url}")
                        await self.deactivate_account_by_username(username)
                        failed_proxies.add(self.current_proxy)
                        await switch_proxy()
                        continue

                    # Закрываем баннер сохранения логина, если всплыл
                    try:
                        not_now_button = await self.page.wait_for_selector(
                            'div[role="button"]:has-text("Not now")',
                            timeout=6000
                        )
                        if not_now_button:
                            await not_now_button.click()
                            self.logger.send("INFO", "✅ Нажата кнопка 'Not now'")
                            await asyncio.sleep(2)
                    except Exception as e:
                        self.logger.send("INFO", f"Окно 'Save your login info?' не появилось или уже закрыто: {e}")

                    await self.accept_cookies_if_needed(self.page)

                    self.logger.send("INFO", f"✅ Перешли на {reels_url}")
                    current_page = self.page
                    self.logger.send("INFO", f"Текущая страница: {current_page}")

                    reel_pairs = await self.scroll_until(self.page, reels_url, selector="div._aajy")

                    if len(reel_pairs) == 0:
                        self.logger.send("INFO", "⚠️ После парсинга собрано 0 рилсов — переключаюсь на другой прокси/аккаунт и пробую заново")
                        failed_proxies.add(self.current_proxy)
                        try:
                            image_tasks.clear()
                        except Exception:
                            pass
                        try:
                            await self.page.goto("about:blank", timeout=10000)
                        except Exception:
                            pass
                        # переключаемся на новый прокси и идём на следующий аккаунт
                        await switch_proxy()
                        continue

                    if not had_endpoint_interaction:
                        self.logger.send("INFO", "⚠️ Данные не были отправлены на эндпоинты — меняем аккаунт и прокси")
                        failed_proxies.add(self.current_proxy)
                        try:
                            image_tasks.clear()
                        except Exception:
                            pass
                        try:
                            await self.page.goto("about:blank", timeout=10000)
                        except Exception:
                            pass
                        try:
                            collected_queries.clear()
                        except Exception:
                            pass
                        await switch_proxy()
                        continue

                    if image_tasks:
                        self.logger.send("INFO", f"📸 Начинаем загрузку {len(image_tasks)} изображений...")
                        for idx, (video_id, img_url) in enumerate(image_tasks):
                            await upload_image(video_id, img_url)
                            if idx < len(image_tasks) - 1:
                                await asyncio.sleep(4)
                    else:
                        self.logger.send("INFO", "Список image_tasks пуст")

                    self.logger.send("INFO", f"✅ Успешно обработано {len(image_tasks)} новых видео")
                    success = True
                    break

                except PlaywrightTimeoutError as e:
                    self.logger.send("ERROR", f"⏱ Timeout при обработке reels {reels_url} после входа {username}: {type(e).__name__}: {e}")
                    self.logger.send("ERROR", traceback.format_exc())
                    try:
                        if getattr(self, "page", None) and not self.page.is_closed():
                            await self.save_html_on_error(self.page, self.page.url or reels_url, f"Timeout при обработке reels: {e}")
                    except Exception as save_err:
                        self.logger.send("INFO", f"Не удалось сохранить HTML после timeout: {save_err}")
                    failed_proxies.add(self.current_proxy)
                    try:
                        image_tasks.clear()
                    except Exception:
                        pass
                    try:
                        await switch_proxy()
                    except Exception as switch_err:
                        self.logger.send("ERROR", f"Не удалось переключиться на новый прокси после timeout: {switch_err}")
                        raise
                    continue

                except Exception as e:
                    self.logger.send("ERROR", f"❗️ Ошибка после входа {username} при открытии {reels_url}: {type(e).__name__}: {e!r}")
                    self.logger.send("ERROR", traceback.format_exc())
                    try:
                        if getattr(self, "page", None) and not self.page.is_closed():
                            await self.save_html_on_error(self.page, self.page.url or reels_url, f"Post-login ошибка: {e}")
                    except Exception as save_err:
                        self.logger.send("INFO", f"Не удалось сохранить HTML после ошибки post-login: {save_err}")
                    failed_proxies.add(self.current_proxy)
                    try:
                        image_tasks.clear()
                    except Exception:
                        pass
                    try:
                        await switch_proxy()
                    except Exception as switch_err:
                        self.logger.send("ERROR", f"Не удалось переключиться на новый прокси после ошибки: {switch_err}")
                        raise
                    continue

            if not success:
                self.logger.send("ERROR", "❌ Не удалось спарсить профиль ни с одним аккаунтом")

        finally:
            await safe_close_all()

        total_views = self._calculate_total_views(collected_videos)
        parse_finished_at = datetime.utcnow()
        started_str = parse_started_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        finished_str = parse_finished_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.logger.send("INFO", f"Собрано - {len(collected_videos)} | профиль - {url} | id канала - {channel_id} | общее кол-во просмотров - {total_views} - {processed_counter} - начало парсинга - {started_str} - конец парсинга - {finished_str}")


# # ----------------------- Пример запуска -----------------------

# async def main():
#     proxy_list = [
#         "iuZKi4BGyp:vHKtDTzA0z@45.150.35.98:24730",
#         "QgSnMzKNDg:rQR6PpWyH6@45.150.35.140:37495",
#         "nGzc2Uw9o1:IOEIP5yqHF@45.150.35.72:30523",
#         "ljpOi6p4wE:AzWMnGcwT9@45.150.35.75:56674",
#         "mpiv4PCpJG:oFct8hLGU3@109.120.131.51:52137",
#         "BnpDZPR6sd:dIciqNGo7d@45.150.35.97:51776",
#         "3fNux7Ul42:pkfkTaLi9D@109.120.131.31:59895",
#         "dnyqkeZB92:y38H1PzPef@45.150.35.28:27472",
#         "udWhRyA0GU:laqpdeslpC@45.150.35.225:22532",
#         "qMGdKOcu0w:MfeGgg0Dh9@45.150.35.205:23070",
#         "cpeFm6Dh5x:bQXTp4e1gf@45.150.35.111:22684",
#         "K6dlqo2Xbn:KJ7TE9kPO7@45.150.35.51:49586",
#         "db2JltFuja:8MItiT5T12@45.150.35.10:58894",
#         "79zEDvbAVA:xJBsip0IQK@45.150.35.4:58129",
#         "mBQnv9UCPd:e3VkzkB9p5@45.150.35.74:55101",
#         "IDWsfoHdf1:z6d3r0tnzM@45.150.35.244:42679",
#     ]
#     parser = InstagramParser()
#     url = "https://www.instagram.com/shd.tattoo"
#     accounts = [
#         "juan.itaandersen:fsm8f5tb:FOJ2E2475FRD3UR5NY2E45YPTEJK5APH",
#         "jodyrhodes74:Kr2V3bxS:2KYNTJCUL74SKSNTVGFENBL6DOAJ65X6",
#         "Jeannetteosley12:7nYEEexK:SVTLSGQZVWLNB3ID2PCB5TR7C4VWWPES",
#         "hild.amoody:6FL9Jg2j:FW26JAKMNNLP2U5BLQQF6L4ABMMMB4DC",
#         "eliseowolf95:CuNAryR3Ly:VF442BGSAVQK3TBMGKM3SAN2U75EKMRG",
#         "jolenemccoy650:KQ9GsFqzHy:GI2NPPGSYMTFZD4F75XMOVIAB4GFWSP4",
#         "taylorvega968:FqR2RBQckZ:USEVPAIL5TQTVIT6N4YZQP6TMS6N6WFL",
#         "danielle_stafford:QbR86VfEud:YSKAUQROK633XKXT5M2GJZPGEEJSPGJ3",
#         "frasheri8498:NzPAAX5xqC:SJZ3D5XWEZYWHOIYXANTZZQTQ34BE47D",
#         "bonilla.scout:KNWKdS3Gew:J33P5656TMAH7R55WUKML3TEA7RGSFQG",
#         "TianaWard468:p4ADst2Y:D32FIPVHV3WVQ773B747IHUEVYWH35SH",
#         "EstaThiel658:hYxMvvBE:EXZ2VZCQYFX7SWQF3SBWS7BAVZ7XEJYQ",
#         "sonyalind672:6Hm6h25c:UAMAGCWNVDQC3LBTBBGOPDJ7ZISVG5NA",
#         "EdenLind866:xJCqXQTh:ZVSYQTTMSSNUJF7YZ3ITQGPMUHE7PD2W",
#         "danawiza885:p5zFe5g9:N3DFOQD7GYLQAE5QKOC6EHKOJHQW6W7B",
#     ]
#     user_id = 1
#     await parser.parse_channel(url, channel_id=1, user_id=user_id,
#                                accounts=accounts, proxy_list=proxy_list)

# if __name__ == "__main__":
#     asyncio.run(main())
