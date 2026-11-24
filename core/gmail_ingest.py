"""
Job-alert email import: turns LinkedIn / Naukri / Indeed / Internshala alert
emails in Gmail into jobs in the tracker.

- Reads Gmail over IMAP with an App Password (GMAIL_ADDRESS +
  GMAIL_APP_PASSWORD). OAuth was rejected on purpose: Google expires refresh
  tokens for unverified apps every 7 days, which would silently break this.
- The mailbox is opened read-only and fetched with BODY.PEEK, so nothing in
  Gmail is ever modified (not even the read/unread state).
- LinkedIn alerts: job IDs are pulled from the links and each posting is
  fetched in full via the LinkedIn guest API (same path as URL import).
- Other senders: the LLM extracts the list of jobs from the email text.
- Each email is processed once (ingested_emails table); jobs go through the
  normal dedup -> save -> score pipeline.
"""

import email
import hashlib
import imaplib
import logging
import os
import re
import threading
import time
from email.header import decode_header, make_header
from pathlib import Path
from typing import Optional

import yaml
from bs4 import BeautifulSoup

from core import db

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_last_summary: dict = {}

_LINKEDIN_ID_RES = [
    re.compile(r"linkedin\.com/(?:comm/)?jobs/view/(\d{6,})"),
    re.compile(r"linkedin\.com%2F(?:comm%2F)?jobs%2Fview%2F(\d{6,})", re.I),
]


# ── Config ────────────────────────────────────────────────────────────────────

def _config() -> dict:
    cfg = yaml.safe_load((Path(__file__).parent.parent / "config.yaml").read_text(encoding="utf-8"))
    return cfg.get("gmail", {}) or {}


def is_configured() -> bool:
    return bool(os.environ.get("GMAIL_ADDRESS") and os.environ.get("GMAIL_APP_PASSWORD"))


def last_summary() -> dict:
    return _last_summary


def _title_passes(title: str, gmail_cfg: dict) -> bool:
    """Apply the include/exclude title keywords (whole-word matches, so short
    keywords like 'ai' or 'bi' don't match inside 'maintenance' or 'cabin')."""
    alerts = gmail_cfg.get("linkedin_alerts", {}) or {}
    t = (title or "").lower()

    def hit(kw: str) -> bool:
        kw = kw.strip().lower()
        return bool(kw) and re.search(r"\b" + re.escape(kw) + r"\b", t) is not None

    if any(hit(k) for k in alerts.get("exclude_title_keywords", []) or []):
        return False
    include = alerts.get("include_title_keywords", []) or []
    return not include or any(hit(k) for k in include)


# ── IMAP ──────────────────────────────────────────────────────────────────────

def _connect() -> imaplib.IMAP4_SSL:
    imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
    imap.login(os.environ["GMAIL_ADDRESS"], os.environ["GMAIL_APP_PASSWORD"])

    # Search All Mail (the \All special-use box) so alerts that a Gmail filter
    # archived or labelled are still found. Its display name is localised.
    mailbox = "INBOX"
    typ, boxes = imap.list()
    if typ == "OK":
        for raw in boxes or []:
            line = raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw)
            m = re.match(r'\((?P<flags>[^)]*)\) "[^"]*" (?P<name>.+)', line)
            if m and "\\All" in m.group("flags"):
                mailbox = m.group("name").strip()
                break
    if not mailbox.startswith('"'):
        mailbox = f'"{mailbox}"'
    imap.select(mailbox, readonly=True)
    return imap


def _search_uids(imap: imaplib.IMAP4_SSL, gmail_cfg: dict) -> list[bytes]:
    imp = gmail_cfg.get("alert_import", {}) or {}
    linkedin_sender = (gmail_cfg.get("linkedin_alerts", {}) or {}).get("sender", "jobs-noreply@linkedin.com")
    senders = [linkedin_sender] + list((imp.get("other_senders") or {}).values())
    days = int(imp.get("lookback_days", 3))
    query = f"from:({' OR '.join(senders)}) newer_than:{days}d"
    typ, data = imap.uid("SEARCH", "X-GM-RAW", f'"{query}"')
    if typ != "OK" or not data or not data[0]:
        return []
    return data[0].split()


