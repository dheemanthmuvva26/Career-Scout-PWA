"""
Fetch a single LinkedIn job URL and return a canonical job dict.

Strategy:
  1. Parse JSON-LD <script type="application/ld+json"> — most reliable
  2. Fall back to HTML tag extraction if JSON-LD is absent/incomplete

Handles URL forms:
  https://www.linkedin.com/jobs/view/1234567890/
  https://www.linkedin.com/jobs/view/title-at-company-1234567890/
  https://in.linkedin.com/jobs/view/...
  URLs with ?trk= / other query params (stripped automatically)
"""

import json
import logging
import re
from typing import Optional

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

_LI_JOB_RE = re.compile(
    r"https?://[a-z.]*linkedin\.com/jobs/(?:view|collections/[^/]+)\S*"
)
_JOB_ID_RE = re.compile(r"/(?:view|currentJobId=)[\w-]*?(\d{8,})")


def _canonical_url(url: str) -> str:
    """Strip query/fragment, keep only the clean /jobs/view/<id>/ form."""
    url = url.strip()
    m = _JOB_ID_RE.search(url)
    if m:
        return f"https://www.linkedin.com/jobs/view/{m.group(1)}/"
    # Return cleaned URL if no numeric ID found (let the fetch resolve it)
    return url.split("?")[0].split("#")[0].rstrip("/") + "/"


def fetch_linkedin_job(url: str) -> dict:
    """
    Fetch a LinkedIn job page and return a normalised job dict.

    Raises ValueError for non-LinkedIn URLs, failed fetches, or login walls.
    Raises requests.RequestException on network errors.
    """
    if not re.search(r"linkedin\.com/jobs/", url):
        raise ValueError("Not a LinkedIn job URL. Share the link from the LinkedIn job page.")

    clean_url = _canonical_url(url)
    logger.info("Fetching LinkedIn job: %s", clean_url)

    resp = requests.get(clean_url, headers=_HEADERS, timeout=20, allow_redirects=True)

    # Detect login wall redirect
    if "linkedin.com/login" in resp.url or "linkedin.com/authwall" in resp.url:
        raise ValueError(
            "LinkedIn requires login to view this job. "
            "Try sharing the public URL (open the job in a private/incognito window first)."
        )

    if resp.status_code == 404:
        raise ValueError("Job not found on LinkedIn — it may have been removed.")
    if resp.status_code != 200:
        raise ValueError(f"LinkedIn returned HTTP {resp.status_code}.")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Detect soft redirects to login / search results pages
    page_title = (soup.title.string or "") if soup.title else ""
    if "sign in" in page_title.lower() or "join now" in page_title.lower():
        raise ValueError(
            "LinkedIn requires login to view this job. "
            "Open the job in a private/incognito window and copy the URL from there."
        )
    if "jobs in " in page_title.lower() or re.search(r"\d,\d{3}\+", page_title):
        raise ValueError(
            "LinkedIn redirected to a search page — the job may have expired or the URL is incomplete. "
            "Copy the full URL directly from the job's page."
        )

    # 1. JSON-LD (preferred)
    job = _parse_json_ld(soup, clean_url)
    if job and job.get("title"):
        return job

    # 2. HTML fallback
    job = _parse_html(soup, clean_url)
    if job and job.get("title"):
        return job

    raise ValueError(
        "Could not extract job details from this LinkedIn page. "
        "The job may require login or may have been removed."
    )


# ── JSON-LD extraction ────────────────────────────────────────────────────────

def _parse_json_ld(soup: BeautifulSoup, url: str) -> Optional[dict]:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            raw = script.string or ""
            data = json.loads(raw)
            # May be a list
            if isinstance(data, list):
                data = next(
                    (d for d in data if d.get("@type") == "JobPosting"), None
                )
            if not data or data.get("@type") != "JobPosting":
                continue

            title = (data.get("title") or "").strip()
            if not title:
                continue

            org = data.get("hiringOrganization") or {}
            company = (org.get("name") or "").strip() if isinstance(org, dict) else ""

            # Location: can be dict or list of dicts
            loc_raw = data.get("jobLocation") or {}
            if isinstance(loc_raw, list):
                loc_raw = loc_raw[0] if loc_raw else {}
            addr = (loc_raw.get("address") or {}) if isinstance(loc_raw, dict) else {}
            location_parts = []
            for key in ("addressLocality", "addressRegion", "addressCountry"):
                val = addr.get(key, "") if isinstance(addr, dict) else ""
                if val and isinstance(val, str):
                    location_parts.append(val)
            location = ", ".join(location_parts)

            # Description — strip HTML tags
            desc_html = data.get("description") or ""
            description = BeautifulSoup(desc_html, "html.parser").get_text(
                separator="\n", strip=True
            )[:5000]

            posted_date = data.get("datePosted") or data.get("validThrough")

            if not company:
                company = _html_company(soup)

            return {
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "source_urls": [url],
                "description": description,
                "source": "linkedin_import",
                "posted_date": posted_date,
            }
        except Exception as exc:
            logger.debug("JSON-LD parse error: %s", exc)
            continue
    return None


# ── HTML fallback extraction ──────────────────────────────────────────────────

def _html_company(soup: BeautifulSoup) -> str:
    for sel in [
        "a.topcard__org-name-link",
        ".top-card-layout__company",
        ".topcard__flavor:first-child",
        "[data-tracking-control-name='public_jobs_topcard-org-name']",
    ]:
        el = soup.select_one(sel)
        if el:
            return el.get_text(strip=True)
    return ""


def _parse_html(soup: BeautifulSoup, url: str) -> Optional[dict]:
    title_el = soup.select_one(
        "h1.top-card-layout__title, h1.topcard__title, "
        ".job-details-jobs-unified-top-card__job-title, h1"
    )
    title = title_el.get_text(strip=True) if title_el else ""

    company = _html_company(soup)

    loc_el = soup.select_one(
        ".topcard__flavor--bullet, "
        ".job-details-jobs-unified-top-card__bullet, "
        ".job-details-jobs-unified-top-card__workplace-type"
    )
    location = loc_el.get_text(strip=True) if loc_el else ""

    desc_el = soup.select_one(
        ".show-more-less-html__markup, "
        ".description__text, "
        ".jobs-description-content__text"
    )
    description = (
        desc_el.get_text(separator="\n", strip=True)[:5000] if desc_el else ""
    )

    if not title:
        return None

    return {
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "source_urls": [url],
        "description": description,
        "source": "linkedin_import",
        "posted_date": None,
    }
