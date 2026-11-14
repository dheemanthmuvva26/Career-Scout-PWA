"""
Career Scout — Python API Server
Runs on host machine at http://localhost:8000
n8n (Docker) calls this via HTTP Request nodes using host.docker.internal:8000

Start: python api.py  (or: uvicorn api:app --reload --port 8000)
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import json
import os
import threading
import uuid as _uuid
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
    get_forage_sims, set_forage_sim_completed,
    find_forage_matches_for_companies, normalize_company,
    add_confirmed_skill, get_confirmed_skills, remove_confirmed_skill,
    save_push_subscription, delete_push_subscription,
)
from core import push as push_lib

app = FastAPI(title="Career Scout API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_API_KEY = os.getenv("API_KEY", "")
_OPEN_PATHS = {"/health", "/"}
_OPEN_PREFIXES = ("/resumes/",)

@app.middleware("http")
async def require_api_key(request: Request, call_next):
    # Allow CORS preflight through without auth
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path
    is_open = path in _OPEN_PATHS or any(path.startswith(p) for p in _OPEN_PREFIXES)
    if _API_KEY and not is_open:
        key = request.headers.get("X-API-Key") or request.headers.get("x-api-key")
        if key != _API_KEY:
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
    return await call_next(request)

# Initialise DB on startup
@app.on_event("startup")
def startup():
    os.makedirs("shared/resumes", exist_ok=True)
    init_db()
    print("DB initialised")
    # Pre-download typst on Render (Linux) during startup so the first
    # forge request doesn't pay the 30-60s download cost inside the 90s timeout
    try:
        import threading
        from forge.forge import _get_typst
        threading.Thread(target=_get_typst, daemon=True).start()
        print("typst pre-warm started")
    except Exception as e:
        print(f"typst pre-warm skipped: {e}")


# ── Health ────────────────────────────────────────────────────────────────────

_BUILD = "20261114-webpush-rls"

@app.get("/health")
def health():
    return {"status": "ok", "build": _BUILD}


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/stats")
def stats():
    return get_stats()


# ── Jobs ──────────────────────────────────────────────────────────────────────

@app.get("/jobs")
def list_jobs(
    status: Optional[str] = None,
    min_score: float = -1.0,
    urgency: Optional[str] = None,
    outcome: Optional[str] = None,
    limit: int = 50,
):
    # Default includes score=-1 (not-yet-scored) jobs — otherwise a job whose
    # background scoring call fails or hasn't run yet (rate limit, cold
    # backend, transient error) silently vanishes from every tab in the feed
    # even though it saved successfully.
    return get_jobs(status=status, min_score=min_score, urgency=urgency, outcome=outcome, limit=limit)


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
    Triggered by n8n schedule or the PWA's Scout button.
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
    """Run the weekly report and return the formatted summary string."""
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


# ── Forge trigger — async via background thread + poll ────────────────────────
# Forge runs Groq (10-20s) + typst download/compile (5-60s).
# Running synchronously hits Render's 90s response timeout on cold starts.
# Instead: POST returns a token immediately; client polls GET /forge/poll/{token}.

_forge_jobs: dict[str, dict] = {}

class ForgeBody(BaseModel):
    ats_hints: dict | None = None   # flagged + missing_keywords from ATS check

@app.post("/forge/{job_id}")
def trigger_forge(job_id: str, profile: str | None = None, body: ForgeBody = ForgeBody()):
    """
    Start forge in a background thread and return a token immediately.
    Client polls GET /forge/poll/{token} every 3s until status == "done".
    Optional body.ats_hints feeds ATS check results back into the optimizer.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    token = _uuid.uuid4().hex[:12]
    _forge_jobs[token] = {"status": "pending"}

    def _run():
        try:
            from forge.forge import generate_resume, _summary_message
            result = generate_resume(job_id, profile_override=profile,
                                     ats_hints=body.ats_hints)
            _forge_jobs[token] = {"status": "done", **result,
                                  "summary_message": _summary_message(result)}
        except Exception as e:
            _forge_jobs[token] = {"status": "done", "error": str(e)}
        def _cleanup():
            import time as _time
            _time.sleep(300)
            _forge_jobs.pop(token, None)
        threading.Thread(target=_cleanup, daemon=True).start()

    threading.Thread(target=_run, daemon=True).start()
    return {"token": token, "status": "pending"}


