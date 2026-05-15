"""
Playwright-based scraper for JS-heavy portals: Naukri and Internshala.

Each scraper function:
  - Takes a role title + optional keywords
  - Returns a list of normalised job dicts
  - Uses content-hash caching to skip unchanged pages
  - Records success/failure in scraper_health table
"""

import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _is_cached(url: str, new_hash: str) -> bool:
    old = db.get_cached_hash(url)
    return old is not None and old == new_hash


def _get_browser():
    """Launch a headless Chromium browser. Caller must close it."""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    return pw, browser


# ── Naukri scraper ────────────────────────────────────────────────────────────

_NAUKRI_BASE = "https://www.naukri.com/{query}-jobs"

def _naukri_search_url(role: str, location: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-")
    loc  = re.sub(r"[^a-z0-9]+", "-", location.lower()).strip("-")
    return f"https://www.naukri.com/{slug}-jobs-in-{loc}"


def scrape_naukri(role_title: str,
                  role_keywords: Optional[list[str]] = None) -> list[dict]:
    cfg       = _cfg()
    locations = cfg.get("locations", ["Mumbai", "Bangalore"])
    delay     = cfg.get("scraping", {}).get("request_delay_seconds", 2)
    results   = []

    try:
        pw, browser = _get_browser()
    except Exception as e:
        db.record_scraper_failure("playwright_naukri", str(e))
        logger.error("Playwright launch failed: %s", e)
        return []

    try:
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

        for loc in locations[:2]:
            url = _naukri_search_url(role_title, loc)
            try:
                page.goto(url, wait_until="networkidle", timeout=30_000)
                time.sleep(delay)

                html = page.content()
                h    = _content_hash(html)
                if _is_cached(url, h):
                    logger.debug("Naukri cache hit: %s", url)
                    continue
                db.set_cached_hash(url, h)

                # Extract job cards
                cards = page.query_selector_all("article.jobTuple, div.job-container, div[class*='jobTuple']")
                if not cards:
                    # Fallback: try generic job card selector
                    cards = page.query_selector_all("[class*='job-container'], [class*='jobCard']")

                for card in cards:
                    try:
                        title_el   = card.query_selector("a.title, a[class*='title'], .job-title a")
                        company_el = card.query_selector(".companyInfo .comp-name, span[class*='comp-name'], .comp-dtls-wrap span")
                        loc_el     = card.query_selector(".locWdth, span[class*='loc'], .location")
                        link_el    = card.query_selector("a.title, a[class*='title'], a[href*='naukri.com']")
                        date_el    = card.query_selector(".freshness, .job-post-day")

                        if not title_el or not company_el:
                            continue

                        title   = title_el.inner_text().strip()
                        company = company_el.inner_text().strip()
                        job_url = link_el.get_attribute("href") if link_el else url
                        job_loc = loc_el.inner_text().strip() if loc_el else loc
                        posted  = date_el.inner_text().strip() if date_el else ""

                        # Company filter from our list
                        results.append({
                            "title":       title,
                            "company":     company,
                            "location":    job_loc,
                            "url":         job_url or url,
                            "source_urls": [job_url or url],
                            "description": "",   # fetched separately if needed
                            "source":      "naukri",
                            "posted_date": _relative_to_iso(posted),
                        })
                    except Exception:
                        continue

            except Exception as e:
                logger.warning("Naukri page failed %s: %s", url, e)
                continue

        db.record_scraper_success("playwright_naukri")
        logger.info("Naukri: %s → %d jobs", role_title, len(results))

    except Exception as e:
        db.record_scraper_failure("playwright_naukri", str(e))
        logger.error("Naukri scraper error: %s", e)
    finally:
        browser.close()
        pw.stop()

    return results


# ── Internshala scraper ───────────────────────────────────────────────────────

def _internshala_search_url(role: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", role.lower()).strip("-")
    return f"https://internshala.com/jobs/{slug}-jobs"


def scrape_internshala(role_title: str,
                       role_keywords: Optional[list[str]] = None) -> list[dict]:
    cfg     = _cfg()
    delay   = cfg.get("scraping", {}).get("request_delay_seconds", 2)
    results = []

    try:
        pw, browser = _get_browser()
    except Exception as e:
        db.record_scraper_failure("playwright_internshala", str(e))
        logger.error("Playwright launch failed: %s", e)
        return []

    try:
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

        url = _internshala_search_url(role_title)
        try:
            page.goto(url, wait_until="networkidle", timeout=30_000)
            time.sleep(delay)

            html = page.content()
            h    = _content_hash(html)
            if _is_cached(url, h):
                logger.debug("Internshala cache hit: %s", url)
                db.record_scraper_success("playwright_internshala")
                return []
            db.set_cached_hash(url, h)

            cards = page.query_selector_all(".internship_meta, .job-internship-card, div[id*='internship_meta']")

            for card in cards:
                try:
                    title_el   = card.query_selector(".job-title a, .profile a, h3 a")
                    company_el = card.query_selector(".company-name, .company a")
                    loc_el     = card.query_selector(".locations span, .location_link")
                    link_el    = card.query_selector("a[href*='internshala.com/jobs/']")

                    if not title_el or not company_el:
                        continue

                    title   = title_el.inner_text().strip()
                    company = company_el.inner_text().strip()
                    job_url = link_el.get_attribute("href") if link_el else url
                    job_loc = loc_el.inner_text().strip() if loc_el else ""
                    if job_url and not job_url.startswith("http"):
                        job_url = "https://internshala.com" + job_url

                    results.append({
                        "title":       title,
                        "company":     company,
                        "location":    job_loc,
                        "url":         job_url or url,
                        "source_urls": [job_url or url],
                        "description": "",
                        "source":      "internshala",
                        "posted_date": None,
                    })
                except Exception:
                    continue

        except Exception as e:
            logger.warning("Internshala page failed: %s", e)

        db.record_scraper_success("playwright_internshala")
        logger.info("Internshala: %s → %d jobs", role_title, len(results))

    except Exception as e:
        db.record_scraper_failure("playwright_internshala", str(e))
        logger.error("Internshala scraper error: %s", e)
    finally:
        browser.close()
        pw.stop()

    return results


# ── Shared helpers ────────────────────────────────────────────────────────────

def _relative_to_iso(text: str) -> Optional[str]:
    """
    Convert Naukri relative dates like '2 days ago', 'Just now', '1 week ago'
    to an approximate ISO date string.
    """
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    t   = text.lower().strip()
    if not t or t in ("just now", "today"):
        return now.date().isoformat()

    m = re.search(r"(\d+)\s*(day|week|month|hour|minute)", t)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    delta = {
        "minute": timedelta(minutes=n),
        "hour":   timedelta(hours=n),
        "day":    timedelta(days=n),
        "week":   timedelta(weeks=n),
        "month":  timedelta(days=n * 30),
    }.get(unit, timedelta(days=n))
    return (now - delta).date().isoformat()
