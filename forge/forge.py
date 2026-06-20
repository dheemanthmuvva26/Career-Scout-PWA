"""
Resume Forge — CLI entrypoint.

Usage:
  python forge/forge.py --job-id <id>

Flow:
  DB job → matcher → Groq optimizer → render .typ → typst compile → PDF

Output:
  - PDF saved to shared/resumes/<company>_<role>_<date>.pdf
  - resume_path written to DB
  - ATS summary printed to stdout (captured by n8n / Telegram)

Requires:
  - typst on PATH: winget install Typst.Typst
  - forge/master_profile.yaml filled in
  - GROQ_API_KEY in .env
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db
from forge.matcher import select_profile
from forge.optimizer import optimize

_MASTER   = Path(__file__).parent / "master_profile.yaml"
_TEMPLATE = Path(__file__).parent / "templates" / "resume.typ"
_OUT_DIR  = Path("shared/resumes")


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


def _load_master() -> dict:
    return yaml.safe_load(_MASTER.read_text(encoding="utf-8"))


# ── Typst rendering ───────────────────────────────────────────────────────────

_ACRONYMS = {"ml", "ai", "bi", "llm", "rag", "nlp", "sql", "etl", "api"}


def _label_word(word: str) -> str:
    return word.upper() if word.lower() in _ACRONYMS else word.capitalize()


def _skills_block(skills_section: dict, skills_order: list[str]) -> str:
    lines = []
    seen = set()
    # Render in profile-preferred order first, then any remaining
    ordered_keys = list(skills_order) + [k for k in skills_section if k not in skills_order]
    for key in ordered_keys:
        if key in seen or key not in skills_section:
            continue
        seen.add(key)
        items = skills_section[key]
        if not items:
            continue
        label = " ".join(_label_word(w) for w in key.replace("_", " ").split())
        lines.append(f"*{label}:* {', '.join(items)}")
    return " \\ \n".join(lines)   # Typst line break between rows


def _experience_block(selected_experience: list[dict]) -> str:
    blocks = []
    for exp in selected_experience:
        bullets = "\n".join(f"- {b}" for b in exp.get("bullets", []))
        loc = f", {exp['location']}" if exp.get("location") else ""
        header = (
            f"*{exp.get('role', '')} — {exp.get('company', '')}{loc}*"
            f" #h(1fr) {exp.get('dates', '')}"
        )
        blocks.append(f"{header}\n{bullets}")
    return "\n\n".join(blocks)


def _projects_block(selected_projects: list[dict], master_projects: list[dict]) -> str:
    sponsors = {p["name"]: p["sponsor"] for p in master_projects if p.get("sponsor")}
    blocks = []
    for proj in selected_projects:
        name = proj.get("name", "")
        tech_str = ", ".join(proj.get("tech", []))
        bullets = "\n".join(f"- {b}" for b in proj.get("bullets", []))
        header = f"*{name}*"
        sponsor = sponsors.get(name)
        if sponsor:
            header += f" #h(1fr) {_escape_typst(sponsor)}"
        if tech_str:
            header += f"\n_{tech_str}_"
        blocks.append(f"{header}\n{bullets}")
    return "\n\n".join(blocks)


def _education_block(education: list[dict]) -> str:
    blocks = []
    for i, ed in enumerate(education):
        gpa = ed.get("gpa", "")
        gpa_part = f"GPA: {_escape_typst(str(gpa))} #h(8pt) " if gpa else ""
        dates = ed.get("graduation", ed.get("dates", ""))
        loc = f", {ed['location']}" if ed.get("location") else ""
        header = (
            f"*{_escape_typst(ed.get('degree', ''))}*"
            f" #h(1fr) {gpa_part}#text(style: \"italic\")[{_escape_typst(dates)}]"
        )
        institution_line = f"{_escape_typst(ed.get('institution', ''))}{_escape_typst(loc)}"
        block = f"{header} #linebreak()\n{institution_line}"
        if i == 0:
            highlights = "\n".join(f"- {_escape_typst(h)}" for h in ed.get("highlights", []))
            if highlights:
                block += f"\n{highlights}"
        blocks.append(block)
    return "\n\n".join(blocks)


def _certs_block(certifications: list[dict]) -> str:
    if not certifications:
        return ""
    lines = "\n".join(
        f"- {_escape_typst(c.get('name', ''))} — {_escape_typst(c.get('issuer', ''))} "
        f"({_escape_typst(c.get('date', ''))})"
        for c in certifications
    )
    return f"= Certifications\n\n{lines}"


def _escape_typst(s: str) -> str:
    """Escape characters that Typst markup would otherwise interpret
    (e.g. '@' in an email address starts a label reference)."""
    for ch in ("\\", "@", "#", "_", "*", "<", ">", "$", "`"):
        s = s.replace(ch, "\\" + ch)
    return s


def _typst_str(s: str) -> str:
    """Escape characters for embedding inside a Typst string literal ("...")."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _contact_line(p: dict) -> str:
    parts = []
    if p.get("email"):
        parts.append(_escape_typst(p["email"]))
    if p.get("phone"):
        parts.append(_escape_typst(p["phone"]))
    if p.get("github"):
        url = p["github"] if p["github"].startswith("http") else f"https://{p['github']}"
        parts.append(f'#link("{_typst_str(url)}")[GitHub]')
    if p.get("linkedin"):
        url = p["linkedin"] if p["linkedin"].startswith("http") else f"https://{p['linkedin']}"
        parts.append(f'#link("{_typst_str(url)}")[LinkedIn]')
    return " #h(6pt) | #h(6pt) ".join(parts)


