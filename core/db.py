import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Optional

import yaml

_config = None

def _load_config() -> dict:
    global _config
    if _config is None:
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        with open(cfg_path) as f:
            _config = yaml.safe_load(f)
    return _config

def db_path() -> str:
    return _load_config()["paths"]["db"]

def connect() -> sqlite3.Connection:
    path = db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            id             TEXT PRIMARY KEY,
            name           TEXT NOT NULL,
            careers_url    TEXT,
            linkedin_slug  TEXT,
            priority       INTEGER DEFAULT 1,
            active         INTEGER DEFAULT 1,
            blacklisted    INTEGER DEFAULT 0,
            jobs_this_week INTEGER DEFAULT 0,
            created_at     TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS roles (
            id         TEXT PRIMARY KEY,
            title      TEXT NOT NULL,
            keywords   TEXT,
            tags       TEXT,
            active     INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id               TEXT PRIMARY KEY,
            title            TEXT NOT NULL,
            company          TEXT NOT NULL,
            location         TEXT,
            url              TEXT,
            source_urls      TEXT,
            description      TEXT,
            source           TEXT,
            posted_date      TEXT,
            urgency          TEXT DEFAULT 'active',
            score            REAL DEFAULT -1,
            score_detail     TEXT,
            tags_matched     TEXT,
            status           TEXT DEFAULT 'new',
            outcome          TEXT DEFAULT 'pending',
            outcome_date     TEXT,
            rejection_reason TEXT,
            follow_up_due    TEXT,
            resume_path      TEXT,
            notes            TEXT,
            is_repost        INTEGER DEFAULT 0,
            original_job_id  TEXT,
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL,
            scored_at        TEXT
        );

        CREATE TABLE IF NOT EXISTS page_cache (
            url          TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            last_scraped TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS insights (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start              TEXT NOT NULL UNIQUE,
            missing_skills_json     TEXT,
            rejection_count         INTEGER DEFAULT 0,
            interview_count         INTEGER DEFAULT 0,
            offer_count             INTEGER DEFAULT 0,
            response_rate_by_source TEXT,
            llm_summary             TEXT,
            created_at              TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scraper_health (
            scraper              TEXT PRIMARY KEY,
            last_success         TEXT,
            consecutive_failures INTEGER DEFAULT 0,
            last_error           TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status   ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_score    ON jobs(score);
        CREATE INDEX IF NOT EXISTS idx_jobs_company  ON jobs(company);
        CREATE INDEX IF NOT EXISTS idx_jobs_urgency  ON jobs(urgency);
        CREATE INDEX IF NOT EXISTS idx_jobs_outcome  ON jobs(outcome);
        """)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Companies ────────────────────────────────────────────────────────────────

def upsert_company(company: dict) -> None:
    with connect() as conn:
        conn.execute("""
            INSERT INTO companies (id, name, careers_url, linkedin_slug, priority, active, created_at)
            VALUES (:id, :name, :careers_url, :linkedin_slug, :priority, :active, :created_at)
            ON CONFLICT(id) DO UPDATE SET
                name          = excluded.name,
                careers_url   = excluded.careers_url,
                linkedin_slug = excluded.linkedin_slug,
                priority      = excluded.priority,
                active        = excluded.active
        """, {
            "id": company["id"],
            "name": company["name"],
            "careers_url": company.get("careers_url", ""),
            "linkedin_slug": company.get("linkedin_slug", ""),
            "priority": company.get("priority", 1),
            "active": int(company.get("active", True)),
            "created_at": now_iso(),
        })

def get_active_companies() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM companies WHERE active=1 AND blacklisted=0 ORDER BY priority DESC"
        ).fetchall()
    return [dict(r) for r in rows]

def blacklist_company(name: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE companies SET blacklisted=1 WHERE LOWER(name)=LOWER(?)", (name,)
        )
    return cur.rowcount > 0


# ── Roles ─────────────────────────────────────────────────────────────────────

def upsert_role(role: dict) -> None:
    with connect() as conn:
        conn.execute("""
            INSERT INTO roles (id, title, keywords, tags, active, created_at)
            VALUES (:id, :title, :keywords, :tags, :active, :created_at)
            ON CONFLICT(id) DO UPDATE SET
                title    = excluded.title,
                keywords = excluded.keywords,
                tags     = excluded.tags,
                active   = excluded.active
        """, {
            "id": role["id"],
            "title": role["title"],
            "keywords": json.dumps(role.get("keywords", [])),
            "tags": json.dumps(role.get("tags", [])),
            "active": int(role.get("active", True)),
            "created_at": now_iso(),
        })

def get_active_roles() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM roles WHERE active=1").fetchall()
    return [dict(r) for r in rows]


# ── Jobs ──────────────────────────────────────────────────────────────────────

def job_exists(job_id: str) -> bool:
    with connect() as conn:
        row = conn.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone()
    return row is not None

def upsert_job(job: dict) -> None:
    ts = now_iso()
    with connect() as conn:
        conn.execute("""
            INSERT INTO jobs (
                id, title, company, location, url, source_urls, description,
                source, posted_date, urgency, score, score_detail, tags_matched,
                status, is_repost, original_job_id, created_at, updated_at
            ) VALUES (
                :id, :title, :company, :location, :url, :source_urls, :description,
                :source, :posted_date, :urgency, :score, :score_detail, :tags_matched,
                :status, :is_repost, :original_job_id, :created_at, :updated_at
            )
            ON CONFLICT(id) DO UPDATE SET
                source_urls  = excluded.source_urls,
                urgency      = excluded.urgency,
                updated_at   = excluded.updated_at
        """, {
            "id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "location": job.get("location", ""),
            "url": job.get("url", ""),
            "source_urls": json.dumps(job.get("source_urls", [job.get("url", "")])),
            "description": job.get("description", ""),
            "source": job.get("source", ""),
            "posted_date": job.get("posted_date", ""),
            "urgency": job.get("urgency", "active"),
            "score": job.get("score", -1),
            "score_detail": json.dumps(job.get("score_detail", {})),
            "tags_matched": json.dumps(job.get("tags_matched", [])),
            "status": job.get("status", "new"),
            "is_repost": int(job.get("is_repost", False)),
            "original_job_id": job.get("original_job_id"),
            "created_at": ts,
            "updated_at": ts,
        })

def get_job(job_id: str) -> Optional[dict]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None

def get_jobs(status: Optional[str] = None, min_score: float = 0.0,
             urgency: Optional[str] = None, limit: int = 100) -> list[dict]:
    query = "SELECT * FROM jobs WHERE score >= ?"
    params: list = [min_score]
    if status:
        query += " AND status=?"
        params.append(status)
    if urgency:
        query += " AND urgency=?"
        params.append(urgency)
    query += " ORDER BY score DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]

def update_job_status(job_id: str, status: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE jobs SET status=?, updated_at=? WHERE id=?",
            (status, now_iso(), job_id)
        )

def update_job_outcome(job_id: str, outcome: str,
                       rejection_reason: Optional[str] = None) -> None:
    with connect() as conn:
        conn.execute("""
            UPDATE jobs SET outcome=?, outcome_date=?, rejection_reason=?, updated_at=?
            WHERE id=?
        """, (outcome, now_iso(), rejection_reason, now_iso(), job_id))

def set_follow_up_due(job_id: str, due_iso: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE jobs SET follow_up_due=?, updated_at=? WHERE id=?",
            (due_iso, now_iso(), job_id)
        )

def update_job_score(job_id: str, score: float, score_detail: dict,
                     tags_matched: list) -> None:
    with connect() as conn:
        conn.execute("""
            UPDATE jobs SET score=?, score_detail=?, tags_matched=?,
                            scored_at=?, updated_at=?
            WHERE id=?
        """, (score, json.dumps(score_detail), json.dumps(tags_matched),
              now_iso(), now_iso(), job_id))

def set_resume_path(job_id: str, path: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE jobs SET resume_path=?, updated_at=? WHERE id=?",
            (path, now_iso(), job_id)
        )

def append_note(job_id: str, note: str) -> None:
    with connect() as conn:
        existing = conn.execute(
            "SELECT notes FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
        current = (existing["notes"] or "") if existing else ""
        updated = f"{current}\n[{now_iso()[:10]}] {note}".strip()
        conn.execute(
            "UPDATE jobs SET notes=?, updated_at=? WHERE id=?",
            (updated, now_iso(), job_id)
        )

def get_unscored_jobs() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE score=-1 AND status != 'expired'"
        ).fetchall()
    return [dict(r) for r in rows]

def mark_expired(job_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE jobs SET status='expired', updated_at=? WHERE id=?",
            (now_iso(), job_id)
        )


# ── Page cache ────────────────────────────────────────────────────────────────

def get_cached_hash(url: str) -> Optional[str]:
    with connect() as conn:
        row = conn.execute(
            "SELECT content_hash FROM page_cache WHERE url=?", (url,)
        ).fetchone()
    return row["content_hash"] if row else None

def set_cached_hash(url: str, content_hash: str) -> None:
    with connect() as conn:
        conn.execute("""
            INSERT INTO page_cache (url, content_hash, last_scraped)
            VALUES (?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                content_hash = excluded.content_hash,
                last_scraped = excluded.last_scraped
        """, (url, content_hash, now_iso()))


# ── Scraper health ────────────────────────────────────────────────────────────

def record_scraper_success(scraper: str) -> None:
    with connect() as conn:
        conn.execute("""
            INSERT INTO scraper_health (scraper, last_success, consecutive_failures)
            VALUES (?, ?, 0)
            ON CONFLICT(scraper) DO UPDATE SET
                last_success         = excluded.last_success,
                consecutive_failures = 0,
                last_error           = NULL
        """, (scraper, now_iso()))

def record_scraper_failure(scraper: str, error: str) -> int:
    with connect() as conn:
        conn.execute("""
            INSERT INTO scraper_health (scraper, consecutive_failures, last_error)
            VALUES (?, 1, ?)
            ON CONFLICT(scraper) DO UPDATE SET
                consecutive_failures = consecutive_failures + 1,
                last_error           = excluded.last_error
        """, (scraper, error))
        row = conn.execute(
            "SELECT consecutive_failures FROM scraper_health WHERE scraper=?",
            (scraper,)
        ).fetchone()
    return row["consecutive_failures"]

def get_scraper_health() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM scraper_health").fetchall()
    return [dict(r) for r in rows]


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    with connect() as conn:
        total   = conn.execute("SELECT COUNT(*) FROM jobs WHERE status != 'expired'").fetchone()[0]
        new     = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='new'").fetchone()[0]
        applied = conn.execute("SELECT COUNT(*) FROM jobs WHERE status='applied'").fetchone()[0]
        interviews = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE outcome='interview'"
        ).fetchone()[0]
        offers  = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE outcome='offer'"
        ).fetchone()[0]
        unscored = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE score=-1"
        ).fetchone()[0]
    return {
        "total": total, "new": new, "applied": applied,
        "interviews": interviews, "offers": offers, "unscored": unscored,
    }


# ── Insights ──────────────────────────────────────────────────────────────────

def upsert_insight(data: dict) -> None:
    """Insert or replace weekly insight row (keyed by week_start)."""
    with connect() as conn:
        conn.execute("""
            INSERT INTO insights (
                week_start, missing_skills_json, rejection_count,
                interview_count, offer_count, response_rate_by_source,
                llm_summary, created_at
            ) VALUES (
                :week_start, :missing_skills_json, :rejection_count,
                :interview_count, :offer_count, :response_rate_by_source,
                :llm_summary, :created_at
            )
            ON CONFLICT(week_start) DO UPDATE SET
                missing_skills_json     = excluded.missing_skills_json,
                rejection_count         = excluded.rejection_count,
                interview_count         = excluded.interview_count,
                offer_count             = excluded.offer_count,
                response_rate_by_source = excluded.response_rate_by_source,
                llm_summary             = excluded.llm_summary
        """, {
            "week_start": data["week_start"],
            "missing_skills_json": data.get("missing_skills_json", "{}"),
            "rejection_count": data.get("rejection_count", 0),
            "interview_count": data.get("interview_count", 0),
            "offer_count": data.get("offer_count", 0),
            "response_rate_by_source": data.get("response_rate_by_source", "{}"),
            "llm_summary": data.get("llm_summary", ""),
            "created_at": now_iso(),
        })


def flag_all_for_rescore() -> int:
    """
    Reset score to -1 for all active, non-expired jobs so score_pending()
    will re-evaluate them on the next scout run.
    Returns the number of jobs flagged.
    """
    with connect() as conn:
        cur = conn.execute(
            "UPDATE jobs SET score=-1, scored_at=NULL, updated_at=? "
            "WHERE status IN ('new') AND urgency != 'stale'",
            (now_iso(),)
        )
    return cur.rowcount


def get_jobs_for_auto_ghost() -> list[dict]:
    """
    Jobs that are applied+pending but follow_up_due was more than 7 days ago,
    meaning 14+ days have passed since the application with no outcome update.
    """
    with connect() as conn:
        rows = conn.execute("""
            SELECT * FROM jobs
            WHERE status = 'applied'
              AND outcome = 'pending'
              AND follow_up_due IS NOT NULL
              AND follow_up_due < datetime('now', '-7 days')
        """).fetchall()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    stats = get_stats()
    print(f"DB initialized at: {db_path()}")
    print(f"Jobs tracked: {stats['total']} total, {stats['new']} new, {stats['unscored']} unscored")
