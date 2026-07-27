"""
Scraper for Forage's (theforage.com) public job simulation catalog.

Builds a company -> simulation catalog so completed simulations can be
matched against jobs by company name (see core.db.find_completed_forage_sim)
and auto-included as a certification when forging a resume for that company.

Discovery: theforage.com/sitemap.xml lists every simulation page directly as
    https://www.theforage.com/simulations/<company-slug>/<sim-slug>
Each simulation page is server-rendered (no JS execution needed) and embeds
structured fields (skills, duration, difficulty, careers) as JSON inside an
inline Next.js script payload, alongside a plain <h1> title and an
"Introduction from <Company>" <h2> heading.
"""

import logging
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
import yaml

from core import db

logger = logging.getLogger(__name__)

_SITEMAP_URL = "https://www.theforage.com/sitemap.xml"
_SIM_URL_RE  = re.compile(r"https://www\.theforage\.com/simulations/([^/?]+)/([^/?]+)$")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_config: dict | None = None

def _cfg() -> dict:
    global _config
    if _config is None:
        cfg_path = Path(__file__).parent.parent / "config.yaml"
        with open(cfg_path) as f:
            _config = yaml.safe_load(f)
    return _config


def _fetch(url: str, timeout: int = 20) -> str | None:
    cfg = _cfg()
    max_retries = cfg.get("scraping", {}).get("max_retries", 3)
    delay       = cfg.get("scraping", {}).get("request_delay_seconds", 2)

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            logger.warning("Forage fetch attempt %d/%d failed for %s: %s",
                           attempt + 1, max_retries, url, e)
            if attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))
    return None


def get_catalog_urls() -> list[str]:
    """Every simulation page URL, discovered via the public sitemap."""
    html = _fetch(_SITEMAP_URL)
    if html is None:
        return []
    locs = re.findall(r"<loc>(.*?)</loc>", html)
    urls = [u for u in locs if _SIM_URL_RE.match(u)]
    return sorted(set(urls))


def _company_display_from_slug(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.split("-"))


def _unescape_unicode(s: str) -> str:
    """Resolve literal \\uXXXX escape sequences left over from regex-extracting
    out of a raw (not json.loads'd) JSON payload, e.g. 'Banking \\u0026 Finance'."""
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s)


def parse_sim_page(url: str) -> dict | None:
    """Fetch and parse a single simulation page into a normalized dict."""
    m = _SIM_URL_RE.match(url)
    if not m:
        return None
    company_slug, sim_slug = m.group(1), m.group(2)

    html = _fetch(url)
    if html is None:
        return None

    soup = BeautifulSoup(html, "html.parser")

    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else sim_slug.replace("-", " ").title()

    company = _company_display_from_slug(company_slug)
    for h2 in soup.find_all(["h2", "h3"]):
        text = h2.get_text(strip=True)
        if text.startswith("Introduction from "):
            company = text[len("Introduction from "):].strip()
            break

    # Some pages ship this JSON payload with escaped quotes (nested one level
    # deeper in React's server-component stream) — normalize before regexing.
    flat = html.replace('\\"', '"')

    duration_m   = re.search(r'"calculatedTimeGuidance":"([^"]+)"', flat)
    difficulty_m = re.search(r'"difficulty":"([^"]+)"', flat)
    skills       = re.findall(r'"skillText":"([^"]+)"', flat)
    careers_m    = re.search(r'"careers":\[(.*?)\]', flat)
    careers      = re.findall(r'"([^"]+)"', careers_m.group(1)) if careers_m else []

    return {
        "id": f"{company_slug}__{sim_slug}",
        "company_slug": company_slug,
        "company": company,
        "title": title,
        "url": url,
        "duration": duration_m.group(1) if duration_m else "",
        "difficulty": difficulty_m.group(1) if difficulty_m else "",
        "skills": [_unescape_unicode(s) for s in dict.fromkeys(skills)][:10],
        "careers": [_unescape_unicode(c) for c in careers],
    }


def sync_catalog(limit: int = 30) -> dict:
    """
    Discover the full catalog, then fetch+store up to `limit` simulations not
    already in the DB. Safe to call repeatedly — subsequent calls only pick
    up newly-added simulations (existing ones are never re-fetched).
    """
    delay = _cfg().get("scraping", {}).get("request_delay_seconds", 2)

    all_urls = get_catalog_urls()
    if not all_urls:
        db.record_scraper_failure("forage_scraper", "sitemap fetch failed or empty")
        return {"total_catalog": 0, "new_added": 0, "remaining": 0, "error": "Could not read Forage sitemap"}

    new_urls = [u for u in all_urls if not db.forage_sim_exists(u)]
    to_process = new_urls[:limit]

    added = 0
    for url in to_process:
        sim = parse_sim_page(url)
        if sim:
            db.upsert_forage_sim(sim)
            added += 1
        time.sleep(delay)

    db.record_scraper_success("forage_scraper")
    return {
        "total_catalog": len(all_urls),
        "new_added": added,
        "remaining": len(new_urls) - added,
    }
