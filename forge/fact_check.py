"""
Resume fact checker.

The forge optimizer (an LLM) reliably invents numbers and outcomes —
"reduced complications by 18%", "92% relevance accuracy", "cut reporting
from 8 to 2 hours" — none of which exist in master_profile.yaml. This module
checks every generated bullet against its own source entry in the master
profile and either repairs the resume (forge output) or reports problems
(user edits).

Pure module: no file, DB, or network access. The caller passes in the master
profile, and optionally a `judge` callable for the LLM claim check, so the
whole thing is testable offline.

Two checks:
  1. Numbers (deterministic): every number in a bullet must appear in that
     same experience/project entry in the master profile (summary may use any
     number from the whole profile). Units are kept distinct so "20%" doesn't
     pass because the source says "20,000+".
  2. Claims (LLM judge, optional): catches unsupported claims with no numbers
     ("informed senior management's pricing strategy"). Fails open — if the
     judge errors, the report says the claim check was skipped.
"""

from __future__ import annotations

import difflib
import re
from datetime import date
from typing import Callable, Optional

# ── Number extraction ─────────────────────────────────────────────────────────

_MINUS = "−–—"  # unicode minus, en dash, em dash
_NUM_RE = re.compile(
    r"(?<![\w.])"
    r"[+\-" + _MINUS + r"±~]?"
    r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
    r"(\+?)"
    r"\s?(%|percent\b|k\b|K\b|M\b|million\b|mn\b|crore\b|cr\b|lakh\b|lakhs\b|x\b|×)?",
)
_SCALE = {"k": 1e3, "m": 1e6, "million": 1e6, "mn": 1e6,
          "crore": 1e7, "cr": 1e7, "lakh": 1e5, "lakhs": 1e5}


def extract_numbers(text: str) -> list[tuple[float, str, str]]:
    """Return [(value, unit, raw)] for every number in text.
    unit is "%" for percentages, "x" for multipliers, "n" otherwise.
    Signs are ignored on purpose: "−17.3%" and "-17.3%" and "17.3%" all match."""
    out = []
    matches = list(_NUM_RE.finditer(text or ""))
    for i, m in enumerate(matches):
        raw_num, _plus, suffix = m.group(1), m.group(2), (m.group(3) or "")
        try:
            value = float(raw_num.replace(",", ""))
        except ValueError:
            continue
        s = suffix.lower()
        # "15-17%" / "15 to 17%": the unit of the second number applies to both.
        if not s and i + 1 < len(matches):
            gap = (text or "")[m.end():matches[i + 1].start()]
            if re.fullmatch(r"\s*(?:[-" + _MINUS + r"]|to)\s*", gap) or gap == "":
                s = (matches[i + 1].group(3) or "").lower()
        if s in ("%", "percent"):
            unit = "%"
        elif s in ("x", "×"):
            unit = "x"
        else:
            unit = "n"
            value *= _SCALE.get(s, 1)
        out.append((value, unit, m.group(0).strip()))
    return out


def _decimals(raw: str) -> int:
    m = re.search(r"\d+\.(\d+)", raw)
    return len(m.group(1)) if m else 0


def _is_year(value: float, unit: str) -> bool:
    return unit == "n" and value == int(value) and 1990 <= value <= 2035


def _same(a: float, b: float) -> bool:
    return abs(a - b) <= max(1e-6, 1e-9 * max(abs(a), abs(b)))


def unsupported_numbers(text: str, allowed: list[tuple[float, str, str]]) -> list[str]:
    """Numbers in `text` that don't appear (same value AND unit) in `allowed`.
    Calendar years are always allowed — they're dates, not metrics."""
    bad = []
    for value, unit, raw in extract_numbers(text):
        if _is_year(value, unit):
            continue
        # Rounding a real figure is fine ("15%" from a source "15.1%"); only
        # applies to plain values — "225k" style scaled values must match exactly.
        places = _decimals(raw)
        if not any(u == unit and (_same(v, value) or (u != "n" or v < 1000) and round(v, places) == value)
                   for v, u, _ in allowed):
            bad.append(raw)
    return bad


# ── Master profile helpers ────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _find_entry(name: str, entries: list[dict], key: str) -> Optional[dict]:
    target = _norm(name)
    if not target:
        return None
    for e in entries:
        if _norm(e.get(key, "")) == target:
            return e
    best, best_ratio = None, 0.0
    for e in entries:
        r = difflib.SequenceMatcher(None, target, _norm(e.get(key, ""))).ratio()
        if r > best_ratio:
            best, best_ratio = e, r
    return best if best_ratio >= 0.8 else None


