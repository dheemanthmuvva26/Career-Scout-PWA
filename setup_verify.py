"""
Run this after completing all manual setup steps.
Verifies every dependency and connection is ready before Phase 1.

Usage:
    python setup_verify.py
"""

import sys
import os
import subprocess

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m!\033[0m"

results = []

def check(label: str, ok: bool, hint: str = "") -> None:
    icon = PASS if ok else FAIL
    print(f"  {icon}  {label}")
    if not ok and hint:
        print(f"      → {hint}")
    results.append(ok)


print("\n── Python packages ──────────────────────────────────────────")

try:
    import jobspy
    check("python-jobspy", True)
except ImportError:
    check("python-jobspy", False, "pip install python-jobspy")

try:
    import playwright
    check("playwright (package)", True)
except ImportError:
    check("playwright (package)", False, "pip install playwright")

try:
    import bs4
    check("beautifulsoup4", True)
except ImportError:
    check("beautifulsoup4", False, "pip install beautifulsoup4")

try:
    import requests
    check("requests", True)
except ImportError:
    check("requests", False, "pip install requests")

try:
    import rapidfuzz
    check("rapidfuzz", True)
except ImportError:
    check("rapidfuzz", False, "pip install rapidfuzz")

try:
    import groq
    check("groq", True)
except ImportError:
    check("groq", False, "pip install groq")

try:
    import streamlit
    check("streamlit", True)
except ImportError:
    check("streamlit", False, "pip install streamlit")

try:
    import yaml
    check("pyyaml", True)
except ImportError:
    check("pyyaml", False, "pip install pyyaml")

try:
    import dotenv
    check("python-dotenv", True)
except ImportError:
    check("python-dotenv", False, "pip install python-dotenv")

try:
    import fastapi
    import uvicorn
    check("fastapi + uvicorn", True)
except ImportError:
    check("fastapi + uvicorn", False, "pip install fastapi uvicorn[standard]")


print("\n── Playwright Chromium ──────────────────────────────────────")
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        browser.close()
    check("Playwright Chromium browser", True)
except Exception as e:
    check("Playwright Chromium browser", False,
          "playwright install chromium")


print("\n── Typst ────────────────────────────────────────────────────")
try:
    result = subprocess.run(["typst", "--version"], capture_output=True, text=True)
    ok = result.returncode == 0
    check(f"Typst ({result.stdout.strip()})", ok)
except FileNotFoundError:
    check("Typst binary", False, "winget install Typst.Typst  (then restart terminal)")


print("\n── Environment variables ────────────────────────────────────")
from dotenv import load_dotenv
load_dotenv()

groq_key = os.getenv("GROQ_API_KEY", "")
check("GROQ_API_KEY set", bool(groq_key),
      "Add to .env: GROQ_API_KEY=your_key  (get from console.groq.com)")

tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
check("TELEGRAM_BOT_TOKEN set", bool(tg_token),
      "Add to .env: TELEGRAM_BOT_TOKEN=your_token  (get from @BotFather)")

tg_chat = os.getenv("TELEGRAM_CHAT_ID", "")
check("TELEGRAM_CHAT_ID set", bool(tg_chat),
      "Add to .env: TELEGRAM_CHAT_ID=your_id  (get from @userinfobot)")


print("\n── Groq API connection ──────────────────────────────────────")
if groq_key:
    from groq import Groq
    client = Groq(api_key=groq_key)

    # Test scoring model
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Reply with the single word: ready"}],
            max_tokens=5,
        )
        reply = resp.choices[0].message.content.strip().lower()
        check(f"Groq scoring model (llama-3.3-70b-versatile) → '{reply}'", True)
    except Exception as e:
        check("Groq scoring model (llama-3.3-70b-versatile)", False, str(e))

    # Test writing model
    try:
        resp = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": "Reply with the single word: ready"}],
            max_tokens=5,
        )
        reply = resp.choices[0].message.content.strip().lower()
        check(f"Groq writing model (gpt-oss-120b) → '{reply}'", True)
    except Exception as e:
        check("Groq writing model (gpt-oss-120b)", False, str(e))
else:
    print(f"  {WARN}  Groq API — skipped (no key set)")


print("\n── SQLite schema ────────────────────────────────────────────")
try:
    from core.db import init_db, get_stats
    init_db()
    stats = get_stats()
    check(f"SQLite DB initialized ({stats['total']} jobs tracked)", True)
except Exception as e:
    check("SQLite DB init", False, str(e))


print("\n── Python API server ────────────────────────────────────────")
try:
    import urllib.request
    urllib.request.urlopen("http://localhost:8000/health", timeout=3)
    check("Python API server at localhost:8000", True)
except Exception:
    check("Python API server at localhost:8000", False,
          "Run in a separate terminal: python api.py")

print("\n── n8n (Docker) ─────────────────────────────────────────────")
try:
    import urllib.request
    urllib.request.urlopen("http://localhost:5678/healthz", timeout=3)
    check("n8n running at localhost:5678", True)
except Exception:
    check("n8n running at localhost:5678", False,
          "Run: docker compose up -d")


print("\n── config.yaml ──────────────────────────────────────────────")
try:
    import yaml
    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)
    sheet_id = cfg.get("sheets", {}).get("spreadsheet_id", "")
    check("config.yaml loads", True)
    if not sheet_id:
        print(f"  {WARN}  sheets.spreadsheet_id is empty — fill in after creating your Google Sheet")
    else:
        check(f"Google Sheet ID set ({sheet_id[:12]}...)", True)
except Exception as e:
    check("config.yaml loads", False, str(e))


print()
passed = sum(results)
total  = len(results)
if passed == total:
    print(f"\033[92m All {total} checks passed — Phase 0 complete. Ready for Phase 1.\033[0m\n")
else:
    failed = total - passed
    print(f"\033[93m {passed}/{total} checks passed. Fix the {failed} issue(s) above, then re-run.\033[0m\n")
