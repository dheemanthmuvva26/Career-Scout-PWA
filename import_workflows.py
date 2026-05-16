"""
n8n workflow auto-importer.

Reads every JSON in n8n/workflows/ and upserts it via the n8n REST API.
  - New workflow  -> POST  /api/v1/workflows
  - Already exists by name -> PUT /api/v1/workflows/{id}  (overwrites)

Setup (one-time):
  1. Open http://localhost:5678
  2. Top-right avatar -> Settings -> API -> Create an API key
  3. Copy the key and add to .env:  N8N_API_KEY=n8n_api_...
  4. Run:  python import_workflows.py

n8n must be running (docker-compose up -d) before you run this.
"""

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

N8N_URL       = os.getenv("N8N_URL", "http://localhost:5678")
API_KEY       = os.getenv("N8N_API_KEY", "")
WORKFLOWS_DIR = Path("n8n/workflows")

# Import in a sensible order: seed data first, then pipelines, then bots
IMPORT_ORDER = [
    "sync_sheets",
    "scout",
    "morning_digest",
    "db_backup",
    "followup",
    "telegram_bot",
    "weekly_insights",
    "gmail_monitor",
]


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"X-N8N-API-KEY": API_KEY, "Content-Type": "application/json"})
    return s


def _existing(s: requests.Session) -> dict[str, str]:
    """Return {workflow_name: workflow_id} for every workflow already in n8n."""
    r = s.get(f"{N8N_URL}/api/v1/workflows", params={"limit": 250})
    r.raise_for_status()
    return {w["name"]: w["id"] for w in r.json().get("data", [])}


def _upsert(s: requests.Session, path: Path, existing: dict[str, str]) -> tuple[str, str]:
    """
    Import one workflow file. Returns (action, workflow_id).
    action is 'created' or 'updated'.
    """
    data = json.loads(path.read_text(encoding="utf-8"))

    # Strip top-level 'id' so n8n assigns its own on creation
    data.pop("id", None)

    name = data.get("name", path.stem)

    if name in existing:
        wf_id = existing[name]
        r = s.put(f"{N8N_URL}/api/v1/workflows/{wf_id}", json=data)
        r.raise_for_status()
        return "updated", wf_id
    else:
        r = s.post(f"{N8N_URL}/api/v1/workflows", json=data)
        r.raise_for_status()
        wf_id = r.json().get("id", "?")
        return "created", wf_id


def main() -> None:
    # ── Pre-flight checks ──────────────────────────────────────────────────────
    if not API_KEY:
        print("ERROR: N8N_API_KEY is not set.")
        print()
        print("  1. Open http://localhost:5678")
        print("  2. Top-right avatar -> Settings -> API -> Create an API key")
        print("  3. Add to .env:  N8N_API_KEY=n8n_api_xxxxx")
        print("  4. Re-run this script.")
        sys.exit(1)

    s = _session()
    try:
        s.get(f"{N8N_URL}/api/v1/workflows", params={"limit": 1}).raise_for_status()
    except Exception as e:
        print(f"ERROR: Cannot reach n8n at {N8N_URL}")
        print(f"  Make sure it is running:  docker-compose up -d")
        print(f"  Details: {e}")
        sys.exit(1)

    existing = _existing(s)

    # ── Build ordered file list ────────────────────────────────────────────────
    all_files = {f.stem: f for f in WORKFLOWS_DIR.glob("*.json")}
    ordered   = [all_files[name] for name in IMPORT_ORDER if name in all_files]
    remainder = [f for stem, f in all_files.items() if stem not in IMPORT_ORDER]
    files     = ordered + remainder

    print(f"Importing {len(files)} workflows into {N8N_URL}\n")

    ok = failed = 0
    for path in files:
        try:
            action, wf_id = _upsert(s, path, existing)
            tag = "NEW    " if action == "created" else "UPDATED"
            print(f"  {tag}  {path.stem}  (id: {wf_id})")
            ok += 1
        except requests.HTTPError as e:
            body = ""
            try: body = e.response.json()
            except Exception: pass
            print(f"  FAILED  {path.stem}:  HTTP {e.response.status_code}  {body}")
            failed += 1
        except Exception as e:
            print(f"  FAILED  {path.stem}:  {e}")
            failed += 1

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{ok} imported, {failed} failed")

    if ok:
        print()
        print("Next steps:")
        print("  1. Open http://localhost:5678")
        print("  2. For each workflow that uses Telegram/Gmail/Google Sheets:")
        print("     click the node -> select your saved credential")
        print("  3. Activate the workflows (toggle top-right in each workflow)")
        print()
        print("  telegram_bot: also copy the webhook URL from the Telegram Trigger")
        print("  node and register it with Telegram:")
        print("  https://api.telegram.org/bot<TOKEN>/setWebhook?url=<WEBHOOK_URL>")


if __name__ == "__main__":
    main()
