"""
Deduplication for job postings.

Three layers:
1. Exact dedup      — sha256(title + company + url) → same DB id, skip insert
2. Cross-portal     — rapidfuzz ratio on normalize(title+company) ≥ 90 →
                      merge source_urls into existing record, skip new insert
3. Repost detection — same normalize(title+company) seen 30+ days later →
                      is_repost=1, original_job_id = first record's id
"""

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from rapidfuzz import fuzz

from core import db


# ── Normalisation ─────────────────────────────────────────────────────────────

_STRIP = re.compile(r"[^a-z0-9 ]")

def normalize(text: str) -> str:
    """Lowercase, strip punctuation/symbols, collapse whitespace."""
    text = text.lower()
    text = _STRIP.sub(" ", text)
    return " ".join(text.split())


def job_id(title: str, company: str, url: str) -> str:
    """Canonical sha256 ID: first 16 hex chars of sha256(title+company+url)."""
    raw = f"{normalize(title)}|{normalize(company)}|{(url or '').strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _fuzzy_key(title: str, company: str) -> str:
    return normalize(title) + " " + normalize(company)


# ── Cross-portal fuzzy lookup ─────────────────────────────────────────────────

def _find_fuzzy_match(title: str, company: str,
                      conn: sqlite3.Connection) -> Optional[dict]:
    """
    Search existing jobs for a close enough match (ratio ≥ 90).
    Only checks jobs created in the last 30 days to keep the scan fast.
    Returns the first matching job row or None.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    rows = conn.execute(
        "SELECT id, title, company, source_urls FROM jobs WHERE created_at >= ?",
        (cutoff,)
    ).fetchall()

    needle = _fuzzy_key(title, company)
    for row in rows:
        candidate = _fuzzy_key(row["title"], row["company"])
        if fuzz.ratio(needle, candidate) >= 90:
            return dict(row)
    return None


def _merge_source_urls(existing_json: str, new_url: str) -> str:
    try:
        urls: list = json.loads(existing_json or "[]")
    except Exception:
        urls = []
    if new_url and new_url not in urls:
        urls.append(new_url)
    return json.dumps(urls)


# ── Repost detection ──────────────────────────────────────────────────────────

def _find_original(title: str, company: str,
                   conn: sqlite3.Connection) -> Optional[dict]:
    """
    Look for the oldest job with the same normalized title+company that was
    created more than repost_window_days ago.
    """
    import yaml
    cfg_path = Path(__file__).parent.parent / "config.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    window_days = cfg.get("repost", {}).get("window_days", 30)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
    # Jobs created BEFORE the cutoff = potential originals
    rows = conn.execute(
        "SELECT id, title, company, created_at FROM jobs WHERE created_at < ?",
        (cutoff,)
    ).fetchall()

    needle = _fuzzy_key(title, company)
    for row in rows:
        candidate = _fuzzy_key(row["title"], row["company"])
        if fuzz.ratio(needle, candidate) >= 90:
            return dict(row)
    return None


# ── Public API ────────────────────────────────────────────────────────────────

class DeduplicationResult:
    __slots__ = ("action", "job_id", "original_id")

    def __init__(self, action: str, job_id: str, original_id: Optional[str] = None):
        self.action      = action       # "insert" | "skip_exact" | "merge" | "repost"
        self.job_id      = job_id
        self.original_id = original_id


def process(job: dict) -> DeduplicationResult:
    """
    Run all three dedup layers against the live DB.
    Mutates `job` dict in-place (sets is_repost, original_job_id) before
    the caller calls db.upsert_job().

    Returns a DeduplicationResult describing what happened.
    """
    jid = job_id(job["title"], job["company"], job.get("url", ""))
    job["id"] = jid

    with db.connect() as conn:
        # ── Layer 1: exact match ──────────────────────────────────────────────
        existing = conn.execute(
            "SELECT id, source_urls FROM jobs WHERE id=?", (jid,)
        ).fetchone()
        if existing:
            return DeduplicationResult("skip_exact", jid)

        # ── Layer 2: cross-portal fuzzy merge ─────────────────────────────────
        fuzzy_match = _find_fuzzy_match(job["title"], job["company"], conn)
        if fuzzy_match:
            merged_urls = _merge_source_urls(
                fuzzy_match["source_urls"], job.get("url", "")
            )
            conn.execute(
                "UPDATE jobs SET source_urls=?, updated_at=? WHERE id=?",
                (merged_urls, db.now_iso(), fuzzy_match["id"])
            )
            return DeduplicationResult("merge", fuzzy_match["id"])

        # ── Layer 3: repost detection ─────────────────────────────────────────
        original = _find_original(job["title"], job["company"], conn)
        if original:
            job["is_repost"]      = True
            job["original_job_id"] = original["id"]
            return DeduplicationResult("repost", jid, original["id"])

    return DeduplicationResult("insert", jid)