def _entry_texts(entry: dict) -> list[str]:
    texts = [b["text"] if isinstance(b, dict) else str(b) for b in entry.get("bullets", [])]
    for k in ("description", "name", "company", "role", "dates", "sponsor", "status"):
        if entry.get(k):
            texts.append(str(entry[k]))
    texts.extend(str(t) for t in entry.get("tech", []))
    return texts


def _bullet_texts(entry: dict) -> list[str]:
    return [b["text"] if isinstance(b, dict) else str(b) for b in entry.get("bullets", [])]


def _all_profile_numbers(master: dict) -> list[tuple[float, str, str]]:
    nums: list[tuple[float, str, str]] = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, (str, int, float)):
            nums.extend(extract_numbers(str(x)))

    walk({k: v for k, v in master.items() if k != "personal"})
    return nums


def _known_skills(master: dict) -> set[str]:
    known = set()
    for items in (master.get("skills") or {}).values():
        known.update(_norm(s) for s in items)
    for p in master.get("projects", []):
        known.update(_norm(t) for t in p.get("tech", []))
    return known


def graduation_status(master: dict, today: Optional[date] = None) -> dict:
    """{"graduated": bool, "end_year": int|None} from the first education entry.
    A degree whose end year has passed (after June of that year) counts as
    completed — used to stop suggestions like "currently in final year"."""
    today = today or date.today()
    edu = (master.get("education") or [{}])[0]
    years = [int(y) for y in re.findall(r"(?:19|20)\d{2}", str(edu.get("dates", edu.get("graduation", ""))))]
    if not years:
        return {"graduated": False, "end_year": None}
    end = max(years)
    graduated = today > date(end, 6, 30)
    return {"graduated": graduated, "end_year": end}


# ── Summary sentence handling ─────────────────────────────────────────────────

def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", (text or "").strip())
    return [p for p in parts if p.strip()]


# ── Main entry point ──────────────────────────────────────────────────────────

Judge = Callable[[list[dict]], dict]
"""judge(items) -> {item_id: reason} for items whose claims are unsupported.
Each item: {"id": str, "text": str, "sources": [str, ...]}."""


