import requests

# Настройки прокси
proxy_url = "pA7b4DkZVm:8yv1LzTa82@109.120.131.6:53046"
proxies = {
    "http": proxy_url,
    "https": proxy_url,
}

url = "https://ya.ru/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

try:
    response = requests.get(url, headers=headers, proxies=proxies, timeout=10)
    response.raise_for_status()  # Проверка на ошибки HTTP
    with open("test_tiktok_html.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("Ответ успешно сохранён в test_tiktok_html.html")
except requests.exceptions.RequestException as e:
    print(f"Ошибка при выполнении запроса: {e}")
