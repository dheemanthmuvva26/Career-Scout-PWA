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
)

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

_BUILD = "20260701-strict-one-page"

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
            from forge.forge import generate_resume, _telegram_message
            result = generate_resume(job_id, profile_override=profile,
                                     ats_hints=body.ats_hints)
            _forge_jobs[token] = {"status": "done", **result,
                                  "telegram_message": _telegram_message(result)}
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


# ── Telegram bot command handler ─────────────────────────────────────────────

HELP_TEXT = """🤖 *Career Scout — Command Reference*

📋 *Browsing Jobs*
/digest — Today's top scored matches
/jobs — List latest new jobs (score ≥ 3.5)
/job <id> — Full detail: score, skills, fit summary

📩 *Tracking Applications*
/apply <id> — Mark as applied, sets 7-day follow-up reminder
/interview <id> — Mark interview received
/offer <id> — Mark offer received
/rejected <id> [reason] — Mark as rejected
/ghosted <id> — Mark as ghosted (no response after 14 days)
/note <id> <text> — Add a private note to a job

📎 *Import*
/import <url> — Save a job from LinkedIn or any company career page

📄 *Resumes*
/resume <id> — Generate ATS-optimised PDF resume for a job

🔍 *Scouting*
/scout — Trigger a fresh job scan right now
/stats — Dashboard summary (pipeline counts + interview rate)

⚙️ *Manage Watchlists*
/add company <name> [url] — Add company to target watchlist
/add role <title> — Add role keyword to search for
/blacklist <company name> — Never show jobs from this company again

💡 *Tips*
• Job IDs appear after each listing — tap to copy, then use in commands
• Urgency: 🔴 hot (<24h)  🟡 active  ⚪ aging  💀 stale
• Scores are out of 5 ★
• /start shows this help any time"""

_URG = {"hot": "🔴", "active": "🟡", "aging": "⚪", "stale": "💀"}


# ── Telegram API helpers ──────────────────────────────────────────────────────

TELEGRAM_API = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN', '')}"

# MarkdownV2 reserved characters that must be escaped in dynamic text
_MD_SPECIAL = set(r"_*[]()~`>#+-=|{}.!")


def _esc(text) -> str:
    """Escape MarkdownV2 special characters in dynamically interpolated text."""
    return "".join(("\\" + c) if c in _MD_SPECIAL else c for c in str(text))


def _esc_url(url: str) -> str:
    """Escape characters required inside a MarkdownV2 link's parentheses."""
    return str(url).replace("\\", "\\\\").replace(")", "\\)")


def _tg(method: str, **params) -> dict:
    """Call the Telegram Bot API. Returns the parsed JSON response."""
    import requests
    try:
        r = requests.post(f"{TELEGRAM_API}/{method}", json=params, timeout=10)
        data = r.json()
        if not data.get("ok"):
            print(f"[telegram] {method} failed: {data}")
        return data
    except Exception as e:
        print(f"[telegram] {method} error: {e}")
        return {"ok": False, "error": str(e)}


