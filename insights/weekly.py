"""
Weekly insights report — run every Sunday at 9am.
Prints a Telegram-formatted report to stdout; n8n captures and sends it.

Usage: python insights/weekly.py
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db, llm


def _week_bounds() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).isoformat()
    return week_start, now.isoformat()


def _collect_missing_skills(week_start: str) -> dict[str, int]:
    jobs = db.get_jobs(status=None, min_score=-1.0, limit=2000)
    freq: dict[str, int] = {}
    for job in jobs:
        if not job.get("scored_at") or job["scored_at"] < week_start:
            continue
        detail = job.get("score_detail")
        if not detail:
            continue
        try:
            d = json.loads(detail) if isinstance(detail, str) else detail
            for skill in d.get("missing_skills", []):
                key = skill.lower().strip()
                freq[key] = freq.get(key, 0) + 1
        except Exception:
            pass
    return freq


def _response_rates(week_start: str) -> dict[str, dict]:
    jobs = db.get_jobs(status="applied", min_score=-1.0, limit=2000)
    applied: dict[str, int] = {}
    responded: dict[str, int] = {}
    for j in jobs:
        src = j.get("source", "unknown")
        applied[src] = applied.get(src, 0) + 1
        if j.get("outcome") in ("interview", "offer"):
            responded[src] = responded.get(src, 0) + 1
    return {
        src: {
            "applied": cnt,
            "responded": responded.get(src, 0),
            "rate": round(responded.get(src, 0) / cnt, 2),
        }
        for src, cnt in applied.items()
    }


def build_report() -> str:
    week_start, _ = _week_bounds()
    all_jobs = db.get_jobs(status=None, min_score=-1.0, limit=2000)

    week_new       = [j for j in all_jobs if j.get("created_at", "") >= week_start]
    week_scored    = [j for j in week_new if j.get("score", -1) >= 3.5]
    week_applied   = [j for j in all_jobs if j.get("status") == "applied"
                      and j.get("updated_at", "") >= week_start]
    week_interview = [j for j in all_jobs if j.get("outcome") == "interview"
                      and j.get("outcome_date", "") >= week_start]
    week_offer     = [j for j in all_jobs if j.get("outcome") == "offer"
                      and j.get("outcome_date", "") >= week_start]
    week_ghosted   = [j for j in all_jobs if j.get("outcome") == "ghosted"
                      and j.get("outcome_date", "") >= week_start]
    week_rejected  = [j for j in all_jobs if j.get("outcome") == "rejected"
                      and j.get("outcome_date", "") >= week_start]

    skill_freq = _collect_missing_skills(week_start)
    top_missing = sorted(skill_freq.items(), key=lambda x: -x[1])[:5]
    source_rates = _response_rates(week_start)

    llm_prompt = f"""Summarise a job-search week for a fresher candidate (graduating 2026, targeting Data/AI roles in India).

Stats:
- Jobs found: {len(week_new)}, Scored ≥3.5: {len(week_scored)}
- Applied: {len(week_applied)}, Interviews: {len(week_interview)}, Offers: {len(week_offer)}
- Ghosted: {len(week_ghosted)}, Rejected: {len(week_rejected)}
- Top missing skills: {', '.join(f"{s}({c}x)" for s, c in top_missing) or 'none'}
- Response rates by source: {json.dumps(source_rates)}

Write 2-3 sentences of direct, actionable advice for next week. No preamble."""

    llm_summary = llm.write(llm_prompt)

    db.upsert_insight({
        "week_start": week_start[:10],
        "missing_skills_json": json.dumps(skill_freq),
        "rejection_count": len(week_rejected),
        "interview_count": len(week_interview),
        "offer_count": len(week_offer),
        "response_rate_by_source": json.dumps(source_rates),
        "llm_summary": llm_summary,
    })

    missing_lines = "\n".join(f"  {s.title()} ({c}×)" for s, c in top_missing) or "  None this week"

    best_src  = max(source_rates, key=lambda s: source_rates[s]["rate"], default="N/A")
    worst_src = min(source_rates, key=lambda s: source_rates[s]["rate"], default="N/A")

    week_label  = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%b %d").lstrip("0")
    today_label = datetime.now(timezone.utc).strftime("%b %d").lstrip("0")

    return (
        f"📊 *Week of {week_label}–{today_label}*\n\n"
        f"Jobs found: {len(week_new)}  |  Scored ≥3.5: {len(week_scored)}\n"
        f"Applied: {len(week_applied)}  |  Interviews: {len(week_interview)}  "
        f"|  Offers: {len(week_offer)}  |  Ghosted: {len(week_ghosted)}\n\n"
        f"*Common missing skills:*\n{missing_lines}\n\n"
        f"Best source: {best_src}  |  Worst: {worst_src}\n\n"
        f"💡 {llm_summary}"
    )


if __name__ == "__main__":
    print(build_report())
