# Z3NITH UWU PANEL

Multi-tenant OWO selfbot farming dashboard. Dark 3D UI. Full isolation per client.

## Features
- Admin creates invite links with optional duration
- Clients register via invite → isolated dashboard
- 0–50 Discord accounts per client
- Auto hunt, battle, daily, pray, curse with human-like random cooldowns
- Multi-service HCaptcha solving (2Captcha, Anti-Captcha, CapMonster, NoPecha, JojoCaps)
- Send OWO coins: all accounts sequential (8s gap) or per-account select
- Admin can view/disable/delete any client
- Live stats refresh, per-account control

## Files
```
main.py              Flask app + all routes
bot/owo_bot.py       Discord selfbot loop (threaded)
bot/captcha.py       Multi-solver captcha routing
templates/           All Jinja2 HTML
requirements.txt
render.yaml          Render deploy config
```

## GitHub → Render Deploy

### Step 1 — Create GitHub Repo
```
git init
git add .
git commit -m "init"
git remote add origin https://github.com/YOURUSER/z3nith-uwu-panel.git
git push -u origin main
```

### Step 2 — Render Setup
1. Go to render.com → New → Web Service
2. Connect your GitHub repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn -k eventlet -w 1 --bind 0.0.0.0:$PORT main:app`
5. Python version: **3.11.0**

### Step 3 — Environment Variables (Render Dashboard)
| Key | Value |
|-----|-------|
| `ADMIN_USERNAME` | your admin username |
| `ADMIN_PASSWORD` | strong password |
| `SECRET_KEY` | random 32-char string |
| `PYTHON_VERSION` | 3.11.0 |

### Step 4 — Deploy
Hit deploy. Panel goes live at your Render URL.

## Usage Flow
1. Login at `/` with admin credentials → Admin dashboard
2. Generate invite link (set account duration if limited)
3. Send link to client
4. Client registers → isolated panel
5. Client adds accounts, sets captcha key, starts farming
6. Admin can view all clients, disable/enable/delete them

## Captcha Keys
Each client sets their OWN keys in Settings. Admin has no captcha config — only clients do.
Supported services: 2Captcha, Anti-Captcha, CapMonster, NoPecha, JojoCaps

## Notes
- `data.json` stores all state (auto-created on first run)
- Each bot runs in its own daemon thread
- Accounts are fully isolated per client — no cross-visibility
- OWO bot ID hardcoded: `408785106942164992`
- Send OWO: sequential, 8-second gap between each account automatically
