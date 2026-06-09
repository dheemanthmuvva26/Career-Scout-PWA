"""
Career Scout — Python API Server
Runs on host machine at http://localhost:8000
n8n (Docker) calls this via HTTP Request nodes using host.docker.internal:8000

Start: python api.py  (or: uvicorn api:app --reload --port 8000)
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

from core.db import (
    init_db, get_stats, get_jobs, get_job,
    update_job_status, update_job_outcome,
    set_follow_up_due, append_note, blacklist_company,
    get_scraper_health, get_unscored_jobs,
    get_active_companies, get_active_roles,
    upsert_company, upsert_role,
    get_jobs_for_auto_ghost,
)

app = FastAPI(title="Career Scout API", version="1.0.0")

# Initialise DB on startup
@app.on_event("startup")
def startup():
    init_db()
    print("DB initialised")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/stats")
def stats():
    return get_stats()


# ── Jobs ──────────────────────────────────────────────────────────────────────

@app.get("/jobs")
def list_jobs(
    status: Optional[str] = None,
    min_score: float = 0.0,
    urgency: Optional[str] = None,
    limit: int = 50,
):
    return get_jobs(status=status, min_score=min_score, urgency=urgency, limit=limit)


@app.get("/jobs/digest")
def digest(limit: int = 5):
    """Today's top jobs: score ≥ min_score, urgency hot or active, sorted by score."""
    import yaml
    from pathlib import Path
    cfg = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())
    min_score = cfg.get("min_score", 3.5)

    hot    = get_jobs(min_score=min_score, urgency="hot",    limit=limit)
    active = get_jobs(min_score=min_score, urgency="active", limit=limit)
    combined = {j["id"]: j for j in hot + active}
    return sorted(combined.values(), key=lambda j: j["score"], reverse=True)[:limit]


