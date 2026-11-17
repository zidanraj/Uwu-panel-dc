import threading, time, random, requests, json, os, re
from datetime import datetime
from bot.captcha import solve_hcaptcha

# active bots: {uid: {aid: thread}}
_bots = {}
_stop_flags = {}

DISCORD_API = "https://discord.com/api/v9"

def _headers(token):
    return {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Super-Properties": "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiQ2hyb21lIiwiZGV2aWNlIjoiIiwic3lzdGVtX2xvY2FsZSI6ImVuLVVTIiwiYnJvd3Nlcl91c2VyX2FnZW50IjoiTW96aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAuMDsgV2luNjQ7IHg2NCkgQXBwbGVXZWJLaXQvNTM3LjM2IChLSFRNTCwgbGlrZSBHZWNrbykgQ2hyb21lLzEyMC4wLjAuMCBTYWZhcmkvNTM3LjM2IiwiYnJvd3Nlcl92ZXJzaW9uIjoiMTIwLjAuMC4wIiwib3NfdmVyc2lvbiI6IjEwIiwicmVmZXJyZXIiOiIiLCJyZWZlcnJpbmdfZG9tYWluIjoiIiwicmVmZXJyZXJfY3VycmVudCI6IiIsInJlZmVycmluZ19kb21haW5fY3VycmVudCI6IiIsInJlbGVhc2VfY2hhbm5lbCI6InN0YWJsZSIsImNsaWVudF9idWlsZF9udW1iZXIiOjI2NTQ5NiwiY2xpZW50X2V2ZW50X3NvdXJjZSI6bnVsbH0=",
    }

def _send_message(token, channel_id, content, proxy=None):
    proxies = None
    if proxy and proxy.strip() and proxy.strip().lower() != "direct":
        p = proxy.strip()
        if not p.startswith(("http", "socks")):
            p = "socks5://" + p
        proxies = {"http": p, "https": p}
    try:
        r = requests.post(
            f"{DISCORD_API}/channels/{channel_id}/messages",
            headers=_headers(token),
            json={"content": content},
            proxies=proxies,
            timeout=15
        )
        return r
    except Exception as e:
        print(f"[send_msg] error: {e}")
        return None

def _get_messages(token, channel_id, limit=5, proxy=None):
    proxies = None
    if proxy and proxy.strip() and proxy.strip().lower() != "direct":
        p = proxy.strip()
        if not p.startswith(("http", "socks")):
            p = "socks5://" + p
        proxies = {"http": p, "https": p}
    try:
        r = requests.get(
            f"{DISCORD_API}/channels/{channel_id}/messages?limit={limit}",
            headers=_headers(token),
            proxies=proxies,
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"[get_msgs] error: {e}")
    return []

def _load_data():
    if not os.path.exists("data.json"):
        return {"clients": {}, "invites": {}}
    with open("data.json") as f:
        return json.load(f)

def _save_data(d):
    with open("data.json", "w") as f:
        json.dump(d, f, indent=2)

def _update_stat(uid, aid, **kwargs):
    try:
        d = _load_data()
        acc = d["clients"].get(uid, {}).get("accounts", {}).get(aid)
        if acc:
            for k, v in kwargs.items():
                if k in ("hunts", "battles", "commands"):
                    acc[k] = acc.get(k, 0) + v
                else:
                    acc[k] = v
            d["clients"][uid]["accounts"][aid] = acc
            _save_data(d)
    except Exception as e:
        print(f"[stat] {e}")

