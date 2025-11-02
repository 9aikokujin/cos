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
        # "2p9UY4YAxP:O9Mru1m26m@109.120.131.161:34945",
        # "pA7b4DkZVm:8yv1LzTa82@109.120.131.6:53046",
        # "fPdEeT67zF:AkrSIiWZRN@109.120.131.124:61827",
        # "iYvNraz4Qo:CtXfUQFIm6@109.120.131.25:36592",
        # "XAQrpqMDWw:IokI8mYSKf@109.120.131.129:43852",
        # "CCgYrPgXPY:KA3apNGhbN@109.120.131.229:27100",
        # "7ImUgttUz5:PlcstoApnp@109.120.131.196:56618",
        # "glyxP8tEya:HPhM9wjQGM@109.120.131.114:31838",
        # "Pujlnq340D:lZXechQsfm@109.120.131.40:56974",
        # "F0AIJxsjsK:0KaDLg5uES@109.120.131.169:31162",

        "msEHZ8:tYomUE@168.196.239.222:9211",
        "msEHZ8:tYomUE@168.196.237.44:9129",
        "msEHZ8:tYomUE@168.196.237.99:9160",
        "msEHZ8:tYomUE@138.219.122.56:9409",
        "msEHZ8:tYomUE@138.219.122.128:9584",
        "msEHZ8:tYomUE@138.219.123.22:9205",
        "msEHZ8:tYomUE@138.59.5.46:9559",
        "msEHZ8:tYomUE@152.232.68.147:9269",
        "msEHZ8:tYomUE@152.232.67.18:9241",
        "msEHZ8:tYomUE@152.232.68.149:9212",
        "msEHZ8:tYomUE@152.232.66.152:9388",
        "msEHZ8:tYomUE@152.232.65.53:9461",
        "msEHZ8:tYomUE@190.185.108.103:9335",
        "msEHZ8:tYomUE@138.99.37.16:9622",
        "msEHZ8:tYomUE@138.99.37.136:9248",
        "msEHZ8:tYomUE@152.232.72.124:9057",
        "msEHZ8:tYomUE@23.229.49.135:9511",
        "msEHZ8:tYomUE@209.127.8.189:9281",
        "msEHZ8:tYomUE@152.232.72.235:9966",
        "msEHZ8:tYomUE@152.232.74.34:9043",

        "d8mAnk3QEW:mJCDjUZQXt@45.150.35.133:20894",
        "quUqYxfzsN:IVsnELV4fT@45.150.35.246:46257",
        "RfbRo1W0gz:Rk5fwJnepP@45.150.35.131:63024",
        "jcB7GBuBdw:wnOUcC6uC2@45.150.35.40:52284",
        "rJexYOOn6O:tjd4Q4SgTN@45.150.35.194:57330",
        "ZoA3aDjewp:lgRGWxPzR5@45.150.35.117:35941",
        "PSKbldOuol:YRinsMQpQB@45.150.35.74:42121",
        "aNpriSRLmG:RVEBaYMSnq@45.150.35.145:27900",
        "um2y7QWzne:3NVuS7S93n@45.150.35.180:58611",
        "gkmSRIalTf:xGROjfA2LF@45.150.35.154:39073",
        "hejdZusT4h:BJYdsmEZKI@45.150.35.10:36612",
        "nbyr75VACh:I5WWfT2oLt@45.150.35.215:48124",
        "fgOfy2ylm9:9fKs4syWBG@45.150.35.48:47557",
        "um2y7QWzne:3NVuS7S93n@45.150.35.180:5861"
    ]

# F0AIJxsjsK:0KaDLg5uES@109.120.131.169:31162\nd8mAnk3QEW:mJCDjUZQXt@45.150.35.133:2089\nquUqYxfzsN:IVsnELV4fT@45.150.35.246:4625\nRfbRo1W0gz:Rk5fwJnepP@45.150.35.131:6302\njcB7GBuBdw:wnOUcC6uC2@45.150.35.40:5228\nrJexYOOn6O:tjd4Q4SgTN@45.150.35.194:5733\nZoA3aDjewp:lgRGWxPzR5@45.150.35.117:3594\nPSKbldOuol:YRinsMQpQB@45.150.35.74:4212\naNpriSRLmG:RVEBaYMSnq@45.150.35.145:2790\num2y7QWzne:3NVuS7S93n@45.150.35.180:5861\ngkmSRIalTf:xGROjfA2LF@45.150.35.154:3907\nhejdZusT4h:BJYdsmEZKI@45.150.35.10:3661\nnbyr75VACh:I5WWfT2oLt@45.150.35.215:4812\nfgOfy2ylm9:9fKs4syWBG@45.150.35.48:47557

    # working = test_all_proxies(proxies, test_url="https://ya.ru/", timeout=10)
    # print(f"Всего рабочих прокси: {len(working)}")
    working = test_all_proxies(proxies, test_url="https://www.youtube.com/shorts/fStb9Ge0c88", timeout=10)
    print(f"Всего рабочих прокси: {len(working)}")
