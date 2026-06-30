"""
Paste-text job import — for job posts copied from WhatsApp, email, LinkedIn
feed posts, or anywhere else that isn't a scrapeable URL.

Unlike the URL scrapers, there's no HTML/JSON-LD structure to parse — the
LLM does the extraction directly from raw pasted text.
"""

import hashlib
import json

from core import llm

_EXTRACT_PROMPT = """Extract job posting details from this raw text (it may be a \
WhatsApp/LinkedIn post, email, or forwarded message — not a structured job page).

Return ONLY valid JSON with these exact keys:
{{
  "title": "job title, cleaned up (no emoji/hashtags)",
  "company": "company or organisation name",
  "location": "location(s) mentioned, or empty string if none",
  "description": "the full job description rewritten as clean plain text — include all \
skills, responsibilities, requirements, duration, and application instructions \
mentioned. Do not invent details not present in the source text.",
  "apply_contact": "an email address or application URL mentioned for applying, or empty string"
}}

If no company name is stated explicitly but an email address is given for applying, \
infer the company name from its domain (e.g. "jobs@acmecorp.io" → "Acmecorp").

If the text does not look like a job posting at all, set "title" to an empty string.

TEXT:
{text}
"""


def extract_job_from_text(raw_text: str, location_override: str = "") -> dict:
    """
    Use the LLM to pull structured job fields out of pasted free text.
    Raises ValueError if the text doesn't look like a job posting.
    """
    raw_text = (raw_text or "").strip()
    if not raw_text:
        raise ValueError("No text provided.")

    prompt = _EXTRACT_PROMPT.format(text=raw_text[:6000])
    response = llm.write(prompt, max_tokens=1200, json_mode=True)
    data = llm.parse_json(response)

    if data.get("error") or not data.get("title"):
        raise ValueError("Could not find a job posting in that text — try pasting the full post.")

    title   = data.get("title", "").strip()
    company = data.get("company", "").strip() or "Unknown Company"
    location = (location_override or data.get("location", "") or "").strip()
    description = data.get("description", "").strip() or raw_text
    contact = (data.get("apply_contact") or "").strip()

    # No real URL to key off — use the contact (email/link) if present,
    # otherwise hash the raw text so re-pasting the same post dedupes cleanly.
    if contact:
        pseudo_url = contact if contact.startswith("http") else f"mailto:{contact}"
    else:
        text_hash = hashlib.sha256(raw_text.encode()).hexdigest()[:16]
        pseudo_url = f"pasted://{text_hash}"

    return {
        "title": title,
        "company": company,
        "location": location,
        "url": pseudo_url,
        "description": description,
        "source": "pasted_text",
        "posted_date": "",
    }
