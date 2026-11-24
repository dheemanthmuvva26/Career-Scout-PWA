"""Offline tests for forge/profile_edits.py."""

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from forge.fact_check import check_resume  # noqa: E402
from forge.profile_edits import apply_edits, validate_suggestion  # noqa: E402

MASTER = yaml.safe_load((ROOT / "forge" / "master_profile.yaml").read_text(encoding="utf-8"))
FDIP = "FDIP — Fertilizer Demand Intelligence Platform"
OLD = next(b["text"] for p in MASTER["projects"] if p["name"] == FDIP for b in p["bullets"]
           if b["text"].startswith("Halved") or "backtest" in b["text"])
DOC = "The improved method's error fell to 8.4% on the 2026 held-out month, across 18,100 dealers."


def _fdip(m):
    return next(p for p in m["projects"] if p["name"] == FDIP)


def test_replace_keeps_tags_and_is_idempotent():
    new = "Cut held-out backtest error to 8.4% across 18,100 dealers"
    edit = {"id": "e1", "kind": "project", "entry_name": FDIP, "old_text": OLD, "new_text": new}
    patched, status = apply_edits(MASTER, [edit])
    assert status[0]["status"] == "applied"
    texts = [b["text"] for b in _fdip(patched)["bullets"]]
    assert new in texts and OLD not in texts
    assert _fdip(patched)["bullets"][texts.index(new)]["tags"]  # tags carried over
    # Same edit again on the patched profile (e.g. after the YAML was synced) is a no-op.
    again, status2 = apply_edits(patched, [edit])
    assert status2[0]["status"] == "already-present"
    assert [b["text"] for b in _fdip(again)["bullets"]] == texts


def test_stale_and_unknown_entries_skipped():
    _, status = apply_edits(MASTER, [
        {"id": "a", "kind": "project", "entry_name": FDIP, "old_text": "no such bullet", "new_text": "x"},
        {"id": "b", "kind": "project", "entry_name": "Nonexistent", "old_text": None, "new_text": "x"},
    ])
    assert [s["status"] for s in status] == ["stale", "unknown-entry"]
    assert MASTER == yaml.safe_load((ROOT / "forge" / "master_profile.yaml").read_text(encoding="utf-8"))


def test_add_new_bullet():
    patched, status = apply_edits(MASTER, [{"id": "c", "kind": "project", "entry_name": FDIP,
                                            "old_text": None, "new_text": "Presented results to the department"}])
    assert status[0]["status"] == "applied"
    assert len(_fdip(patched)["bullets"]) == len(_fdip(MASTER)["bullets"]) + 1


def test_suggestion_numbers_must_come_from_document():
    ok = {"kind": "project", "entry_name": FDIP, "new_text": "Cut error to 8.4% across 18,100 dealers"}
    bad = {"kind": "project", "entry_name": FDIP, "new_text": "Cut error to 6.2% across 18,100 dealers"}
    assert validate_suggestion(ok, DOC, MASTER) is None
    assert "6.2%" in validate_suggestion(bad, DOC, MASTER)


def test_quote_check_ignores_markdown_and_already_covered_detected():
    from forge.profile_edits import _already_covered, _quote_found
    doc = "its error was cut from **19.1%** to **9.3%** — in **100% of the 1,000 trials**."
    assert _quote_found("its error was cut from 19.1% to 9.3%", doc)
    assert not _quote_found("error was cut from 25% to 9%", doc)
    dup = {"kind": "project", "entry_name": FDIP, "old_text": None,
           "new_text": "Reduced error from 19.1% to 9.3%, winning 100% of 1,000 resamples"}
    new = {**dup, "new_text": "Reduced error to 8.4% on the 2026 month"}
    assert _already_covered(dup, MASTER) and not _already_covered(new, MASTER)


def test_fact_checker_accepts_approved_numbers():
    new = "Cut held-out backtest error to 8.4% across 18,100 dealers"
    patched, _ = apply_edits(MASTER, [{"id": "e", "kind": "project", "entry_name": FDIP,
                                       "old_text": OLD, "new_text": new}])
    resume = {"selected_projects": [{"name": FDIP, "tech": [], "bullets": [new]}]}
    _, before = check_resume(resume, MASTER, mode="warn")
    _, after = check_resume(resume, patched, mode="warn")
    assert before["issues"] and not after["issues"]
