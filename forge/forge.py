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
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import tarfile
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import db
from core.jd_clean import strip_boilerplate
from forge.matcher import select_profile, get_profile_by_id
from forge.optimizer import optimize

_MASTER        = Path(__file__).parent / "master_profile.yaml"
_TEMPLATE      = Path(__file__).parent / "templates" / "resume.typ"
_CERTS_BY_ROLE = Path(__file__).parent / "certs_by_role.yaml"
_OUT_DIR       = Path("shared/resumes")


def _load_role_certs(profile_id: str) -> list[dict]:
    """Return role-specific certs for the given profile id, or default certs."""
    try:
        data = yaml.safe_load(_CERTS_BY_ROLE.read_text(encoding="utf-8"))
        return data.get(profile_id) or data.get("default") or []
    except Exception:
        return []


def _merge_certs(master_certs: list[dict], role_certs: list[dict]) -> list[dict]:
    """Prepend role-specific certs then master certs, deduplicating by name."""
    seen: set[str] = set()
    merged = []
    for c in role_certs + master_certs:
        if c["name"] not in seen:
            seen.add(c["name"])
            merged.append(c)
    return merged


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


def _experience_block(selected_experience: list[dict], block_gap: str = "8pt") -> str:
    blocks = []
    for exp in selected_experience:
        bullets = "\n".join(f"- {b}" for b in exp.get("bullets", []))
        loc = f", {_escape_typst(exp['location'])}" if exp.get("location") else ""
        role_company = f"*{_escape_typst(exp.get('role',''))} — {_escape_typst(exp.get('company',''))}{loc}*"
        dates = _escape_typst(exp.get("dates", ""))
        # Use grid so dates are always right-aligned on the SAME line even for long company names
        header = f"#grid(columns: (1fr, auto), gutter: 4pt)[{role_company}][{dates}]"
        blocks.append(f"{header}\n{bullets}")
    return f"\n\n#v({block_gap})\n\n".join(blocks)


def _projects_block(selected_projects: list[dict], master_projects: list[dict], block_gap: str = "8pt") -> str:
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
    return f"\n\n#v({block_gap})\n\n".join(blocks)


def _education_block(education: list[dict]) -> str:
    blocks = []
    for i, ed in enumerate(education):
        gpa = ed.get("gpa", "")
        gpa_part = f"GPA: {_escape_typst(str(gpa))} #h(8pt) " if gpa else ""
        dates = ed.get("dates", ed.get("graduation", ""))
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


# Progressively tighter spacing presets, tried in order until the resume fits
# one page without trimming any content. Index 0 is the "normal, comfortable"
# spacing — only later levels get visibly denser.
_SPACING_LEVELS = [
    {"font_size": "10pt",   "margin_x": "0.45in", "margin_y": "0.25in",
     "par_leading": "0.45em", "par_spacing": "0.7em",
     "heading_gap_before": "10pt", "heading_gap_after": "5pt", "block_gap": "8pt"},
    {"font_size": "9.7pt",  "margin_x": "0.42in", "margin_y": "0.22in",
     "par_leading": "0.42em", "par_spacing": "0.6em",
     "heading_gap_before": "8pt",  "heading_gap_after": "4pt", "block_gap": "6pt"},
    {"font_size": "9.4pt",  "margin_x": "0.4in",  "margin_y": "0.2in",
     "par_leading": "0.4em",  "par_spacing": "0.5em",
     "heading_gap_before": "6pt",  "heading_gap_after": "3pt", "block_gap": "4pt"},
    {"font_size": "9.2pt",  "margin_x": "0.38in", "margin_y": "0.18in",
     "par_leading": "0.38em", "par_spacing": "0.45em",
     "heading_gap_before": "5pt",  "heading_gap_after": "2pt", "block_gap": "3pt"},
]


