"""
Groq ATS optimization pass.

Takes job + master_profile + profile_config → returns a structured dict
with tailored summary, skills reordering, selected bullets, and ATS score estimate.

Strict rules enforced in the prompt:
- Only select bullets that exist verbatim in master_profile (no hallucination)
- Rewrites only surface keywords already implied in the original bullet
- Use exact JD keywords verbatim for ATS literal matching
- Single-page constraint: fewer bullets if content is long
- Never claim a skill the candidate doesn't have
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import llm


def optimize(job: dict, master_profile: dict, profile_config: dict,
             ats_hints: dict | None = None) -> dict:
    """
    Returns:
    {
      "summary": "<2-sentence tailored summary>",
      "ats_keywords": ["kw1", ...],
      "skills_section": { "programming": [...], ... },
      "selected_experience": [
          { "company": "...", "role": "...", "dates": "...",
            "location": "...", "bullets": ["..."] }
      ],
      "selected_projects": [
          { "name": "...", "tech": [...], "github": "...", "bullets": ["..."] }
      ],
      "ats_score_estimate": <int 0-100>
    }
    """
    jd = (job.get("description") or "")[:2000]

    score_detail: dict = {}
    try:
        sd = job.get("score_detail")
        score_detail = json.loads(sd) if isinstance(sd, str) else (sd or {})
    except Exception:
        pass

    # profile_slim excludes internal-only fields (tags, github) that the LLM
    # never uses for selection decisions — saves ~390 tokens vs original,
    # keeping total under gpt-oss-120b's 8k TPM limit without any quality loss.
    # (github is re-injected at render time by forge.py from master_profile)
    profile_slim = {
        "skills": master_profile.get("skills", {}),
        "experience": [
            {
                "company": e["company"],
                "role": e["role"],
                "dates": e.get("dates", ""),
                "location": e.get("location", ""),
                "bullets": [b["text"] for b in e.get("bullets", [])],
            }
            for e in master_profile.get("experience", [])
        ],
        "projects": [
            {
                "name": p["name"],
                "tech": p.get("tech", []),
                "bullets": [b["text"] for b in p.get("bullets", [])],
            }
            for p in master_profile.get("projects", [])
        ],
        "certifications": [
            {
                "name": c["name"],
                "issuer": c.get("issuer", ""),
                "date": c.get("date", ""),
            }
            for c in master_profile.get("certifications", [])
        ],
    }

    prompt = f"""You are an expert ATS resume optimizer. The candidate is a fresher graduating 2026, targeting Data and AI roles in India.

JOB:
Title: {job.get("title")}
Company: {job.get("company")}
Location: {job.get("location")}
Description (first 2000 chars):
{jd}

SCORING CONTEXT:
Fit summary: {score_detail.get("fit_summary", "N/A")}
Matched skills: {score_detail.get("matched_skills", [])}
{f"""
ATS CHECK RESULTS FROM PREVIOUS VERSION (fix these in this regeneration):
Flagged sections: {[f["section"]+": "+f["issue"] for f in (ats_hints.get("flagged") or [])]}
Missing keywords to incorporate: {ats_hints.get("missing_keywords", [])}
""" if ats_hints else ""}
Missing skills: {score_detail.get("missing_skills", [])}

PROFILE CONFIG:
Display name: {profile_config.get("display_name")}
Summary framing guidance: {(profile_config.get("summary_focus") or "")[:200].strip()}
Max experience roles: {profile_config.get("max_experience_roles", 2)}
Max experience bullets per role: {profile_config.get("max_experience_bullets", 2)}
Max projects: {profile_config.get("max_projects", 2)}
Max project bullets: {profile_config.get("max_project_bullets", 2)}
Skills order: {profile_config.get("skills_order", [])}

CANDIDATE PROFILE (JSON):
{json.dumps(profile_slim, indent=2)}