@app.get("/jobs/{job_id}")
def job_detail(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


class StatusUpdate(BaseModel):
    status: str   # new | reviewed | applied | rejected | expired

@app.post("/jobs/{job_id}/status")
def set_status(job_id: str, body: StatusUpdate):
    update_job_status(job_id, body.status)
    return {"ok": True}


class OutcomeUpdate(BaseModel):
    outcome: str                          # pending | interview | offer | rejected | ghosted
    rejection_reason: Optional[str] = None

@app.post("/jobs/{job_id}/outcome")
def set_outcome(job_id: str, body: OutcomeUpdate):
    update_job_outcome(job_id, body.outcome, body.rejection_reason)
    if body.outcome == "applied":
        from datetime import datetime, timedelta, timezone
        due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        set_follow_up_due(job_id, due)
    return {"ok": True}


class NoteBody(BaseModel):
    text: str

@app.post("/jobs/{job_id}/note")
def add_note(job_id: str, body: NoteBody):
    append_note(job_id, body.text)
    return {"ok": True}


# ── Apply (sets status + follow_up_due in one call) ───────────────────────────

@app.post("/jobs/{job_id}/apply")
def apply_job(job_id: str):
    """Mark job as applied: status=applied, outcome=pending, follow_up_due=now+7d."""
    from datetime import datetime, timedelta, timezone
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    update_job_status(job_id, "applied")
    update_job_outcome(job_id, "pending")
    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    set_follow_up_due(job_id, due)
    return {
        "ok": True,
        "title": job["title"],
        "company": job["company"],
        "follow_up_due": due[:10],
    }


# ── Follow-up jobs due ─────────────────────────────────────────────────────────

@app.get("/followups")
def followups():
    """
    Returns two lists:
      nudge   — applied+pending with follow_up_due < now (send 7-day reminder)
      auto_ghost — applied+pending with follow_up_due < now-7 days (14+ days, auto-ghost)
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    all_applied = get_jobs(status="applied", min_score=0.0, limit=500)
    pending = [
        j for j in all_applied
        if j.get("outcome") == "pending" and j.get("follow_up_due")
    ]
    nudge = [j for j in pending if j["follow_up_due"] < now]
    auto_ghost = get_jobs_for_auto_ghost()
    auto_ghost_ids = {j["id"] for j in auto_ghost}
    # nudge list should exclude jobs already in auto_ghost bucket
    nudge_only = [j for j in nudge if j["id"] not in auto_ghost_ids]
    return {"nudge": nudge_only, "auto_ghost": auto_ghost}


@app.post("/followups/auto-ghost")
def auto_ghost():
    """Auto-ghost all jobs 14+ days applied with no outcome. Returns ghosted list."""
    jobs = get_jobs_for_auto_ghost()
    ghosted = []
    for j in jobs:
        update_job_outcome(j["id"], "ghosted")
        ghosted.append({"id": j["id"], "title": j["title"], "company": j["company"]})
    return {"ghosted": ghosted, "count": len(ghosted)}




# ── Companies ─────────────────────────────────────────────────────────────────

@app.get("/companies")
def companies():
    return get_active_companies()


class CompanyBody(BaseModel):
    name: str
    careers_url: Optional[str] = ""
    linkedin_slug: Optional[str] = ""
    priority: int = 1

@app.post("/companies")
def add_company(body: CompanyBody):
    import hashlib
    cid = hashlib.sha256(body.name.lower().encode()).hexdigest()[:16]
    upsert_company({
        "id": cid,
        "name": body.name,
        "careers_url": body.careers_url,
        "linkedin_slug": body.linkedin_slug,
        "priority": body.priority,
        "active": True,
    })
    return {"ok": True, "id": cid}

@app.post("/companies/blacklist")
def blacklist(name: str):
    found = blacklist_company(name)
    return {"ok": found, "message": f"{'Blacklisted' if found else 'Not found'}: {name}"}


# ── Roles ─────────────────────────────────────────────────────────────────────

@app.get("/roles")
def roles():
    return get_active_roles()


class RoleBody(BaseModel):
    title: str
    keywords: list[str] = []
    tags: list[str] = []

@app.post("/roles")
def add_role(body: RoleBody):
    import hashlib
    rid = hashlib.sha256(body.title.lower().encode()).hexdigest()[:16]
    upsert_role({
        "id": rid,
        "title": body.title,
        "keywords": body.keywords,
        "tags": body.tags,
        "active": True,
    })
    return {"ok": True, "id": rid}


# ── Scraper health ────────────────────────────────────────────────────────────

@app.get("/scraper-health")
def scraper_health():
    return get_scraper_health()


# ── Scout trigger ─────────────────────────────────────────────────────────────

_last_scout_summary: dict = {}

def _run_scout_task():
    global _last_scout_summary
    from scrapers.pipeline import run_scout
    try:
        _last_scout_summary = run_scout()
    except Exception as e:
        _last_scout_summary = {"error": str(e)}


@app.post("/scout")
def trigger_scout(background_tasks: BackgroundTasks):
    """
    Triggered by n8n schedule or /scout Telegram command.
    Runs the full scout pipeline in the background.
    Returns immediately; poll GET /scout/last for the result.
    """
    background_tasks.add_task(_run_scout_task)
    return {"ok": True, "message": "Scout started"}


@app.get("/scout/last")
def last_scout_summary():
    """Return summary of the most recent scout run."""
    return _last_scout_summary or {"message": "No scout run yet"}


# ── Insights triggers ─────────────────────────────────────────────────────────

@app.get("/insights/weekly")
def insights_weekly():
    """Run the weekly report and return the Telegram-formatted string."""
    from insights.weekly import build_report
    return {"report": build_report()}


@app.get("/insights/gaps")
def insights_gaps():
    """Check skill gap thresholds and return new roadmap messages."""
    from insights.gaps import check_and_fire
    return {"messages": check_and_fire()}


@app.get("/insights/signals")
def insights_signals():
    """Return hiring signal messages for companies crossing the threshold."""
    from insights.signals import hiring_signal_messages
    import yaml
    from pathlib import Path
    cfg = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())
    threshold = cfg.get("hiring_signal", {}).get("threshold", 5)
    return {"messages": hiring_signal_messages(threshold)}


# ── Forge trigger (Phase 3 — wired up when forge is implemented) ───────────────

@app.post("/forge/{job_id}")
def trigger_forge(job_id: str):
    """
    Triggered by /resume <id> Telegram command via n8n.
    Runs the full forge pipeline: DB → optimizer → Typst → PDF.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    from forge.forge import generate_resume, _telegram_message
    result = generate_resume(job_id)
    return {**result, "telegram_message": _telegram_message(result)}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