def _render(master: dict, optimized: dict, profile_config: dict, spacing: dict | None = None) -> str:
    """Fill the template placeholders and return a complete .typ string."""
    template = _TEMPLATE.read_text(encoding="utf-8")
    p  = master.get("personal", {})
    sp = spacing or _SPACING_LEVELS[0]

    replacements = {
        "<<NAME>>":             _escape_typst(p.get("name", "Your Name")),
        "<<CONTACT_LINE>>":     _contact_line(p),
        "<<SUMMARY>>":          _escape_typst(optimized.get("summary", "")),
        "<<EDUCATION_BLOCK>>":  _education_block(master.get("education", [])),
        "<<SKILLS_BLOCK>>":     _skills_block(
                                    optimized.get("skills_section", master.get("skills", {})),
                                    profile_config.get("skills_order", []),
                                ),
        "<<EXPERIENCE_BLOCK>>": _experience_block(optimized.get("selected_experience", []), sp["block_gap"]),
        "<<PROJECTS_BLOCK>>":   _projects_block(optimized.get("selected_projects", []), master.get("projects", []), sp["block_gap"]),
        "<<CERTIFICATIONS_BLOCK>>": _certs_block(
                                    optimized.get("selected_certifications", master.get("certifications", []))
                                ),
        "<<FONT_SIZE>>":            sp["font_size"],
        "<<MARGIN_X>>":             sp["margin_x"],
        "<<MARGIN_Y>>":             sp["margin_y"],
        "<<PAR_LEADING>>":          sp["par_leading"],
        "<<PAR_SPACING>>":          sp["par_spacing"],
        "<<HEADING_GAP_BEFORE>>":   sp["heading_gap_before"],
        "<<HEADING_GAP_AFTER>>":    sp["heading_gap_after"],
    }

    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


# ── PDF compilation ───────────────────────────────────────────────────────────

_TYPST_VERSION = "v0.13.0"
_TYPST_BINARY: str | None = None