def _render(master: dict, optimized: dict, profile_config: dict) -> str:
    """Fill the template placeholders and return a complete .typ string."""
    template = _TEMPLATE.read_text(encoding="utf-8")
    p  = master.get("personal", {})

    replacements = {
        "<<NAME>>":             _escape_typst(p.get("name", "Your Name")),
        "<<CONTACT_LINE>>":     _contact_line(p),
        "<<SUMMARY>>":          _escape_typst(optimized.get("summary", "")),
        "<<EDUCATION_BLOCK>>":  _education_block(master.get("education", [])),
        "<<SKILLS_BLOCK>>":     _skills_block(
                                    optimized.get("skills_section", master.get("skills", {})),
                                    profile_config.get("skills_order", []),
                                ),
        "<<EXPERIENCE_BLOCK>>": _experience_block(optimized.get("selected_experience", [])),
        "<<PROJECTS_BLOCK>>":   _projects_block(optimized.get("selected_projects", []), master.get("projects", [])),
        "<<CERTIFICATIONS_BLOCK>>": _certs_block(master.get("certifications", [])),
    }

    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


# ── PDF compilation ───────────────────────────────────────────────────────────

def _compile(typ_content: str, pdf_path: Path) -> tuple[bool, str]:
    """Write .typ to a temp file and compile with typst. Returns (ok, stderr)."""
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        suffix=".typ", delete=False, mode="w", encoding="utf-8"
    ) as tmp:
        tmp.write(typ_content)
        typ_path = Path(tmp.name)

    try:
        result = subprocess.run(
            ["typst", "compile", str(typ_path), str(pdf_path)],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0, result.stderr
    finally:
        typ_path.unlink(missing_ok=True)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_resume(job_id: str) -> dict:
    """
    Full pipeline: job → optimize → render → compile → DB update.
    Always returns a dict — never raises.
    """
    job = db.get_job(job_id)
    if not job:
        return {"error": f"Job {job_id} not found in DB"}

    master = _load_master()

    tags: list[str] = []
    try:
        tags = json.loads(job.get("tags_matched") or "[]")
    except Exception:
        pass

    profile_config = select_profile(tags)
    optimized      = optimize(job, master, profile_config)

    typ_content = _render(master, optimized, profile_config)

    company_slug = _slugify(job.get("company", "company"))
    role_slug    = _slugify(job.get("title", "role"))
    date_str     = datetime.now().strftime("%Y-%m-%d")
    pdf_path     = _OUT_DIR / f"{company_slug}_{role_slug}_{date_str}.pdf"

    ok, stderr = _compile(typ_content, pdf_path)
    if not ok:
        return {"error": f"Typst compile failed: {stderr.strip()}"}

    db.set_resume_path(job_id, str(pdf_path))

    score_detail: dict = {}
    try:
        sd = job.get("score_detail")
        score_detail = json.loads(sd) if isinstance(sd, str) else (sd or {})
    except Exception:
        pass

    return {
        "ok": True,
        "pdf_path": str(pdf_path),
        "ats_score": optimized.get("ats_score_estimate", -1),
        "ats_keywords": optimized.get("ats_keywords", []),
        "missing_keywords": score_detail.get("missing_skills", []),
        "profile_used": profile_config.get("display_name", "default"),
        "title": job.get("title", ""),
        "company": job.get("company", ""),
    }


def _telegram_message(result: dict) -> str:
    if result.get("error"):
        return f"❌ Resume generation failed:\n{result['error']}"

    ats     = result.get("ats_score", -1)
    ats_str = f"{ats}%" if ats >= 0 else "N/A"
    matched = ", ".join(result.get("ats_keywords", [])[:8]) or "N/A"
    missing = ", ".join(result.get("missing_keywords", [])[:5]) or "None"

    return (
        f"✅ *Resume generated — {result['title']} @ {result['company']}*\n\n"
        f"Profile used: {result.get('profile_used')}\n"
        f"ATS score estimate: *{ats_str}*\n\n"
        f"✅ Matched keywords: {matched}\n"
        f"❌ Missing from profile: {missing}\n\n"
        f"📄 `{result.get('pdf_path')}`"
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Generate a tailored resume PDF for a job.")
    parser.add_argument("--job-id", required=True, help="Job ID from the DB")
    args = parser.parse_args()

    result = generate_resume(args.job_id)
    print(_telegram_message(result))
    sys.exit(0 if result.get("ok") else 1)
