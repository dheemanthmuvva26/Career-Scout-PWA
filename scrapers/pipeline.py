"""
Scout pipeline — full run orchestration.

run_scout() is called by:
  - POST /scout  (FastAPI, triggered by n8n or /scout Telegram command)
  - CLI: python -m scrapers.pipeline

Flow per (company, role) pair:
  jobspy_scraper  → LinkedIn, Indeed, Glassdoor
  playwright_scraper → Naukri, Internshala
  static_scraper  → company careers page

Then per job:
  urgency.classify()  → urgency tier
  dedup.process()     → skip / merge / repost / insert
  db.upsert_job()     → write new records
  scorer.score_pending() → Groq score all unscored (batched at end)

Returns a summary dict consumed by api.py for Telegram notification.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

import yaml

from core import db, urgency, scorer
from scrapers import dedup, jobspy_scraper, playwright_scraper, static_scraper

logger = logging.getLogger(__name__)

_config: dict | None = None

def _cfg() -> dict:
    global _config
    if _config is None:
        cfg_path = Path(__file__).parent.parent / "config.yaml"
        with open(cfg_path) as f:
            _config = yaml.safe_load(f)
    return _config


# ── Company hiring signal ─────────────────────────────────────────────────────

def _increment_hiring_signal(company_name: str, count: int) -> None:
    """Bump jobs_this_week counter for a company by `count`."""
    with db.connect() as conn:
        conn.execute(
            "UPDATE companies SET jobs_this_week = jobs_this_week + ? WHERE LOWER(name)=LOWER(?)",
            (count, company_name)
        )


def _check_hiring_signals() -> list[str]:
    """Return company names that crossed the hiring-signal threshold this week."""
    alerts = []
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT name, jobs_this_week FROM companies WHERE jobs_this_week >= 5"
        ).fetchall()
    for row in rows:
        alerts.append(f"{row['name']} posted {row['jobs_this_week']} roles this week")
    return alerts


# ── Single-pair scrape ────────────────────────────────────────────────────────

def _scrape_pair(company: dict, role: dict) -> list[dict]:
    """Collect raw jobs from all sources for one (company, role) pair."""
    role_kw = []
    try:
        import json
        role_kw = json.loads(role.get("keywords") or "[]")
    except Exception:
        pass

    raw: list[dict] = []

    # 1. jobspy — LinkedIn / Indeed / Glassdoor
    try:
        raw += jobspy_scraper.scrape(company["name"], role["title"], role_kw)
    except Exception as e:
        logger.warning("jobspy failed for %s / %s: %s", company["name"], role["title"], e)

    # 2. Naukri
    try:
        naukri_jobs = playwright_scraper.scrape_naukri(role["title"], role_kw)
        # Filter to this company
        raw += [j for j in naukri_jobs
                if company["name"].lower() in j["company"].lower()]
    except Exception as e:
        logger.warning("Naukri failed for %s: %s", role["title"], e)

    # 3. Internshala (no company filter — it's fresher-focused, keep all)
    try:
        raw += playwright_scraper.scrape_internshala(role["title"], role_kw)
    except Exception as e:
        logger.warning("Internshala failed for %s: %s", role["title"], e)

    # 4. Static career page (company-specific)
    careers_url = company.get("careers_url", "")
    if careers_url:
        try:
            raw += static_scraper.scrape_careers_page(company["name"], careers_url, role_kw)
        except Exception as e:
            logger.warning("Static scraper failed for %s: %s", company["name"], e)

    return raw


# ── Ingest a single job ───────────────────────────────────────────────────────

def _ingest_job(job: dict) -> str:
    """
    Apply urgency, dedup, and DB upsert for one raw job dict.
    Returns dedup action string: insert | skip_exact | merge | repost
    """
    # Assign urgency tier
    job["urgency"] = urgency.classify(job.get("posted_date"))

    # Run dedup (also mutates job["id"], job["is_repost"], job["original_job_id"])
    result = dedup.process(job)

    if result.action == "insert":
        db.upsert_job(job)
    elif result.action == "repost":
        db.upsert_job(job)   # stored as new record with is_repost=1
    # merge / skip_exact → already handled inside dedup.process()

    return result.action


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_scout() -> dict:
    """
    Full scout pipeline. Returns summary dict.
    Thread-safe: each call opens its own DB connections.
    """
    cfg = _cfg()
    db.init_db()

    companies = db.get_active_companies()
    roles     = db.get_active_roles()

    if not companies or not roles:
        logger.warning("Scout: no active companies or roles — nothing to do")
        return {"error": "no active companies or roles"}

    counters = {
        "pairs_checked": 0,
        "raw_scraped":   0,
        "inserted":      0,
        "merged":        0,
        "reposts":       0,
        "skipped":       0,
    }

    alert_threshold = cfg.get("scraping", {}).get("health_alert_threshold", 3)

    for company in companies:
        company_new_jobs = 0

        for role in roles:
            counters["pairs_checked"] += 1
            raw = _scrape_pair(company, role)
            counters["raw_scraped"] += len(raw)

            for job in raw:
                try:
                    action = _ingest_job(job)
                    if action == "insert":
                        counters["inserted"] += 1
                        company_new_jobs += 1
                    elif action == "merge":
                        counters["merged"] += 1
                    elif action == "repost":
                        counters["reposts"] += 1
                        company_new_jobs += 1
                    else:
                        counters["skipped"] += 1
                except Exception as e:
                    logger.error("Ingest failed for job %s: %s",
                                 job.get("title", "?"), e)

        # Increment hiring signal
        if company_new_jobs > 0:
            _increment_hiring_signal(company["name"], company_new_jobs)

    # Score all new unscored jobs in one batched pass
    score_summary = scorer.score_pending(batch_size=100)

    # Check hiring signals
    hiring_alerts = _check_hiring_signals()

    # Check scraper health — flag busted scrapers
    health_alerts = []
    for row in db.get_scraper_health():
        if row["consecutive_failures"] >= alert_threshold:
            health_alerts.append(
                f"{row['scraper']} failed {row['consecutive_failures']}× "
                f"(last: {row['last_error'] or 'unknown'})"
            )

    summary = {
        "ran_at":         datetime.now(timezone.utc).isoformat(),
        "pairs_checked":  counters["pairs_checked"],
        "raw_scraped":    counters["raw_scraped"],
        "inserted":       counters["inserted"],
        "merged":         counters["merged"],
        "reposts":        counters["reposts"],
        "skipped":        counters["skipped"],
        "scored":         score_summary["scored"],
        "score_failed":   score_summary["failed"],
        "hiring_alerts":  hiring_alerts,
        "health_alerts":  health_alerts,
    }
    logger.info("Scout complete: %s", summary)
    return summary


# ── Telegram message builder ──────────────────────────────────────────────────

def format_new_jobs_alert(min_score: float = 3.5) -> str:
    """
    Build a Telegram message for newly scored jobs above min_score
    that are hot or active urgency.
    """
    jobs = db.get_jobs(status="new", min_score=min_score, limit=10)
    jobs = [j for j in jobs if j.get("urgency") in ("hot", "active")]

    if not jobs:
        return ""

    import json
    lines = ["🆕 *New job matches:*\n"]
    for j in jobs:
        badge = "🔴" if j.get("urgency") == "hot" else "🟡"
        score = j.get("score", 0)
        try:
            detail = json.loads(j.get("score_detail") or "{}")
            summary = detail.get("fit_summary", "")
        except Exception:
            summary = ""

        lines.append(
            f"{badge} *{j['title']}* @ {j['company']}\n"
            f"   ⭐ {score:.1f}  📍 {j.get('location', '?')}\n"
            f"   {summary}\n"
            f"   ID: `{j['id']}`\n"
        )

    return "\n".join(lines)


# ── CLI entry ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    summary = run_scout()
    print("\n=== Scout Summary ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    alert = format_new_jobs_alert()
    if alert:
        print("\n=== Telegram Alert Preview ===")
        print(alert)
    sys.exit(0)
