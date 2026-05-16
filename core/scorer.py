"""
Groq-based job scoring.

Builds the prompt from config.yaml candidate profile + job fields,
calls core.llm.score(), parses the JSON response, and writes results
to the DB via core.db.update_job_score().

Graceful degradation: if Groq is unavailable, llm.score() already returns
a fallback JSON with score=-1. This module stores that and moves on.
"""

import hashlib
import json
from pathlib import Path
from typing import Optional
import yaml

from core import db, llm

_HASH_FILE = Path("shared/.config_hash")


_config: dict | None = None


def _cfg() -> dict:
    global _config
    if _config is None:
        cfg_path = Path(__file__).parent.parent / "config.yaml"
        with open(cfg_path) as f:
            _config = yaml.safe_load(f)
    return _config


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(job: dict) -> str:
    cfg = _cfg()
    c = cfg["candidate"]

    roles_str      = ", ".join(cfg.get("target_roles", []))
    locations_str  = ", ".join(cfg.get("locations", []))
    skills_str     = "\n".join(f"  - {s}" for s in c.get("core_skills", []))
    internships    = "\n".join(f"  - {i}" for i in c.get("internships", []))
    projects       = "\n".join(f"  - {p}" for p in c.get("notable_projects", []))

    description = (job.get("description") or "")[:1500]

    return f"""You are evaluating a job posting for a fresher candidate graduating 2026.

CANDIDATE PROFILE:
Name:             {c.get('name', 'Candidate')}
Degree:           {c.get('degree', '')}
Experience:       {c.get('experience_level', '0–1 year internships')}
Target sector:    {c.get('target_sector', '')}
Target roles:     {roles_str}
Preferred locations: {locations_str}

Core skills:
{skills_str}

Internships:
{internships}

Notable projects:
{projects}

JOB POSTING:
Title:       {job.get('title', '')}
Company:     {job.get('company', '')}
Location:    {job.get('location', '')}
Source:      {job.get('source', '')}
Description:
{description}

Respond ONLY with valid JSON — no explanation, no markdown, no code fences:
{{
  "score": <float 0.0–5.0>,
  "fit_summary": "<one sentence>",
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill1"],
  "seniority_fit": true|false,
  "location_fit": true|false
}}"""


# ── Tag matching ──────────────────────────────────────────────────────────────

def _match_tags(job: dict, score_detail: dict) -> list[str]:
    """Return role tags that appear in matched_skills or job title/description."""
    cfg = _cfg()
    matched_skills_lower = {s.lower() for s in score_detail.get("matched_skills", [])}
    text_lower = (
        (job.get("title") or "") + " " + (job.get("description") or "")
    ).lower()

    tags: list[str] = []
    for role in cfg.get("target_roles", []):
        role_key = role.lower().replace(" ", "_")
        if role.lower() in text_lower:
            tags.append(role_key)
    return list(dict.fromkeys(tags))   # deduplicate, preserve order


# ── Public API ────────────────────────────────────────────────────────────────

def score_job(job: dict) -> dict:
    """
    Score a single job dict. Returns the score_detail dict.
    Writes results to DB. Always returns — never raises.
    """
    prompt = _build_prompt(job)
    raw = llm.score(prompt)

    try:
        detail = llm.parse_json(raw)
    except Exception:
        detail = {
            "score": -1,
            "fit_summary": "JSON parse failed",
            "matched_skills": [],
            "missing_skills": [],
            "seniority_fit": False,
            "location_fit": False,
        }

    score_val   = float(detail.get("score", -1))
    tags        = _match_tags(job, detail)

    db.update_job_score(job["id"], score_val, detail, tags)
    return detail


def flag_for_rescore() -> dict:
    """
    Check if config.yaml has changed since last run. If so, reset all active
    job scores so they get re-evaluated on the next score_pending() call.
    Returns {"triggered": bool, "flagged": int}.
    """
    cfg_path = Path(__file__).parent.parent / "config.yaml"
    current_hash = hashlib.sha256(cfg_path.read_bytes()).hexdigest()

    _HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _HASH_FILE.exists():
        stored = _HASH_FILE.read_text().strip()
        if stored == current_hash:
            return {"triggered": False, "flagged": 0}

    flagged = db.flag_all_for_rescore()
    _HASH_FILE.write_text(current_hash)
    return {"triggered": True, "flagged": flagged}


def score_pending(batch_size: int = 50) -> dict:
    """
    Score all unscored jobs (score=-1, not expired).
    Returns summary: {scored, skipped, failed}.
    """
    jobs = db.get_unscored_jobs()
    scored = skipped = failed = 0

    for job in jobs[:batch_size]:
        # Skip stale — not worth scoring
        if job.get("urgency") == "stale":
            skipped += 1
            continue
        try:
            detail = score_job(job)
            if detail.get("score", -1) >= 0:
                scored += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    return {"scored": scored, "skipped": skipped, "failed": failed}
