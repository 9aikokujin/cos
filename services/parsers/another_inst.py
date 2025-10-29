#!/usr/bin/env python3
import argparse, json, sys, time, typing as t
from datetime import datetime
from urllib.parse import quote
import requests

INSTAGRAM_APP_ID = "936619743392459"  # актуальный app id веб-клиента
DEFAULT_DOC_ID_REEL = "25981206651899035"  # может меняться у IG

BASE_HEADERS = {
    "x-ig-app-id": INSTAGRAM_APP_ID,
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "*/*",
}

def jprint(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))

def fetch_profile(username: str, cookies: dict[str, str] | None, timeout: float=15.0) -> dict:
    url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
    r = requests.get(url, headers=BASE_HEADERS, cookies=cookies, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"web_profile_info HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    # ожидаем data -> user
    if not isinstance(data, dict) or "data" not in data or "user" not in data["data"]:
        raise RuntimeError(f"Unexpected profile JSON shape: {r.text[:400]}")
    return data["data"]["user"]

def iter_post_nodes_from_profile(profile_json: dict) -> list[dict]:
    # первые посты в: edge_owner_to_timeline_media.edges[].node
    media = (
        profile_json
        .get("edge_owner_to_timeline_media", {})
        .get("edges", [])
    )
    return [e.get("node", {}) for e in media if isinstance(e, dict)]

def fetch_reel_by_shortcode(shortcode: str, doc_id: str, cookies: dict[str, str] | None, timeout: float=15.0) -> dict:
    variables = {
        "shortcode": shortcode,
        "fetch_like_count": True,
        "fetch_comment_count": True,
        "parent_comment_count": 24,
        "has_threaded_comments": True
    }
    url = (
        "https://www.instagram.com/graphql/query/"
        f"?doc_id={doc_id}&variables={quote(json.dumps(variables, separators=(',',':')))}"
    )
    r = requests.get(url, headers=BASE_HEADERS, cookies=cookies, timeout=timeout)
    if r.status_code != 200:
        raise RuntimeError(f"graphql/query HTTP {r.status_code}: {r.text[:200]}")
    data = r.json()
    if not isinstance(data, dict) or "data" not in data or "shortcode_media" not in data["data"]:
        # иногда IG отвечает иначе — покажем, что пришло
        raise RuntimeError(f"Unexpected reel JSON shape: {r.text[:400]}")
    return data["data"]["shortcode_media"]

def extract_metrics(shortcode_media: dict) -> dict:
    # лайки
    likes = (
        shortcode_media
        .get("edge_media_preview_like", {})
        .get("count")
    )
    # комменты
    comments = (
        shortcode_media
        .get("edge_media_to_parent_comment", shortcode_media.get("edge_media_to_comment", {}))
        .get("count")
    )
    # просмотры/проигрывания
    views = shortcode_media.get("video_view_count") or shortcode_media.get("video_play_count")
    ts = shortcode_media.get("taken_at_timestamp")
    caption_edges = (
        shortcode_media
        .get("edge_media_to_caption", {})
        .get("edges", [])
    )
    caption = caption_edges[0]["node"]["text"] if caption_edges else ""
    preview = shortcode_media.get("display_url") or shortcode_media.get("thumbnail_src")
    video_url = shortcode_media.get("video_url")

    return {
        "shortcode": shortcode_media.get("shortcode"),
        "likes": likes,
        "comments": comments,
        "views": views,
        "timestamp": ts,
        "created_utc": datetime.utcfromtimestamp(ts).isoformat() + "Z" if isinstance(ts, int) else None,
        "caption": caption,
        "preview_image": preview,
        "video_url": video_url,
    }

def parse_cookies(args) -> dict[str, str] | None:
    if not (args.sessionid or args.csrftoken or args.ds_user_id):
        return None
    cookies = {}
    if args.sessionid:  cookies["sessionid"] = args.sessionid
    if args.csrftoken:  cookies["csrftoken"] = args.csrftoken
    if args.ds_user_id: cookies["ds_user_id"] = args.ds_user_id
    return cookies

def run_from_sample(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # поддержим два формата: 1) целиком ответ graphql; 2) уже media под ключом data.shortcode_media
    if "data" in data and "shortcode_media" in data["data"]:
        media = data["data"]["shortcode_media"]
        return [extract_metrics(media)]
    # или список
    if isinstance(data, list):
        out = []
        for item in data:
            if "data" in item and "shortcode_media" in item["data"]:
                out.append(extract_metrics(item["data"]["shortcode_media"]))
        return out
    # или одиночная нода
    return [extract_metrics(data)]

def main():
    ap = argparse.ArgumentParser(description="Fetch Instagram Reels metrics from a public profile")
    ap.add_argument("username", help="instagram username, e.g. shd.tattoo")
    ap.add_argument("--limit", type=int, default=12, help="limit posts to check (default: 12)")
    ap.add_argument("--doc-id", default=DEFAULT_DOC_ID_REEL, help="GraphQL doc_id for reel detail")
    ap.add_argument("--sessionid")
    ap.add_argument("--csrftoken")
    ap.add_argument("--ds_user_id")
    ap.add_argument("--sample", help="read reels from local JSON (no network)")
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args()

    if args.sample:
        print("[i] Using sample JSON:", args.sample)
        rows = run_from_sample(args.sample)
        for r in rows:
            jprint(r)
        return

    cookies = parse_cookies(args)

    try:
        print(f"[i] Fetching profile for @{args.username} ...")
        profile = fetch_profile(args.username, cookies, timeout=args.timeout)
        nodes = iter_post_nodes_from_profile(profile)
        if not nodes:
            print("[!] No posts found in profile JSON (maybe private or blocked).")
            return

        checked = 0
        for node in nodes:
            if checked >= args.limit:
                break
            shortcode = node.get("shortcode")
            is_video = node.get("__typename") in ("GraphVideo", "GraphSidecar") or node.get("is_video")
            # Reels обычно видео; на всякий случай проверяем флаг:
            if not shortcode or not is_video:
                continue
            try:
                print(f"[i] Fetching reel {shortcode} ...")
                scm = fetch_reel_by_shortcode(shortcode, args.doc_id, cookies, timeout=args.timeout)
                row = extract_metrics(scm)
                jprint(row)
                checked += 1
                time.sleep(0.8)  # легкая пауза, чтобы не душили
            except Exception as e:
                print(f"[!] Reel {shortcode} failed: {e}")
        if checked == 0:
            print("[!] No reels parsed. Try adding cookies or adjusting --doc-id.")
    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    main()
