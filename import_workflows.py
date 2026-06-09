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
    # List containers with port info so we can prefer the one bound to 5678
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=n8n", "--format", "{{.Names}}\t{{.Ports}}"],
        capture_output=True, text=True,
    )
    rows = [r.strip() for r in result.stdout.strip().splitlines() if r.strip()]
    if not rows:
        print("ERROR: No running n8n container found.")
        print("  Start it with:  docker-compose up -d")
        sys.exit(1)
    # Prefer the container that has 5678 exposed to the host
    for row in rows:
        parts = row.split("\t", 1)
        if len(parts) == 2 and "5678" in parts[1] and "0.0.0.0" in parts[1]:
            return parts[0]
    # Fallback: first container found
    return rows[0].split("\t")[0]


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

    # ensure_ascii=True so the payload stays pure ASCII — no emoji/Unicode issues
    # on Windows where subprocess text mode defaults to cp1252
    payload = json.dumps(data, ensure_ascii=True).encode("utf-8")
    dest    = f"/tmp/wf_{path.stem}.json"

    # Write JSON into the container and immediately import — no docker cp needed
    result = subprocess.run(
        ["docker", "exec", "-i", container, "sh", "-c",
         f"cat > {dest} && n8n import:workflow --input={dest} && rm -f {dest}"],
        input=payload,
        capture_output=True,
        # Use bytes mode (no text=True) to avoid Windows cp1252 encoding errors
    )

    if result.returncode == 0:
        return True, ""
    err = result.stderr or result.stdout or b"unknown error"
    return False, err.decode("utf-8", errors="replace").strip()


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
