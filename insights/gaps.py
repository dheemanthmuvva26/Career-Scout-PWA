"""
Skill gap roadmap generator.

Fires once per skill when it appears missing in 3+ job evaluations.
Tracks already-fired skills in shared/.gaps_fired.json so each skill
triggers a roadmap message exactly once (until that file is deleted to reset).

Usage: python insights/gaps.py
Prints one Telegram message per newly triggered skill, separated by ---NEXT---
"""

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db, llm

_GAPS_FILE = Path("shared/.gaps_fired.json")
_DEFAULT_TRIGGER = 3


def _load_fired() -> set[str]:
    if _GAPS_FILE.exists():
        try:
            return set(json.loads(_GAPS_FILE.read_text()))
        except Exception:
            pass
    return set()


def _save_fired(fired: set[str]) -> None:
    _GAPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _GAPS_FILE.write_text(json.dumps(sorted(fired)))


def _count_missing() -> dict[str, int]:
    jobs = db.get_jobs(status=None, min_score=-1.0, limit=5000)
    freq: dict[str, int] = {}
    for job in jobs:
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


def _roadmap_prompt(skill: str, count: int) -> str:
    return (
        f'A job seeker is missing "{skill}" in {count} recent evaluations for '
        f"Data/AI roles (fresher, India market).\n\n"
        f"Provide a concise skill gap roadmap:\n"
        f"1. Fastest free learning path (specific course or resource name)\n"
        f"2. A small project to demonstrate the skill on GitHub\n"
        f"3. Estimated weeks to basic proficiency\n"
        f"4. Expected impact on interview callbacks\n\n"
        f"Under 80 words. No preamble."
    )


def check_and_fire() -> list[str]:
    cfg_path = Path(__file__).parent.parent / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    trigger = cfg.get("skill_gap", {}).get("trigger_count", _DEFAULT_TRIGGER)

    skill_counts = _count_missing()
    fired = _load_fired()
    messages: list[str] = []

    for skill, count in sorted(skill_counts.items(), key=lambda x: -x[1]):
        if count < trigger or skill in fired:
            continue
        roadmap = llm.write(_roadmap_prompt(skill, count))
        messages.append(
            f"🎯 *Skill Gap Alert: {skill.title()} ({count}× missing)*\n\n{roadmap}"
        )
        fired.add(skill)

    _save_fired(fired)
    return messages


if __name__ == "__main__":
    msgs = check_and_fire()
    if not msgs:
        print("No new skill gaps crossed the threshold.")
    else:
        print("\n---NEXT---\n".join(msgs))
