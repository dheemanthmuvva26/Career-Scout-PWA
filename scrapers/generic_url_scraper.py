"""
Generic job URL scraper — for company career sites, ATS platforms
(Greenhouse, Lever, Workday, SmartRecruiters, etc.), and any non-LinkedIn URL.

Strategy:
  1. application/ld+json JobPosting — most ATS platforms embed this for SEO
  2. OpenGraph / meta tags — og:title, og:description
  3. HTML heuristics — h1 for title, common company-name selectors

Works without per-site logic because most ATS platforms (Greenhouse, Lever,
Workday, SmartRecruiters, Ashby, Workable) all emit schema.org JobPosting.
"""

import json
import logging
import re
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _clean_html(raw: str) -> str:
    text = BeautifulSoup(raw, "html.parser").get_text(separator="\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", text)


def _parse_json_ld(soup: BeautifulSoup) -> Optional[dict]:
    """Find a JobPosting in any application/ld+json block (handles @graph too)."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except Exception:
            continue

        candidates = data if isinstance(data, list) else [data]
        # Some sites nest postings inside a @graph array
        expanded = []
        for d in candidates:
            if isinstance(d, dict) and "@graph" in d:
                expanded.extend(d["@graph"])
            else:
                expanded.append(d)

        for d in expanded:
            if isinstance(d, dict) and d.get("@type") in ("JobPosting", ["JobPosting"]):
                return d
    return None


def _extract_location(ld: dict) -> str:
    loc = ld.get("jobLocation")
    if not loc:
        return ""
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    addr = loc.get("address", {}) if isinstance(loc, dict) else {}
    if isinstance(addr, str):
        return addr
    parts = [addr.get("addressLocality", ""), addr.get("addressRegion", ""), addr.get("addressCountry", "")]
    return ", ".join(p for p in parts if p)


def _extract_company(ld: dict, soup: BeautifulSoup, url: str) -> str:
    org = ld.get("hiringOrganization")
    if isinstance(org, dict) and org.get("name"):
        return org["name"].strip()
    if isinstance(org, str) and org.strip():
        return org.strip()
    # Fallback: site name from og:site_name or domain
    site_name = soup.find("meta", attrs={"property": "og:site_name"})
    if site_name and site_name.get("content"):
        return site_name["content"].strip()
    domain = urlparse(url).netloc.replace("www.", "").split(".")[0]
    return domain.capitalize()


def fetch_job_from_url(url: str, location_override: str = "") -> dict:
    """
    Fetch any job posting URL and return a normalised job dict.
    Raises ValueError if no job data could be extracted.
    """
    resp = requests.get(url, headers=_HEADERS, timeout=20, allow_redirects=True)
    if resp.status_code >= 400:
        raise ValueError(f"Page returned HTTP {resp.status_code}")

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Strategy 1: JSON-LD JobPosting ──────────────────────────────────────
    ld = _parse_json_ld(soup)
    if ld:
        title = (ld.get("title") or "").strip()
        if title:
            return {
                "title":        title,
                "company":      _extract_company(ld, soup, url),
                "location":     location_override.strip() or _extract_location(ld),
                "url":          url,
                "source_urls":  [url],
                "description":  _clean_html(ld.get("description", ""))[:8000],
                "source":       "url_import",
                "posted_date":  (ld.get("datePosted") or "")[:10] or None,
            }

    # ── Strategy 2: OpenGraph / meta tags ───────────────────────────────────
    def meta(prop: str) -> str:
        tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        return (tag.get("content") or "").strip() if tag else ""

    og_title = meta("og:title") or (soup.title.string if soup.title else "")
    og_desc  = meta("og:description") or meta("description")

    title, company = "", ""
    if " at " in og_title:
        parts = og_title.split(" at ", 1)
        title, company = parts[0].strip(), parts[1].strip()
    elif " - " in og_title:
        parts = og_title.split(" - ", 1)
        title, company = parts[0].strip(), parts[1].strip()
    else:
        title = og_title.strip()

    # ── Strategy 3: HTML heuristics ─────────────────────────────────────────
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""

    if not title:
        raise ValueError(
            "Could not extract job details from this page. "
            "The site may require JavaScript rendering or login."
        )

    if not company:
        company = _extract_company({}, soup, url)

    body_text = og_desc or soup.get_text(separator=" ", strip=True)[:2000]

    return {
        "title":        title,
        "company":      company or "Unknown",
        "location":     location_override.strip(),
        "url":          url,
        "source_urls":  [url],
        "description":  body_text[:8000],
        "source":       "url_import",
        "posted_date":  None,
    }
