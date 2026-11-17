import os, json, uuid, hashlib, secrets, threading
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_socketio import SocketIO, emit, join_room
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

ADMIN_USER = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "changeme")
DATA_FILE = "data.json"
DATA_LOCK = threading.Lock()

# ─── Data Layer ───────────────────────────────────────────────
def load_data():
    if not os.path.exists(DATA_FILE):
        return {"clients": {}, "invites": {}}
    with open(DATA_FILE) as f:
        return json.load(f)

def save_data(d):
    with DATA_LOCK:
        with open(DATA_FILE, "w") as f:
            json.dump(d, f, indent=2)

def hash_pass(p):
    return hashlib.sha256(p.encode()).hexdigest()

# ─── Auth Decorators ──────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if session.get("role") != "admin":
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper

def client_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if session.get("role") not in ("admin", "client"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper

# ─── Auth Routes ──────────────────────────────────────────────
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        if u == ADMIN_USER and p == ADMIN_PASS:
            session["role"] = "admin"
            session["uid"] = "admin"
            session["username"] = u
            return redirect(url_for("admin_dashboard"))
        d = load_data()
        for uid, cl in d["clients"].items():
            if cl["username"] == u and cl["password"] == hash_pass(p):
                exp = cl.get("expires_at")
                if exp and datetime.fromisoformat(exp) < datetime.utcnow():
                    flash("account_expired")
                    return redirect(url_for("login"))
                if not cl.get("active", True):
                    flash("account_disabled")
                    return redirect(url_for("login"))
                session["role"] = "client"
                session["uid"] = uid
                session["username"] = u
                return redirect(url_for("client_dashboard"))
        flash("invalid_credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─── Invite System ────────────────────────────────────────────
@app.route("/invite/<code>", methods=["GET", "POST"])
def use_invite(code):
    d = load_data()
    inv = d["invites"].get(code)
    if not inv:
        return render_template("login.html", invite_error="Invalid invite link.")
    if inv.get("used"):
        return render_template("login.html", invite_error="Invite already used.")
    if datetime.fromisoformat(inv["expires_at"]) < datetime.utcnow():
        return render_template("login.html", invite_error="Invite expired.")
    if request.method == "POST":
        u = request.form.get("username", "").strip()
        p = request.form.get("password", "").strip()
        if not u or not p:
            return render_template("register.html", code=code, error="Fill all fields.")
        for cl in d["clients"].values():
            if cl["username"] == u:
                return render_template("register.html", code=code, error="Username taken.")
        uid = str(uuid.uuid4())
        acc_expires = None
        if inv.get("duration_hours"):
            acc_expires = (datetime.utcnow() + timedelta(hours=inv["duration_hours"])).isoformat()
        d["clients"][uid] = {
            "username": u,
            "password": hash_pass(p),
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": acc_expires,
            "active": True,
            "accounts": {},
            "settings": {
                "captcha_service": "2captcha",
                "captcha_key": "",
                "jojo_key": "",
                "capmonster_key": "",
                "nopecha_key": "",
                "prefix": "owo",
                "hunt_enabled": True,
                "battle_enabled": True,
                "daily_enabled": True,
                "pray_enabled": False,
                "curse_enabled": False,
                "hunt_min": 10,
                "hunt_max": 15,
                "battle_min": 15,
                "battle_max": 20,
            }
        }
        d["invites"][code]["used"] = True
        d["invites"][code]["used_by"] = u
        save_data(d)
        flash("registered")
        return redirect(url_for("login"))
    return render_template("register.html", code=code)

# ─── Admin Routes ─────────────────────────────────────────────
@app.route("/admin")
@admin_required
def admin_dashboard():
    d = load_data()
    stats = {
        "total_clients": len(d["clients"]),
        "active_clients": sum(1 for c in d["clients"].values() if c.get("active")),
        "total_invites": len(d["invites"]),
        "pending_invites": sum(1 for i in d["invites"].values() if not i.get("used")),
        "total_accounts": sum(len(c.get("accounts", {})) for c in d["clients"].values()),
    }
    clients = []
    for uid, cl in d["clients"].items():
        exp = cl.get("expires_at")
        expired = exp and datetime.fromisoformat(exp) < datetime.utcnow()
        clients.append({
            "uid": uid,
            "username": cl["username"],
            "active": cl.get("active", True),
            "expired": expired,
            "expires_at": exp,
            "account_count": len(cl.get("accounts", {})),
            "created_at": cl.get("created_at", ""),
        })
    return render_template("admin/dashboard.html", stats=stats, clients=clients)

@app.route("/admin/invite/create", methods=["POST"])
@admin_required
def create_invite():
    d = load_data()
    hours = int(request.form.get("duration_hours", 0)) or None
    acc_hours = int(request.form.get("account_duration_hours", 0)) or None
    code = secrets.token_urlsafe(16)
    inv_expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    d["invites"][code] = {
        "code": code,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": inv_expires,
        "duration_hours": acc_hours,
        "used": False,
        "used_by": None,
    }
    save_data(d)
    link = request.host_url + f"invite/{code}"
    return jsonify({"link": link, "code": code})

@app.route("/admin/client/<uid>/toggle", methods=["POST"])
@admin_required
def toggle_client(uid):
    d = load_data()
    if uid in d["clients"]:
        d["clients"][uid]["active"] = not d["clients"][uid].get("active", True)
        save_data(d)
        return jsonify({"ok": True, "active": d["clients"][uid]["active"]})
    return jsonify({"ok": False}), 404

@app.route("/admin/client/<uid>/delete", methods=["POST"])
@admin_required
def delete_client(uid):
    d = load_data()
    if uid in d["clients"]:
        del d["clients"][uid]
        save_data(d)
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 404

@app.route("/admin/client/<uid>/view")
@admin_required
def view_client(uid):
    d = load_data()
    cl = d["clients"].get(uid)
    if not cl:
        return redirect(url_for("admin_dashboard"))
    accounts = []
    for aid, acc in cl.get("accounts", {}).items():
        accounts.append({
            "aid": aid,
            "name": acc.get("name", "Account"),
            "token_preview": acc.get("token", "")[:20] + "...",
            "channel_id": acc.get("channel_id", ""),
            "running": acc.get("running", False),
            "balance": acc.get("balance", 0),
            "hunts": acc.get("hunts", 0),
            "battles": acc.get("battles", 0),
            "proxy": acc.get("proxy", ""),
        })
    return render_template("admin/client_view.html", client=cl, uid=uid, accounts=accounts)

@app.route("/admin/invites")
@admin_required
def admin_invites():
    d = load_data()
    invites = []
    for code, inv in d["invites"].items():
        exp = inv.get("expires_at")
        expired = exp and datetime.fromisoformat(exp) < datetime.utcnow()
        invites.append({
            "code": code,
            "link": request.host_url + f"invite/{code}",
            "created_at": inv.get("created_at", ""),
            "expires_at": exp,
            "duration_hours": inv.get("duration_hours"),
            "used": inv.get("used", False),
            "used_by": inv.get("used_by"),
            "expired": expired,
        })
    return render_template("admin/invites.html", invites=invites)

@app.route("/admin/invite/<code>/delete", methods=["POST"])
@admin_required
def delete_invite(code):
    d = load_data()
    if code in d["invites"]:
        del d["invites"][code]
        save_data(d)
    return jsonify({"ok": True})

# ─── Client Routes ────────────────────────────────────────────
def get_client_data():
    d = load_data()
    uid = session.get("uid")
    if uid == "admin":
        return None, None, d
    return uid, d["clients"].get(uid), d

@app.route("/dashboard")
@client_required
def client_dashboard():
    uid, cl, d = get_client_data()
    if uid == "admin":
        return redirect(url_for("admin_dashboard"))
    if not cl:
        session.clear()
        return redirect(url_for("login"))
    accounts = cl.get("accounts", {})
    total = len(accounts)
    running = sum(1 for a in accounts.values() if a.get("running"))
    total_hunts = sum(a.get("hunts", 0) for a in accounts.values())
    total_battles = sum(a.get("battles", 0) for a in accounts.values())
    total_balance = sum(a.get("balance", 0) for a in accounts.values())
    return render_template("client/dashboard.html",
        client=cl, accounts=accounts,
        total=total, running=running,
        total_hunts=total_hunts, total_battles=total_battles,
        total_balance=total_balance)

@app.route("/accounts")
@client_required
def client_accounts():
    uid, cl, d = get_client_data()
    if uid == "admin":
        return redirect(url_for("admin_dashboard"))
    accounts = cl.get("accounts", {})
    acc_list = []
    for aid, acc in accounts.items():
        acc_list.append({
            "aid": aid,
            "name": acc.get("name", "Account"),
            "channel_id": acc.get("channel_id", ""),
            "running": acc.get("running", False),
            "balance": acc.get("balance", 0),
            "hunts": acc.get("hunts", 0),
            "battles": acc.get("battles", 0),
            "proxy": acc.get("proxy", "direct"),
            "status": acc.get("status", "stopped"),
        })
    return render_template("client/accounts.html", client=cl, accounts=acc_list,
        can_add=len(accounts) < 50)

@app.route("/accounts/add", methods=["POST"])
@client_required
def add_account():
    uid, cl, d = get_client_data()
    if len(cl.get("accounts", {})) >= 50:
        return jsonify({"ok": False, "error": "Max 50 accounts"}), 400
    name = request.form.get("name", "Account").strip()
    token = request.form.get("token", "").strip()
    channel_id = request.form.get("channel_id", "").strip()
    proxy = request.form.get("proxy", "").strip()
    if not token or not channel_id:
        return jsonify({"ok": False, "error": "Token and channel ID required"}), 400
    aid = str(uuid.uuid4())
    d["clients"][uid]["accounts"][aid] = {
        "name": name,
        "token": token,
        "channel_id": channel_id,
        "proxy": proxy,
        "running": False,
        "status": "stopped",
        "balance": 0,
        "hunts": 0,
        "battles": 0,
        "commands": 0,
        "uptime_start": None,
    }
    save_data(d)
    return jsonify({"ok": True, "aid": aid})

@app.route("/accounts/<aid>/delete", methods=["POST"])
@client_required
def delete_account(aid):
    uid, cl, d = get_client_data()
    if aid in d["clients"][uid]["accounts"]:
        # stop bot if running
        from bot.owo_bot import stop_account
        stop_account(uid, aid)
        del d["clients"][uid]["accounts"][aid]
        save_data(d)
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 404

@app.route("/accounts/<aid>/start", methods=["POST"])
@client_required
def start_account(aid):
    uid, cl, d = get_client_data()
    acc = d["clients"][uid]["accounts"].get(aid)
    if not acc:
        return jsonify({"ok": False}), 404
    from bot.owo_bot import start_account as sa
    sa(uid, aid, acc, cl.get("settings", {}))
    d["clients"][uid]["accounts"][aid]["running"] = True
    d["clients"][uid]["accounts"][aid]["status"] = "running"
    d["clients"][uid]["accounts"][aid]["uptime_start"] = datetime.utcnow().isoformat()
    save_data(d)
    return jsonify({"ok": True})

@app.route("/accounts/<aid>/stop", methods=["POST"])
@client_required
def stop_account_route(aid):
    uid, cl, d = get_client_data()
    from bot.owo_bot import stop_account
    stop_account(uid, aid)
    if aid in d["clients"][uid]["accounts"]:
        d["clients"][uid]["accounts"][aid]["running"] = False
        d["clients"][uid]["accounts"][aid]["status"] = "stopped"
        save_data(d)
    return jsonify({"ok": True})

@app.route("/accounts/start_all", methods=["POST"])
@client_required
def start_all():
    uid, cl, d = get_client_data()
    from bot.owo_bot import start_account as sa
    settings = cl.get("settings", {})
    for aid, acc in d["clients"][uid]["accounts"].items():
        if not acc.get("running"):
            sa(uid, aid, acc, settings)
            d["clients"][uid]["accounts"][aid]["running"] = True
            d["clients"][uid]["accounts"][aid]["status"] = "running"
            d["clients"][uid]["accounts"][aid]["uptime_start"] = datetime.utcnow().isoformat()
    save_data(d)
    return jsonify({"ok": True})

@app.route("/accounts/stop_all", methods=["POST"])
@client_required
def stop_all():
    uid, cl, d = get_client_data()
    from bot.owo_bot import stop_account
    for aid in list(d["clients"][uid]["accounts"].keys()):
        stop_account(uid, aid)
        d["clients"][uid]["accounts"][aid]["running"] = False
        d["clients"][uid]["accounts"][aid]["status"] = "stopped"
    save_data(d)
    return jsonify({"ok": True})

@app.route("/send_owo", methods=["POST"])
@client_required
def send_owo():
    uid, cl, d = get_client_data()
    target = request.form.get("target", "").strip()
    amount = request.form.get("amount", "1").strip()
    account_ids = request.form.getlist("account_ids")  # empty = all
    if not target or not amount:
        return jsonify({"ok": False, "error": "Target and amount required"}), 400
    from bot.owo_bot import send_owo_coins
    if not account_ids:
        account_ids = list(d["clients"][uid]["accounts"].keys())
    threading.Thread(target=send_owo_coins, args=(uid, account_ids, target, amount, d), daemon=True).start()
    return jsonify({"ok": True, "queued": len(account_ids)})

@app.route("/settings", methods=["GET", "POST"])
@client_required
def client_settings():
    uid, cl, d = get_client_data()
    if request.method == "POST":
        settings = cl.get("settings", {})
        for key in ["captcha_service", "captcha_key", "jojo_key", "capmonster_key",
                    "nopecha_key", "prefix", "hunt_min", "hunt_max", "battle_min",
                    "battle_max"]:
            val = request.form.get(key)
            if val is not None:
                settings[key] = int(val) if key.endswith(("_min", "_max")) else val
        for toggle in ["hunt_enabled", "battle_enabled", "daily_enabled",
                       "pray_enabled", "curse_enabled"]:
            settings[toggle] = toggle in request.form
        d["clients"][uid]["settings"] = settings
        save_data(d)
        return jsonify({"ok": True})
    return render_template("client/settings.html", client=cl, settings=cl.get("settings", {}))

@app.route("/stats")
@client_required
def client_stats():
    uid, cl, d = get_client_data()
    accounts = cl.get("accounts", {})
    data = []
    for aid, acc in accounts.items():
        data.append({
            "name": acc.get("name", aid[:8]),
            "hunts": acc.get("hunts", 0),
            "battles": acc.get("battles", 0),
            "balance": acc.get("balance", 0),
            "commands": acc.get("commands", 0),
            "running": acc.get("running", False),
            "status": acc.get("status", "stopped"),
        })
    return jsonify(data)

# ─── SocketIO ─────────────────────────────────────────────────
@socketio.on("join")
def on_join(data):
    room = session.get("uid", "anon")
    join_room(room)

# ─── Entry Point ──────────────────────────────────────────────
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