def _tg_send(chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
    """Send a message. Falls back to plain text if MarkdownV2 parsing fails."""
    params = {"chat_id": chat_id, "text": text, "parse_mode": "MarkdownV2"}
    if reply_markup:
        params["reply_markup"] = reply_markup
    resp = _tg("sendMessage", **params)
    if not resp.get("ok"):
        # MarkdownV2 escaping bug shouldn't make the reply vanish silently —
        # retry as plain text so the user still sees something.
        params.pop("parse_mode", None)
        _tg("sendMessage", **params)


def _tg_send_document(chat_id: int, file_path: str, caption: str = "") -> bool:
    """Upload and send a local file (e.g. a generated resume PDF). Caption is plain text."""
    import requests
    try:
        with open(file_path, "rb") as f:
            r = requests.post(
                f"{TELEGRAM_API}/sendDocument",
                data={"chat_id": chat_id, "caption": caption[:1024]},
                files={"document": f},
                timeout=60,
            )
        data = r.json()
        if not data.get("ok"):
            print(f"[telegram] sendDocument failed: {data}")
        return bool(data.get("ok"))
    except Exception as e:
        print(f"[telegram] sendDocument error: {e}")
        return False


# ── Inline keyboard builders ──────────────────────────────────────────────────

def _job_row(short_id: str) -> list:
    return [
        {"text": "📋 Details", "callback_data": f"job:{short_id}"},
        {"text": "✅ Apply",   "callback_data": f"apply:{short_id}"},
        {"text": "❌ Skip",    "callback_data": f"skip:{short_id}"},
    ]


def _detail_markup(short_id: str) -> dict:
    return {"inline_keyboard": [[
        {"text": "✅ Apply",  "callback_data": f"apply:{short_id}"},
        {"text": "📄 Resume", "callback_data": f"resume:{short_id}"},
        {"text": "❌ Reject", "callback_data": f"rejected:{short_id}"},
    ]]}


def _outcome_markup(short_id: str) -> dict:
    return {"inline_keyboard": [[
        {"text": "🎉 Interview", "callback_data": f"interview:{short_id}"},
        {"text": "👎 Rejected",  "callback_data": f"rejected:{short_id}"},
        {"text": "👻 Ghosted",   "callback_data": f"ghosted:{short_id}"},
    ]]}


class BotRequest(BaseModel):
    cmd: str
    args: list[str] = []
    chat_id: int
    callback_query_id: Optional[str] = None


@app.post("/bot")
def bot_command(body: BotRequest):
    """Handle all Telegram bot commands (messages and button taps)."""
    cmd = body.cmd.lower().strip()
    args = body.args
    chat_id = body.chat_id

    # Dismiss the loading spinner on the tapped button, if any
    cb_id = (body.callback_query_id or "").strip()
    if cb_id and cb_id.lower() != "null":
        _tg("answerCallbackQuery", callback_query_id=cb_id)

    # Handle /add sub-commands
    if cmd == "add" and args:
        cmd = "add_" + args[0].lower()
        args = args[1:]

    reply, markup = _dispatch(cmd, args, chat_id)
    if reply is not None:
        _tg_send(chat_id, reply, markup)
    return {"ok": True}


def _dispatch(cmd: str, args: list[str], chat_id: Optional[int] = None) -> tuple[str, Optional[dict]]:
    """Returns (reply_text, reply_markup). reply_markup is an inline-keyboard
    dict or None."""
    import json as _json

    if cmd in ("start", "help"):
        prefix = "👋 Welcome to *Career Scout*\\!\n\nI scan job boards every 6 hours and send you the best Data / AI / BI roles in India — scored and ranked for your profile.\n\n" if cmd == "start" else ""
        return prefix + HELP_TEXT, None

    if cmd == "stats":
        s = get_stats()
        pct = round(s["interviews"] / s["applied"] * 100) if s["applied"] else 0
        return (
            f"📊 *Career Scout Stats*\n\n"
            f"💼 Total tracked: {s['total']}\n"
            f"🆕 New / unreviewed: {s['new']}\n"
            f"📨 Applied: {s['applied']}\n"
            f"🤝 Interviews: {s['interviews']}\n"
            f"🎊 Offers: {s['offers']}\n"
            f"⏳ Unscored: {s['unscored']}\n\n"
            f"📈 Interview rate: {pct}%"
        ), None

    if cmd in ("jobs", "digest"):
        if cmd == "jobs":
            jobs = get_jobs(status="new", min_score=3.5, limit=5)
            empty_msg = "No new jobs right now\\. Try /scout to run a fresh scan\\."
            header = "🗂 *Top new jobs:*\n\n"
            footer = ""
        else:
            import yaml
            from pathlib import Path
            cfg = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())
            min_score = cfg.get("min_score", 3.5)
            hot    = get_jobs(min_score=min_score, urgency="hot",    limit=5)
            active = get_jobs(min_score=min_score, urgency="active", limit=5)
            combined = {j["id"]: j for j in hot + active}
            jobs = sorted(combined.values(), key=lambda j: j.get("score") or 0, reverse=True)[:5]
            empty_msg = "No high-scoring jobs today\\. Try /scout to fetch fresh listings\\."
            header = "☀️ *Today's top matches:*\n\n"
            footer = "\n\n_Use the buttons below, or /job <id> for full details\\._"

        if not jobs:
            return empty_msg, None

        lines = []
        keyboard = []
        for j in jobs:
            sid = j.get('short_id') or j['id']
            lines.append(
                f"{_URG.get(j.get('urgency',''), '⚪')} *{_esc(j['title'])}* @ {_esc(j['company'])} "
                f"\\({(j.get('score') or 0):.1f}★\\)\n"
                f"  {_esc(j.get('location') or 'N/A')} — `{sid}`"
            )
            keyboard.append(_job_row(sid))
        return header + "\n\n".join(lines) + footer, {"inline_keyboard": keyboard}

    if cmd == "job":
        if not args:
            return "Usage: /job <id>", None
        j = get_job(args[0])
        if not j:
            return "Job not found\\. Use /jobs to get valid IDs\\.", None
        try:
            d = _json.loads(j.get("score_detail") or "{}")
        except Exception:
            d = {}
        matched = ", ".join(d.get("matched_skills", [])) or "N/A"
        missing = ", ".join(d.get("missing_skills", [])) or "None"
        score = (j.get("score") or 0)
        sid = j.get('short_id') or j['id']
        url = j.get('url') or ''
        url_line = f"🔗 [Open posting]({_esc_url(url)})" if url else "🔗 N/A"
        text = (
            f"{_URG.get(j.get('urgency',''), '⚪')} *{_esc(j['title'])}* @ {_esc(j['company'])}\n"
            f"{_esc(j.get('location') or 'N/A')} — Score: {score:.1f}★ — _{_esc(j.get('status','new'))}_\n\n"
            f"💡 {_esc(d.get('fit_summary', 'No summary.'))}\n\n"
            f"✅ *Matched:* {_esc(matched)}\n"
            f"❌ *Missing:* {_esc(missing)}\n\n"
            f"{url_line}\n\n"
            f"ID: `{sid}`"
        )
        return text, _detail_markup(sid)

    if cmd == "apply":
        if not args:
            return "Usage: /apply <job\\_id>", None
        j = get_job(args[0])
        if not j:
            return "Job not found\\. Check the ID\\.", None
        from datetime import datetime, timedelta, timezone
        due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        update_job_status(args[0], "applied")
        update_job_outcome(args[0], "pending")
        set_follow_up_due(args[0], due)
        sid = j.get('short_id') or j['id']
        text = f"✅ Applied to *{_esc(j['title'])}* @ {_esc(j['company'])}\nFollow\\-up reminder set for {due[:10]}\\."
        return text, _outcome_markup(sid)

    if cmd == "skip":
        if not args:
            return "Usage: /skip <job\\_id>", None
        j = get_job(args[0])
        if not j:
            return "Job not found\\.", None
        update_job_status(args[0], "skipped")
        return f"⏭️ Skipped *{_esc(j['title'])}* @ {_esc(j['company'])}\\.", None

    if cmd == "interview":
        if not args:
            return "Usage: /interview <job\\_id>", None
        update_job_outcome(args[0], "interview")
        return "🎉 *Interview scheduled\\!* Marked\\. Go prep — you got this\\!", None

    if cmd == "offer":
        if not args:
            return "Usage: /offer <job\\_id>", None
        update_job_outcome(args[0], "offer")
        return "🎊 *OFFER received\\! Congratulations\\!* 🍳", None

    if cmd == "rejected":
        if not args:
            return "Usage: /rejected <job\\_id> \\[optional reason\\]", None
        reason = " ".join(args[1:]) or None
        update_job_outcome(args[0], "rejected", reason)
        return "👎 Marked as rejected\\. Every no gets you closer to a yes\\.", None

    if cmd == "ghosted":
        if not args:
            return "Usage: /ghosted <job\\_id>", None
        update_job_outcome(args[0], "ghosted")
        return "👻 Marked as ghosted\\. Auto\\-ghost runs after 14 days anyway\\.", None

    if cmd == "note":
        if len(args) < 2:
            return "Usage: /note <job\\_id> <your note text>", None
        append_note(args[0], " ".join(args[1:]))
        return "📝 Note saved\\.", None

    if cmd == "blacklist":
        if not args:
            return "Usage: /blacklist <company name>", None
        name = " ".join(args)
        blacklist_company(name)
        return f"🚫 *{_esc(name)}* blacklisted\\. No more jobs from them\\.", None

    if cmd == "add_company":
        if not args:
            return "Usage: /add company <name> \\[careers\\_url\\]", None
        import hashlib
        cid = hashlib.sha256(args[0].lower().encode()).hexdigest()[:16]
        upsert_company({"id": cid, "name": args[0], "careers_url": args[1] if len(args) > 1 else "", "linkedin_slug": "", "priority": 1, "active": True})
        return f"🏢 *{_esc(args[0])}* added to watchlist\\.", None

    if cmd == "add_role":
        if not args:
            return "Usage: /add role <job title>", None
        import hashlib
        title = " ".join(args)
        rid = hashlib.sha256(title.lower().encode()).hexdigest()[:16]
        upsert_role({"id": rid, "title": title, "keywords": [], "tags": [], "active": True})
        return f"🎯 Role *{_esc(title)}* added to watchlist\\.", None

    if cmd == "scout":
        # Fire-and-forget; already has background task in /scout endpoint
        import threading
        from scrapers.pipeline import run_scout
        threading.Thread(target=run_scout, daemon=True).start()
        return "🔍 Scout started\\! New jobs will appear in your next digest\\. Check back with /jobs in a few minutes\\.", None

    if cmd == "resume":
        if not args:
            return "Usage: /resume <job\\_id>\n\nGenerates an ATS\\-optimised PDF resume tailored to that specific job\\.", None
        j = get_job(args[0])
        if not j:
            return "Job not found\\.", None
        try:
            from forge.forge import generate_resume, _telegram_message
            result = generate_resume(args[0])
            pdf_path = result.get("pdf_path")
            if pdf_path and chat_id is not None:
                ats = result.get("ats_score", -1)
                ats_str = f"{ats}%" if ats >= 0 else "N/A"
                caption = (
                    f"Resume — {result.get('title','')} @ {result.get('company','')}\n"
                    f"Profile: {result.get('profile_used','')}\n"
                    f"ATS score estimate: {ats_str}"
                )
                if not _tg_send_document(chat_id, pdf_path, caption=caption):
                    return _telegram_message(result), None
                return None, None
            return _telegram_message(result), None
        except Exception as e:
            return f"❌ Resume generation failed: {_esc(e)}", None

    if cmd == "import":
        if not args or not args[0].startswith("http"):
            return "📎 *Import a job*\n\nUsage: /import <url>\n\nPaste a LinkedIn job URL, or any company career page / ATS job link\\.", None
        url = args[0]
        try:
            from scrapers import dedup
            from core import urgency, scorer
            from core.db import upsert_job

            if "linkedin.com" in url:
                from scrapers.linkedin_url_scraper import fetch_linkedin_job
                job = fetch_linkedin_job(url)
            else:
                from scrapers.generic_url_scraper import fetch_job_from_url
                job = fetch_job_from_url(url)
            job["urgency"] = urgency.classify(job.get("posted_date"))
            result = dedup.process(job)

            if result.action in ("insert", "repost"):
                upsert_job(job)
                scorer.score_pending(batch_size=1)

            j = get_job(result.job_id) or job
            score = j.get("score") or -1
            score_str = f"{score:.1f}★" if score > 0 else "scoring pending"
            badge = "✅ *Saved to Career Scout*" if result.action in ("insert", "repost") else "📋 *Already in your tracker*"
            sid = j.get('short_id') or j.get('id', '?')
            text = (
                f"{badge}\n\n"
                f"*{_esc(j.get('title','Unknown'))}* @ {_esc(j.get('company','Unknown'))}\n"
                f"📍 {_esc(j.get('location') or 'N/A')}  ·  ⭐ {score_str}\n\n"
                f"ID: `{sid}`"
            )
            return text, _detail_markup(sid)
        except ValueError as e:
            return f"❌ {_esc(e)}", None
        except Exception as e:
            return f"❌ Could not import: {_esc(e)}", None

    return f"❓ Unknown command: */{_esc(cmd)}*\n\nSend /help to see all available commands\\.", None


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
