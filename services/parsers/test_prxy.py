import requests
from urllib.parse import quote

url = "https://www.youtube.com/shorts/7O0FbpwkD50"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Данные прокси
user = "msEHZ8"
pwd  = "tYomUE"
host = "168.196.239.222"
port = 9211

# На случай спецсимволов в логине/пароле
auth = f"{quote(user)}:{quote(pwd)}"

# ЕСЛИ это обычный HTTP-прокси (чаще всего так и есть):
proxy_url = f"http://{auth}@{host}:{port}"
proxies = {
    "http": proxy_url,
    "https": proxy_url,  # HTTPS-трафик пойдёт через CONNECT поверх HTTP-прокси
}

# # ЕСЛИ это именно HTTPS-прокси (TLS до прокси), используйте:
# proxy_url = f"https://{auth}@{host}:{port}"
# proxies = {"http": proxy_url, "https": proxy_url}

# # ЕСЛИ это SOCKS5-прокси:
# # pip install "requests[socks]"
# proxy_url = f"socks5h://{auth}@{host}:{port}"
# proxies = {"http": proxy_url, "https": proxy_url}

try:
    r = requests.get(url, headers=headers, proxies=proxies, timeout=15)
    r.raise_for_status()
    with open("test_youtube_last_html.html", "w", encoding="utf-8") as f:
        f.write(r.text)
    print("Ответ успешно сохранён в test_youtube_last_html.html")
except requests.RequestException as e:
    print(f"Ошибка при выполнении запроса: {e}")
