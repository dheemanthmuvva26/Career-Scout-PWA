"""
python-jobspy wrapper.

Scrapes LinkedIn, Indeed, and Glassdoor for each (company, role) pair.
Returns a list of normalised job dicts ready for dedup + DB insert.
"""

import time
import logging
from datetime import datetime, timezone
from typing import Optional

import yaml
from pathlib import Path

try:
    from jobspy import scrape_jobs
except ImportError:
    scrape_jobs = None   # allows import without crashing; runtime check below

logger = logging.getLogger(__name__)

_config: dict | None = None

def _cfg() -> dict:
    global _config
    if _config is None:
        cfg_path = Path(__file__).parent.parent / "config.yaml"
        with open(cfg_path) as f:
            _config = yaml.safe_load(f)
    return _config


# ── Normalisation ─────────────────────────────────────────────────────────────

def _norm_date(val) -> Optional[str]:
    """Convert jobspy date/datetime to ISO string."""
    if val is None:
        return None
    if isinstance(val, str):
        return val
    if hasattr(val, "isoformat"):
        dt = val
        if not hasattr(dt, "tzinfo") or dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc) if hasattr(dt, "replace") else dt
        return dt.isoformat()
    return str(val)


def _to_job_dict(row, source: str) -> dict:
    """Map a jobspy DataFrame row (as dict) → our canonical job dict."""
    title   = str(row.get("title") or "").strip()
    company = str(row.get("company") or "").strip()
    url     = str(row.get("job_url") or row.get("url") or "").strip()

    return {
        "title":       title,
        "company":     company,
        "location":    str(row.get("location") or "").strip(),
        "url":         url,
        "source_urls": [url] if url else [],
        "description": str(row.get("description") or "")[:5000],
        "source":      source,
        "posted_date": _norm_date(row.get("date_posted") or row.get("posted_date")),
    }


# ── Per-site scrape ───────────────────────────────────────────────────────────

_SITES = ["linkedin", "indeed", "glassdoor"]
_RESULTS_WANTED = 20      # per site per search term — generous but not abusive


def _scrape_one(search_term: str, location: str, site: str,
                hours_old: int, delay: float) -> list[dict]:
    """Run jobspy for a single site + search term. Returns normalised dicts."""
    if scrape_jobs is None:
        raise RuntimeError("python-jobspy not installed; run: pip install python-jobspy")

    try:
        df = scrape_jobs(
            site_name=site,
            search_term=search_term,
            location=location,
            results_wanted=_RESULTS_WANTED,
            hours_old=hours_old,
            country_indeed="India",      # keeps Indeed results India-scoped
        )
    except Exception as e:
        logger.warning("jobspy %s failed for '%s': %s", site, search_term, e)
        return []

    if df is None or df.empty:
        return []

    time.sleep(delay)
    return [_to_job_dict(row, site) for row in df.to_dict("records")]


# ── Public API ────────────────────────────────────────────────────────────────

def scrape(company_name: str, role_title: str,
           role_keywords: Optional[list[str]] = None) -> list[dict]:
    """
    Scrape LinkedIn + Indeed + Glassdoor for jobs matching role at company.

    Strategy:
      - Primary search: "{role_title} {company_name}"
      - If role_keywords provided, also search the first keyword alone
        (catches jobs not mentioning the exact title).
    """
    cfg  = _cfg()
    hours_old = cfg.get("hours_old", 72)
    delay     = cfg.get("scraping", {}).get("request_delay_seconds", 2)
    locations = cfg.get("locations", ["India"])

    search_terms = [f"{role_title} {company_name}"]
    if role_keywords:
        search_terms.append(role_keywords[0])

    results: list[dict] = []
    seen_urls: set[str] = set()

    for site in _SITES:
        for term in search_terms:
            for loc in locations[:2]:   # top 2 locations only to limit volume
                jobs = _scrape_one(term, loc, site, hours_old, delay)
                for job in jobs:
                    # Company filter: only keep jobs mentioning target company
                    if company_name.lower() not in job["company"].lower():
                        continue
                    # URL-level dedup within this batch
                    if job["url"] and job["url"] in seen_urls:
                        continue
                    if job["url"]:
                        seen_urls.add(job["url"])
                    results.append(job)

    logger.info(
        "jobspy: %s @ %s → %d raw results",
        role_title, company_name, len(results)
    )
    return results


def scrape_role_open(role_title: str,
                     role_keywords: Optional[list[str]] = None) -> list[dict]:
    """
    Scrape without company filter — used for broad role searches
    when no specific company careers page is targeted.
    """
    cfg  = _cfg()
    hours_old = cfg.get("hours_old", 72)
    delay     = cfg.get("scraping", {}).get("request_delay_seconds", 2)
    locations = cfg.get("locations", ["India"])

    results:   list[dict] = []
    seen_urls: set[str]   = set()

    search_terms = [role_title]
    if role_keywords:
        search_terms.append(role_keywords[0])

    for site in _SITES:
        for term in search_terms:
            for loc in locations[:2]:
                jobs = _scrape_one(term, loc, site, hours_old, delay)
                for job in jobs:
                    if job["url"] and job["url"] in seen_urls:
                        continue
                    if job["url"]:
                        seen_urls.add(job["url"])
                    results.append(job)

    logger.info("jobspy open: %s → %d raw results", role_title, len(results))
    return results
