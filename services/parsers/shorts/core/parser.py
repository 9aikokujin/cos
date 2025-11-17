import re
import asyncio
# import time
import json
from collections import deque
from datetime import datetime, timezone
from typing import Optional, Dict, List, Union, Any
import httpx
import requests
# from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import random

from bs4 import BeautifulSoup
from utils.logger import TCPLogger
from urllib.parse import urlparse, urlunparse


ARTICLE_PREFIXES = ("#sv", "#jw", "#qz", "#sr", "#fg")
API_BASE_URL = "https://cosmeya.dev-klick.cyou/api/v1/videos"
# API_BASE_URL = "http://127.0.0.1:8000/api/v1/videos"


class ShortsParser:
    def __init__(
            self,
            logger: TCPLogger
    ):
        self.logger = logger
        self.current_proxy_index = 0
        self.seen_video_ids: set = set()
        self.collected_videos: List[Dict] = []
        self.response_tasks: List[asyncio.Task] = []
        self.dom_images = {}
        self.dom_video_links = {}
        self.dom_order: List[str] = []
        self.saved_html_count = 0

    @staticmethod
    def _parse_started_at(value: Optional[Union[str, datetime]]) -> datetime:
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str) and value.strip():
            text = value.strip()
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(text)
            except ValueError:
                dt = datetime.now(timezone.utc)
        else:
            dt = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    def _log_summary(
        self,
        url: str,
        channel_id: int,
        video_count: int,
        total_views: int,
        started_at: datetime,
        ended_at: datetime,
        success: bool,
    ) -> None:
        status_icon = "✅" if success else "⚠️"
        status_text = "Успешно спарсили" if success else "Не удалось спарсить"
        self.logger.send(
            "INFO",
            f"{status_icon} {status_text} {url} с {channel_id} "
            f"кол-во видео - {video_count}, кол-во просмотров - {total_views}, "
            f"время начала парсинга - {started_at.isoformat()}, конец парсинга - {ended_at.isoformat()}",
        )

    async def _start_playwright(self):
        try:
            return await async_playwright().start()
        except Exception as exc:
            self.logger.send("INFO", f"❌ Не удалось запустить Playwright: {exc}")
            return None

    async def _safe_close(self, obj, label: str, method: str = "close"):
        if not obj:
            return
        closer = getattr(obj, method, None)
        if not closer:
            return
        try:
            result = closer()
            if asyncio.iscoroutine(result):
                await result
        except Exception as exc:
            self.logger.send("INFO", f"⚠️ Ошибка закрытия {label}: {exc}")

    async def _cleanup_browser_stack(self, page=None, context=None, browser=None):
        await self._safe_close(page, "page")
        await self._safe_close(context, "context")
        await self._safe_close(browser, "browser")

    def reset_dom_state(self):
        """Сбрасывает накопленные DOM-данные перед новой попыткой парсинга."""
        self.dom_images = {}
        self.dom_video_links = {}
        self.dom_order = []
        self.collected_videos.clear()
        self.seen_video_ids.clear()
        self.response_tasks.clear()
        self.saved_html_count = 0

    def _select_next_proxy(self, proxies: List[Optional[str]], last_proxy: Optional[str]) -> Optional[str]:
        if not proxies:
            return None
        if len(proxies) == 1:
            return proxies[0]
        candidates = [p for p in proxies if p != last_proxy]
        return random.choice(candidates) if candidates else proxies[0]

    def normalize_profile_url(self, raw_url: str) -> str:
        cleaned = (raw_url or "").strip()
        if not cleaned:
            raise ValueError("Пустой URL профиля YouTube")
        if not re.match(r"^https?://", cleaned, re.IGNORECASE):
            cleaned = f"https://{cleaned.lstrip('/')}"
        parsed = urlparse(cleaned)
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc or "youtube.com"
        path = parsed.path or ""

        segments = [segment for segment in path.split("/") if segment]
        username_segment = next((segment for segment in segments if segment.startswith("@")), None)
        if username_segment:
            path = f"/{username_segment}"
        elif segments:
            path = f"/{segments[0]}"
        else:
            path = "/"

        return urlunparse((scheme, netloc, path.rstrip("/"), "", "", ""))

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

    def _looks_like_views_text(self, text: str) -> bool:
        if not text:
            return False
        normalized = text.lower()
        keywords = (
            "view",
            "просмот",
            "visualiz",
            "vista",
            "vues",
            "ansehen",
            "ansicht",
            "bekeken",
            "weergav",
            "görüntülenme",
            "المشاهدات",
        )
        return any(keyword in normalized for keyword in keywords)

    def _looks_like_likes_text(self, text: str) -> bool:
        if not text:
            return False
        normalized = text.lower()
        keywords = (
            "like",
            "лайк",
            "thumb",
            "класс",
            "me gusta",
            "gusta",
        )
        return any(keyword in normalized for keyword in keywords)

    def _looks_like_comments_text(self, text: str) -> bool:
        if not text:
            return False
        normalized = text.lower()
        keywords = (
            "comment",
            "коммент",
            "coment",
            "reactie",
            "ответ",
            "reply",
        )
        return any(keyword in normalized for keyword in keywords)

    def _looks_like_publish_text(self, text: str) -> bool:
        if not text:
            return False
        normalized = text.lower()
        keywords = (
            "publish",
            "uploaded",
            "опублик",
            "вышло",
            "premiered",
            "премьера",
            "дата",
        )
        return any(keyword in normalized for keyword in keywords)

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
            self.logger.send("INFO", f"Не удалось получить количество видео из шапки: {e}")

        return None

    async def extract_images_from_dom(self, page, url: str):
        """Проходимся по карточкам, сохраняем ссылки и превью для шортов."""
        self.logger.send("INFO", "🔍 Извлекаем данные о шортах из DOM…")

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
                self.logger.send("INFO", f"Карточек по '{selector}': {len(items)}")

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
                self.logger.send("INFO", f"Ошибка при обходе '{selector}': {e}")
                continue

        self.logger.send(
            "INFO",
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
            self.logger.send("INFO", f"Прокрутка страницы, попытка {attempt + 1}/{max_scroll_attempts}")

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
                    self.logger.send("INFO", "Обнаружена CAPTCHA на странице")
                    return len(self.dom_order)

                await self.extract_images_from_dom(page, url)

                current_total = len(self.dom_order)
                target_info = target_count if target_count else "?"
                self.logger.send("INFO", f"🔢 Собрано {current_total} уникальных видео (цель: {target_info})")

                if target_count and current_total >= target_count:
                    self.logger.send("INFO", "🎯 Достигнуто требуемое количество видео из шапки.")
                    return current_total

                try:
                    current_count = await page.eval_on_selector_all(selector, "els => els.length")
                    self.logger.send("INFO", f"Текущее количество элементов по селектору '{selector}': {current_count}")
                except PlaywrightTimeoutError:
                    self.logger.send("INFO", "Timeout при оценке элементов, продолжаем...")

                if current_total == prev_count and not height_increased:
                    idle_rounds += 1
                    if idle_rounds >= max_idle_rounds:
                        self.logger.send("INFO", f"Достигнут конец списка видео профиля {url}")
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
                self.logger.send("INFO", f"Не удалось распарсить JSON по маркеру '{marker}': {e}")
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

    def _normalize_article(self, tag: str) -> Optional[str]:
        if not tag:
            return None
        if not tag.startswith("#"):
            tag = "#" + tag
        lower_tag = tag.lower()
        for prefix in ARTICLE_PREFIXES:
            if lower_tag.startswith(prefix):
                return tag
        return None

    def _extract_text(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            simple = value.get("simpleText") or value.get("text")
            if isinstance(simple, str):
                return simple
            runs = value.get("runs")
            if isinstance(runs, list):
                parts = [
                    run.get("text", "")
                    for run in runs
                    if isinstance(run, dict) and isinstance(run.get("text"), str)
                ]
                if parts:
                    return "".join(parts)
        return ""

    def extract_date_from_text(self, text: str) -> Optional[str]:
        if not text:
            return None

        cleaned = text.strip()
        cleaned = re.sub(
            r"(?i)\b(published|uploaded|опубликован[а-я]*|премьера|premiered|дата публикации|date)\b[:\-]?",
            "",
            cleaned,
        ).strip()

        iso_match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", cleaned)
        if iso_match:
            year, month, day = iso_match.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

        dotted_match = re.search(r"(\d{1,2})[.](\d{1,2})[.](\d{4})", cleaned)
        if dotted_match:
            day, month, year = dotted_match.groups()
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

        month_aliases = {
            "january": 1, "jan": 1, "jan.": 1,
            "february": 2, "feb": 2, "feb.": 2,
            "march": 3, "mar": 3, "mar.": 3,
            "april": 4, "apr": 4, "apr.": 4,
            "may": 5,
            "june": 6, "jun": 6, "jun.": 6,
            "july": 7, "jul": 7, "jul.": 7,
            "august": 8, "aug": 8, "aug.": 8,
            "september": 9, "sep": 9, "sep.": 9, "sept": 9, "sept.": 9,
            "october": 10, "oct": 10, "oct.": 10,
            "november": 11, "nov": 11, "nov.": 11,
            "december": 12, "dec": 12, "dec.": 12,
            "января": 1, "январь": 1, "янв": 1, "янв.": 1,
            "февраля": 2, "февраль": 2, "фев": 2, "фев.": 2,
            "марта": 3, "март": 3, "мар": 3, "мар.": 3,
            "апреля": 4, "апрель": 4, "апр": 4, "апр.": 4,
            "мая": 5, "май": 5,
            "июня": 6, "июнь": 6, "июн": 6, "июн.": 6,
            "июля": 7, "июль": 7, "июл": 7, "июл.": 7,
            "августа": 8, "август": 8, "авг": 8, "авг.": 8,
            "сентября": 9, "сентябрь": 9, "сен": 9, "сен.": 9,
            "октября": 10, "октябрь": 10, "окт": 10, "окт.": 10,
            "ноября": 11, "ноябрь": 11, "ноя": 11, "ноя.": 11,
            "декабря": 12, "декабрь": 12, "дек": 12, "дек.": 12,
        }

        def month_to_number(name: str) -> Optional[int]:
            if not name:
                return None
            key = name.strip().lower().replace("ё", "е")
            return month_aliases.get(key)

        match_en = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", cleaned)
        if match_en:
            month_name, day, year = match_en.groups()
            month_num = month_to_number(month_name)
            if month_num:
                return f"{int(year):04d}-{month_num:02d}-{int(day):02d}"

        match_day_first = re.search(r"(\d{1,2})\s+([A-Za-zА-Яа-яё.]+)\s+(\d{4})", cleaned)
        if match_day_first:
            day, month_name, year = match_day_first.groups()
            month_num = month_to_number(month_name)
            if month_num:
                return f"{int(year):04d}-{month_num:02d}-{int(day):02d}"

        return None

    def extract_articles(self, description: str, text_extra: Optional[List[dict]]) -> Optional[str]:
        found: set[str] = set()

        if description:
            for match in re.findall(r"#[\w-]+", description):
                normalized = self._normalize_article(match)
                if normalized:
                    found.add(normalized)

        if isinstance(text_extra, list):
            for block in text_extra:
                if not isinstance(block, dict):
                    continue
                name = block.get("hashtagName")
                if isinstance(name, str):
                    normalized = self._normalize_article(name)
                    if normalized:
                        found.add(normalized)

        if not found:
            return None

        # сохраняем порядок для детерминированности
        return ", ".join(sorted(found, key=lambda x: x.lower()))

    def extract_views_from_initial_data(self, data: Any) -> Optional[int]:
        """Извлекаем количество просмотров из различных структур ytInitialData."""

        def parse_candidate(value: Any) -> Optional[int]:
            if value is None:
                return None
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

    def _extract_metric_from_factoids(self, data: Any, label_checker) -> Optional[int]:
        """Общий обход структур factoidRenderer для извлечения числовых метрик по подписи."""

        def parse_candidate(value: Any) -> Optional[int]:
            if value is None:
                return None
            if isinstance(value, (str, dict, list)):
                text = self._extract_text(value)
            else:
                text = str(value)
            if not text:
                return None
            parsed = self.parse_views(text)
            return parsed if parsed else None

        def extract_from_renderer(renderer: Any) -> Optional[int]:
            if not isinstance(renderer, dict):
                return None
            label_text = self._extract_text(renderer.get("label"))
            if label_text and label_checker(label_text):
                for key in (
                    "value",
                    "viewCount",
                    "accessibilityText",
                    "simpleText",
                    "text",
                    "title",
                ):
                    candidate = renderer.get(key)
                    parsed = parse_candidate(candidate)
                    if parsed is not None:
                        return parsed
                nested = renderer.get("factoid")
                if isinstance(nested, dict):
                    nested_renderer = nested.get("factoidRenderer")
                    if nested_renderer:
                        parsed = extract_from_renderer(nested_renderer)
                        if parsed is not None:
                            return parsed
            else:
                nested = renderer.get("factoid")
                if isinstance(nested, dict):
                    nested_renderer = nested.get("factoidRenderer")
                    if nested_renderer:
                        parsed = extract_from_renderer(nested_renderer)
                        if parsed is not None:
                            return parsed
            return None

        if not isinstance(data, (dict, list)):
            return None

        stack = [data]
        visited: set[int] = set()

        while stack:
            node = stack.pop()
            node_id = id(node)
            if node_id in visited:
                continue
            visited.add(node_id)

            if isinstance(node, dict):
                if "factoidRenderer" in node:
                    result = extract_from_renderer(node["factoidRenderer"])
                    if result is not None:
                        return result

                renderer = node.get("viewCountFactoidRenderer")
                if isinstance(renderer, dict):
                    result = extract_from_renderer(renderer)
                    if result is not None:
                        return result

                factoids = node.get("factoid")
                if isinstance(factoids, list):
                    for fact in factoids:
                        if isinstance(fact, (dict, list)):
                            stack.append(fact)

                for value in node.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)

            elif isinstance(node, list):
                for item in node:
                    if isinstance(item, (dict, list)):
                        stack.append(item)

        return None

    def extract_likes_from_initial_data(self, data: Any) -> Optional[int]:
        """Ищет количество лайков в factoidRenderer внутри ytInitialData."""
        return self._extract_metric_from_factoids(data, self._looks_like_likes_text)

    def extract_publish_date_from_initial_data(self, data: Any) -> Optional[str]:
        """Извлекает дату публикации из factoidRenderer внутри ytInitialData."""

        def try_parse_from_renderer(renderer: dict) -> Optional[str]:
            if not isinstance(renderer, dict):
                return None
            candidates = [
                renderer.get("accessibilityText"),
                renderer.get("value"),
                renderer.get("label"),
            ]
            for candidate in candidates:
                text = self._extract_text(candidate)
                if not text:
                    continue
                parsed = self.extract_date_from_text(text)
                if parsed:
                    return parsed
            combined = " ".join(
                filter(
                    None,
                    [
                        self._extract_text(renderer.get("value")),
                        self._extract_text(renderer.get("label")),
                    ],
                )
            )
            if combined:
                parsed = self.extract_date_from_text(combined)
                if parsed:
                    return parsed
            nested = renderer.get("factoid")
            if isinstance(nested, dict):
                nested_renderer = nested.get("factoidRenderer")
                if nested_renderer:
                    return try_parse_from_renderer(nested_renderer)
            return None

        if not isinstance(data, (dict, list)):
            return None

        stack = [data]
        visited: set[int] = set()

        while stack:
            node = stack.pop()
            node_id = id(node)
            if node_id in visited:
                continue
            visited.add(node_id)

            if isinstance(node, dict):
                renderer = node.get("factoidRenderer")
                if isinstance(renderer, dict):
                    parsed = try_parse_from_renderer(renderer)
                    if parsed:
                        return parsed
                renderer = node.get("viewCountFactoidRenderer")
                if isinstance(renderer, dict):
                    parsed = try_parse_from_renderer(renderer)
                    if parsed:
                        return parsed
                factoids = node.get("factoid")
                if isinstance(factoids, list):
                    stack.extend(
                        item for item in factoids if isinstance(item, (dict, list))
                    )
                for value in node.values():
                    if isinstance(value, (dict, list)):
                        stack.append(value)

            elif isinstance(node, list):
                for item in node:
                    if isinstance(item, (dict, list)):
                        stack.append(item)

        return None

    def extract_comment_count(self, data: Any) -> Optional[int]:
        """Извлекаем количество комментариев из engagementPanels."""
        if not isinstance(data, dict):
            return None

        panels = data.get("engagementPanels")
        if not isinstance(panels, list):
            return None

        for panel in panels:
            if not isinstance(panel, dict):
                continue
            renderer = panel.get("engagementPanelSectionListRenderer")
            if not isinstance(renderer, dict):
                continue
            header = renderer.get("header")
            if not isinstance(header, dict):
                continue
            title_renderer = header.get("engagementPanelTitleHeaderRenderer")
            if not isinstance(title_renderer, dict):
                continue
            title_text = self._extract_text(title_renderer.get("title")).lower()
            if "comment" not in title_text and "коммент" not in title_text:
                continue
            contextual = title_renderer.get("contextualInfo")
            count_text = self._extract_text(contextual)
            parsed = self.parse_views(count_text)
            if parsed:
                return parsed

        return None

    def extract_overlay_metrics(self, data: Any) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}
        if not isinstance(data, dict):
            return metrics

        overlay = data.get("overlay", {}).get("reelPlayerOverlayRenderer", {})
        if not isinstance(overlay, dict):
            return metrics

        header = overlay.get("reelPlayerHeaderSupportedRenderers", {}).get("reelPlayerHeaderRenderer", {})
        if isinstance(header, dict):
            accessibility = header.get("accessibility") or {}
            label_data = accessibility.get("accessibilityData", {}) if isinstance(accessibility, dict) else {}
            label_text = self._extract_text(label_data.get("label"))
            if label_text:
                segments = re.split(r"[•·|•]|\s{2,}", label_text)
                for segment in segments:
                    cleaned = segment.strip()
                    if not cleaned:
                        continue
                    if self._looks_like_views_text(cleaned):
                        metrics.setdefault("views", self.parse_views(cleaned))
                        continue
                    if self._looks_like_likes_text(cleaned):
                        metrics.setdefault("likes", self.parse_views(cleaned))
                        continue
                    if self._looks_like_comments_text(cleaned):
                        metrics.setdefault("comments", self.parse_views(cleaned))
                        continue
                    if self._looks_like_publish_text(cleaned):
                        date_candidate = self.extract_date_from_text(cleaned)
                        if date_candidate:
                            metrics.setdefault("date_published", date_candidate)

        description_candidate = overlay.get("description") or overlay.get("descriptionText")
        description_text = self._extract_text(description_candidate)
        if description_text:
            metrics.setdefault("description", description_text.strip())

        return metrics

    async def fetch_video_metadata(self, video_id: str, video_url: str, proxy: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Запрашиваем страницу шорта и достаём метаданные (название, просмотры, описание)."""
        formatted_proxy = self.prepare_proxy(proxy)
        headers = {
            "Accept-Language": "en-US,en;q=0.9"
        }
        proxies = {"http": formatted_proxy, "https": formatted_proxy} if formatted_proxy else None

        def _fetch_html() -> str:
            response = requests.get(
                video_url,
                headers=headers,
                timeout=30.0,
                # allow_redirects=True,
                proxies=proxies,
            )
            response.raise_for_status()
            return response.text

        try:
            html = await asyncio.to_thread(_fetch_html)
        except Exception as e:
            self.logger.send("INFO", f"❌ Не удалось получить страницу {video_url} через {formatted_proxy or 'без прокси'}: {e}")
            return None

        # if self.saved_html_count < 2:
        #     debug_dir = Path("debug_html")
        #     debug_dir.mkdir(parents=True, exist_ok=True)
        #     safe_video_id = video_id or f"video_{self.saved_html_count + 1}"
        #     debug_path = debug_dir / f"{self.saved_html_count + 1}_{safe_video_id}.html"
        #     try:
        #         debug_path.write_text(html)
        #         self.logger.send("INFO", f"💾 Сохранён HTML ответа {debug_path}")
        #     except Exception as save_err:
        #         self.logger.send("INFO", f"⚠️ Не удалось сохранить HTML {debug_path}: {save_err}")
        #     finally:
        #         self.saved_html_count += 1

        parsed = self.parse_video_page(html)
        player_data = parsed.get("player") or {}
        if not player_data:
            self.logger.send("INFO", f"⚠️ Не найден ytInitialPlayerResponse для {video_url}")
            return None

        video_details = player_data.get("videoDetails", {}) or {}
        microformat_container = player_data.get("microformat", {})
        if not isinstance(microformat_container, dict):
            microformat_container = {}
        microformat = microformat_container.get("playerMicroformatRenderer", {}) or {}
        if not isinstance(microformat, dict):
            microformat = {}

        title_candidate = video_details.get("title") or microformat.get("title")
        title = self._extract_text(title_candidate)

        view_count_raw = video_details.get("viewCount")
        views = 0
        if isinstance(view_count_raw, str) and view_count_raw.isdigit():
            views = int(view_count_raw)
        elif isinstance(view_count_raw, str):
            views = self.parse_views(view_count_raw)

        if not views:
            view_count_text = self._extract_text(microformat.get("viewCount"))
            if view_count_text:
                views = self.parse_views(view_count_text)

        initial_data = parsed.get("initial") or {}
        overlay_metrics: Dict[str, Any] = {}
        if initial_data:
            overlay_metrics = self.extract_overlay_metrics(initial_data)

        overlay_views = overlay_metrics.get("views")
        if not views and isinstance(overlay_views, int):
            views = overlay_views
        if not views and initial_data:
            extracted = self.extract_views_from_initial_data(initial_data)
            if extracted:
                views = extracted

        description = self._extract_text(microformat.get("description")) or ""
        if not description:
            short_description = video_details.get("shortDescription")
            if isinstance(short_description, str):
                description = short_description
        if not description:
            overlay_description = overlay_metrics.get("description")
            if isinstance(overlay_description, str):
                description = overlay_description
        description = description.strip()

        like_raw = microformat.get("likeCount")
        likes = 0
        if isinstance(like_raw, str):
            likes = self.parse_views(like_raw) or 0
        elif like_raw is not None:
            likes = self.parse_views(self._extract_text(like_raw)) or 0

        overlay_likes = overlay_metrics.get("likes")
        if not likes and isinstance(overlay_likes, int):
            likes = overlay_likes
        if not likes and initial_data:
            extracted_likes = self.extract_likes_from_initial_data(initial_data)
            if extracted_likes:
                likes = extracted_likes

        comments = self.extract_comment_count(initial_data) or 0
        overlay_comments = overlay_metrics.get("comments")
        if not comments and isinstance(overlay_comments, int):
            comments = overlay_comments

        publish_candidate = microformat.get("uploadDate") or microformat.get("publishDate")
        date_published = None
        if isinstance(publish_candidate, str):
            iso_candidate = publish_candidate.strip()
            if iso_candidate:
                if iso_candidate.endswith("Z"):
                    iso_candidate = iso_candidate[:-1] + "+00:00"
                try:
                    date_published = datetime.fromisoformat(iso_candidate).date().isoformat()
                except ValueError:
                    if len(iso_candidate) >= 10:
                        date_published = iso_candidate[:10]

        if not date_published:
            overlay_date = overlay_metrics.get("date_published")
            if isinstance(overlay_date, str):
                date_published = overlay_date
        if not date_published and initial_data:
            extracted_date = self.extract_publish_date_from_initial_data(initial_data)
            if extracted_date:
                date_published = extracted_date

        articles = self.extract_articles(description, None) if description else None

        return {
            "video_id": video_id,
            "link": video_url,
            "title": title,
            "views": views,
            "description": description,
            "likes": likes,
            "comments": comments,
            "articles": articles,
            "date_published": date_published,
        }

    async def fetch_videos_with_proxies(self, video_ids: List[str], delay: float = 5.0) -> List[Dict[str, Any]]:
        """Запрашиваем страницы шортов пакетами, по одному URL на прокси."""
        if not video_ids:
            return []

        # video_ids = video_ids[:20]  # тестовый пример первые 20 видосов

        proxies = self.proxy_list if self.proxy_list else [None]
        total_proxies = len(proxies) if proxies else 1
        batch_size = total_proxies or 1
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
                    self.logger.send("INFO", f"⚠️ Для видео {video_id} не найдена ссылка в DOM, пропускаем.")
                    continue
                start_proxy_idx = idx % (total_proxies or 1)
                task_video_ids.append(video_id)
                tasks.append(asyncio.create_task(
                    self._fetch_with_proxy_rotation(video_id, video_url, proxies, start_proxy_idx)
                ))

            if tasks:
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                for video_id, result in zip(task_video_ids, batch_results):
                    if isinstance(result, Exception):
                        self.logger.send("INFO", f"❌ Ошибка при обработке {video_id}: {result}")
                        continue
                    if result:
                        results.append(result)

            index += batch_size
            if index < total:
                self.logger.send("INFO", f"⏳ Ждём {delay} секунд перед следующей пачкой запросов ({index}/{total})")
                await asyncio.sleep(delay)

        return results

    async def _fetch_with_proxy_rotation(
        self,
        video_id: str,
        video_url: str,
        proxies: List[Optional[str]],
        start_index: int,
    ) -> Optional[Dict[str, Any]]:
        """Пробуем получить метаданные видео, перебирая прокси по кругу."""
        if not proxies:
            proxies = [None]

        total_proxies = len(proxies)
        for attempt in range(total_proxies):
            proxy = proxies[(start_index + attempt) % total_proxies]
            if attempt > 0:
                self.logger.send("INFO", f"🔁 Повторная попытка для {video_url} через {proxy or 'без прокси'} (попытка {attempt + 1})")
            result = await self.fetch_video_metadata(video_id, video_url, proxy)
            if result:
                return result

        self.logger.send("INFO", f"⚠️ Все прокси исчерпаны для {video_url}, видео пропущено.")
        return None

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
            self.logger.send("INFO", f"❌ Ошибка загрузки изображения {url}: {e}")
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
                f"{API_BASE_URL}/{video_id}/upload-image/",
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
            self.logger.send("INFO", f"⚠️ Ошибка загрузки фото для видео {video_id}: {e}")
            return None, str(e)

        image_path = None
        if isinstance(payload, dict):
            image_path = payload.get("image")
            if image_path and not image_path.startswith(("http://", "https://", "/")):
                image_path = "/" + image_path

        return status_code, image_path or payload

    async def parse_channel(
        self,
        url: str,
        channel_id: int,
        user_id: int,
        max_retries: int = 3,
        proxy_list: list = None,
        parse_started_at: Optional[Union[str, datetime]] = None,
    ):
        """
        Новая логика:
        1. Получаем общее количество видео из шапки канала.
        2. Скроллим ленту шортов до совпадения количества либо до конца.
        3. Сохраняем ссылки и превью из DOM.
        4. По одному запросу на прокси собираем метаданные каждого видео через httpx + BS4.
        5. Передаём данные дальше на API (ниже по функции).
        """
        run_started_at = self._parse_started_at(parse_started_at)
        history_created_at_iso = run_started_at.isoformat()
        processed_count = 0
        total_views = 0

        def log_final(success: bool) -> None:
            ended_at = datetime.now(timezone.utc)
            self._log_summary(
                url,
                channel_id,
                processed_count,
                total_views,
                run_started_at,
                ended_at,
                success and processed_count > 0,
            )

        self.proxy_list = proxy_list or []

        url = self.normalize_profile_url(url)
        if not url.endswith('/shorts'):
            url = url.rstrip('/') + '/shorts'
        self.logger.send("INFO", f"Переход на канал: {url}")

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
                self.logger.send("INFO", f"Неверный формат прокси: {e}")
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
        effective_retries = max_retries if max_retries is not None else 0
        if self.proxy_list:
            base_attempts = len(proxy_candidates)
            max_proxy_attempts = max(1, max(base_attempts, effective_retries))
        else:
            max_proxy_attempts = max(1, effective_retries or 1)

        all_videos_data: List[Dict] = []
        header_videos_count: Optional[int] = None
        total_videos_from_dom = 0
        videos_limit = 0
        total_collected = 0

        best_state = None
        best_total = 0

        for attempt_idx in range(max_proxy_attempts):
            current_proxy = proxy_candidates[attempt_idx % len(proxy_candidates)] if proxy_candidates else None
            self.logger.send(
                "INFO",
                f"🔁 Попытка {attempt_idx + 1}/{max_proxy_attempts} "
                f"с прокси {current_proxy or 'без прокси'}"
            )
            self.reset_dom_state()

            playwright = None
            browser = None
            context = None
            page = None

            try:
                playwright = await self._start_playwright()
                if not playwright:
                    self.logger.send("INFO", "❌ Не удалось инициализировать Playwright, пробуем следующую попытку.")
                    await asyncio.sleep(1.0)
                    continue
                browser, context, page = await create_browser_with_proxy(current_proxy, playwright)

                self.logger.send("INFO", "🔍 Загружаем страницу Shorts…")
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
                            self.logger.send("INFO", "Закрыта модалка с куки")
                            break
                    except Exception:
                        continue

                header_videos_count = await self.get_videos_count_from_header(page)
                if header_videos_count:
                    self.logger.send("INFO", f"🎯 Количество видео из шапки: {header_videos_count}")
                else:
                    self.logger.send("INFO", "ℹ️ Не удалось определить количество видео из шапки, опираемся на DOM.")

                selector = "ytd-rich-item-renderer, ytd-reel-item-renderer, ytm-shorts-lockup-view-model, ytd-grid-video-renderer"
                total_videos_from_dom = await self.scroll_until(
                    page,
                    url,
                    selector=selector,
                    target_count=header_videos_count,
                    delay=3.0
                )
                self.logger.send("INFO", f"📊 Всего уникальных видео в DOM: {len(self.dom_order)} (scroll_until вернул {total_videos_from_dom})")

            except Exception as main_error:
                self.logger.send("INFO", f"Критическая ошибка при работе с Playwright: {main_error}")
            finally:
                await self._cleanup_browser_stack(page, context, browser)
                await self._safe_close(playwright, "playwright", method="stop")

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
                self.logger.send("INFO", "⚠️ Не удалось собрать ни одного видео в этой попытке, пробуем другой прокси.")
                await asyncio.sleep(1.5)
                continue

            if (
                header_videos_count
                and total_collected < header_videos_count
                and attempt_idx + 1 < max_proxy_attempts
            ):
                self.logger.send(
                    "INFO",
                    f"⚠️ Собрано только {total_collected} из {header_videos_count} видео. "
                    "Пробуем обновить страницу с другим прокси."
                )
                await asyncio.sleep(1.0)
                continue

            break
        else:
            if best_state and best_state["dom_order"]:
                self.logger.send("INFO", "ℹ️ Используем данные лучшей из предыдущих попыток.")
                self.dom_images = best_state["dom_images"]
                self.dom_video_links = best_state["dom_video_links"]
                self.dom_order = best_state["dom_order"]
                header_videos_count = best_state["header_count"]
                total_videos_from_dom = best_state["total_from_dom"]
                total_collected = len(self.dom_order)
            else:
                self.logger.send("INFO", "⚠️ Не удалось собрать ни одного видео из DOM после всех попыток.")
                log_final(False)
                return []
        total_collected = len(self.dom_order)
        if total_collected == 0:
            self.logger.send("INFO", "⚠️ Не удалось собрать ни одного видео из DOM.")
            log_final(False)
            return []

        videos_limit = header_videos_count if header_videos_count else total_collected
        videos_limit = min(videos_limit, total_collected)
        videos_to_process = self.dom_order[:videos_limit]
        self.logger.send(
            "INFO",
            f"🎯 Подготовлено к обработке {len(videos_to_process)} видео "
            f"(шапка: {header_videos_count or '—'}, собрано: {total_collected})"
        )

        metadata_list = await self.fetch_videos_with_proxies(videos_to_process)
        self.logger.send("INFO", f"📦 Получены метаданные для {len(metadata_list)} видео")

        for meta in metadata_list:
            video_id = meta.get("video_id")
            if not video_id:
                continue
            image_url = self.dom_images.get(video_id) or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            all_videos_data.append(
                {
                    "link": meta.get("link"),
                    "type": "youtube",
                    "name": meta.get("title") or "",
                    "image_url": image_url,
                    "channel_id": channel_id,
                    # "description": meta.get("description") or "",
                    "amount_views": meta.get("views") or 0,
                    "amount_likes": meta.get("likes") or 0,
                    "amount_comments": meta.get("comments") or 0,
                    "articles": meta.get("articles"),
                    "date_published": meta.get("date_published"),
                    "history_created_at": history_created_at_iso,
                }
            )

        self.logger.send(
            "INFO",
            f"✅ Собрано {len(all_videos_data)} из {videos_limit} видео "
            f"(DOM найдено: {total_collected})"
        )
        total_views = sum(int(item.get("amount_views", 0) or 0) for item in all_videos_data)
        image_queue = []
        queued_video_ids = set()
        for video_data in all_videos_data:
            try:
                async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                    # self.logger.send("INFO", f"🔍 Проверка видео: {video_data['link']}")
                    check_resp = await client.get(f"{API_BASE_URL}/?link={video_data['link']}")
                    is_new = False
                    video_id = None

                    if check_resp.status_code == 200:
                        res = check_resp.json()
                        vids = res.get("videos", [])
                        if vids:
                            existing_video = vids[0]
                            video_id = existing_video['id']
                            update_payload = {
                                "amount_views": video_data.get("amount_views", 0),
                                "amount_likes": video_data.get("amount_likes", 0),
                                "amount_comments": video_data.get("amount_comments", 0),
                                "articles": video_data.get("articles"),
                                # "description": video_data.get("description"),
                                "date_published": video_data.get("date_published"),
                                "history_created_at": history_created_at_iso,
                            }
                            update_payload = {k: v for k, v in update_payload.items() if v is not None}
                            await client.patch(
                                f"{API_BASE_URL}/{video_id}",
                                json=update_payload
                            )

                            existing_image = existing_video.get("image")
                            image_missing = not (isinstance(existing_image, str) and existing_image.strip())
                            if image_missing and video_data.get("image_url"):
                                if video_id not in queued_video_ids:
                                    image_queue.append((video_id, video_data["image_url"]))
                                    queued_video_ids.add(video_id)
                        else:
                            is_new = True
                    else:
                        is_new = True

                    if is_new:
                        create_payload = {
                            key: value
                            for key, value in video_data.items()
                            if value is not None
                        }
                        resp = await client.post(f"{API_BASE_URL}/", json=create_payload)
                        resp.raise_for_status()
                        created_video = resp.json()
                        video_id = created_video["id"]
                        # self.logger.send("INFO", f"✅ Создано новое видео {video_id}")
                        created_image = created_video.get("image")
                        image_missing = not (isinstance(created_image, str) and created_image.strip())
                        if image_missing and video_data.get("image_url") and video_id not in queued_video_ids:
                            image_queue.append((video_id, video_data["image_url"]))
                            queued_video_ids.add(video_id)
                processed_count += 1
            except Exception as e:
                self.logger.send("INFO", f"⚠️ Ошибка при обработке {video_data.get('link')}: {e}")

        self.logger.send("INFO", f"📦 Всего обработано {processed_count} видео, ожидают загрузки {len(image_queue)} обложек.")

        # --- Загрузка изображений ---
        proxy_candidates: List[Optional[str]] = list(proxy_list) if proxy_list else [None]
        pending_images = deque((vid, img_url, None) for vid, img_url in image_queue)

        while pending_images:
            vid, img_url, last_proxy_used = pending_images.popleft()
            proxy = self._select_next_proxy(proxy_candidates, last_proxy_used)
            # self.logger.send("INFO", f"🖼️ Загружаем изображение для {vid} через {proxy or 'без прокси'}")

            try:
                status, _ = await self.upload_image(vid, img_url, proxy=proxy)
                if status == 200:
                    # self.logger.send("INFO", f"✅ Фото для видео {vid} загружено")
                    await asyncio.sleep(5.0)
                    continue
                self.logger.send("INFO", f"⚠️ Фото для видео {vid} вернуло статус {status}")
            except Exception as e:
                self.logger.send("INFO", f"❌ Ошибка загрузки фото {vid}: {e}")

            self.logger.send("INFO", f"🔄 Повторим загрузку фото для {vid} через 1 минуту на другой прокси")
            pending_images.append((vid, img_url, proxy))
            await asyncio.sleep(60.0)

        self.logger.send("INFO", f"🎉 Парсинг завершён: {processed_count} видео обработано.")
        log_final(processed_count > 0)


# ----------------------- Пример запуска -----------------------

# async def main():
#     proxy_list = [
#         "msEHZ8:tYomUE@152.232.65.53:9461",
#         "msEHZ8:tYomUE@190.185.108.103:9335",
#         "msEHZ8:tYomUE@138.99.37.16:9622",
#         "msEHZ8:tYomUE@138.99.37.136:9248",
#         "msEHZ8:tYomUE@152.232.72.124:9057",
#         "msEHZ8:tYomUE@23.229.49.135:9511",
#         "msEHZ8:tYomUE@209.127.8.189:9281",
#         "msEHZ8:tYomUE@152.232.72.235:9966",
#         "msEHZ8:tYomUE@152.232.74.34:9043",
#         "PvJVn6:jr8EvS@38.148.133.33:8000",
#         "PvJVn6:jr8EvS@38.148.142.71:8000",
#         "PvJVn6:jr8EvS@38.148.133.69:8000",
#         "PvJVn6:jr8EvS@38.148.138.48:8000",
#         "msEHZ8:tYomUE@168.196.239.222:9211",
#         "msEHZ8:tYomUE@168.196.237.44:9129",
#         "msEHZ8:tYomUE@168.196.237.99:9160",
#         "msEHZ8:tYomUE@138.219.122.56:9409",
#         "msEHZ8:tYomUE@138.219.122.128:9584",
#         "msEHZ8:tYomUE@138.219.123.22:9205",
#         "msEHZ8:tYomUE@138.59.5.46:9559",
#         "msEHZ8:tYomUE@152.232.68.147:9269",
#         "msEHZ8:tYomUE@152.232.67.18:9241",
#         "msEHZ8:tYomUE@152.232.68.149:9212",
#         "msEHZ8:tYomUE@152.232.66.152:9388",
#     ]
#     parser = ShortsParser()
#     url = "https://www.youtube.com/@sofi.beomaa"
#     user_id = 1
#     await parser.parse_channel(url, channel_id=7, user_id=user_id, proxy_list=proxy_list)


# if __name__ == "__main__":
#     asyncio.run(main())