def check_resume(optimized: dict, master: dict, *, mode: str = "repair",
                 allowed_certs: Optional[list[dict]] = None,
                 judge: Optional[Judge] = None) -> tuple[dict, dict]:
    """
    Check (and in "repair" mode, fix) an optimized resume against the master profile.

    mode="repair": forge output — unsupported bullets are swapped for an unused
        verbatim bullet from the same entry (or dropped), unknown skills/certs are
        removed, header fields are forced from the master profile.
    mode="warn": user edits — nothing is changed, every problem is reported.

    allowed_certs: certs that may appear besides the master's own (the role
        pool from certs_by_role.yaml, a completed Forage sim). Those not in the
        master profile are kept but flagged "enroll before sending".

    Returns (resume, report). In warn mode `resume` is the input, untouched.
    """
    import copy
    repair = mode == "repair"
    out = copy.deepcopy(optimized) if repair else optimized
    issues: list[dict] = []
    warnings: list[str] = []

    def issue(section, entry, text, reason, action="flagged", replacement=None):
        issues.append({"section": section, "entry": entry, "text": text, "reason": reason,
                       "action": action if repair else "flagged",
                       **({"replacement": replacement} if replacement else {})})

    # ── Experience + projects: numbers ────────────────────────────────────────
    judge_items: list[dict] = []
    sections = (
        ("experience", "selected_experience", master.get("experience", []), "company"),
        ("projects", "selected_projects", master.get("projects", []), "name"),
    )
    for section, key, master_entries, name_key in sections:
        kept_entries = []
        for entry in out.get(key, []) or []:
            label = entry.get(name_key, "")
            src = _find_entry(label, master_entries, name_key)
            if src is None:
                issue(section, label, label, "not in your master profile", "dropped entry")
                if not repair:
                    kept_entries.append(entry)
                continue

            if repair:
                # Header facts always come from the master profile, never the LLM.
                if section == "experience":
                    for f in ("company", "role", "dates", "location"):
                        entry[f] = src.get(f, "")
                else:
                    entry["name"] = src["name"]
                    master_tech = {_norm(t): t for t in src.get("tech", [])}
                    tech = [master_tech[_norm(t)] for t in entry.get("tech", []) if _norm(t) in master_tech]
                    entry["tech"] = tech or list(src.get("tech", []))
            elif section == "experience":
                for f in ("role", "dates"):
                    if entry.get(f) and _norm(entry[f]) != _norm(src.get(f, "")):
                        issue(section, label, entry[f], f"{f} differs from your profile ({src.get(f, '')})")

            allowed = [n for t in _entry_texts(src) for n in extract_numbers(t)]
            source_bullets = _bullet_texts(src)
            new_bullets = []
            for b in entry.get("bullets", []) or []:
                bad = unsupported_numbers(b, allowed)
                if bad:
                    issue(section, label, b, f"numbers not in this entry of your profile: {', '.join(bad)}")
                    new_bullets.append(None)  # placeholder, repaired below
                else:
                    new_bullets.append(b)
                    judge_items.append({"id": f"{section}|{src.get(name_key)}|{len(new_bullets)-1}",
                                        "text": b, "sources": source_bullets})
            entry["_bullets_tmp"] = new_bullets
            entry["_src"] = src
            kept_entries.append(entry)
        if repair:
            out[key] = kept_entries

    # ── LLM claim check (numbers-free fabrications) ───────────────────────────
    claim_check = "not run"
    flagged_claims: dict = {}
    summary_text = out.get("summary", "")
    if judge is not None:
        items = list(judge_items)
        if summary_text:
            items.append({"id": "summary", "text": summary_text,
                          "sources": _summary_sources(master)})
        try:
            flagged_claims = judge(items) or {}
            claim_check = "ok"
        except Exception as e:  # fail open, but visibly
            claim_check = f"skipped: {str(e)[:120]}"
            warnings.append("The claim check (for made-up outcomes without numbers) could not run — review bullets by hand.")

    for section, key, _m, name_key in sections:
        for entry in out.get(key, []) or []:
            src = entry.pop("_src", None)
            tmp = entry.pop("_bullets_tmp", None)
            if tmp is None:
                continue
            label = entry.get(name_key, "")
            for i, b in enumerate(tmp):
                cid = f"{section}|{src.get(name_key) if src else label}|{i}"
                if b is not None and cid in flagged_claims:
                    issue(section, label, b, f"claim not supported by your profile: {flagged_claims[cid]}")
                    tmp[i] = None
            if repair and src is not None:
                entry["bullets"] = _repair_bullets(tmp, entry.get("bullets", []), _bullet_texts(src), issues, section, label)

    # ── Summary ───────────────────────────────────────────────────────────────
    profile_nums = _all_profile_numbers(master)
    if summary_text:
        bad = unsupported_numbers(summary_text, profile_nums)
        claim_reason = flagged_claims.get("summary")
        if bad or claim_reason:
            reason = (f"numbers not in your profile: {', '.join(bad)}" if bad
                      else f"claim not supported by your profile: {claim_reason}")
            if repair:
                kept = [s for s in _sentences(summary_text) if not unsupported_numbers(s, profile_nums)]
                if claim_reason and not bad:
                    kept = []  # judge flags the summary as a whole; rebuild it
                new_summary = " ".join(kept) or _fallback_summary(master)
                issue("summary", "Summary", summary_text, reason, "rewritten", new_summary)
                out["summary"] = new_summary
            else:
                issue("summary", "Summary", summary_text, reason)

    # ── Skills ────────────────────────────────────────────────────────────────
    known = _known_skills(master)
    skills = out.get("skills_section") or {}
    for cat in list(skills):
        keep = []
        for s in skills[cat] or []:
            if _norm(s) in known:
                keep.append(s)
            else:
                issue("skills", cat, s, "skill not in your profile", "removed")
        if repair:
            if keep:
                skills[cat] = keep
            else:
                del skills[cat]

    # ── Certifications ────────────────────────────────────────────────────────
    master_certs = {_norm(c["name"]): c for c in master.get("certifications", [])}
    extra_certs = {_norm(c["name"]): c for c in (allowed_certs or [])}
    certs = out.get("selected_certifications")
    if certs:
        keep = []
        for c in certs:
            n = _norm(c.get("name", ""))
            if n in master_certs:
                keep.append(master_certs[n] if repair else c)
            elif n in extra_certs:
                keep.append(c)
                if str(c.get("date", "")).lower() != "completed":
                    warnings.append(f"\"{c.get('name')}\" isn't in your profile yet — enroll before sending this resume.")
            else:
                issue("certifications", c.get("name", ""), c.get("name", ""), "certification not in your profile", "removed")
        if repair:
            out["selected_certifications"] = [{k: v for k, v in c.items() if k in ("name", "issuer", "date")} for c in keep]

    report = {
        "ok": not issues,
        "mode": mode,
        "issues": issues,
        "warnings": warnings,
        "claim_check": claim_check,
    }
    return out, report


