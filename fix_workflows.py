"""
One-shot fixer for n8n workflow JSONs.
Makes them importable by:
  1. Adding required top-level fields (versionId, meta, pinData, tags)
  2. Replacing short node IDs with proper UUIDs
  3. Rounding float typeVersion values to integers (e.g. 4.2 -> 4, 1.1 -> 1)
  4. Setting active: false so n8n doesn't auto-enable on import

Connections reference node *names*, not IDs, so they need no changes.
"""

import json
import uuid
from pathlib import Path

WORKFLOWS_DIR = Path("n8n/workflows")

def fix_workflow(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))

    # ── Top-level required fields ──────────────────────────────────────────────
    data.setdefault("versionId", str(uuid.uuid4()))
    data.setdefault("meta", {"instanceId": "career-scout"})
    data.setdefault("pinData", {})
    data.setdefault("tags", [])
    data["active"] = False          # always import inactive; user enables manually

    # ── Fix nodes ─────────────────────────────────────────────────────────────
    for node in data.get("nodes", []):
        # Replace short IDs with UUIDs
        current_id = node.get("id", "")
        if not _is_uuid(current_id):
            node["id"] = str(uuid.uuid4())

        # Round float typeVersion to int (4.2 → 4, 1.1 → 1)
        tv = node.get("typeVersion")
        if isinstance(tv, float):
            node["typeVersion"] = int(tv)

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  OK {path.name}")


def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(str(s))
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    files = sorted(WORKFLOWS_DIR.glob("*.json"))
    print(f"Fixing {len(files)} workflow files…")
    for f in files:
        fix_workflow(f)
    print("Done.")
