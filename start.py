"""
Career Scout — one-command startup
Starts: Docker/n8n  |  ngrok tunnel  |  FastAPI  |  Telegram webhook

Usage:
    python start.py

Run this every time you boot your PC before using Career Scout.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── Load env ──────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID", "")
N8N_KEY    = os.getenv("N8N_API_KEY", "")
N8N_API    = "http://localhost:5678/api/v1"
ROOT       = Path(__file__).parent
DC_FILE    = ROOT / "docker-compose.yml"
LOG_FILE   = ROOT / "shared" / "api.log"

# ── Helpers ───────────────────────────────────────────────────────────────────

def step(msg):
    print(f"\n[+] {msg}")

def ok(msg):
    print(f"    OK  {msg}")

def warn(msg):
    print(f"    !!  {msg}")

def fail(msg):
    print(f"    ERR {msg}")
    sys.exit(1)

def n8n(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(
        f"{N8N_API}{path}", data=data,
        headers={"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception:
        return {}

def tg(endpoint, **kwargs):
    data = json.dumps(kwargs).encode()
    req  = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/{endpoint}",
        data=data, headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ── Step 1: Docker / n8n ──────────────────────────────────────────────────────
step("Starting n8n (Docker)...")

docker_check = subprocess.run(
    ["docker", "ps", "--filter", "name=career-scout-n8n-1", "--format", "{{.Names}}"],
    capture_output=True, text=True,
)
if "career-scout-n8n-1" in docker_check.stdout:
    ok("n8n container already running")
else:
    result = subprocess.run(["docker-compose", "up", "-d"], cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        fail(f"docker-compose failed:\n{result.stderr}")
    ok("n8n container started")

# ── Step 2: ngrok ─────────────────────────────────────────────────────────────
step("Starting ngrok tunnel (port 5678)...")

# Kill any existing ngrok so we get a fresh URL
subprocess.run(["taskkill", "/f", "/im", "ngrok.exe"], capture_output=True)
time.sleep(1)

subprocess.Popen(
    ["ngrok", "http", "5678"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
)

ngrok_url = None
for attempt in range(10):
    time.sleep(2)
    try:
        with urllib.request.urlopen("http://localhost:4040/api/tunnels", timeout=3) as r:
            tunnels = json.loads(r.read()).get("tunnels", [])
        for t in tunnels:
            if t["proto"] == "https":
                ngrok_url = t["public_url"].rstrip("/")
                break
        if ngrok_url:
            break
    except Exception:
        pass

if not ngrok_url:
    fail("Could not get ngrok public URL. Is ngrok installed?")
ok(f"ngrok: {ngrok_url}")

# ── Step 3: Update docker-compose WEBHOOK_URL if changed ──────────────────────
step("Syncing WEBHOOK_URL in docker-compose.yml...")

dc_content = DC_FILE.read_text(encoding="utf-8")
new_webhook_line    = f"      - WEBHOOK_URL={ngrok_url}/"
new_editor_line     = f"      - N8N_EDITOR_BASE_URL={ngrok_url}/"
webhook_pattern     = r"      - WEBHOOK_URL=https?://[^\n]+"
editor_pattern      = r"      - N8N_EDITOR_BASE_URL=https?://[^\n]+"

needs_restart = False

current_webhook = re.search(webhook_pattern, dc_content)
if current_webhook and current_webhook.group() != new_webhook_line:
    dc_content    = re.sub(webhook_pattern, new_webhook_line, dc_content)
    dc_content    = re.sub(editor_pattern,  new_editor_line,  dc_content)
    DC_FILE.write_text(dc_content, encoding="utf-8")
    needs_restart = True
    ok("WEBHOOK_URL updated — will restart n8n")
else:
    ok("WEBHOOK_URL already matches, no restart needed")

if needs_restart:
    subprocess.run(["docker-compose", "down"], cwd=ROOT, capture_output=True)
    result = subprocess.run(["docker-compose", "up", "-d"], cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        fail(f"docker-compose restart failed:\n{result.stderr}")
    ok("n8n restarted with new WEBHOOK_URL")

# ── Step 4: Wait for n8n API ──────────────────────────────────────────────────
step("Waiting for n8n to be ready...")

for attempt in range(24):          # up to ~72 seconds
    wfs = n8n("GET", "/workflows")
    if wfs.get("data") is not None:
        ok(f"n8n API ready ({len(wfs['data'])} workflows)")
        break
    print(f"    ... waiting ({attempt + 1})", end="\r")
    time.sleep(3)
else:
    fail("n8n API did not become ready in time. Check Docker logs.")

# ── Step 5: FastAPI server ─────────────────────────────────────────────────────
step("Starting FastAPI server (port 8000)...")

api_running = False
try:
    with urllib.request.urlopen("http://localhost:8000/health", timeout=2) as r:
        api_running = json.loads(r.read()).get("status") == "ok"
except Exception:
    pass

if api_running:
    ok("FastAPI already running")
else:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api:app",
         "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"],
        stdout=open(LOG_FILE, "w"), stderr=subprocess.STDOUT,
        cwd=ROOT,
    )
    for attempt in range(10):
        time.sleep(2)
        try:
            with urllib.request.urlopen("http://localhost:8000/health", timeout=2) as r:
                if json.loads(r.read()).get("status") == "ok":
                    ok("FastAPI started")
                    api_running = True
                    break
        except Exception:
            pass
    if not api_running:
        warn("FastAPI did not start cleanly — check shared/api.log")

# ── Step 6: Register Telegram webhook ─────────────────────────────────────────
# Uses a fixed path (plain Webhook node — more reliable than telegramTrigger)
TELEGRAM_WEBHOOK_PATH = "career-scout-telegram"

step("Registering Telegram webhook...")
webhook_url = f"{ngrok_url}/webhook/{TELEGRAM_WEBHOOK_PATH}"
result = tg("setWebhook", url=webhook_url)
if result.get("ok"):
    ok(f"Webhook set: {webhook_url}")
else:
    warn(f"setWebhook failed: {result}")

# Verify path is live in n8n
try:
    req = urllib.request.Request(
        f"http://localhost:5678/webhook/{TELEGRAM_WEBHOOK_PATH}",
        data=b"{}", headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        ok(f"n8n webhook path responding (HTTP {r.status})")
except urllib.error.HTTPError as e:
    if e.code == 404:
        warn("n8n webhook path 404 — telegram_bot workflow may need reactivation")
    else:
        ok(f"n8n webhook path HTTP {e.code}")

# ── Step 8: Activate any inactive workflows ────────────────────────────────────
step("Activating workflows...")

all_wfs = n8n("GET", "/workflows").get("data", [])
all_active = True
for wf in all_wfs:
    if not wf["active"]:
        r = n8n("POST", f'/workflows/{wf["id"]}/activate')
        status = "ACTIVE" if r.get("active") else "FAILED"
        if not r.get("active"):
            all_active = False
        print(f"    {wf['name']:30s} {status}")

if all_active:
    ok("All 8 workflows already active")

# ── Step 9: Final summary ──────────────────────────────────────────────────────
print()
print("=" * 55)
print("  Career Scout is LIVE")
print("=" * 55)
print(f"  n8n dashboard : http://localhost:5678")
print(f"  API server    : http://localhost:8000/docs")
print(f"  ngrok tunnel  : {ngrok_url}")
print(f"  Telegram bot  : ready — try /stats or /jobs")
print("=" * 55)

# Send startup notification to Telegram
tg("sendMessage",
   chat_id=CHAT_ID,
   text="Career Scout started. Try /stats or /jobs",
)
