import requests, time, json

OWO_SITE_KEY = "2a60c466-cf50-4d79-9d6b-eae1caabde77"
OWO_PAGE_URL = "https://owobot.com"

def solve_hcaptcha(service, key_2captcha, jojo_key, capmonster_key, nopecha_key):
    """Route to the right solver based on selected service."""
    service = service.lower().strip()
    try:
        if service == "2captcha" and key_2captcha:
            return _2captcha(key_2captcha)
        elif service == "capmonster" and capmonster_key:
            return _capmonster(capmonster_key)
        elif service == "nopecha" and nopecha_key:
            return _nopecha(nopecha_key)
        elif service == "jojo" and jojo_key:
            return _jojo(jojo_key)
        elif service == "anticaptcha" and key_2captcha:
            return _anticaptcha(key_2captcha)
    except Exception as e:
        print(f"[captcha] solve error: {e}")
    return None

def _2captcha(api_key):
    r = requests.post("https://2captcha.com/in.php", data={
        "key": api_key,
        "method": "hcaptcha",
        "sitekey": OWO_SITE_KEY,
        "pageurl": OWO_PAGE_URL,
        "json": 1
    }, timeout=30)
    data = r.json()
    if data.get("status") != 1:
        return None
    task_id = data["request"]
    for _ in range(30):
        time.sleep(5)
        r2 = requests.get(f"https://2captcha.com/res.php?key={api_key}&action=get&id={task_id}&json=1", timeout=15)
        d2 = r2.json()
        if d2.get("status") == 1:
            return d2["request"]
        if d2.get("request") == "ERROR_CAPTCHA_UNSOLVABLE":
            return None
    return None

def _anticaptcha(api_key):
    r = requests.post("https://api.anti-captcha.com/createTask", json={
        "clientKey": api_key,
        "task": {
            "type": "HCaptchaTaskProxyless",
            "websiteURL": OWO_PAGE_URL,
            "websiteKey": OWO_SITE_KEY,
        }
    }, timeout=30)
    data = r.json()
    if data.get("errorId") != 0:
        return None
    task_id = data["taskId"]
    for _ in range(30):
        time.sleep(5)
        r2 = requests.post("https://api.anti-captcha.com/getTaskResult", json={
            "clientKey": api_key,
            "taskId": task_id
        }, timeout=15)
        d2 = r2.json()
        if d2.get("status") == "ready":
            return d2.get("solution", {}).get("gRecaptchaResponse")
    return None

def _capmonster(api_key):
    r = requests.post("https://api.capmonster.cloud/createTask", json={
        "clientKey": api_key,
        "task": {
            "type": "HCaptchaTaskProxyless",
            "websiteURL": OWO_PAGE_URL,
            "websiteKey": OWO_SITE_KEY,
        }
    }, timeout=30)
    data = r.json()
    if data.get("errorId") != 0:
        return None
    task_id = data["taskId"]
    for _ in range(30):
        time.sleep(5)
        r2 = requests.post("https://api.capmonster.cloud/getTaskResult", json={
            "clientKey": api_key,
            "taskId": task_id
        }, timeout=15)
        d2 = r2.json()
        if d2.get("status") == "ready":
            return d2.get("solution", {}).get("gRecaptchaResponse")
    return None

def _nopecha(api_key):
    r = requests.post("https://api.nopecha.com/", json={
        "type": "hcaptcha",
        "sitekey": OWO_SITE_KEY,
        "url": OWO_PAGE_URL,
        "key": api_key
    }, timeout=30)
    data = r.json()
    if data.get("error"):
        return None
    job_id = data.get("data")
    for _ in range(30):
        time.sleep(5)
        r2 = requests.get(f"https://api.nopecha.com/?key={api_key}&id={job_id}", timeout=15)
        d2 = r2.json()
        if not d2.get("error") and d2.get("data"):
            return d2["data"]
    return None

def _jojo(api_key):
    r = requests.post("https://api.jojocaps.com/createTask", json={
        "clientKey": api_key,
        "task": {
            "type": "HCaptchaTaskProxyless",
            "websiteURL": OWO_PAGE_URL,
            "websiteKey": OWO_SITE_KEY,
        }
    }, timeout=30)
    data = r.json()
    if data.get("errorId") != 0:
        return None
    task_id = data.get("taskId")
    for _ in range(30):
        time.sleep(5)
        r2 = requests.post("https://api.jojocaps.com/getTaskResult", json={
            "clientKey": api_key,
            "taskId": task_id
        }, timeout=15)
        d2 = r2.json()
        if d2.get("status") == "ready":
            return d2.get("solution", {}).get("gRecaptchaResponse")
    return None
