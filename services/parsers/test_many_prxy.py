import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

def test_proxy(proxy_str, test_url, timeout=10):
    """
    Проверяет работоспособность одного прокси.
    
    :param proxy_str: строка вида 'login:pass@ip:port'
    :param test_url: URL для проверки
    :param timeout: таймаут запроса в секундах
    :return: кортеж (proxy_str, success: bool, response_time: float или None)
    """
    try:
        # Разбор прокси
        auth_ip_port = proxy_str.strip()
        if '@' not in auth_ip_port:
            return proxy_str, False, None
        
        auth, ip_port = auth_ip_port.split('@')
        login, password = auth.split(':')
        ip, port = ip_port.split(':')
        
        proxies = {
            "http": f"http://{login}:{password}@{ip}:{port}",
            "https": f"http://{login}:{password}@{ip}:{port}"
        }

        start = time.time()
        response = requests.get(test_url, proxies=proxies, timeout=timeout)
        elapsed = time.time() - start

        if response.status_code == 200:
            return proxy_str, True, round(elapsed, 2)
        else:
            return proxy_str, False, round(elapsed, 2)
    except Exception as e:
        return proxy_str, False, None

def test_all_proxies(proxy_list, test_url, timeout=10, max_workers=10):
    """
    Тестирует список прокси параллельно.
    
    :param proxy_list: список строк прокси
    :param test_url: URL для проверки
    :param timeout: таймаут запроса
    :param max_workers: количество потоков
    """
    working_proxies = []
    print(f"Тестирую {len(proxy_list)} прокси на доступ к {test_url}...\n")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_proxy = {
            executor.submit(test_proxy, proxy, test_url, timeout): proxy
            for proxy in proxy_list
        }

        for future in as_completed(future_to_proxy):
            proxy, success, response_time = future.result()
            status = "✅ Работает" if success else "❌ Не работает"
            rt_info = f" ({response_time}s)" if response_time else ""
            print(f"{status}{rt_info}: {proxy}")
            if success:
                working_proxies.append(proxy)

    print(f"\n✅ Всего рабочих прокси: {len(working_proxies)}")
    return working_proxies

# Пример использования:
if __name__ == "__main__":
    proxies = [
        "DWtvBb:M1uRTE@181.177.87.15:9725",
        "DWtvBb:M1uRTE@181.177.84.185:9254",
        "DWtvBb:M1uRTE@94.131.54.252:9746",
        "DWtvBb:M1uRTE@95.164.200.121:9155",
        "DWtvBb:M1uRTE@45.237.85.119:9458",
        "MecAgR:v5fbu6@186.65.118.237:9808",
        "MecAgR:v5fbu6@186.65.115.230:9065",
        "MecAgR:v5fbu6@186.65.115.105:9825",
        "suQs3N:j30sT6@170.246.55.146:9314",
        "MecAgR:v5fbu6@186.65.118.237:9808",
        "MecAgR:v5fbu6@186.65.115.230:9065",
        "MecAgR:v5fbu6@186.65.115.105:9825",
    ]

# F0AIJxsjsK:0KaDLg5uES@109.120.131.169:31162\nd8mAnk3QEW:mJCDjUZQXt@45.150.35.133:2089\nquUqYxfzsN:IVsnELV4fT@45.150.35.246:4625\nRfbRo1W0gz:Rk5fwJnepP@45.150.35.131:6302\njcB7GBuBdw:wnOUcC6uC2@45.150.35.40:5228\nrJexYOOn6O:tjd4Q4SgTN@45.150.35.194:5733\nZoA3aDjewp:lgRGWxPzR5@45.150.35.117:3594\nPSKbldOuol:YRinsMQpQB@45.150.35.74:4212\naNpriSRLmG:RVEBaYMSnq@45.150.35.145:2790\num2y7QWzne:3NVuS7S93n@45.150.35.180:5861\ngkmSRIalTf:xGROjfA2LF@45.150.35.154:3907\nhejdZusT4h:BJYdsmEZKI@45.150.35.10:3661\nnbyr75VACh:I5WWfT2oLt@45.150.35.215:4812\nfgOfy2ylm9:9fKs4syWBG@45.150.35.48:47557

    # working = test_all_proxies(proxies, test_url="https://ya.ru/", timeout=10)
    # print(f"Всего рабочих прокси: {len(working)}")

    # working = test_all_proxies(proxies, test_url="https://www.tiktok.com/", timeout=10)
    # print(f"Всего рабочих прокси: {len(working)}")
    
    working = test_all_proxies(proxies, test_url="https://www.instagram.com/", timeout=10)
    print(f"Всего рабочих прокси: {len(working)}")
    
