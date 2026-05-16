"""
n8n workflow auto-importer — uses docker exec + n8n CLI (no API key needed).

How it works:
  1. Detects the running n8n container name automatically
  2. Copies n8n/workflows/*.json into the container via docker cp
  3. Runs: docker exec <container> n8n import:workflow --input=<file>
     for each workflow in dependency order

Usage:
  python import_workflows.py

Requirements:
  - Docker must be running
  - n8n container must be up:  docker-compose up -d
  - Run from the project root:  C:\\Users\\dheem\\Documents\\career-scout
"""

import subprocess
import sys
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
    """Find the running n8n container name."""
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


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def main() -> None:
    container = _container_name()
    print(f"Found n8n container: {container}\n")

    # Create a temp directory inside the container
    _run(["docker", "exec", container, "mkdir", "-p", "/tmp/cs_workflows"])

    # Build ordered file list
    all_files  = {f.stem: f for f in WORKFLOWS_DIR.glob("*.json")}
    ordered    = [all_files[n] for n in IMPORT_ORDER if n in all_files]
    remainder  = [f for stem, f in all_files.items() if stem not in IMPORT_ORDER]
    files      = ordered + remainder

    print(f"Importing {len(files)} workflows into container '{container}'...\n")

    ok = failed = 0
    for path in files:
        # Copy file into container
        dest = f"{container}:/tmp/cs_workflows/{path.name}"
        cp = _run(["docker", "cp", str(path), dest], check=False)
        if cp.returncode != 0:
            print(f"  FAILED  {path.stem}  (docker cp failed: {cp.stderr.strip()})")
            failed += 1
            continue

        # Import via n8n CLI
        imp = _run(
            ["docker", "exec", container,
             "n8n", "import:workflow",
             f"--input=/tmp/cs_workflows/{path.name}"],
            check=False,
        )
        if imp.returncode == 0:
            print(f"  OK      {path.stem}")
            ok += 1
        else:
            err = (imp.stderr or imp.stdout or "unknown error").strip()
            print(f"  FAILED  {path.stem}  ({err[:120]})")
            failed += 1

    # Cleanup temp dir
    _run(["docker", "exec", container, "rm", "-rf", "/tmp/cs_workflows"], check=False)

    print(f"\n{ok} imported, {failed} failed")

    if ok:
        print()
        print("Next steps:")
        print("  1. Open http://localhost:5678")
        print("  2. For each workflow: click Telegram / Gmail / Google Sheets")
        print("     nodes and select your saved credential")
        print("  3. Activate each workflow (toggle in top-right of workflow)")
        print()
        print("  telegram_bot: copy the webhook URL from the Telegram Trigger")
        print("  node, then register it with Telegram:")
        print("  https://api.telegram.org/bot<TOKEN>/setWebhook?url=<WEBHOOK_URL>")


if __name__ == "__main__":
    main()
