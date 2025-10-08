import time
from playwright.sync_api import sync_playwright
import json
import re
from typing import Optional, List, Dict


def get_uid_from_profile_page(short_id: str,
                              timeout_ms: int = 15000) -> Optional[str]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        profile_url = f"https://likee.video/p/{short_id}"
        print(f"➡️ Открываем профиль: {profile_url}")

        try:
            with page.expect_response(
                lambda response: "getUserVideo" in response.url and response.status == 200,
                timeout=timeout_ms
            ) as response_info:
                page.goto(profile_url)

            response = response_info.value
            data = response.json()
            if data.get("code") == 0 and data.get("data", {}).get("videoList"):
                first_video = data["data"]["videoList"][0]
                uid = first_video.get("posterUid")
                if uid:
                    print(f"✅ Найден posterUid: {uid}")
                    browser.close()
                    return str(uid)
        except Exception as e:
            print(f"❌ Ошибка: {e}")

        browser.close()
        return None


def get_all_videos_by_uid(uid: str) -> List[Dict]:
    """
    Собирает ВСЕ видео через пагинацию (до 100 за запрос).
    """
    all_videos = []
    last_post_id = ""
    max_per_request = 100
    total_fetched = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        while True:
            print(f"  🔍 Запрашиваем до {max_per_request} видео (после postId: {last_post_id or 'начала'})...")
            api_url = "https://api.like-video.com/likee-activity-flow-micro/videoApi/getUserVideo"
            payload = {
                "uid": uid,
                "count": max_per_request,
                "tabType": 0,
                "lastPostId": last_post_id
            }
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
                "Referer": "https://likee.video/",
                "Origin": "https://likee.video"
            }

            try:
                resp = page.request.post(api_url, data=json.dumps(payload), headers=headers)
                if resp.status == 200:
                    data = resp.json()
                    if data.get("code") == 0:
                        videos = data["data"].get("videoList", [])
                        print(f"    → Получено {len(videos)} видео")

                        if not videos:
                            print("    → Больше нет видео. Завершаем.")
                            break

                        all_videos.extend(videos)
                        total_fetched += len(videos)

                        # Если меньше 100 — это последняя порция
                        if len(videos) < max_per_request:
                            print("    → Достигнут конец профиля.")
                            break

                        # Иначе — берём последний postId для следующей страницы
                        last_post_id = videos[-1].get("postId", "")
                        if not last_post_id:
                            print("    → Нет lastPostId — завершаем.")
                            break

                    else:
                        print(f"    → API ошибка: code={data.get('code')}")
                        break
                else:
                    print(f"    → HTTP ошибка: {resp.status}")
                    break

                # Не спамим — небольшая пауза
                time.sleep(10)

            except Exception as e:
                print(f"    → Ошибка: {e}")
                break

        browser.close()
        print(f"  📦 Всего собрано видео: {len(all_videos)}")
        return all_videos


def save_videos_to_file(videos: List[Dict], filename: str):
    with open(filename, "w", encoding="utf-8") as f:
        for i, video in enumerate(videos, 1):
            f.write(f"Видео {i}\n")
            f.write(f"coverUrl: {video['coverUrl']}\n")
            f.write(f"playCount: {video['playCount']}\n")
            f.write(f"likeCount: {video['likeCount']}\n")
            f.write(f"commentCount: {video['commentCount']}\n")
            f.write(f"postId: {video['postId']}\n")
            f.write("\n")
    print(f"✅ Сохранено {len(videos)} видео в файл: {filename}")


def parse_likee_profile_by_url(profile_url: str) -> List[Dict]:
    profile_url = profile_url.strip()
    match = re.search(r"/p/([a-zA-Z0-9]+)", profile_url)
    if not match:
        raise ValueError(f"Неверный формат URL: {profile_url}")

    short_id = match.group(1)
    print(f"🔍 Извлечен short_id: {short_id}")

    uid = get_uid_from_profile_page(short_id, timeout_ms=15000)
    if not uid:
        raise RuntimeError("Не удалось получить uid.")

    print(f"🔑 Получен uid: {uid}. Собираем максимум видео...")
    return get_all_videos_by_uid(uid)


# === Запуск ===
if __name__ == "__main__":
    urls = [
        "https://likee.video/p/BE4Uku",
        "https://likee.video/p/88ClN7"
    ]

    for url in urls:
        try:
            print("\n" + "="*60)
            videos = parse_likee_profile_by_url(url)
            print(f"\n✅ ВСЕГО найдено {len(videos)} видео для {url}")

            short_id = re.search(r"/p/([a-zA-Z0-9]+)", url).group(1)
            filename = f"likee_videos_{short_id}.txt"
            save_videos_to_file(videos, filename)

            # Показываем первые 2 видео
            for i, v in enumerate(videos[:2], 1):
                print(f"  {i}. Просмотры: {v['playCount']}, Лайки: {v['likeCount']}")
                print(f"     Обложка: {v['coverUrl']}")
        except Exception as e:
            print(f"❌ ФАТАЛЬНАЯ ОШИБКА для {url}: {e}")