@app.get("/forge/poll/{token}")
def forge_poll(token: str):
    """Poll for forge result. Returns {status: pending} or {status: done, ...result}."""
    result = _forge_jobs.get(token)
    if result is None:
        raise HTTPException(status_code=404, detail="Token not found or expired")
    return result


@app.post("/forge/{job_id}/audit")
def forge_audit(job_id: str):
    """
    Step 1 — Pre-forge audit: score profile vs JD, return 5 missing keywords + 3 red flags.
    Fast single LLM call, no PDF generated.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    from forge.forge import audit_resume
    return audit_resume(job_id)


@app.post("/forge/{job_id}/ats-check")
def forge_ats_check(job_id: str):
    """
    Step 3 — Post-forge ATS simulation: scan last generated resume as ATS + hiring manager.
    Requires a resume to have been generated first (loads saved JSON from shared/resumes/).
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    from forge.forge import ats_check
    return ats_check(job_id)


# ── Web Push (proactive notifications — replaces the old Telegram bot) ─────────

class PushSubscribeRequest(BaseModel):
    endpoint: str
    keys: dict  # {"p256dh": "...", "auth": "..."}


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


class PushNotifyRequest(BaseModel):
    title: str
    body: str
    url: str = "/dashboard"


@app.get("/push/vapid-public-key")
def push_vapid_public_key():
    """The browser needs this to call pushManager.subscribe()."""
    return {"publicKey": os.environ.get("VAPID_PUBLIC_KEY", "")}


@app.post("/push/subscribe")
def push_subscribe(body: PushSubscribeRequest):
    save_push_subscription(body.endpoint, body.keys.get("p256dh", ""), body.keys.get("auth", ""))
    return {"ok": True}


@app.post("/push/unsubscribe")
def push_unsubscribe(body: PushUnsubscribeRequest):
    delete_push_subscription(body.endpoint)
    return {"ok": True}


@app.post("/push/notify")
def push_notify(body: PushNotifyRequest):
    """Called by n8n (morning digest, scout results, follow-up nudges) instead
    of the old Telegram sendMessage API."""
    return push_lib.send_push(body.title, body.body, body.url)


# ── LinkedIn URL import ───────────────────────────────────────────────────────

class ImportRequest(BaseModel):
    url: str
    location: str = ""   # optional override — lets same URL be imported for multiple cities

def _ingest_job(job: dict) -> dict:
    """Shared dedupe → score → save pipeline for any newly-fetched/extracted job."""
    from scrapers import dedup
    from core import urgency, scorer

    job["urgency"] = urgency.classify(job.get("posted_date"))
    result = dedup.process(job)

    if result.action in ("insert", "repost"):
        from core.db import upsert_job
        upsert_job(job)
        scorer.score_pending(batch_size=1)
        return {"action": "added", "job": get_job(result.job_id)}

    # merge or skip_exact — already in DB
    return {"action": "already_saved", "job": get_job(result.job_id)}