def _get_typst() -> str:
    """Return path to typst binary, auto-downloading on Linux if not on PATH."""
    global _TYPST_BINARY
    if _TYPST_BINARY:
        return _TYPST_BINARY

    # Check PATH first (covers local Windows/Mac dev with typst installed)
    found = shutil.which("typst")
    if found:
        _TYPST_BINARY = found
        return found

    # On Linux (Render), download the static binary on first use
    if sys.platform.startswith("linux"):
        local_bin = Path.home() / ".local" / "bin" / "typst"
        if not local_bin.exists():
            print(f"[forge] typst not found — downloading {_TYPST_VERSION}…", flush=True)
            local_bin.parent.mkdir(parents=True, exist_ok=True)
            url = (
                f"https://github.com/typst/typst/releases/download/{_TYPST_VERSION}"
                "/typst-x86_64-unknown-linux-musl.tar.xz"
            )
            tmp = Path(tempfile.mktemp(suffix=".tar.xz"))
            urllib.request.urlretrieve(url, tmp)
            with tarfile.open(tmp, "r:xz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith("/typst"):
                        member.name = "typst"
                        tar.extract(member, local_bin.parent)
                        break
            tmp.unlink(missing_ok=True)
            local_bin.chmod(0o755)
            print(f"[forge] typst installed at {local_bin}", flush=True)
        _TYPST_BINARY = str(local_bin)
        return _TYPST_BINARY

    raise RuntimeError("typst not found on PATH. Install via: winget install Typst.Typst")


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
            [_get_typst(), "compile", str(typ_path), str(pdf_path)],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0, result.stderr
    finally:
        typ_path.unlink(missing_ok=True)


def _page_count(pdf_path: Path) -> int:
    from pypdf import PdfReader
    try:
        return len(PdfReader(str(pdf_path)).pages)
    except Exception:
        return 1  # fail open — never block a resume on a PDF-introspection bug


def _trim_one_bullet(optimized: dict) -> bool:
    """
    Drop the single least-important bullet to help the resume fit one page.
    Priority: last bullet of the 2nd (lower-priority) project, then the 2nd
    experience role, then the 1st project, then the 1st experience role —
    never trims an entry below 2 bullets. Mutates `optimized` in place so the
    JSON sidecar saved afterward matches what's actually on the PDF.
    Returns False once there's nothing left to safely cut.
    """
    projects   = optimized.get("selected_projects", [])
    experience = optimized.get("selected_experience", [])

    for entries, idx in ((projects, 1), (experience, 1), (projects, 0), (experience, 0)):
        if len(entries) > idx and len(entries[idx].get("bullets", [])) > 2:
            entries[idx]["bullets"].pop()
            return True
    return False


def _fit_to_one_page(master: dict, optimized: dict, profile_config: dict, pdf_path: Path) -> tuple[bool, str]:
    """
    Compile the resume with a STRICT one-page limit — never returns success
    for a 2+ page PDF. Tries progressively tighter spacing first (no content
    loss); if it still overflows at the tightest spacing, trims the least
    important bullet and retries from the top. Gives up only once there's
    nothing left to safely trim, returning a clear error instead of a
    silently-overflowing resume.
    """
    last_stderr = ""
    for _ in range(8):  # safety cap on trim passes
        for level in _SPACING_LEVELS:
            typ_content = _render(master, optimized, profile_config, spacing=level)
            ok, stderr = _compile(typ_content, pdf_path)
            if not ok:
                last_stderr = stderr
                continue
            if _page_count(pdf_path) <= 1:
                return True, ""
        if not _trim_one_bullet(optimized):
            break

    if last_stderr:
        return False, f"Typst compile failed: {last_stderr.strip()}"
    return False, "Resume content doesn't fit one page even after trimming — JD/profile may need fewer roles or projects."


# ── Public API ────────────────────────────────────────────────────────────────

def generate_resume(job_id: str, profile_override: str | None = None,
                    ats_hints: dict | None = None) -> dict:
    """
    Full pipeline: job → optimize → render → compile → DB update.
    Always returns a dict — never raises.
    profile_override: forge profile id (e.g. "risk_analyst") — skips auto-select.
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

    if profile_override:
        profile_config = get_profile_by_id(profile_override) or select_profile(tags)
    else:
        profile_config = select_profile(tags)

    # Inject role-specific certs so optimizer can pick ATS-matching ones
    role_certs = _load_role_certs(profile_config.get("id", "default"))
    master_for_opt = {
        **master,
        "certifications": _merge_certs(master.get("certifications", []), role_certs),
    }

    optimized = optimize(job, master_for_opt, profile_config, ats_hints=ats_hints)
    if optimized.get("error"):
        return {"error": optimized["error"]}

    company_slug = _slugify(job.get("company", "company"))
    role_slug    = _slugify(job.get("title", "role"))
    date_str     = datetime.now().strftime("%Y-%m-%d")
    pdf_path     = _OUT_DIR / f"{company_slug}_{role_slug}_{date_str}.pdf"

    # Strict one-page enforcement: tightens spacing, then trims bullets if needed.
    # May mutate optimized["selected_experience"/"selected_projects"] in place.
    ok, err = _fit_to_one_page(master, optimized, profile_config, pdf_path)
    if not ok:
        return {"error": err}

    db.set_resume_path(job_id, str(pdf_path))

    # Save optimized content alongside PDF for ATS check
    import json as _json
    json_path = pdf_path.with_suffix(".json")
    try:
        json_path.write_text(_json.dumps({
            "summary":                  optimized.get("summary", ""),
            "skills_section":           optimized.get("skills_section", {}),
            "selected_experience":      optimized.get("selected_experience", []),
            "selected_projects":        optimized.get("selected_projects", []),
            "selected_certifications":  optimized.get("selected_certifications", []),
            "ats_keywords":             optimized.get("ats_keywords", []),
        }, indent=2), encoding="utf-8")
    except Exception:
        pass  # non-critical

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


def audit_resume(job_id: str) -> dict:
    """
    Step 1: Score profile vs JD, return top 5 missing keywords + 3 red flags.
    Fast — single LLM call using the scoring model.
    """
    from core import llm
    job = db.get_job(job_id)
    if not job:
        return {"error": f"Job {job_id} not found"}

    master = _load_master()
    jd = strip_boilerplate(job.get("description") or "")[:4000]
    p = master.get("personal", {})
    skills_flat = ", ".join(
        v if isinstance(v, str) else ", ".join(v)
        for v in master.get("skills", {}).values()
    )
    exp_lines = "\n".join(
        f"- {e['role']} at {e['company']} ({e.get('dates','')})"
        for e in master.get("experience", [])
    )
    proj_lines = "\n".join(
        f"- {p['name']} ({', '.join(p.get('tech',[])[:4])})"
        for p in master.get("projects", [])
    )

    prompt = f"""You are a senior recruiter scoring a fresher candidate against a job description.
Be strict and realistic, not encouraging — most fresher candidates do not meet every
requirement, and a superficial keyword overlap should not inflate the score.

JOB (read the full posting below — responsibilities and qualifications included — before scoring):
Title: {job.get("title")}
Company: {job.get("company")}
Description: {jd}

CANDIDATE PROFILE:
Skills: {skills_flat}
Experience:
{exp_lines}
Projects:
{proj_lines}

Score the candidate out of 100 based on genuine, documented overlap between the JD's actual
requirements and the candidate's real experience/projects — not adjacent or hypothetical fit.
Identify the 5 most critical missing keywords/requirements (domain expertise, tools, years of
experience, certifications, etc. the JD calls for that the profile above does not demonstrate),
and name 3 red flags a hiring manager would notice immediately (e.g. missing required domain
background, no evidence of a specifically-named tool/skill, seniority mismatch).

Respond ONLY with valid JSON:
{{
  "score": <int 0-100>,
  "missing_keywords": ["kw1","kw2","kw3","kw4","kw5"],
  "red_flags": ["flag1","flag2","flag3"]
}}"""

    raw = llm.score(prompt)
    try:
        return llm.parse_json(raw)
    except Exception:
        return {"score": -1, "missing_keywords": [], "red_flags": []}


def ats_check(job_id: str) -> dict:
    """
    Step 3: Run ATS + hiring manager simulation on the last generated resume.
    Loads saved optimized JSON from shared/resumes/.
    """
    from core import llm
    import json as _json
    import glob as _glob

    job = db.get_job(job_id)
    if not job:
        return {"error": f"Job {job_id} not found"}

    # Find the most recent optimized JSON for this job
    company_slug = _slugify(job.get("company", "company"))
    role_slug    = _slugify(job.get("title", "role"))
    pattern = str(_OUT_DIR / f"{company_slug}_{role_slug}_*.json")
    files = sorted(_glob.glob(pattern))
    if not files:
        return {"error": "No generated resume found — forge first, then run ATS check"}

    try:
        optimized = _json.loads(Path(files[-1]).read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": f"Could not load resume data: {e}"}

    jd = strip_boilerplate(job.get("description") or "")[:4000]
    summary = optimized.get("summary", "")
    skills  = optimized.get("skills_section", {})
    skills_text = "\n".join(f"  {k}: {', '.join(v)}" for k, v in skills.items())
    exp_text = "\n".join(
        f"  {r['role']} @ {r['company']}:\n" +
        "\n".join(f"    - {b}" for b in r.get("bullets", []))
        for r in optimized.get("selected_experience", [])
    )
    proj_text = "\n".join(
        f"  {p['name']}:\n" + "\n".join(f"    - {b}" for b in p.get("bullets", []))
        for p in optimized.get("selected_projects", [])
    )

    prompt = f"""You are simultaneously an ATS system and a senior hiring manager reviewing a resume for this role.
Be a realistic, skeptical reviewer — most resumes have real gaps against a full JD, and your
job is to surface them, not to reassure the candidate. Read the entire JD below (responsibilities,
qualifications, requirements) before judging, not just the opening paragraph.

JOB: {job.get("title")} at {job.get("company")}
JD: {jd}

RESUME:
Summary: {summary}

Skills:
{skills_text}

Experience:
{exp_text}

Projects:
{proj_text}

As ATS: which sections contain sufficient JD-matching keywords and will be parsed correctly?
Which JD requirements (tools, domain terms, years of experience, certifications) have NO
keyword match anywhere in this resume — call these out explicitly, don't omit them.
As Hiring Manager: which sections would make you slow down or skip? Be specific about gaps
against the JD's actual requirements, not generic resume advice. What specific rewrites would
increase selection chances?
The overall_verdict must reflect genuine selection likelihood given the gaps found — do not
default to an optimistic verdict when significant JD requirements are unaddressed.

Respond ONLY with valid JSON:
{{
  "ats_pass": ["Section1","Section2"],
  "flagged": [
    {{"section":"SectionName","issue":"specific issue","fix":"one-line suggested fix"}}
  ],
  "overall_verdict": "one concise, honest sentence on selection likelihood"
}}"""

    raw = llm.score(prompt)
    try:
        return llm.parse_json(raw)
    except Exception:
        return {"error": "ATS check parsing failed — try again"}


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