def _decode(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _bodies(msg: email.message.Message) -> tuple[str, str]:
    """Return (html, plain) bodies of an email."""
    html, plain = "", ""
    for part in msg.walk() if msg.is_multipart() else [msg]:
        ctype = part.get_content_type()
        if part.get_content_maintype() == "multipart":
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if ctype == "text/html" and not html:
            html = text
        elif ctype == "text/plain" and not plain:
            plain = text
    return html, plain


def _source_for(sender: str, gmail_cfg: dict) -> Optional[str]:
    s = sender.lower()
    linkedin_sender = (gmail_cfg.get("linkedin_alerts", {}) or {}).get("sender", "jobs-noreply@linkedin.com")
    if linkedin_sender.lower() in s or "linkedin.com" in s:
        return "linkedin"
    for name, term in ((gmail_cfg.get("alert_import", {}) or {}).get("other_senders") or {}).items():
        if term.lower() in s:
            return name
    return None


# ── Parsers ───────────────────────────────────────────────────────────────────

def _linkedin_job_ids(html: str, plain: str) -> list[str]:
    ids: list[str] = []
    for text in (html, plain):
        for rx in _LINKEDIN_ID_RES:
            for jid in rx.findall(text or ""):
                if jid not in ids:
                    ids.append(jid)
    return ids


def _text_with_link_ids(html: str, plain: str) -> tuple[str, list[str]]:
    """Email text with each link replaced by a short [Ln] marker, so the LLM
    can point at a job's link without us sending long tracking URLs."""
    links: list[str] = []
    if not html:
        return (plain or "")[:8000], links
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["style", "script", "head"]):
        tag.decompose()
    for a in soup.find_all("a", href=True):
        href, txt = a["href"].strip(), a.get_text(" ", strip=True)
        low = href.lower()
        if txt and low.startswith("http") and "unsubscribe" not in low:
            links.append(href)
            a.replace_with(f"{txt} [L{len(links)}]")
        else:
            a.replace_with(txt)
    text = re.sub(r"\n\s*\n+", "\n", soup.get_text("\n"))
    return text[:8000], links


_EXTRACT_PROMPT = """Below is a job-alert email from {source}. Links appear as markers like [L3] right after the text they belong to.

Extract every distinct job posting listed in the email. Return JSON:
{{"jobs": [{{"title": "...", "company": "...", "location": "...", "link": "L3", "details": "..."}}]}}

Rules:
- link: the marker of that job's own posting link (not logo, settings or unsubscribe links). Empty string if none.
- details: one or two sentences of facts the email states about the job (experience, skills, salary, type). Empty if none.
- Only include jobs actually listed. If this email is not a job alert (application status, account notice, newsletter), return {{"jobs": []}}.
- Never invent jobs, companies, or details.

EMAIL SUBJECT: {subject}

EMAIL TEXT:
{text}
"""


def _extract_other(source: str, subject: str, html: str, plain: str) -> list[dict]:
    from core import llm
    text, links = _text_with_link_ids(html, plain)
    if not text.strip():
        return []
    raw = llm.write(_EXTRACT_PROMPT.format(source=source, subject=subject, text=text),
                    max_tokens=2000, json_mode=True)
    data = llm.parse_json(raw)
    jobs = []
    for j in data.get("jobs", []) or []:
        title = (j.get("title") or "").strip()
        company = (j.get("company") or "").strip()
        if not title or not company:
            continue
        m = re.fullmatch(r"L(\d+)", (j.get("link") or "").strip())
        url = links[int(m.group(1)) - 1] if m and 0 < int(m.group(1)) <= len(links) else ""
        if not url:
            key = hashlib.sha256(f"{source}|{title}|{company}".lower().encode()).hexdigest()[:16]
            url = f"email://{source}/{key}"
        details = (j.get("details") or "").strip()
        jobs.append({
            "title": title,
            "company": company,
            "location": (j.get("location") or "").strip(),
            "url": url,
            "description": f"{details}\n\n(Imported from a {source} job-alert email: {subject})".strip(),
            "source": f"email_{source}",
            "posted_date": "",
        })
    return jobs


# ── Ingestion ─────────────────────────────────────────────────────────────────

def _job_url_known(url: str) -> bool:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM jobs WHERE url=? OR source_urls LIKE ?", (url, f'%"{url}"%')
        ).fetchone()
    return row is not None


def _save(job: dict) -> Optional[str]:
    """dedup -> upsert. Returns the job id if it was newly inserted."""
    from core import urgency
    from scrapers import dedup
    job["urgency"] = urgency.classify(job.get("posted_date"))
    result = dedup.process(job)
    if result.action in ("insert", "repost"):
        db.upsert_job(job)
        return result.job_id
    return None