STRICT RULES:
1. summary: EXACTLY 2 sentences (not 3, not 1) — be concise, mention the role title and company name, use keywords from JD ONLY for skills/domains the candidate's profile actually has. If "Summary framing guidance" is provided above, follow it exactly — it overrides the default framing approach. Write "Data and AI" (not "Data/AI") when describing the candidate's field. Avoid generic boilerplate phrasing (e.g. "strong data analysis and BI & visualization capabilities") — instead name 1-2 specific tools, techniques, or deliverables from the candidate's profile (e.g. Power BI dashboards, forecasting models, Python/SQL analysis) and connect them to the JD's primary function (e.g. financial planning & analysis, reporting, forecasting)
2. ats_keywords: exact phrases lifted verbatim from the JD that appear in the candidate's profile
3. skills_section: include at most 4 skill categories — choose the ones with the highest overlap with this JD; within each category keep only the 4-5 most JD-relevant items (drop low-relevance items). Reorder within each retained category to surface JD keywords first. Drop a category entirely if it has fewer than 2 items relevant to this role.
4. selected_experience: pick exactly "Max experience roles" roles (the most relevant ones); select EXACTLY "Max experience bullets per role" bullets per role — not 1, not 2 if the max is 3; always hit the exact count. GOOGLE XYZ FORMAT: structure each bullet as "Accomplished [X outcome] as measured by [Y metric/impact], by doing [Z specific method/tool]" — the outcome leads, the metric quantifies it, the method explains how. BULLET LENGTH: 16-22 words — single-line bullets, never wrap to 2 lines. ORDERING: list the selected roles newest-first (most recent end date first) — never reorder to oldest-first regardless of relevance ranking. REWRITE each selected bullet with a noticeably different sentence structure than the original (don't just swap one or two words) — reorder clauses, change the lead verb, and lead with whichever part of the bullet best matches the JD — while using the JD's own terminology ONLY for a skill, tool, or technique that is the SAME thing already present in the bullet (e.g. "exploratory data analysis" -> "data analytics", "Power BI dashboard" -> "BI & visualization", "predictive model" -> "forecasting model" if the JD says "forecasting" and the bullet is genuinely a predictive model). Lead each bullet with a strong action verb and frame its impact around the high-level themes the JD emphasizes (e.g. automation, efficiency, reporting, risk reduction, collaboration, accuracy) — connect the concrete deliverable to why it matters for this role. Do NOT change the subject matter, domain, or industry of the work — e.g. do not recast an automobile-sales analysis as "financial data analysis", or a flight-price-prediction model as "budget/financial forecasting". Every fact, tool, technology, number, and outcome from the original bullet must still be present — only the phrasing, structure, and framing change. Each bullet must come from, and only from, its own role/project's bullets in the profile — never copy or merge in a bullet from a different role or project.
5. selected_projects: pick exactly "Max projects" projects whose tags overlap with the JD's domain (the most relevant ones); select EXACTLY "Max project bullets" bullets per project — not 1, not 2 if the max is 3; always hit the exact count. GOOGLE XYZ FORMAT: same structure as rule 4 — Accomplished [X] as measured by [Y], by doing [Z]. BULLET LENGTH: 16-22 words — single-line bullets, never wrap to 2 lines. — when a project has bullets spanning both technical/ML implementation and business-outcome work (e.g. dashboards, reporting, risk or decision-support), prioritize the business-outcome bullets if they align with the JD's core function, while still selecting only from that project's own bullets. ORDER the selected bullets so the one most aligned with the JD's core function comes FIRST, regardless of its order in the source profile. Apply the same rewrite constraints as rule 4.
6. ats_score_estimate: integer 0-100 reflecting how well this resume will pass ATS for this JD
7. NEVER include a skill, domain, or claim (in the summary, ats_keywords, or any bullet) that is not present in the profile above. If a JD keyword (e.g. "Financial Reporting", "Budgeting") names a skill/domain the candidate's profile does not have, do NOT work it into the summary, ats_keywords, or any bullet.
8. The final resume should fill close to a full single US-letter page — use the bullet/project/skill counts above as TARGETS, not maximums to undercut. Do not pad with filler, but do not under-fill either.
9. selected_certifications: ALWAYS include this section — pick exactly 2 certifications from the profile list whose name, issuer, or tags best match this JD's domain/keywords. Prioritise certifications from brand-name institutions (Wharton, Google, etc.) and ones tagged with finance, risk, data_analyst, or similar JD-relevant domains. Return the full cert object (name, issuer, date) unchanged — do not omit this field.

HARD CONSTRAINT — BULLET COUNTS (checked before output is accepted):
- Every object in selected_experience MUST have bullets array with EXACTLY {profile_config.get("max_experience_bullets", 2)} items — no more, no fewer.
- Every object in selected_projects MUST have bullets array with EXACTLY {profile_config.get("max_project_bullets", 3)} items — no more, no fewer.
- If the source only has 2 bullets and you need 3, paraphrase a different aspect of the same experience as the third bullet.
- Returning 2 bullets when the count is 3 is a CRITICAL ERROR.

Respond ONLY with valid JSON — no markdown, no explanation:
{{
  "summary": "...",
  "ats_keywords": ["..."],
  "skills_section": {{
    "languages": ["..."]
  }},
  "selected_experience": [
    {{
      "company": "...",
      "role": "...",
      "dates": "...",
      "location": "...",
      "bullets": ["bullet_1", "bullet_2", "bullet_3"]
    }}
  ],
  "selected_projects": [
    {{
      "name": "...",
      "tech": ["..."],
      "github": "...",
      "bullets": ["bullet_1", "bullet_2", "bullet_3"]
    }}
  ],
  "selected_certifications": [
    {{
      "name": "...",
      "issuer": "...",
      "date": "..."
    }}
  ],
  "ats_score_estimate": 0
}}"""

    raw = llm.write(prompt, max_tokens=3000)
    try:
        return llm.parse_json(raw)
    except Exception as e:
        return {"error": f"Resume optimizer failed — could not parse output: {e}"}
