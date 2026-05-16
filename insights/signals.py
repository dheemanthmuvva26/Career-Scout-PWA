"""
Company hiring-signal tracker and response-rate analyser.

Used by weekly_insights workflow and importable as a module.

Usage: python insights/signals.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db


def get_hiring_signals(threshold: int = 5) -> list[dict]:
    """Return companies whose jobs_this_week counter meets or exceeds threshold."""
    companies = db.get_active_companies()
    return [c for c in companies if c.get("jobs_this_week", 0) >= threshold]


def get_response_rates() -> dict[str, dict]:
    """
    Response rate (interview + offer) per job source, calculated over all
    applied jobs in the DB regardless of time window.
    """
    jobs = db.get_jobs(status="applied", min_score=-1.0, limit=5000)
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


def hiring_signal_messages(threshold: int = 5) -> list[str]:
    signals = get_hiring_signals(threshold)
    return [
        f"📈 *Hiring signal:* {c['name']} posted {c['jobs_this_week']} "
        f"Data/AI roles this week — they're actively hiring."
        for c in signals
    ]


if __name__ == "__main__":
    import yaml
    cfg = yaml.safe_load((Path(__file__).parent.parent / "config.yaml").read_text())
    threshold = cfg.get("hiring_signal", {}).get("threshold", 5)

    for msg in hiring_signal_messages(threshold):
        print(msg)

    rates = get_response_rates()
    if rates:
        print("\nResponse rates by source:")
        for src, data in sorted(rates.items(), key=lambda x: -x[1]["rate"]):
            print(f"  {src}: {data['responded']}/{data['applied']} ({data['rate']:.0%})")
    else:
        print("No application data yet.")