@app.post("/import")
def import_job(body: ImportRequest):
    """
    Import a single job from any URL — LinkedIn or a company career site /
    ATS platform (Greenhouse, Lever, Workday, etc.).
    Fetches the page, extracts job data, dedupes, scores, saves to DB.
    Optional location field overrides the scraped location (useful when the
    same job is posted for multiple cities under the same URL).
    """
    is_linkedin = "linkedin.com" in body.url

    try:
        if is_linkedin:
            from scrapers.linkedin_url_scraper import fetch_linkedin_job
            job = fetch_linkedin_job(body.url, location_override=body.location.strip())
        else:
            from scrapers.generic_url_scraper import fetch_job_from_url
            job = fetch_job_from_url(body.url, location_override=body.location.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        source = "LinkedIn" if is_linkedin else "the page"
        raise HTTPException(status_code=502, detail=f"Could not fetch {source}: {e}")

    return _ingest_job(job)


class ImportTextRequest(BaseModel):
    text: str
    location: str = ""

@app.post("/import/text")
def import_job_text(body: ImportTextRequest):
    """
    Import a job from raw pasted text — WhatsApp forward, LinkedIn feed post,
    email, anything that isn't a scrapeable URL. LLM extracts the structured
    fields, then runs through the same dedupe/score/save pipeline as /import.
    """
    from scrapers.text_import import extract_job_from_text

    try:
        job = extract_job_from_text(body.text, location_override=body.location.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not extract job from text: {e}")

    return _ingest_job(job)


# ── Batch import + forge ───────────────────────────────────────────────────────

class BatchImportRequest(BaseModel):
    urls: list[str]
    profile: str = "auto"   # profile name or "auto" to pick from job tags
    location: str = ""

_PROFILE_TAG_MAP = {
    # Ordered most-specific first — first match wins
    # ── AI / Tech ──
    "genai_engineer":      ["genai", "rag", "knowledge_graph", "langchain", "vector_db", "agentic", "graph_rag"],
    "applied_ai_engineer": ["applied_ai_engineer", "applied_ai", "applied_ml", "ai_solutions", "ai_product", "applied_machine_learning", "real_world_ai", "industry_ai"],
    "ai_researcher":       ["ai_researcher", "ai_research", "research_engineer", "ml_research", "research_scientist", "ai_lab", "applied_research", "model_research"],
    "mlops_engineer":      ["mlops_engineer", "mlops", "ml_platform", "model_deployment", "model_monitoring", "ml_pipeline", "feature_store", "model_registry", "cicd_ml"],
    "ai_engineer":         ["ai_engineer", "artificial_intelligence", "ai_system", "ai_integration", "intelligent_systems", "ai_solution", "ai_platform"],
    "ai_developer":        ["applied_ai", "chatbot", "automation", "dialogflow", "conversational_ai"],
    "ml_engineer":         ["ml", "machine_learning", "machine_learning_engineer", "deep_learning", "pytorch", "tensorflow", "model_training"],
    "data_engineer":       ["data_engineer", "data_engineering", "etl", "data_pipeline", "spark", "airflow", "kafka", "dbt", "data_warehouse", "bigquery"],
    "data_scientist":      ["data_scientist", "predictive_modeling", "statistical_analysis"],
    "bi_developer":        ["bi_developer", "bi", "data_analyst", "reporting", "dashboard", "visualization", "business_intelligence"],
    "nlp_engineer":        ["nlp_engineer", "nlp", "natural_language_processing", "text_classification", "sentiment_analysis", "named_entity_recognition", "ner", "text_mining", "conversational_ai", "speech_recognition"],
    "computer_vision":     ["computer_vision", "cv_engineer", "image_classification", "object_detection", "image_segmentation", "yolo", "opencv", "image_processing", "video_analytics"],
    "backend_developer":   ["backend_developer", "backend", "software_engineer", "rest_api", "microservices", "nodejs", "fastapi", "django", "spring_boot", "api_development"],
    "ai_operations":       ["ai_operations", "ai_ops", "process_associate_ai", "data_annotation", "ai_quality_assurance", "ai_labeling", "ai_pipeline_ops", "content_moderation", "ai_reviewer"],
    # ── Business ──
    "business_analyst":    ["business_analyst", "business_analysis", "brd", "requirements_gathering", "process_mapping", "stakeholder_management", "use_case", "gap_analysis"],
    "product_analyst":     ["product_analyst", "product_analytics", "ab_testing", "funnel_analysis", "user_behaviour", "product_metrics", "growth_analytics", "retention_analysis"],
    # ── Finance ──
    "investment_banking":  ["investment_banking", "ib_analyst", "mergers_acquisitions", "ma", "deal_structuring", "pitchbook", "dcf", "lbo", "capital_markets"],
    "fpa_analyst":         ["fpa", "fpa_analyst", "financial_planning", "budgeting", "forecasting", "variance_analysis", "management_reporting", "planning_analysis"],
    "research_analyst":    ["research_analyst", "investment_research", "industry_research", "sector_analysis", "company_analysis", "fundamental_analysis", "market_research"],
    "treasury_analyst":    ["treasury_analyst", "treasury", "cash_management", "liquidity", "forex", "fx_management", "working_capital", "cash_flow"],
    "audit_analyst":       ["audit_analyst", "internal_audit", "internal_auditor", "sox", "controls_testing", "audit_report", "process_audit", "risk_controls"],
    "tax_analyst":         ["tax_analyst", "tax_compliance", "gst", "income_tax", "tax_planning", "direct_tax", "indirect_tax", "tax_filing"],
    "credit_analyst":      ["credit_risk", "credit_analyst", "underwriting", "lending", "loan_analysis", "credit_scoring"],
    "quant_analyst":       ["quant_analyst", "quantitative", "quantitative_analysis", "statistical_modeling", "econometrics", "actuarial"],
    "financial_analyst":   ["financial_analyst", "financial_reporting", "financial_modeling", "investment", "equity_research", "valuation", "accounting"],
    "risk_analyst":        ["risk_analyst", "risk", "risk_management", "market_risk", "operational_risk", "banking"],
    "compliance_analyst":  ["compliance", "regulatory", "aml", "audit", "kyc", "financial_crime"],
}

def _pick_profile(tags: list[str]) -> str:
    """Pick the best forge profile from a job's matched tags."""
    for profile, profile_tags in _PROFILE_TAG_MAP.items():
        if any(t in profile_tags for t in tags):
            return profile
    return "default"

@app.post("/batch")
def batch_import(body: BatchImportRequest):
    """
    Import multiple jobs from URLs and kick off async forge for each.
    Returns per-URL results immediately — forge tokens can be polled via
    GET /forge/poll/{token}. Processes URLs sequentially to avoid rate limits.
    """
    results = []
    for url in body.urls:
        url = url.strip()
        if not url:
            continue
        entry: dict = {"url": url}
        try:
            # — import —
            is_linkedin = "linkedin.com" in url
            if is_linkedin:
                from scrapers.linkedin_url_scraper import fetch_linkedin_job
                job_data = fetch_linkedin_job(url, location_override=body.location.strip())
            else:
                from scrapers.generic_url_scraper import fetch_job_from_url
                job_data = fetch_job_from_url(url, location_override=body.location.strip())

            ingest = _ingest_job(job_data)
            saved = ingest["job"]
            entry.update({
                "import_status": ingest["action"],   # "added" or "already_saved"
                "job_id": saved["id"],
                "title": saved["title"],
                "company": saved["company"],
            })

            # — forge —
            profile = body.profile
            if profile == "auto":
                profile = _pick_profile(saved.get("tags_matched") or [])

            token = _uuid.uuid4().hex[:12]
            _forge_jobs[token] = {"status": "pending"}

            job_id_cap = saved["id"]
            profile_cap = profile
            token_cap = token

            def _run(jid=job_id_cap, prof=profile_cap, tok=token_cap):
                try:
                    from forge.forge import generate_resume, _summary_message
                    result = generate_resume(jid, profile_override=prof)
                    _forge_jobs[tok] = {"status": "done", **result,
                                        "summary_message": _summary_message(result)}
                except Exception as exc:
                    _forge_jobs[tok] = {"status": "done", "error": str(exc)}
                def _cleanup():
                    import time as _t; _t.sleep(300); _forge_jobs.pop(tok, None)
                threading.Thread(target=_cleanup, daemon=True).start()

            threading.Thread(target=_run, daemon=True).start()
            entry.update({"forge_token": token, "profile_used": profile, "forge_status": "pending"})

        except Exception as exc:
            entry["error"] = str(exc)

        results.append(entry)

    return {"results": results}


# ── Forage job simulations ────────────────────────────────────────────────────

_last_forage_sync: dict = {}

def _run_forage_sync_task(limit: int):
    global _last_forage_sync
    try:
        from scrapers.forage_scraper import sync_catalog
        _last_forage_sync = sync_catalog(limit=limit)
    except Exception as e:
        _last_forage_sync = {"error": str(e)}

@app.post("/forage/sync")
def forage_sync(background_tasks: BackgroundTasks, limit: int = 30):
    """
    Fetch newly-added Forage simulations into the local catalog (up to `limit`
    per call — simulations already in the DB are never re-fetched, so once
    the catalog is backfilled, repeat calls are cheap and only pick up new
    additions to Forage's public catalog).
    Runs in the background; poll GET /forage/sync/status for the result.
    """
    background_tasks.add_task(_run_forage_sync_task, limit)
    return {"ok": True, "message": "Forage sync started"}

@app.get("/forage/sync/status")
def forage_sync_status():
    return _last_forage_sync or {"message": "No sync run yet"}


def _decode_sim(sim: dict) -> dict:
    sim["skills"] = json.loads(sim.get("skills") or "[]")
    sim["careers"] = json.loads(sim.get("careers") or "[]")
    return sim

@app.get("/forage/sims")
def forage_sims_list(company: Optional[str] = None, completed: Optional[bool] = None):
    """List the Forage catalog, optionally filtered by company or completion."""
    sims = get_forage_sims(completed_only=bool(completed)) if completed is not None else get_forage_sims()
    if company:
        target = normalize_company(company)
        sims = [
            s for s in sims
            if target and (target in normalize_company(s["company"]) or normalize_company(s["company"]) in target)
        ]
    return [_decode_sim(s) for s in sims]


class ForageCompleteRequest(BaseModel):
    completed: bool = True

@app.post("/forage/sims/{sim_id}/complete")
def forage_mark_complete(sim_id: str, body: ForageCompleteRequest):
    """Mark (or unmark) a simulation as completed — completed sims are what
    forge.py matches against a job's company to auto-add a certification."""
    if not set_forage_sim_completed(sim_id, body.completed):
        raise HTTPException(status_code=404, detail="Simulation not found")
    return {"ok": True}


@app.get("/forage/recommendations")
def forage_recommendations():
    """
    Cross-reference companies in your active job pipeline (new/applied/
    interview/offer) against the Forage catalog for simulations you haven't
    completed yet — grouped by simulation, with the matching jobs attached.
    """
    active_statuses = ["new", "applied", "interview", "offer"]
    company_to_jobs: dict[str, list[dict]] = {}
    for status in active_statuses:
        for j in get_jobs(status=status, limit=200):
            company_to_jobs.setdefault(j["company"], []).append(j)

    matches = find_forage_matches_for_companies(list(company_to_jobs.keys()))

    recs: dict[str, dict] = {}
    for company, sims in matches.items():
        for sim in sims:
            entry = recs.setdefault(sim["id"], {**_decode_sim(dict(sim)), "matched_jobs": []})
            entry["matched_jobs"].extend(
                {"id": j["id"], "title": j["title"], "status": j["status"]}
                for j in company_to_jobs[company]
            )
    return sorted(recs.values(), key=lambda r: -len(r["matched_jobs"]))


# ── Confirmed skills ──────────────────────────────────────────────────────────

class ConfirmSkillRequest(BaseModel):
    skill: str

@app.post("/skills/confirm")
def confirm_skill(body: ConfirmSkillRequest):
    """
    Record a skill the user has confirmed they have (from a "missing keyword"
    prompt in the app). Fed back into future scoring/audit prompts so the
    same skill doesn't keep getting flagged as missing.
    """
    skill = body.skill.strip()
    if not skill:
        raise HTTPException(status_code=400, detail="skill is required")
    return add_confirmed_skill(skill)

@app.get("/skills/confirmed")
def list_confirmed_skills():
    return get_confirmed_skills()

@app.delete("/skills/confirmed/{skill_id}")
def unconfirm_skill(skill_id: str):
    if not remove_confirmed_skill(skill_id):
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"ok": True}


# ── DB Backup ─────────────────────────────────────────────────────────────────

@app.post("/backup")
def run_backup():
    """Backup jobs.db to shared/backups/ — called by n8n db_backup workflow."""
    import shutil, glob
    from pathlib import Path
    from datetime import date
    src = Path("shared/jobs.db")
    if not src.exists():
        raise HTTPException(status_code=404, detail="jobs.db not found")
    backup_dir = Path("shared/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    dst = backup_dir / f"jobs_{date.today().isoformat()}.db"
    shutil.copy(src, dst)
    # Keep last 30 days
    backups = sorted(backup_dir.glob("jobs_*.db"))
    deleted = []
    for old in backups[:-30]:
        old.unlink()
        deleted.append(old.name)
    return {"ok": True, "backup": str(dst), "deleted": deleted}


# ── Static files — resume PDFs served without auth ────────────────────────────
os.makedirs("shared/resumes", exist_ok=True)
app.mount("/resumes", StaticFiles(directory="shared/resumes"), name="resumes")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
