"""
n8n workflow auto-importer — pipes JSON directly into the container via stdin.
No temp files, no docker cp path issues.

Usage (from project root):
  python import_workflows.py

Requirements:
  - Docker must be running
  - n8n container must be up:  docker-compose up -d
"""

import json
import subprocess
import sys
import uuid
from pathlib import Path

WORKFLOWS_DIR = Path("n8n/workflows")

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


def _container_name() -> str:
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=n8n", "--format", "{{.Names}}"],
        capture_output=True, text=True,
    )
    names = [n.strip() for n in result.stdout.strip().splitlines() if n.strip()]
    if not names:
        print("ERROR: No running n8n container found.")
        print("  Start it with:  docker-compose up -d")
        sys.exit(1)
    return names[0]


def _import_one(container: str, path: Path) -> tuple[bool, str]:
    """
    Pipe workflow JSON into the container via stdin, write to a temp file
    inside the container, then import it with n8n CLI.
    Returns (success, message).
    """
    data = json.loads(path.read_text(encoding="utf-8"))

    # n8n v2+ requires both fields as non-null UUIDs.
    # Fresh UUIDs on every run avoid UNIQUE constraint violations.
    data["id"]        = str(uuid.uuid4())
    data["versionId"] = str(uuid.uuid4())
    for field in ("meta", "pinData", "tags"):
        data.pop(field, None)

    payload = json.dumps(data, ensure_ascii=False)
    dest    = f"/tmp/wf_{path.stem}.json"

    # Write JSON into the container and immediately import — no docker cp needed
    result = subprocess.run(
        ["docker", "exec", "-i", container, "sh", "-c",
         f"cat > {dest} && n8n import:workflow --input={dest} && rm -f {dest}"],
        input=payload,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        return True, ""
    return False, (result.stderr or result.stdout or "unknown error").strip()


def main() -> None:
    container = _container_name()
    print(f"Found n8n container: {container}\n")

    all_files = {f.stem: f for f in WORKFLOWS_DIR.glob("*.json")}
    ordered   = [all_files[n] for n in IMPORT_ORDER if n in all_files]
    remainder = [f for stem, f in all_files.items() if stem not in IMPORT_ORDER]
    files     = ordered + remainder

    print(f"Importing {len(files)} workflows...\n")

    ok = failed = 0
    for path in files:
        success, err = _import_one(container, path)
        if success:
            print(f"  OK      {path.stem}")
            ok += 1
        else:
            print(f"  FAILED  {path.stem}")
            print(f"          {err}")
            failed += 1

    print(f"\n{ok} imported, {failed} failed")

    if ok:
        print()
        print("Next steps:")
        print("  1. Open http://localhost:5678")
        print("  2. In each workflow: click Telegram / Gmail / Google Sheets nodes")
        print("     and select your saved credential")
        print("  3. Activate each workflow (toggle top-right inside the workflow)")
        print()
        print("  telegram_bot: copy the Webhook URL from the Telegram Trigger node,")
        print("  then register it with Telegram:")
        print("  https://api.telegram.org/bot<TOKEN>/setWebhook?url=<WEBHOOK_URL>")


if __name__ == "__main__":
    main()
