import asyncio
import json
import re
import random
from urllib.parse import urlparse, urlunparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth
import httpx


class InstagramParser:
    def __init__(self):
        self.proxy_list = [
            "J7hnPSWjfS:DMNa7O7ZhS@103.127.76.132:34259",
            # "TwgvqV:KpJWjKHitx@188.130.219.228:1050",
        ]
        self.accounts = [
            "elenaking889:MzLN7h9jq:LLGLPQYOYAF3DSIFCPPKJKG4U4G636MY",
            "valentineabdullah:AgUjDk2F:SK64JY4RRN27J3WPWLPTH4PDJSSHTDQY",
            "alfaroaugust36:u9btQq4p:VJUSPOUW5DQVBFW36QV32H5AI3AGKBMW",
            "delarosaxzavier:2Gxew7Y7:OTWMXHH4UIJASWVSBTRNFP6TVVUU5MEO",
            "iylaayala685:HQRydh4f:SVBNV64SPB5HQPKH5A2XPS2RPJGADRKR",
            # "lanehaley527:7DjA9GZc:ZTLPSGVSIG6SNNOIIMTMFOXBWYAFFZC2",

            "lizamarks974:cEprBdwR:4LAJODJX6QBH3UGMTINIIATEV5LIMALH",
            # "ednastamm889:h5JrHw8j:SHMSJZULXUBEY2DXSY35MTVHBEN4QNDN",
            "ihaldare381:c22BC6cY:6CHNKT2Z5VC2IWPHDLP2KP5CEOM5PVNQ",
            "gerrylind948:AZYGpACe:IQZC4GVAAL66CIRSNGLK22OSELQ5BZ33",
            "kanekutch913:v5yprTC5:63FWYHZHIYUD7YVTPDO3LJV5TYX2PX7L",
            "alecryan795:T7xJ6euZ:3W4224N56AO7K5LBXKLPLUWHQZJZRRMB",
            "lonzokoch385:C5cF5u4v:ESSSG7QBBKA2J2ZZZM2ZKAJDMC7MKXFK",
            # "connerhoffman8:rA2JVsXJ:5FH7UM5DB5QW4TZMCN6Q5RWBSQCZKQ6M"
        ]

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

    # async def send_batch(self, batch):
    #     async with httpx.AsyncClient() as client:
    #         try:
    #             response = await client.post(
    #                 "http://analytics-api:8000/analytics/video",
    #                 json=batch,
    #                 timeout=10.0
    #             )
    #             if response.status_code == 200:
    #                 print(f"📦 Отправлено {len(batch)} видео")
    #             else:
    #                 print(f"❌ Ошибка при отправке: {response.status_code}, {response.text}")
    #         except Exception as e:
    #             print(f"❌ Исключение при отправке батча: {str(e)}")

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

    async def login_to_instagram(self, page, username,
                                 password, two_factor_code):
        try:
            print(f"Начало авторизации для пользователя {username}")
            print("Переход на главную страницу Instagram")
            await page.goto("https://www.instagram.com", timeout=60000)
            print("Ожидание полной загрузки страницы")
            await page.wait_for_load_state("networkidle", timeout=60000)
            print("Страница загружена")

            # Обработка баннера cookies
            print("Проверка наличия баннера cookies")
            try:
                cookie_selectors = [
                    'button:has-text("Allow all cookies")',
                    'div[role="dialog"] button:has-text("Allow all cookies")',
                    # 'button[type="button"]:has-text("Allow all cookies")',
                    # 'button:has-text("Accept All")',
                    # 'button:has-text("Accept")',
                    # 'button:has-text("Allow essential and optional cookies")',
                    # 'div[role="dialog"] button:has-text("Decline optional cookies")',
                    # 'button[type="button"]:has-text("Decline optional cookies")',
                    # 'div[role="dialog"] button'
                ]
                accept_cookies_button = None
                for selector in cookie_selectors:
                    print(f"Поиск кнопки cookies: {selector}")
                    try:
                        await page.wait_for_selector(selector, timeout=25000)
                        accept_cookies_button = await page.query_selector(
                            selector)
                        if accept_cookies_button:
                            print(
                                f"Кнопка cookies найдена по селектору: {selector}"
                            )
                            break
                    except Exception as e:
                        print(f"Селектор {selector} не найден: {str(e)}")

                if not accept_cookies_button:
                    print("Попытка найти кнопку 'Allow all cookies' через JavaScript")
                    accept_cookies_button = await page.evaluate_handle("""
                        () => {
                            const buttons = document.querySelectorAll('button');
                            for (const button of buttons) {
                                if (button.textContent.includes('Allow all cookies')) {
                                    return button;
                                }
                            }
                            return null;
                        }
                    """)
                    if accept_cookies_button:
                        print("Кнопка 'Allow all cookies' найдена через JavaScript")

                if not accept_cookies_button:
                    print(

                        "Попытка найти кнопку 'Decline optional cookies' "
                        "через JavaScript"
                    )
                    accept_cookies_button = await page.evaluate_handle("""
                        () => {
                            const buttons = document.querySelectorAll('button');
                            for (const button of buttons) {
                                if (button.textContent.includes('Decline optional cookies')) {
                                    return button;
                                }
                            }
                            return null;
                        }
                    """)
                    if accept_cookies_button:
                        print(
                            "Кнопка 'Decline optional cookies' "
                            "найдена через JavaScript"
                        )

                if accept_cookies_button:
                    is_visible = await accept_cookies_button.is_visible()
                    is_enabled = await accept_cookies_button.is_enabled()
                    print(
                        f"Кнопка cookies видима: {is_visible}, "
                        "активна: {is_enabled}"
                    )
                    if is_visible and is_enabled:
                        try:
                            print("Клик по кнопке cookies")
                            await accept_cookies_button.click(timeout=25000)
                            await page.wait_for_timeout(6000)
                            print(
                                             "Баннер cookies обработан")
                        except Exception as click_error:
                            print(

                                f"Не удалось кликнуть по кнопке cookies: {str(click_error)}"
                            )

                            print(

                                "Попытка принудительного скрытия баннера "
                                "cookies через JavaScript"
                            )
                            await page.evaluate("""
                                () => {
                                    const banner = document.querySelector('div[role="dialog"].x1n2onr6');
                                    if (banner) {
                                        banner.style.display = 'none';
                                    }
                                }
                            """)
                            await page.wait_for_timeout(4000)
                    else:
                        print(
                            "Кнопка cookies не видима "
                            "или не активна"
                        )
                        await self.save_html_on_error(
                            page, "https://www.instagram.com",
                            "Кнопка cookies не видима или не активна"
                        )
                else:
                    print(
                        "Баннер cookies не найден, продолжаем"
                    )
            except Exception as e:
                print(
                    f"Ошибка при обработке баннера cookies: {str(e)}"
                )
                await self.save_html_on_error(
                    page, "https://www.instagram.com",
                    f"Ошибка при обработке баннера cookies: {str(e)}"
                )

            print("Поиск начальной кнопки Log in")
            login_button = await page.query_selector(
                'button:has-text("Log in"), div[role="button"]:has-text("Log in")'
            )
            if not login_button:
                await self.save_html_on_error(
                    page, "https://www.instagram.com",
                    "Начальная кнопка Log in не найдена"
                )
                print("Начальная кнопка Log in не найдена")
                return False
            is_visible = await login_button.is_visible()
            is_enabled = await login_button.is_enabled()
            print(
                f"Начальная кнопка Log in видима: {is_visible}, "
                f"активна: {is_enabled}"
            )
            if is_visible and is_enabled:
                print("Клик по начальной кнопке Log in")
                await login_button.click(timeout=60000)
            else:
                await self.save_html_on_error(
                    page, "https://www.instagram.com",
                    "Начальная кнопка Log in не видима или не активна"
                )
                print(
                    "Начальная кнопка Log in не видима или не активна"
                )
                return False

            print("Ожидание формы логина")
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    await page.wait_for_selector('input[name="username"]',
                                                 timeout=12000)
                    print("Форма логина найдена")
                    break
                except PlaywrightTimeoutError:
                    print(f"Поле username не найдено, попытка {attempt}/{max_attempts}")
                    if attempt == max_attempts:
                        await self.save_html_on_error(
                            page, "https://www.instagram.com",
                            "Поле username не найдено после всех попыток")
                        print(
                            "Поле username не найдено после всех попыток"
                        )
                        return False
                    await page.wait_for_timeout(3000)

            print("Поиск поля username")
            username_field = await page.query_selector(
                'input[name="username"]')
            if not username_field:
                await self.save_html_on_error(
                    page, "https://www.instagram.com",
                    "Поле username не найдено")
                print("Поле username не найдено")
                return False
            is_visible = await username_field.is_visible()
            is_enabled = await username_field.is_enabled()
            print(f"Поле username видимо: {is_visible}, активно: {is_enabled}")
            if not (is_visible and is_enabled):
                await self.save_html_on_error(
                    page, "https://www.instagram.com",
                    "Поле username не видимо или не активно")
                print("Поле username не видимо или не активно")
                return False
            print(f"Заполнение поля username: {username}")
            await username_field.fill(username)
            print(f"Имя пользователя введено: {username}")

            print("Поиск поля password")
            password_field = await page.query_selector(
                'input[name="password"]')
            if not password_field:
                await self.save_html_on_error(
                    page, "https://www.instagram.com",
                    "Поле password не найдено")
                print("Поле password не найдено")
                return False
            is_visible = await password_field.is_visible()
            is_enabled = await password_field.is_enabled()
            print(f"Поле password видимо: {is_visible}, активно: {is_enabled}")
            if not (is_visible and is_enabled):
                await self.save_html_on_error(
                    page, "https://www.instagram.com",
                    "Поле password не видно или не активно")
                print("Поле password не видно или не активно")
                return False
            print("Заполнение поля password")
            await password_field.fill(password)
            print("Пароль введён")

            print("Поиск финальной кнопки Log in")
            final_login_button = await page.query_selector(
                'button[type="submit"], div[role="button"][aria-label="Log in"]'
            )
            if not final_login_button:
                await self.save_html_on_error(
                    page, "https://www.instagram.com",
                    "Финальная кнопка Log in не найдена")
                print("Финальная кнопка Log in не найдена")
                return False
            is_visible = await final_login_button.is_visible()
            is_enabled = await final_login_button.is_enabled()
            print(f"Финальная кнопка Log in видима: {is_visible}, активна: {is_enabled}")
            if is_visible and is_enabled:
                print("Клик по финальной кнопке Log in")
                await final_login_button.click(timeout=60000)
            else:
                await self.save_html_on_error(
                    page, "https://www.instagram.com",
                    "Финальная кнопка Log in не видима или не активна")
                print("Финальная кнопка Log in не видима или не активна")
                return False

            print(
                "Проверка на перенаправление на страницу /challenge/"
            )
            await page.wait_for_timeout(3000)
            current_url = page.url
            print(f"Текущий URL после клика Log in: {current_url}")
            if "/challenge/" in current_url:
                await self.save_html_on_error(
                    page, current_url,
                    "Перенаправление на страницу /challenge/")
                print(
                    "ERROR", "Обнаружено перенаправление на страницу /challenge/."
                    " Возможно, требуется CAPTCHA или дополнительная верификация."
                )
                return False

            # Обработка 2FA
            print("Проверка необходимости 2FA")
            try:
                await page.wait_for_selector('input[aria-label="Code"]',
                                             timeout=60000)
                print("Найдено поле для ввода 2FA кода")
                verification_field = await page.query_selector(
                    'input[aria-label="Code"]')
                if not verification_field:
                    await self.save_html_on_error(page, page.url,
                                                  "Поле ввода 2FA не найдено")
                    print("Поле ввода 2FA не найдено")
                    return False

                # Получение 2FA кода
                max_2fa_attempts = 3
                for attempt in range(1, max_2fa_attempts + 1):
                    print(f"Попытка получения 2FA кода, попытка {attempt}/{max_2fa_attempts}")
                    verification_code = await self.get_2fa_code(
                        page, two_factor_code)
                    if verification_code:
                        print(f"Введён 2FA код: {verification_code}")
                        await verification_field.fill(verification_code)

                        # Ожидание активации кнопки Continue
                        print("Поиск кнопки Continue")
                        continue_button = await page.query_selector(
                            'div[role="button"][aria-label="Continue"]')
                        if not continue_button:
                            await self.save_html_on_error(
                                page, page.url,
                                "Кнопка Continue не найдена")
                            print("Кнопка Continue не найдена")
                            return False

                        # Проверка активности кнопки
                        try:
                            print("Ожидание активации кнопки Continue")
                            await page.wait_for_selector(
                                'div[role="button"][aria-label="Continue"]:not([aria-disabled="true"])',
                                timeout=10000)
                            print("Клик по кнопке Continue")
                            await continue_button.click(timeout=60000)
                            break
                        except PlaywrightTimeoutError:
                            print(f"Кнопка Continue не активна, попытка {attempt}/{max_2fa_attempts}")
                            if attempt == max_2fa_attempts:
                                await self.save_html_on_error(page, page.url, "Кнопка Continue не стала активной после всех попыток")
                                print("Кнопка Continue не стала активной после всех попыток")
                                return False
                            await page.wait_for_timeout(3000)
                    else:
                        await self.save_html_on_error(
                            page, page.url, "Не удалось получить 2FA код")
                        print(f"Не удалось получить 2FA код, попытка {attempt}/{max_2fa_attempts}")
                        if attempt == max_2fa_attempts:
                            print("Не удалось получить 2FA код после всех попыток")
                            return False
                        await page.wait_for_timeout(3000)

                print(
                    "Проверка чекбокса 'Trust this device'"
                )
                try:
                    trust_device_checkbox = await page.query_selector(
                        'div[role="checkbox"][aria-label="Trust this '
                        'device and skip this step from now on"]'
                        )
                    if trust_device_checkbox:
                        is_checked = await trust_device_checkbox.get_attribute(
                            'aria-checked') == 'true'
                        if not is_checked:
                            print("Клик по чекбоксу 'Trust this device'")
                            await trust_device_checkbox.click()
                        else:
                            print("Чекбокс 'Trust this device' уже отмечен")
                    else:
                        print("Чекбокс 'Trust this device' не найден")
                except Exception as e:
                    print(f"Не удалось кликнуть по 'Trust this device': {e}")
            except PlaywrightTimeoutError:
                print("Поле 2FA не найдено, возможно, не требуется")

            # Обработка кнопки "Не сейчас"
            print("Проверка кнопки 'Не сейчас' или 'Dismiss'")
            try:
                await page.wait_for_selector(
                    'div[role="button"]:has-text("Не сейчас"),'
                    ' div[role="button"]:has-text("Not now"), '
                    'button:has-text("Dismiss")',
                    timeout=60000
                    )
                not_now_button = await page.query_selector(
                    'div[role="button"]:has-text("Не сейчас")'
                ) or await page.query_selector(
                    'div[role="button"]:has-text("Not now")'
                ) or await page.query_selector('button:has-text("Dismiss")')
                if not_now_button:
                    print(
                        "Клик по кнопке 'Не сейчас' или 'Dismiss'"
                    )
                    await not_now_button.click()
                else:
                    await self.save_html_on_error(
                        page, page.url,
                        "Кнопка 'Не сейчас' или 'Dismiss' не найдена"
                    )
                    print(
                        "ERROR",
                        "Кнопка 'Не сейчас' или 'Dismiss' не найдена")
            except PlaywrightTimeoutError:
                print(

                    "Кнопка 'Не сейчас' или 'Dismiss' не найдена, продолжаем")

            print("Успешно вошли в Instagram")
            return True
        except Exception as e:
            await self.save_html_on_error(
                page, "https://www.instagram.com",
                f"Ошибка при входе в Instagram: {str(e)}")
            print(
                "ERROR",
                f"Ошибка при входе в Instagram с пользователем {username}: {e}"
            )
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
                                    print(f"Изображение найдено: {image_url} для рила {full_url}")
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

    async def parse_channel(self, url: str, channel_id: int, user_id: int,
                            max_retries: int = 3, accounts: list = None):
        proxy = self.proxy_list[channel_id % len(self.proxy_list)]
        proxy_auth, proxy_host_port = proxy.split('@')
        proxy_username, proxy_password = proxy_auth.split(':')
        proxy_host, proxy_port = proxy_host_port.split(':')

        proxy_config = {
            "server": f"http://{proxy_host}:{proxy_port}",
            "username": proxy_username,
            "password": proxy_password
        }

        async def download_image(url: str) -> bytes:
            async with httpx.AsyncClient(proxy=proxy_config) as client:
                resp = await client.get(url, timeout=20.0)
                print(f"✅ Загружено изображение для видео {url}")
                resp.raise_for_status()
                return resp.content

        async def upload_image(video_id: int, image_url: str):
            try:
                image_bytes = await download_image(image_url)
                file_name = image_url.split("/")[-1].split("?")[0] or f"{video_id}.jpg"
                async with httpx.AsyncClient(verify=False) as client:  # убрать ложную верификация
                    files = {"file": (file_name, image_bytes, "image/jpeg")}
                    resp = await client.post(
                        f"http://localhost:8000/api/v1/videos/{video_id}/upload-image/",
                        files=files,
                        timeout=30.0
                    )
                    resp.raise_for_status()
                    print(f"📸 Загружено превью {image_url} для видео {video_id}")
            except Exception as e:
                print(f"❌ Ошибка загрузки превью {image_url} для видео {video_id}: {e}")

        async def save_video_and_image(channel_id: int, reel_code: str, reel_url: str, play_count: int, image_url: str):
            video_data = {
                "type": "instagram",
                "channel_id": 5,
                "link": reel_url,
                "name": reel_code,
                "amount_views": play_count,
                "image_url": image_url,
            }
            try:
                async with httpx.AsyncClient(verify=False) as client:
                    resp = await client.post(
                        "http://localhost:8000/api/v1/videos/",
                        json=video_data,
                        timeout=20.0,
                    )
                    resp.raise_for_status()
                    created_video = resp.json()
                    video_id = created_video["id"]
                    print(f"📦 Создано видео {video_id} ({reel_url})")

                    if image_url:
                        asyncio.create_task(upload_image(video_id, image_url))
            except Exception as e:
                print(f"❌ Ошибка сохранения видео {reel_url}: {e}")

        # ✅ Запускаем Playwright
        async with async_playwright() as p:
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

                # новый формат (api/v1/clips/...)
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
                    # ✅ 2. Убраны лишние пробелы
                    reel_url = f"https://www.instagram.com/reel/{reel_code}/"
                    play_count = media.get("play_count", 0)
                    image_url = (
                        media.get("image_versions2", {})
                        .get("candidates", [{}])[0]
                        .get("url")
                    )
                    await save_video_and_image(channel_id, reel_code, reel_url, play_count, image_url)

                # старый формат (graphql user.timeline_media)
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
                    # ✅ 2. Убраны лишние пробелы
                    reel_url = f"https://www.instagram.com/reel/{reel_code}/"
                    play_count = node.get("video_play_count", 0)
                    image_url = node.get("display_url")
                    await save_video_and_image(channel_id, reel_code, reel_url, play_count, image_url)

                if "play_count" in str(json_resp):
                    print(f"🎯 Нашли play_count в {url}")

            page.on("response", handle_response)
            page.on("request", lambda req: print("➡️", req.method, req.url))
            page.on("response", lambda resp: print("⬅️", resp.status, resp.url))

            await page.goto("https://www.instagram.com", wait_until="networkidle")
            await page.wait_for_timeout(2000)

            used_accounts = set()
            accounts = self.accounts
            print(f"Используемые аккаунты: {accounts}")
            max_account_retries = len(accounts)

            for account_attempt in range(max_account_retries):
                available_accounts = [acc for acc in accounts if acc not in used_accounts]
                if not available_accounts:
                    print("Все аккаунты использованы, парсинг невозможен")
                    break

                account = random.choice(available_accounts)
                used_accounts.add(account)
                username, password, proxy = account.split(":")
                print(f"Попытка {account_attempt + 1}/{max_account_retries} с аккаунтом {username}")

                login_success = await self.login_to_instagram(page, username, password, proxy)
                if not login_success:
                    print(f"Не удалось войти с {username}, пробуем следующий")
                    continue

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

                    await self.scroll_until(page, reels_url, selector="div._aajy")

                    print(f"🎉 Собрано всего graphql/api: {len(collected_queries)}")
                    await browser.close()
                    return

                except PlaywrightTimeoutError as e:
                    await self.save_html_on_error(page, reels_url, f"Таймаут: {str(e)}")
                    print(f"Таймаут для {reels_url}: {e}")
                    if account_attempt + 1 < max_account_retries:
                        print("Пробуем другой аккаунт...")
                        continue
                except Exception as e:
                    await self.save_html_on_error(page, reels_url, f"Ошибка: {str(e)}")
                    print(f"Ошибка парсинга {reels_url}: {e}")
                    break

            print("❌ Не удалось спарсить профиль")
            await browser.close()
            return

    async def parse_profiles(self, profiles: list, user_id: int):
        for index, profile_url in enumerate(profiles):
            await self.parse_channel(profile_url, index, user_id)

    async def extract_username(self, page):
        """Extract username from meta description tag"""
        try:
            meta_element = await page.query_selector('meta[name="description"]')
            if meta_element:
                content = await meta_element.get_attribute('content')
                match = re.search(
                    r'(\w+)\s+on\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}',
                    content
                )
                if match:
                    username = match.group(1)
                    print(f"INFO: Extracted username: {username}")
                    return username
                await self.save_html_on_error(page, page.url, "Username not found in meta description")
                print("ERROR: Username not found in meta description")
                return None
            await self.save_html_on_error(page, page.url, "Meta description element not found")
            print("ERROR: Meta description element not found")
            return None
        except Exception as e:
            await self.save_html_on_error(page, page.url, f"Error extracting username: {str(e)}")
            print(f"ERROR: Error extracting username: {e}")
            return None


async def main():
    parser = InstagramParser()
    profiles = ["https://www.instagram.com/9akokujin/"]  # Replace with real profile
    user_id = 1
    await parser.parse_profiles(profiles, user_id)

if __name__ == "__main__":
    asyncio.run(main())
