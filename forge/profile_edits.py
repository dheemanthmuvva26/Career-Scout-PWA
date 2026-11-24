"""
Keep master-profile numbers current from a pasted results document.

  suggest_edits(doc, master)  → LLM proposes bullet changes; every number in a
                                 proposed bullet must appear in the pasted doc,
                                 or the suggestion is rejected. A human approves.
  apply_edits(master, edits)  → approved edits (stored in the DB, since Render's
                                 disk resets on deploy) applied on top of
                                 master_profile.yaml at load time. Pure.

Edits match on the bullet's old text, so once the same change lands in the
YAML in the repo, the stored edit becomes a no-op instead of applying twice.
"""

from __future__ import annotations

import copy
import json
import re

from forge.fact_check import _norm, extract_numbers, unsupported_numbers

_KINDS = {"experience": ("experience", "company"), "project": ("projects", "name")}


def _entry(master: dict, kind: str, name: str) -> dict | None:
    if kind not in _KINDS:
        return None
    key, name_key = _KINDS[kind]
    target = _norm(name)
    return next((e for e in master.get(key, []) if _norm(e.get(name_key, "")) == target), None)


def apply_edits(master: dict, edits: list[dict]) -> tuple[dict, list[dict]]:
    """Return (patched master, status per edit). Status is one of
    applied / already-present / stale (old text gone) / unknown-entry."""
    out = copy.deepcopy(master)
    status = []
    for ed in edits:
        e = _entry(out, ed.get("kind", ""), ed.get("entry_name", ""))
        if e is None:
            status.append({"id": ed.get("id"), "status": "unknown-entry"})
            continue
        bullets = e.setdefault("bullets", [])
        texts = [_norm(b["text"] if isinstance(b, dict) else b) for b in bullets]
        new_n = _norm(ed["new_text"])
        if new_n in texts:
            status.append({"id": ed.get("id"), "status": "already-present"})
            continue
        old = ed.get("old_text")
        if old:
            try:
                i = texts.index(_norm(old))
            except ValueError:
                status.append({"id": ed.get("id"), "status": "stale"})
                continue
            prev = bullets[i]
            tags = ed.get("tags") or (prev.get("tags", []) if isinstance(prev, dict) else [])
            bullets[i] = {"text": ed["new_text"], "tags": tags}
        else:
            bullets.append({"text": ed["new_text"], "tags": ed.get("tags") or list(e.get("tags", []))})
        status.append({"id": ed.get("id"), "status": "applied"})
    return out, status


def validate_suggestion(s: dict, doc: str, master: dict) -> str | None:
    """Return a rejection reason, or None if the suggestion may be shown."""
    if not s.get("new_text") or _entry(master, s.get("kind", ""), s.get("entry_name", "")) is None:
        return "doesn't match any entry in your profile"
    bad = unsupported_numbers(s["new_text"], extract_numbers(doc))
    if bad:
        return f"numbers not found in the document: {', '.join(bad)}"
    return None


def _plain(s: str) -> str:
    """Lowercase text with markdown emphasis, quotes and dashes/whitespace normalised."""
    s = re.sub(r"[*_`>#]", "", s or "")
    s = s.replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[‐-―−]", "-", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def _quote_found(quote: str, doc: str) -> bool:
    q = _plain(quote).strip(' ."')
    return len(q) >= 12 and q[:120] in _plain(doc)


def _already_covered(s: dict, master: dict) -> bool:
    """An addition whose numbers all already appear in that entry adds nothing new."""
    if s.get("old_text"):
        return False
    nums = [n for n in extract_numbers(s["new_text"]) if not (n[1] == "n" and 1990 <= n[0] <= 2035)]
    if not nums:
        return False
    e = _entry(master, s["kind"], s["entry_name"])
    existing = [n for b in e.get("bullets", []) for n in extract_numbers(b["text"] if isinstance(b, dict) else b)]
    return not unsupported_numbers(s["new_text"], existing)


def suggest_edits(doc: str, master: dict) -> dict:
    """Ask the model which bullets the document updates. Returns
    {"suggestions": [...], "rejected": [...]}; nothing is applied here."""
    from core import llm

    doc = (doc or "").strip()
    if len(doc) < 40:
        return {"suggestions": [], "rejected": [], "error": "Paste the document's text (at least a paragraph)."}
    doc_cut = doc[:9000]

    entries = []
    for kind, (key, name_key) in _KINDS.items():
        for e in master.get(key, []):
            entries.append({"kind": kind, "entry_name": e.get(name_key),
                            "bullets": [b["text"] if isinstance(b, dict) else b for b in e.get("bullets", [])]})

    prompt = f"""You keep a candidate's resume profile accurate. Below are their current profile entries
and a document with newer results about their work.

For each bullet the document makes out of date (a number changed, a newer headline result exists),
propose a replacement. Propose a NEW bullet only for a significant result the profile lacks.
Rules:
- Use ONLY facts and numbers stated in the document. Copy numbers exactly as written.
- If the document gives two different figures for the same thing, propose nothing for it and
  mention the conflict in "note".
- Keep each bullet one sentence, 20-35 words, starting with a past-tense verb.
- Don't overstate: if the document says a result is validated but not shipped/live, say "validated".
- "source_quote" must be a short exact quote from the document backing the bullet.

PROFILE ENTRIES:
{json.dumps(entries, ensure_ascii=False)[:6000]}

DOCUMENT:
{doc_cut}

Respond ONLY with JSON:
{{"suggestions": [{{"kind": "project|experience", "entry_name": "exact name from profile",
  "old_text": "exact current bullet text, or null to add a new bullet", "new_text": "...",
  "source_quote": "...", "note": ""}}]}}"""

    raw = llm.write(prompt, max_tokens=1800)
    try:
        data = llm.parse_json(raw)
    except Exception:
        return {"suggestions": [], "rejected": [], "error": "Couldn't read the model's answer — try again."}

    suggestions, rejected = [], []
    for s in data.get("suggestions") or []:
        if not isinstance(s, dict):
            continue
        reason = validate_suggestion(s, doc, master)
        if reason:
            rejected.append({**s, "reason": reason})
            continue
        e = _entry(master, s["kind"], s["entry_name"])
        texts = {_norm(b["text"] if isinstance(b, dict) else b): (b["text"] if isinstance(b, dict) else b)
                 for b in e.get("bullets", [])}
        old = s.get("old_text")
        # An old_text the model paraphrased instead of copying: treat as an addition.
        s["old_text"] = texts.get(_norm(old)) if old else None
        if _already_covered(s, master):
            rejected.append({**s, "reason": "your profile already has these numbers"})
            continue
        s["quote_verified"] = _quote_found(s.get("source_quote", ""), doc)
        suggestions.append(s)
    return {"suggestions": suggestions, "rejected": rejected}