def run_sync(trigger: str = "manual") -> dict:
    """Process new job-alert emails. Safe to call concurrently (second caller
    gets status=busy). Never raises."""
    global _last_summary
    if not is_configured():
        return {"status": "not_configured",
                "message": "Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD on the backend."}
    if not _LOCK.acquire(blocking=False):
        return {"status": "busy"}

    started = time.time()
    summary = {"status": "ok", "trigger": trigger, "emails_seen": 0, "emails_processed": 0,
               "jobs_found": 0, "jobs_new": 0, "jobs_filtered": 0, "errors": []}
    new_ids: list[str] = []
    try:
        gmail_cfg = _config()
        imp = gmail_cfg.get("alert_import", {}) or {}
        if not imp.get("enabled", True):
            summary["status"] = "disabled"
            return summary
        cap = int(imp.get("max_jobs_per_run", 40))

        imap = _connect()
        try:
            uids = _search_uids(imap, gmail_cfg)
            summary["emails_seen"] = len(uids)
            for uid in reversed(uids):          # newest first
                if len(new_ids) >= cap:
                    break
                typ, data = imap.uid("FETCH", uid, "(BODY.PEEK[])")
                if typ != "OK" or not data or not isinstance(data[0], tuple):
                    continue
                raw = data[0][1]
                msg = email.message_from_bytes(raw)
                message_id = (msg.get("Message-ID") or "").strip() or \
                    "sha:" + hashlib.sha256(raw).hexdigest()[:32]
                if db.email_already_ingested(message_id):
                    continue

                source = _source_for(_decode(msg.get("From")), gmail_cfg)
                if not source:
                    continue
                subject = _decode(msg.get("Subject"))
                html, plain = _bodies(msg)
                failed = False

                if source == "linkedin":
                    candidates = []
                    for jid in _linkedin_job_ids(html, plain):
                        url = f"https://www.linkedin.com/jobs/view/{jid}/"
                        if _job_url_known(url):
                            continue
                        try:
                            from scrapers.linkedin_url_scraper import fetch_linkedin_job
                            job = fetch_linkedin_job(url)
                            job["source"] = "email_linkedin"
                            candidates.append(job)
                        except Exception as e:
                            failed = True
                            summary["errors"].append(f"linkedin {jid}: {str(e)[:120]}")
                        time.sleep(1)   # be gentle with the guest API
                else:
                    try:
                        candidates = _extract_other(source, subject, html, plain)
                    except Exception as e:
                        failed = True
                        candidates = []
                        summary["errors"].append(f"{source} '{subject[:60]}': {str(e)[:120]}")

                summary["jobs_found"] += len(candidates)
                for job in candidates:
                    if not _title_passes(job.get("title", ""), gmail_cfg):
                        summary["jobs_filtered"] += 1
                        continue
                    jid = _save(job)
                    if jid:
                        new_ids.append(jid)

                # Leave the email for the next run if a fetch failed, so a
                # transient LinkedIn/LLM error doesn't lose jobs for good.
                if not failed:
                    db.mark_email_ingested(message_id, source, len(candidates))
                    summary["emails_processed"] += 1
        finally:
            try:
                imap.logout()
            except Exception:
                pass

        summary["jobs_new"] = len(new_ids)
        if new_ids:
            from core import scorer
            scorer.score_pending(batch_size=len(new_ids) + 5)
            _notify(new_ids)
    except Exception as e:
        summary["status"] = "error"
        summary["errors"].append(str(e)[:300])
        logger.exception("gmail sync failed")
    finally:
        summary["duration_s"] = round(time.time() - started, 1)
        summary["finished_at"] = db.now_iso()
        summary["errors"] = summary["errors"][:10]
        _last_summary = summary
        _LOCK.release()
    return summary


def _notify(job_ids: list[str]) -> None:
    try:
        from core import push
        jobs = [j for j in (db.get_job(i) for i in job_ids) if j]
        jobs.sort(key=lambda j: j.get("score") or -1, reverse=True)
        top = "; ".join(f"{j['title']} @ {j['company']}" for j in jobs[:3])
        n = len(jobs)
        push.send_push(f"{n} new job{'s' if n != 1 else ''} from email alerts", top, "/jobs")
    except Exception as e:
        logger.warning("gmail sync notify failed: %s", e)


# ── Background scheduler ──────────────────────────────────────────────────────

_scheduler_started = False


def start_scheduler() -> None:
    """Poll Gmail every gmail.poll_interval_minutes in a daemon thread. Render
    keeps the process alive (keepalive pings), so no external cron is needed."""
    global _scheduler_started
    if _scheduler_started or not is_configured():
        return
    _scheduler_started = True

    def loop():
        time.sleep(60)   # let startup finish first
        while True:
            try:
                run_sync(trigger="scheduled")
            except Exception:
                logger.exception("scheduled gmail sync crashed")
            try:
                minutes = int(_config().get("poll_interval_minutes", 30))
            except Exception:
                minutes = 30
            time.sleep(max(minutes, 10) * 60)

    threading.Thread(target=loop, daemon=True, name="gmail-sync").start()
