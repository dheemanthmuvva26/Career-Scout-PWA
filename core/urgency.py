"""
Urgency tier assignment based on job posting age.

Tiers:
    hot    — posted < 24h
    active — posted 1–4 days
    aging  — posted 5–10 days
    stale  — posted > 10 days
"""

from datetime import datetime, timezone
from typing import Optional
from pathlib import Path
import yaml

_config: dict | None = None


def _get_thresholds() -> tuple[int, int, int]:
    global _config
    if _config is None:
        cfg_path = Path(__file__).parent.parent / "config.yaml"
        with open(cfg_path) as f:
            _config = yaml.safe_load(f)
    u = _config["urgency"]
    return u["hot_hours"], u["active_hours"], u["aging_hours"]


def _parse_posted_date(posted_date: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            s = posted_date[:len(fmt)]
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def classify(posted_date: Optional[str]) -> str:
    """Return urgency tier string for a posted_date ISO string."""
    if not posted_date:
        return "active"
    dt = _parse_posted_date(posted_date)
    if dt is None:
        return "active"

    age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    hot_h, active_h, aging_h = _get_thresholds()

    if age_h < hot_h:
        return "hot"
    elif age_h < active_h:
        return "active"
    elif age_h < aging_h:
        return "aging"
    else:
        return "stale"


def age_hours(posted_date: Optional[str]) -> float:
    """Return posting age in hours. Returns 9999 if unparseable."""
    if not posted_date:
        return 9999.0
    dt = _parse_posted_date(posted_date)
    if dt is None:
        return 9999.0
    return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
