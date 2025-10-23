import re
import asyncio
# import time
import json
from typing import Optional, Dict, List, Union, Any
import httpx
import requests
# from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import random
from datetime import datetime

from bs4 import BeautifulSoup


# from utils.logger import TCPLogger


class ShortsParser:
    def __init__(
            self,
            # logger: TCPLogger
    ):
        # self.logger = logger
        self.current_proxy_index = 0
        self.seen_video_ids: set = set()
        self.collected_videos: List[Dict] = []
        self.response_tasks: List[asyncio.Task] = []
        self.dom_images = {}
        self.dom_video_links = {}
        self.dom_order: List[str] = []
        self.saved_html_count = 0

    def reset_dom_state(self):
        """Сбрасывает накопленные DOM-данные перед новой попыткой парсинга."""
        self.dom_images = {}
        self.dom_video_links = {}
        self.dom_order = []
        self.collected_videos.clear()
        self.seen_video_ids.clear()
        self.response_tasks.clear()
        self.saved_html_count = 0

    def parse_views(self, text: str) -> int:
        if not text:
            return 0
        cleaned = text.replace("\xa0", " ").strip()
        match = re.search(r"([\d\s.,]+)", cleaned)
        if not match:
            return 0
        number_part = match.group(1)
        digits_only = re.sub(r"[^\d]", "", number_part)
        return int(digits_only) if digits_only else 0

    def parse_compact_number(self, raw_number: str, suffix: Optional[str] = None) -> Optional[int]:
        if not raw_number:
            return None

        cleaned = raw_number.replace("\xa0", "").replace(" ", "")
        cleaned = cleaned.replace(",", ".")

        try:
            value = float(cleaned)
        except ValueError:
            return None

        if suffix:
            suffix_normalized = suffix.strip().lower()
            if suffix_normalized in {"k", "тыс"}:
                value *= 1_000
            elif suffix_normalized in {"m", "млн"}:
                value *= 1_000_000
            elif suffix_normalized in {"b", "млрд"}:
                value *= 1_000_000_000

        return int(round(value))

    async def get_videos_count_from_header(self, page, timeout: int = 8000) -> Optional[int]:
        try:
            try:
                await page.wait_for_selector("yt-content-metadata-view-model span", timeout=timeout)
            except PlaywrightTimeoutError:
                pass

            header_elements = await page.query_selector_all("yt-content-metadata-view-model span")
            for element in header_elements:
                try:
                    raw_text = await element.inner_text()
                except Exception:
                    continue

                if not raw_text:
                    continue

                normalized = re.sub(r"\s+", " ", raw_text).strip()
                lowered = normalized.lower()

                if "video" not in lowered and "видео" not in lowered:
                    continue

                match = re.search(r"([\d\s.,]+)\s*(k|m|b|тыс|млн|млрд)?", normalized, re.IGNORECASE)
                if not match:
                    continue

                number_part = match.group(1)
                suffix = match.group(2)
                parsed = self.parse_compact_number(number_part, suffix)
                if parsed:
                    return parsed
        except Exception as e:
            print(f"Не удалось получить количество видео из шапки: {e}")

        return None

    async def extract_images_from_dom(self, page, url: str):
        """Проходимся по карточкам, сохраняем ссылки и превью для шортов."""
        print("🔍 Извлекаем данные о шортах из DOM…")

        item_selectors = [
            "ytm-shorts-lockup-view-model",   # мобильная
            "ytd-rich-item-renderer",         # десктопная
            "ytd-reel-item-renderer",         # reel items
            "ytd-grid-video-renderer"         # сетка
        ]

        added_images = 0
        added_links = 0
        total_cards_seen = 0

        for selector in item_selectors:
            try:
                items = await page.query_selector_all(selector)
                total_cards_seen += len(items)
                print(f"Карточек по '{selector}': {len(items)}")

                for el in items:
                    try:
                        link_el = await el.query_selector("a[href*='/shorts/']") \
                                or await el.query_selector("a.shortsLockupViewModelHostEndpoint")
                        href = await link_el.get_attribute("href") if link_el else None
                        if not href:
                            continue
                        m = re.search(r"/shorts/([a-zA-Z0-9_-]{11})", href)
                        if not m:
                            continue
                        video_id = m.group(1)

                        if video_id not in self.dom_video_links:
                            self.dom_video_links[video_id] = f"https://www.youtube.com/shorts/{video_id}"
                            self.dom_order.append(video_id)
                            added_links += 1

                        img_el = await el.query_selector("img.ytCoreImageHost, img.yt-img-shadow, img")
                        img_url = None
                        if img_el:
                            src = await img_el.get_attribute("src")
                            if src and src.strip() and not src.startswith("data:"):
                                img_url = src
                            else:
                                # бывает, что только srcset
                                srcset = await img_el.get_attribute("srcset")
                                if srcset:
                                    parts = [p.strip().split(" ")[0] for p in srcset.split(",") if p.strip()]
                                    if parts:
                                        img_url = parts[-1]

                        if not img_url:
                            img_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                        if video_id not in self.dom_images or not self.dom_images[video_id]:
                            self.dom_images[video_id] = img_url
                            added_images += 1

                    except Exception:
                        continue

            except Exception as e:
                print(f"Ошибка при обходе '{selector}': {e}")
                continue

        print(
            f"✅ Извлечено: +{added_links} ссылок, +{added_images} превью; всего уникальных видео: "
            f"{len(self.dom_order)}; карточек просмотрено: {total_cards_seen}"
        )
        return len(self.dom_order)

    async def scroll_until(self, page, url: str, selector: str, target_count: Optional[int] = None,
                           delay: float = 2.5, max_idle_rounds: int = 7):
        """Скроллим страницу, пока не соберём нужное количество шортов или не дойдём до конца."""
        prev_count = len(self.dom_order)
        idle_rounds = 0
        max_scroll_attempts = 6

        for attempt in range(max_scroll_attempts):
            print(f"Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

            if attempt > 0:
                try:
                    await page.evaluate("() => window.scrollTo({top: 0, behavior: 'instant'})")
                    await page.wait_for_timeout(800)
                except Exception:
                    pass

            while True:
                prev_height = await page.evaluate("() => document.documentElement.scrollHeight")

                try:
                    await page.keyboard.press("End")
                except Exception:
                    pass

                try:
                    await page.mouse.wheel(0, 1800)
                except Exception:
                    pass

                await page.wait_for_timeout(int(delay * 1000))

                height_increased = True
                try:
                    await page.wait_for_function(
                        "(oldHeight) => document.documentElement.scrollHeight - oldHeight > 120",
                        prev_height,
                        timeout=2500
                    )
                except PlaywrightTimeoutError:
                    height_increased = False
                except Exception:
                    height_increased = False

                captcha = await page.query_selector("text=CAPTCHA")
                if captcha:
                    print("Обнаружена CAPTCHA на странице")
                    return len(self.dom_order)

                await self.extract_images_from_dom(page, url)

                current_total = len(self.dom_order)
                target_info = target_count if target_count else "?"
                print(f"🔢 Собрано {current_total} уникальных видео (цель: {target_info})")

                if target_count and current_total >= target_count:
                    print("🎯 Достигнуто требуемое количество видео из шапки.")
                    return current_total

                try:
                    current_count = await page.eval_on_selector_all(selector, "els => els.length")
                    print(f"Текущее количество элементов по селектору '{selector}': {current_count}")
                except PlaywrightTimeoutError:
                    print("Timeout при оценке элементов, продолжаем...")

                if current_total == prev_count and not height_increased:
                    idle_rounds += 1
                    if idle_rounds >= max_idle_rounds:
                        print(f"Достигнут конец списка видео профиля {url}")
                        return current_total
                else:
                    idle_rounds = 0
                    prev_count = current_total

                # если высота не увеличилась и мы всё ещё внизу — делаем небольшую паузу
                if not height_increased:
                    await page.wait_for_timeout(800)

                if height_increased:
                    continue

                # проверяем, появился ли новый элемент
                try:
                    newly_visible = await page.eval_on_selector_all(
                        selector,
                        "els => els.length"
                    )
                except PlaywrightTimeoutError:
                    newly_visible = None

                if newly_visible is not None and newly_visible <= current_total:
                    break

        await self.extract_images_from_dom(page, url)
        return len(self.dom_order)

    def prepare_proxy(self, proxy_str: Optional[str]) -> Optional[str]:
        """Приводим строку прокси к формату, понятному requests."""
        if not proxy_str:
            return None
        proxy_str = proxy_str.strip()
        if not proxy_str:
            return None
        if proxy_str.startswith(("http://", "https://")):
            return proxy_str
        if "@" in proxy_str:
            auth, host_port = proxy_str.split("@", 1)
            host, port = host_port.split(":", 1)
            return f"http://{auth}@{host}:{port}"
        if ":" in proxy_str:
            host, port = proxy_str.split(":", 1)
            return f"http://{host}:{port}"
        return proxy_str

    def _extract_json_fragment(self, text: str, marker: str) -> Optional[str]:
        """Извлекаем JSON-структуру, начинающуюся сразу после маркера."""
        if marker not in text:
            return None
        start = text.find(marker)
        if start == -1:
            return None
        start += len(marker)
        while start < len(text) and text[start] in " \n\r\t=":
            start += 1
        if start >= len(text):
            return None
        opening = text[start]
        if opening not in "{[":
            return None
        closing = "}" if opening == "{" else "]"
        depth = 0
        in_string = False
        escape = False

        for pos in range(start, len(text)):
            ch = text[pos]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
            elif ch == opening:
                depth += 1
            elif ch == closing:
                depth -= 1
                if depth == 0:
                    return text[start:pos + 1]

        return None

    def _load_json_segment(self, text: str, markers: List[str]) -> Optional[Dict[str, Any]]:
        for marker in markers:
            fragment = self._extract_json_fragment(text, marker)
            if not fragment:
                continue
            try:
                return json.loads(fragment)
            except json.JSONDecodeError as e:
                print(f"Не удалось распарсить JSON по маркеру '{marker}': {e}")
        return None

    def parse_video_page(self, html: str) -> Dict[str, Optional[Dict[str, Any]]]:
        """Возвращаем распарсенные структуры ytInitialPlayerResponse и ytInitialData."""
        soup = BeautifulSoup(html, "html.parser")
        script_texts = []
        for script in soup.find_all("script"):
            if script.string:
                script_texts.append(script.string)

        player_markers = [
            "var ytInitialPlayerResponse = ",
            "ytInitialPlayerResponse = ",
            'window["ytInitialPlayerResponse"] = ',
            "window.ytInitialPlayerResponse = ",
        ]
        initial_markers = [
            "var ytInitialData = ",
            "ytInitialData = ",
            'window["ytInitialData"] = ',
            "window.ytInitialData = ",
        ]

        player_data = None
        initial_data = None

        for text in script_texts:
            if not player_data and "ytInitialPlayerResponse" in text:
                player_data = self._load_json_segment(text, player_markers)
            if not initial_data and "ytInitialData" in text:
                initial_data = self._load_json_segment(text, initial_markers)
            if player_data and initial_data:
                break

        # fallback — ищем прямо в html, если BeautifulSoup не помог
        if not player_data:
            player_data = self._load_json_segment(html, player_markers)
        if not initial_data:
            initial_data = self._load_json_segment(html, initial_markers)

        return {"player": player_data, "initial": initial_data}

    def extract_views_from_initial_data(self, data: Any) -> Optional[int]:
        """Извлекаем количество просмотров из различных структур ytInitialData."""

        def parse_candidate(value: Any) -> Optional[int]:
            if isinstance(value, str):
                parsed = self.parse_views(value)
                return parsed if parsed else None
            if isinstance(value, dict):
                text = value.get("simpleText") or value.get("text")
                if text:
                    parsed = self.parse_views(text)
                    if parsed:
                        return parsed
                runs = value.get("runs")
                if runs:
                    combined = "".join(run.get("text", "") for run in runs if run.get("text"))
                    parsed = self.parse_views(combined)
                    if parsed:
                        return parsed
            return None

        stack = [data]
        visited = set()

        while stack:
            node = stack.pop()
            node_id = id(node)
            if node_id in visited:
                continue
            visited.add(node_id)

            if isinstance(node, dict):
                # videoDescriptionHeaderRenderer -> views / factoid
                header = node.get("videoDescriptionHeaderRenderer")
                if isinstance(header, dict):
                    direct_views = parse_candidate(header.get("views"))
                    if direct_views:
                        return direct_views

                    factoids = header.get("factoid")
                    if isinstance(factoids, list):
                        for fact in factoids:
                            renderer = fact.get("viewCountFactoidRenderer") if isinstance(fact, dict) else None
                            if isinstance(renderer, dict):
                                factoid_renderer = renderer.get("factoid", {}).get("factoidRenderer", {})
                                for key in ("accessibilityText", "value", "label"):
                                    candidate = factoid_renderer.get(key)
                                    parsed = parse_candidate(candidate)
                                    if parsed:
                                        return parsed
                                views_candidate = renderer.get("viewCount")
                                parsed = parse_candidate(views_candidate)
                                if parsed:
                                    return parsed

                # direct factoid structure without header wrapper
                renderer = node.get("viewCountFactoidRenderer")
                if isinstance(renderer, dict):
                    factoid_renderer = renderer.get("factoid", {}).get("factoidRenderer", {})
                    for key in ("accessibilityText", "value", "label"):
                        candidate = factoid_renderer.get(key)
                        parsed = parse_candidate(candidate)
                        if parsed:
                            return parsed
                    parsed = parse_candidate(renderer.get("viewCount"))
                    if parsed:
                        return parsed

                label = node.get("label")
                parsed_label = parse_candidate(label)
                if parsed_label:
                    for key in ("accessibilityText", "simpleText", "text", "title"):
                        candidate = node.get(key)
                        parsed = parse_candidate(candidate)
                        if parsed:
                            return parsed

                for value in node.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)

            elif isinstance(node, list):
                for item in node:
                    if isinstance(item, (dict, list)):
                        stack.append(item)

        return None

    async def fetch_video_metadata(self, video_id: str, video_url: str, proxy: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Запрашиваем страницу шорта и достаём метаданные (название, просмотры, описание)."""
        formatted_proxy = self.prepare_proxy(proxy)
        # headers = {
        #     "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        #     "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        # }
        proxies = {"http": formatted_proxy, "https": formatted_proxy} if formatted_proxy else None

        def _fetch_html() -> str:
            response = requests.get(
                video_url,
                # headers=headers,
                timeout=30.0,
                # allow_redirects=True,
                proxies=proxies,
            )
            response.raise_for_status()
            return response.text

        try:
            html = await asyncio.to_thread(_fetch_html)
        except Exception as e:
            print(f"❌ Не удалось получить страницу {video_url} через {formatted_proxy or 'без прокси'}: {e}")
            return None

        # if self.saved_html_count < 2:
        #     debug_dir = Path("debug_html")
        #     debug_dir.mkdir(parents=True, exist_ok=True)
        #     safe_video_id = video_id or f"video_{self.saved_html_count + 1}"
        #     debug_path = debug_dir / f"{self.saved_html_count + 1}_{safe_video_id}.html"
        #     try:
        #         debug_path.write_text(html)
        #         print(f"💾 Сохранён HTML ответа {debug_path}")
        #     except Exception as save_err:
        #         print(f"⚠️ Не удалось сохранить HTML {debug_path}: {save_err}")
        #     finally:
        #         self.saved_html_count += 1

        parsed = self.parse_video_page(html)
        player_data = parsed.get("player") or {}
        if not player_data:
            print(f"⚠️ Не найден ytInitialPlayerResponse для {video_url}")
            return None

        video_details = player_data.get("videoDetails", {}) or {}
        microformat_container = player_data.get("microformat", {})
        if not isinstance(microformat_container, dict):
            microformat_container = {}
        microformat = microformat_container.get("playerMicroformatRenderer", {}) or {}
        if not isinstance(microformat, dict):
            microformat = {}

        def _extract_text(value: Any) -> str:
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                if value.get("simpleText"):
                    return value["simpleText"]
                runs = value.get("runs")
                if isinstance(runs, list):
                    return "".join(run.get("text", "") for run in runs if isinstance(run, dict))
            return ""

        def _parse_number_from_text(raw: Optional[str]) -> Optional[int]:
            if not raw:
                return None
            cleaned = raw.replace("\xa0", " ").strip()
            match = re.search(
                r"([\d\s.,]+)\s*(тыс(?:яч[аи])?|млн|миллион(?:ов)?|млрд|миллиард(?:ов)?|k|m|b)?",
                cleaned,
                re.IGNORECASE,
            )
            if match:
                number_part = match.group(1)
                suffix = match.group(2)
                if suffix:
                    suffix = suffix.strip().lower()
                    if suffix.startswith("тыс"):
                        suffix = "тыс"
                    elif suffix.startswith("миллион") or suffix == "млн":
                        suffix = "млн"
                    elif suffix.startswith("миллиард") or suffix == "млрд":
                        suffix = "млрд"
                parsed_number = self.parse_compact_number(number_part, suffix) if suffix else self.parse_views(number_part)
                if parsed_number:
                    return parsed_number
            return self.parse_views(cleaned)

        def _normalize_publish_date(value: Optional[str]) -> Optional[str]:
            if not value:
                return None
            candidate = value.strip()
            if candidate.endswith("Z"):
                candidate = candidate[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(candidate)
                return dt.date().isoformat()
            except ValueError:
                return None

        def _extract_publish_date_from_factoids(factoids: List[Any]) -> Optional[str]:
            month_aliases = {
                "янв": 1,
                "январь": 1,
                "января": 1,
                "фев": 2,
                "февр": 2,
                "февраль": 2,
                "февраля": 2,
                "мар": 3,
                "март": 3,
                "марта": 3,
                "апр": 4,
                "апрель": 4,
                "апреля": 4,
                "май": 5,
                "мая": 5,
                "июн": 6,
                "июнь": 6,
                "июня": 6,
                "июл": 7,
                "июль": 7,
                "июля": 7,
                "авг": 8,
                "август": 8,
                "августа": 8,
                "сен": 9,
                "сент": 9,
                "сентябрь": 9,
                "сентября": 9,
                "oct": 10,
                "october": 10,
                "окт": 10,
                "октябрь": 10,
                "октября": 10,
                "nov": 11,
                "november": 11,
                "ноя": 11,
                "ноябрь": 11,
                "ноября": 11,
                "dec": 12,
                "december": 12,
                "дек": 12,
                "декабрь": 12,
                "декабря": 12,
                "aug": 8,
                "august": 8,
                "apr": 4,
                "april": 4,
                "february": 2,
                "january": 1,
                "jan": 1,
                "feb": 2,
                "mar": 3,
                "may": 5,
                "jun": 6,
                "june": 6,
                "jul": 7,
                "july": 7,
                "sep": 9,
                "sept": 9,
                "september": 9,
            }
            for fact in factoids:
                if not isinstance(fact, dict):
                    continue
                renderer = fact.get("factoidRenderer")
                if not renderer:
                    renderer = fact.get("viewCountFactoidRenderer", {}).get("factoid", {}).get("factoidRenderer")
                if not renderer:
                    continue
                label_text = _extract_text(renderer.get("label"))
                value_text = _extract_text(renderer.get("value"))
                if not label_text or not value_text:
                    continue
                year_match = re.search(r"(\\d{4})", label_text)
                if not year_match:
                    continue
                year = int(year_match.group(1))
                day_match = re.search(r"(\\d{1,2})", value_text)
                month_match = re.search(r"([A-Za-zА-Яа-яёЁ]+)", value_text)
                if not day_match or not month_match:
                    continue
                day = int(day_match.group(1))
                month_key = month_match.group(1).lower().rstrip(".")
                month = month_aliases.get(month_key)
                if not month:
                    continue
                try:
                    return datetime(year, month, day).date().isoformat()
                except ValueError:
                    continue
            return None

        title_candidate = video_details.get("title") or microformat.get("title")
        title = _extract_text(title_candidate)

        description = video_details.get("shortDescription")
        if not description:
            description = _extract_text(microformat.get("description"))
        description = description.strip() if isinstance(description, str) else ""

        view_count_raw = video_details.get("viewCount")
        views = 0
        if isinstance(view_count_raw, str) and view_count_raw.isdigit():
            views = int(view_count_raw)
        elif isinstance(view_count_raw, str):
            views = self.parse_views(view_count_raw)

        if not views:
            view_count_text = _extract_text(microformat.get("viewCount"))
            if view_count_text:
                views = self.parse_views(view_count_text)

        initial_data = parsed.get("initial") or {}
        overlay = {}
        if isinstance(initial_data, dict):
            overlay = initial_data.get("overlay", {}).get("reelPlayerOverlayRenderer", {}) or {}

        if not views and overlay:
            try:
                header = overlay.get("reelPlayerHeaderSupportedRenderers", {}).get("reelPlayerHeaderRenderer", {})
                sub_label = header.get("accessibility", {}).get("accessibilityData", {}).get("label", "")
                views = self.parse_views(sub_label)
            except Exception:
                views = views or 0

        if not views and initial_data:
            extracted = self.extract_views_from_initial_data(initial_data)
            if extracted:
                views = extracted

        likes = None
        microformat_like = microformat.get("likeCount")
        if isinstance(microformat_like, str):
            likes = self.parse_views(microformat_like)
        elif isinstance(microformat_like, (int, float)):
            likes = int(microformat_like)

        published_at = None
        for candidate in (microformat.get("publishDate"), microformat.get("uploadDate")):
            published_at = _normalize_publish_date(candidate)
            if published_at:
                break

        comments = None
        if overlay:
            button_bar = overlay.get("buttonBar", {}).get("reelActionBarViewModel", {})
            button_models = button_bar.get("buttonViewModels", []) if isinstance(button_bar, dict) else []
            for button in button_models:
                if not isinstance(button, dict):
                    continue
                like_vm = button.get("likeButtonViewModel")
                if like_vm:
                    like_count_vm = like_vm.get("likeCountViewModel")
                    if isinstance(like_count_vm, dict):
                        like_count_vm = like_count_vm.get("likeCountViewModel", like_count_vm)
                    if isinstance(like_count_vm, dict) and not likes:
                        like_candidate = like_count_vm.get("shortText") or like_count_vm.get("accessibilityText")
                        likes = _parse_number_from_text(like_candidate) or likes
                    if not likes:
                        toggle_vm = (
                            like_vm.get("toggleButtonViewModel", {})
                            .get("toggleButtonViewModel", {})
                            .get("defaultButtonViewModel", {})
                            .get("buttonViewModel", {})
                        )
                        like_text = toggle_vm.get("accessibilityText")
                        likes = _parse_number_from_text(like_text) or likes
                    continue

                generic_vm = button.get("buttonViewModel") or {}
                tooltip = generic_vm.get("tooltip") or generic_vm.get("title") or generic_vm.get("accessibilityText") or ""
                if isinstance(tooltip, str) and "коммент" in tooltip.lower():
                    raw_comments = generic_vm.get("title") or generic_vm.get("accessibilityText")
                    comments = _parse_number_from_text(raw_comments)

        if (published_at is None) and isinstance(initial_data, dict):
            try:
                panels = initial_data.get("engagementPanels", []) or []
                for panel in panels:
                    if not isinstance(panel, dict):
                        continue
                    section = panel.get("engagementPanelSectionListRenderer")
                    if not section:
                        continue
                    content = section.get("content", {})
                    structured = content.get("structuredDescriptionContentRenderer", {})
                    if not structured:
                        continue
                    for item in structured.get("items", []):
                        if not isinstance(item, dict):
                            continue
                        header = item.get("videoDescriptionHeaderRenderer")
                        if header:
                            published_at = _extract_publish_date_from_factoids(header.get("factoid", []))
                            if published_at:
                                break
                    if published_at:
                        break
            except Exception:
                published_at = published_at or None

        return {
            "video_id": video_id,
            "link": video_url,
            "title": title,
            "views": views or 0,
            "likes": likes or 0,
            "comments": comments or 0,
            "published_at": published_at or "",
            "description": description,
        }

    async def fetch_videos_with_proxies(self, video_ids: List[str], delay: float = 5.0) -> List[Dict[str, Any]]:
        """Запрашиваем страницы шортов пакетами, по одному URL на прокси."""
        if not video_ids:
            return []

        proxies = self.proxy_list if self.proxy_list else [None]
        batch_size = len(proxies) if proxies else 1
        results: List[Dict[str, Any]] = []

        index = 0
        total = len(video_ids)
        while index < total:
            batch_ids = video_ids[index:index + batch_size]
            tasks: List[asyncio.Task] = []
            task_video_ids: List[str] = []

            for idx, video_id in enumerate(batch_ids):
                video_url = self.dom_video_links.get(video_id)
                if not video_url:
                    print(f"⚠️ Для видео {video_id} не найдена ссылка в DOM, пропускаем.")
                    continue
                proxy = proxies[idx] if proxies else None
                task_video_ids.append(video_id)
                tasks.append(asyncio.create_task(self.fetch_video_metadata(video_id, video_url, proxy)))

            if tasks:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                for video_id, result in zip(task_video_ids, batch_results):
                    if isinstance(result, Exception):
                        print(f"❌ Ошибка при обработке {video_id}: {result}")
                        continue
                    if result:
                        results.append(result)

            index += batch_size
            if index < total:
                print(f"⏳ Ждём {delay} секунд перед следующей пачкой запросов ({index}/{total})")
                await asyncio.sleep(delay)

        return results

    async def download_image(self, url: str, proxy: str = None) -> Union[bytes, None]:
        """Скачивает изображение с YouTube (можно с прокси)."""
        formatted_proxy = self.prepare_proxy(proxy)
        proxies = {"http": formatted_proxy, "https": formatted_proxy} if formatted_proxy else None

        def _download() -> bytes:
            response = requests.get(url, timeout=20.0, proxies=proxies)
            response.raise_for_status()
            return response.content

        try:
            return await asyncio.to_thread(_download)
        except Exception as e:
            print(f"❌ Ошибка загрузки изображения {url}: {e}")
            return None

    async def upload_image(self, video_id: int, image_url: str, proxy: str = None):
        """Скачивает изображение (с прокси) и загружает его на API, нормализуя путь."""
        image_bytes = await self.download_image(image_url, proxy=proxy)
        if not image_bytes:
            return None, "Download failed"

        file_name = image_url.split("/")[-1].split("?")[0] or "cover.jpg"
        files = {"file": (file_name, image_bytes, "image/jpeg")}

        def _upload():
            response = requests.post(
                f"http://127.0.0.1:8000/api/v1/videos/{video_id}/upload-image/",
                files=files,
                timeout=30.0,
            )
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            return response.status_code, payload

        try:
            status_code, payload = await asyncio.to_thread(_upload)
        except Exception as e:
            print(f"⚠️ Ошибка загрузки фото для видео {video_id}: {e}")
            return None, str(e)

        image_path = None
        if isinstance(payload, dict):
            image_path = payload.get("image")
            if image_path and not image_path.startswith(("http://", "https://", "/")):
                image_path = "/" + image_path

        return status_code, image_path or payload

    def extract_article_tag(self, caption: str) -> Optional[str]:
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

    async def parse_channel(self, url: str, channel_id: int, user_id: int, max_retries: int = 3, proxy_list: list = None):
        """
        Новая логика:
        1. Получаем общее количество видео из шапки канала.
        2. Скроллим ленту шортов до совпадения количества либо до конца.
        3. Сохраняем ссылки и превью из DOM.
        4. По одному запросу на прокси собираем метаданные каждого видео через httpx + BS4.
        5. Передаём данные дальше на API (ниже по функции).
        """
        self.proxy_list = proxy_list or []
        current_proxy_index = 0

        if not url.endswith('/shorts'):
            url = url.rstrip('/') + '/shorts'
        print(f"Переход на канал: {url}")

        async def get_proxy_config(proxy_str):
            try:
                if "@" in proxy_str:
                    auth, host_port = proxy_str.split("@", 1)
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

        proxy_candidates = list(self.proxy_list) if self.proxy_list else [None]
        if self.proxy_list:
            random.shuffle(proxy_candidates)
        max_proxy_attempts = (
            min(max_retries, len(proxy_candidates)) if self.proxy_list else max(1, max_retries)
        )
        max_proxy_attempts = max(1, max_proxy_attempts)

        all_videos_data: List[Dict] = []
        header_videos_count: Optional[int] = None
        total_videos_from_dom = 0
        videos_limit = 0
        total_collected = 0

        best_state = None
        best_total = 0

        for attempt_idx in range(max_proxy_attempts):
            current_proxy = proxy_candidates[attempt_idx % len(proxy_candidates)] if proxy_candidates else None
            print(
                f"🔁 Попытка {attempt_idx + 1}/{max_proxy_attempts} "
                f"с прокси {current_proxy or 'без прокси'}"
            )
            self.reset_dom_state()

            playwright = None
            browser = None
            context = None
            page = None

            try:
                playwright = await async_playwright().start()
                browser, context, page = await create_browser_with_proxy(current_proxy, playwright)

                print("🔍 Загружаем страницу Shorts…")
                await page.goto(url, wait_until="networkidle", timeout=60000)

                cookie_selectors = [
                    "button[aria-label='Accept all']",
                    "button:has-text('Accept all')",
                    "button:has-text('Принять все')",
                    "button:has-text('Принять всё')",
                    "ytd-button-renderer#accept-button button",
                ]
                for selector in cookie_selectors:
                    try:
                        btn = await page.query_selector(selector)
                        if btn:
                            await btn.click()
                            await page.wait_for_timeout(1200)
                            print("Закрыта модалка с куки")
                            break
                    except Exception:
                        continue

                header_videos_count = await self.get_videos_count_from_header(page)
                if header_videos_count:
                    print(f"🎯 Количество видео из шапки: {header_videos_count}")
                else:
                    print("ℹ️ Не удалось определить количество видео из шапки, опираемся на DOM.")

                selector = "ytd-rich-item-renderer, ytd-reel-item-renderer, ytm-shorts-lockup-view-model, ytd-grid-video-renderer"
                total_videos_from_dom = await self.scroll_until(
                    page,
                    url,
                    selector=selector,
                    target_count=header_videos_count,
                    delay=3.0
                )
                print(f"📊 Всего уникальных видео в DOM: {len(self.dom_order)} (scroll_until вернул {total_videos_from_dom})")

            except Exception as main_error:
                print(f"Критическая ошибка при работе с Playwright: {main_error}")
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

            total_collected = len(self.dom_order)
            if total_collected > best_total:
                best_state = {
                    "dom_images": dict(self.dom_images),
                    "dom_video_links": dict(self.dom_video_links),
                    "dom_order": list(self.dom_order),
                    "header_count": header_videos_count,
                    "total_from_dom": total_videos_from_dom,
                }
                best_total = total_collected

            if total_collected == 0:
                print("⚠️ Не удалось собрать ни одного видео в этой попытке, пробуем другой прокси.")
                await asyncio.sleep(1.5)
                continue

            if (
                header_videos_count
                and total_collected < header_videos_count
                and attempt_idx + 1 < max_proxy_attempts
            ):
                print(
                    f"⚠️ Собрано только {total_collected} из {header_videos_count} видео. "
                    "Пробуем обновить страницу с другим прокси."
                )
                await asyncio.sleep(1.0)
                continue

            break
        else:
            if best_state and best_state["dom_order"]:
                print("ℹ️ Используем данные лучшей из предыдущих попыток.")
                self.dom_images = best_state["dom_images"]
                self.dom_video_links = best_state["dom_video_links"]
                self.dom_order = best_state["dom_order"]
                header_videos_count = best_state["header_count"]
                total_videos_from_dom = best_state["total_from_dom"]
                total_collected = len(self.dom_order)
            else:
                print("⚠️ Не удалось собрать ни одного видео из DOM после всех попыток.")
                return []
        total_collected = len(self.dom_order)
        if total_collected == 0:
            print("⚠️ Не удалось собрать ни одного видео из DOM.")
            return []

        videos_limit = header_videos_count if header_videos_count else total_collected
        videos_limit = min(videos_limit, total_collected)
        videos_to_process = self.dom_order[:videos_limit]
        print(
            f"🎯 Подготовлено к обработке {len(videos_to_process)} видео "
            f"(шапка: {header_videos_count or '—'}, собрано: {total_collected})"
        )

        metadata_list = await self.fetch_videos_with_proxies(videos_to_process)
        print(f"📦 Получены метаданные для {len(metadata_list)} видео")

        for meta in metadata_list:
            video_id = meta.get("video_id")
            if not video_id:
                continue
            image_url = self.dom_images.get(video_id) or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            description = meta.get("description") or ""
            articles = self.extract_article_tag(description)
            all_videos_data.append(
                {
                    "link": meta.get("link"),
                    "type": "youtube",
                    "name": meta.get("title") or "",
                    "image": image_url,
                    "channel_id": channel_id,
                    "articles": articles,
                    "amount_views": meta.get("views") or 0,
                    "amount_likes": meta.get("likes") or 0,
                    "amount_comments": meta.get("comments") or 0,
                    "date_published": meta.get("published_at") or "",
                }
            )

        print(
            f"✅ Собрано {len(all_videos_data)} из {videos_limit} видео "
            f"(DOM найдено: {total_collected})"
        )
        processed_count = 0
        image_queue = []
        queued_video_ids = set()
        for video_data in all_videos_data:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    # print(f"🔍 Проверка видео: {video_data['link']}")
                    check_resp = await client.get(f"http://127.0.0.1:8000/api/v1/videos/?link={video_data['link']}")
                    is_new = False
                    video_id = None

                    if check_resp.status_code == 200:
                        res = check_resp.json()
                        vids = res.get("videos", [])
                        if vids:
                            existing_video = vids[0]
                            video_id = existing_video['id']
                            update_payload = {
                                "amount_views": video_data["amount_views"],
                                "amount_likes": video_data["amount_likes"],
                                "amount_comments": video_data["amount_comments"],
                                "date_published": video_data["date_published"],
                                "articles": video_data["articles"],
                            }
                            await client.patch(
                                f"http://127.0.0.1:8000/api/v1/videos/{video_id}",
                                json=update_payload
                            )

                            existing_image = existing_video.get("image")
                            image_missing = not existing_image
                            image_needs_update = False
                            if isinstance(existing_image, str):
                                normalized_existing = existing_image.strip()
                                if normalized_existing.startswith(("http://", "https://")):
                                    image_needs_update = True
                            if (image_missing or image_needs_update) and video_data.get("image"):
                                if video_id not in queued_video_ids:
                                    image_queue.append((video_id, video_data["image"]))
                                    queued_video_ids.add(video_id)
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        resp = await client.post("http://127.0.0.1:8000/api/v1/videos", json=video_data)
                        resp.raise_for_status()
                        video_id = resp.json()["id"]
                        # print(f"✅ Создано новое видео {video_id}")
                        if video_data.get("image") and video_id not in queued_video_ids:
                            image_queue.append((video_id, video_data["image"]))
                            queued_video_ids.add(video_id)
                processed_count += 1
            except Exception as e:
                print(f"⚠️ Ошибка при обработке {video_data.get('link')}: {e}")

        print(f"📦 Всего обработано {processed_count} видео, ожидают загрузки {len(image_queue)} обложек.")

        # --- Загрузка изображений ---
        idx = 0
        while idx < len(image_queue):
            proxy = proxy_list[current_proxy_index] if proxy_list else None
            current_proxy_index = (current_proxy_index + 1) % len(proxy_list) if proxy_list else 0
            batch = image_queue[idx:idx + 15]
            print(f"🖼️ Загружаем {len(batch)} изображений через {proxy or 'без прокси'}")

            for vid, img_url in batch:
                try:
                    status, _ = await self.upload_image(vid, img_url, proxy=proxy)
                    print(f"{'✅' if status == 200 else '⚠️'} Фото для видео {vid} → статус {status}")
                except Exception as e:
                    print(f"❌ Ошибка загрузки фото {vid}: {e}")
                await asyncio.sleep(5.0)
            idx += 15

        print(f"🎉 Парсинг завершён: {processed_count} видео обработано.")


# ----------------------- Пример запуска -----------------------

async def main():
    proxy_list = [
        "6hro8o:N6A7Yn@181.177.84.234:9413",
        "6hro8o:N6A7Yn@181.177.87.128:9966",
        "6hro8o:N6A7Yn@181.177.84.125:9613",
        "6hro8o:N6A7Yn@23.236.139.90:9758",
        "6hro8o:N6A7Yn@23.236.141.118:9234",
        "6hro8o:N6A7Yn@23.236.141.94:9893",
        "6hro8o:N6A7Yn@23.236.138.18:9055",
        "6hro8o:N6A7Yn@23.236.149.166:9775",
        "6hro8o:N6A7Yn@23.236.148.87:9845",
        "6hro8o:N6A7Yn@170.246.55.141:9663",
        "6hro8o:N6A7Yn@191.102.172.185:9891",
        "6hro8o:N6A7Yn@191.102.172.131:9083",
        "6hro8o:N6A7Yn@170.246.55.97:9246",
    ]
    parser = ShortsParser()
    url = "https://www.youtube.com/@nastya.beomaa"
    user_id = 1
    await parser.parse_channel(url, channel_id=5, user_id=user_id, proxy_list=proxy_list)


if __name__ == "__main__":
    asyncio.run(main())