def _bot_loop(uid, aid, token, channel_id, proxy, settings, stop_flag):
    prefix = settings.get("prefix", "owo")
    hunt_enabled = settings.get("hunt_enabled", True)
    battle_enabled = settings.get("battle_enabled", True)
    daily_enabled = settings.get("daily_enabled", True)
    pray_enabled = settings.get("pray_enabled", False)
    curse_enabled = settings.get("curse_enabled", False)
    hunt_min = int(settings.get("hunt_min", 10))
    hunt_max = int(settings.get("hunt_max", 15))
    battle_min = int(settings.get("battle_min", 15))
    battle_max = int(settings.get("battle_max", 20))

    captcha_service = settings.get("captcha_service", "2captcha")
    captcha_key = settings.get("captcha_key", "")
    jojo_key = settings.get("jojo_key", "")
    capmonster_key = settings.get("capmonster_key", "")
    nopecha_key = settings.get("nopecha_key", "")

    last_daily = 0
    hunt_cycle = 0
    battle_cycle = 0

    print(f"[bot] started uid={uid} aid={aid[:8]}")

    while not stop_flag["stop"]:
        now = time.time()

        # hunt
        if hunt_enabled and now - hunt_cycle >= random.randint(hunt_min, hunt_max):
            r = _send_message(token, channel_id, f"{prefix} hunt", proxy)
            if r and r.status_code == 200:
                hunt_cycle = now
                _update_stat(uid, aid, hunts=1, commands=1)
                time.sleep(random.uniform(1.5, 3.0))
                # check for captcha in recent messages
                msgs = _get_messages(token, channel_id, 3, proxy)
                for m in msgs:
                    if m.get("author", {}).get("id") == "408785106942164992":
                        content = m.get("content", "")
                        if "captcha" in content.lower() or "verify" in content.lower():
                            print(f"[captcha] detected for {aid[:8]}")
                            token_solved = solve_hcaptcha(
                                captcha_service, captcha_key,
                                jojo_key, capmonster_key, nopecha_key
                            )
                            if token_solved:
                                _send_message(token, channel_id, token_solved, proxy)
                            break

        # battle
        if battle_enabled and now - battle_cycle >= random.randint(battle_min, battle_max):
            r = _send_message(token, channel_id, f"{prefix} battle", proxy)
            if r and r.status_code == 200:
                battle_cycle = now
                _update_stat(uid, aid, battles=1, commands=1)

        # daily (once per 23h)
        if daily_enabled and now - last_daily >= 23 * 3600:
            r = _send_message(token, channel_id, f"{prefix} daily", proxy)
            if r and r.status_code == 200:
                last_daily = now
                _update_stat(uid, aid, commands=1)

        # pray
        if pray_enabled:
            _send_message(token, channel_id, f"{prefix} pray", proxy)
            _update_stat(uid, aid, commands=1)
            time.sleep(random.uniform(1, 2))

        # curse
        if curse_enabled:
            _send_message(token, channel_id, f"{prefix} curse", proxy)
            _update_stat(uid, aid, commands=1)
            time.sleep(random.uniform(1, 2))

        # check balance periodically
        if random.random() < 0.05:  # ~5% chance each loop
            r = _send_message(token, channel_id, f"{prefix} cash", proxy)
            if r and r.status_code == 200:
                time.sleep(1.5)
                msgs = _get_messages(token, channel_id, 3, proxy)
                for m in msgs:
                    if m.get("author", {}).get("id") == "408785106942164992":
                        m_content = m.get("content", "")
                        match = re.search(r"[\d,]+", m_content.replace(",", ""))
                        if match:
                            try:
                                bal = int(match.group().replace(",", ""))
                                _update_stat(uid, aid, balance=bal)
                            except:
                                pass
                        break

        time.sleep(random.uniform(0.8, 1.5))

    print(f"[bot] stopped uid={uid} aid={aid[:8]}")
    _update_stat(uid, aid, running=False, status="stopped")

def start_account(uid, aid, acc, settings):
    key = f"{uid}:{aid}"
    if key in _bots and _bots[key].is_alive():
        return
    flag = {"stop": False}
    _stop_flags[key] = flag
    t = threading.Thread(
        target=_bot_loop,
        args=(uid, aid, acc["token"], acc["channel_id"],
              acc.get("proxy", ""), settings, flag),
        daemon=True
    )
    _bots[key] = t
    t.start()

def stop_account(uid, aid):
    key = f"{uid}:{aid}"
    if key in _stop_flags:
        _stop_flags[key]["stop"] = True
    if key in _bots:
        del _bots[key]

def send_owo_coins(uid, account_ids, target, amount, d):
    """Send owo coins sequentially with 8s gap between each account."""
    for i, aid in enumerate(account_ids):
        acc = d["clients"].get(uid, {}).get("accounts", {}).get(aid)
        if not acc:
            continue
        token = acc.get("token", "")
        channel_id = acc.get("channel_id", "")
        proxy = acc.get("proxy", "")
        prefix = d["clients"][uid].get("settings", {}).get("prefix", "owo")
        cmd = f"{prefix} give {target} {amount}"
        r = _send_message(token, channel_id, cmd, proxy)
        if r:
            print(f"[send_owo] aid={aid[:8]} status={r.status_code}")
        if i < len(account_ids) - 1:
            time.sleep(8)
