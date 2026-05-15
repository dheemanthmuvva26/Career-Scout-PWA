"""
Static career page scraper using requests + BeautifulSoup4.

Used for company career pages that render server-side HTML.
Content-hash caching prevents redundant re-scrapes.
Falls back to Playwright if the page appears to be JS-rendered.
"""

import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import yaml

from core import db

logger = logging.getLogger(__name__)

_config: dict | None = None

def _cfg() -> dict:
    global _config
    if _config is None:
        cfg_path = Path(__file__).parent.parent / "config.yaml"
        with open(cfg_path) as f:
            _config = yaml.safe_load(f)
    return _config

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _fetch(url: str, timeout: int = 15) -> Optional[str]:
    """Fetch URL, return HTML text or None on failure."""
    cfg = _cfg()
    max_retries = cfg.get("scraping", {}).get("max_retries", 3)
    delay       = cfg.get("scraping", {}).get("request_delay_seconds", 2)

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=timeout)
            resp.raise_for_status()
            time.sleep(delay)
            return resp.text
        except requests.RequestException as e:
            logger.warning("Fetch attempt %d/%d failed for %s: %s",
                           attempt + 1, max_retries, url, e)
            if attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))
    return None


def _is_js_heavy(html: str) -> bool:
    """Heuristic: page is probably JS-rendered if there's almost no visible text."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    return len(text) < 500


# ── Generic career page parser ────────────────────────────────────────────────

_JOB_LINK_PATTERN = re.compile(
    r"(job|career|position|opening|vacancy|role)", re.IGNORECASE
)

def _extract_jobs_generic(html: str, base_url: str, company: str) -> list[dict]:
    """
    Generic heuristic extraction for company career pages.
    Looks for links whose text or href contains job-related keywords.
    """
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href  = a["href"].strip()
        text  = a.get_text(separator=" ", strip=True)

        if not text or len(text) < 5 or len(text) > 200:
            continue
        if not (_JOB_LINK_PATTERN.search(text) or _JOB_LINK_PATTERN.search(href)):
            continue

        # Resolve relative URLs
        if href.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            href = f"{parsed.scheme}://{parsed.netloc}{href}"
        elif not href.startswith("http"):
            continue

        if href in seen:
            continue
        seen.add(href)

        jobs.append({
            "title":       text,
            "company":     company,
            "location":    "",
            "url":         href,
            "source_urls": [href],
            "description": "",
            "source":      "careers_page",
            "posted_date": None,
        })

    return jobs


def _extract_jobs_structured(html: str, base_url: str, company: str) -> list[dict]:
    """
    Structured extraction for pages with semantic markup.
    Looks for <li>/<article>/<div> blocks containing title + location patterns.
    """
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    # Try common job listing containers
    for container in soup.find_all(
        ["li", "article", "div"],
        class_=re.compile(r"job|position|opening|role|vacancy", re.IGNORECASE),
        limit=50
    ):
        title_el = (
            container.find(["h2", "h3", "h4", "a"],
                           class_=re.compile(r"title|name|role", re.IGNORECASE))
            or container.find(["h2", "h3", "h4"])
        )
        loc_el = container.find(
            string=re.compile(r"Mumbai|Pune|Bangalore|Hyderabad|Remote|Delhi|Chennai",
                              re.IGNORECASE)
        )
        link_el = container.find("a", href=True)

        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        if not title or len(title) > 150:
            continue

        href = link_el["href"] if link_el else ""
        if href and href.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            href = f"{parsed.scheme}://{parsed.netloc}{href}"

        jobs.append({
            "title":       title,
            "company":     company,
            "location":    loc_el.strip() if loc_el else "",
            "url":         href or base_url,
            "source_urls": [href or base_url],
            "description": "",
            "source":      "careers_page",
            "posted_date": None,
        })

    return jobs


# ── Public API ────────────────────────────────────────────────────────────────

def scrape_careers_page(company_name: str, careers_url: str,
                        role_keywords: Optional[list[str]] = None) -> list[dict]:
    """
    Scrape a company's static career page.

    Returns normalised job dicts. Applies content-hash cache — returns []
    if page hasn't changed since last scrape.
    """
    if not careers_url:
        return []

    html = _fetch(careers_url)
    if html is None:
        db.record_scraper_failure("static_scraper", f"fetch failed: {careers_url}")
        return []

    h = _content_hash(html)
    if db.get_cached_hash(careers_url) == h:
        logger.debug("Static cache hit: %s", careers_url)
        db.record_scraper_success("static_scraper")
        return []
    db.set_cached_hash(careers_url, h)

    if _is_js_heavy(html):
        logger.info("JS-heavy page detected, skipping static: %s", careers_url)
        db.record_scraper_success("static_scraper")
        return []

    # Try structured first, fall back to generic link extraction
    jobs = _extract_jobs_structured(html, careers_url, company_name)
    if not jobs:
        jobs = _extract_jobs_generic(html, careers_url, company_name)

    # Keyword filter if provided
    if role_keywords:
        kw_lower = [k.lower() for k in role_keywords]
        jobs = [
            j for j in jobs
            if any(kw in j["title"].lower() for kw in kw_lower)
        ]

    db.record_scraper_success("static_scraper")
    logger.info("Static: %s → %d jobs from %s", company_name, len(jobs), careers_url)
    return jobs