def _repair_bullets(tmp: list, original: list, source: list[str], issues: list,
                    section: str, label: str) -> list[str]:
    """Replace each None in tmp with the most similar unused verbatim source
    bullet; drop it when none are left. Records the action on the issue.
    A kept (rewritten) bullet "uses up" the source bullet it was written from,
    so the repair never puts the same fact on the resume twice."""
    used: set[str] = set()
    for b in tmp:
        if b is not None and source:
            used.add(_norm(max(source, key=lambda s: _overlap(b, s))))
    result = []
    for i, b in enumerate(tmp):
        if b is not None:
            result.append(b)
            continue
        bad_text = original[i] if i < len(original) else ""
        candidates = [s for s in source if _norm(s) not in used]
        # Find the issue we logged for this bullet to annotate the action.
        rec = next((x for x in reversed(issues)
                    if x["section"] == section and x["entry"] == label and x["text"] == bad_text
                    and x["action"] == "flagged"), None)
        if candidates:
            best = max(candidates, key=lambda s: _overlap(bad_text, s))
            used.add(_norm(best))
            result.append(best)
            if rec:
                rec["action"], rec["replacement"] = "replaced with your original bullet", best
        elif rec:
            rec["action"] = "dropped"
    return result


_STOP = {"a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "by", "using",
         "across", "into", "from", "that", "as", "at", "via", "its", "their", "is", "are"}


def _overlap(a: str, b: str) -> float:
    """Word-overlap similarity (Jaccard on content words) — more reliable than
    character similarity for long, reworded sentences."""
    wa = {w for w in _norm(a).split() if w not in _STOP}
    wb = {w for w in _norm(b).split() if w not in _STOP}
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def _summary_sources(master: dict) -> list[str]:
    edu = (master.get("education") or [{}])[0]
    srcs = [f"Education: {edu.get('degree', '')}, {edu.get('institution', '')}, {edu.get('dates', '')}"]
    for e in master.get("experience", []):
        srcs.append(f"Role held: {e.get('role')} at {e.get('company')} ({e.get('dates')})")
    for p in master.get("projects", []):
        srcs.append(f"Project: {p.get('name')} — {p.get('description', '')}")
    return srcs


def _fallback_summary(master: dict) -> str:
    edu = (master.get("education") or [{}])[0]
    skills = [s for items in (master.get("skills") or {}).values() for s in items][:4]
    deg = edu.get("degree", "Graduate")
    return f"{deg} with hands-on internship experience in data analysis using {', '.join(skills)}."


# ── Default LLM judge ─────────────────────────────────────────────────────────

def llm_judge(items: list[dict]) -> dict:
    """Ask the scoring model which texts make claims their sources don't support.
    Kept small: the optimizer call just used most of Groq's per-minute budget."""
    import json
    from core import llm

    if not items:
        return {}
    lines = []
    for it in items:
        src = " | ".join(s[:300] for s in it["sources"])[:1400]
        lines.append(f'ID: {it["id"]}\nTEXT: {it["text"]}\nSOURCES: {src}')
    prompt = (
        "You verify resume text against the candidate's own source facts. For each item, decide "
        "whether TEXT claims anything that the SOURCES do not support: an outcome or impact "
        "(e.g. 'informed pricing strategy', 'reduced complications'), a job title the candidate "
        "never held, client or consulting work, a tool or domain not in the sources. Rephrasing, "
        "reordering and generic framing are fine — only flag genuinely new factual claims.\n\n"
        + "\n\n".join(lines)
        + '\n\nRespond ONLY with JSON: {"unsupported": [{"id": "...", "reason": "short reason"}]}'
    )
    raw = llm.score(prompt)
    data = llm.parse_json(raw)
    valid = {it["id"] for it in items}
    return {d["id"]: d.get("reason", "unsupported claim")
            for d in data.get("unsupported", []) if d.get("id") in valid}
