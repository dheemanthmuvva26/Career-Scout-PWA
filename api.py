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
)

app = FastAPI(title="Career Scout API", version="1.0.0")

# Initialise DB on startup
@app.on_event("startup")
def startup():
    init_db()
    print("✓ DB initialised")


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


# ── Follow-up jobs due ─────────────────────────────────────────────────────────

@app.get("/followups")
def followups():
    """Jobs that are applied, pending outcome, and past follow_up_due date."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    jobs = get_jobs(status="applied", min_score=0.0, limit=200)
    due = [
        j for j in jobs
        if j.get("outcome") == "pending"
        and j.get("follow_up_due")
        and j["follow_up_due"] < now
    ]
    return due


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


# ── Forge trigger (Phase 3 — wired up when forge is implemented) ───────────────

@app.post("/forge/{job_id}")
def trigger_forge(job_id: str):
    """
    Triggered by /resume <id> Telegram command via n8n.
    Phase 3: import and call forge.forge(job_id) here.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    # TODO Phase 3: from forge.forge import generate_resume; result = generate_resume(job_id)
    return {"ok": True, "message": f"Forge triggered for job {job_id} (wired in Phase 3)"}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
