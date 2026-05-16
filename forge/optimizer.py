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


def optimize(job: dict, master_profile: dict, profile_config: dict) -> dict:
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

    # Trim master profile to reduce token count — remove unneeded keys
    profile_slim = {
        "skills": master_profile.get("skills", {}),
        "experience": [
            {
                "company": e["company"],
                "role": e["role"],
                "dates": e.get("dates", ""),
                "location": e.get("location", ""),
                "tags": e.get("tags", []),
                "bullets": [{"text": b["text"], "tags": b["tags"]} for b in e.get("bullets", [])],
            }
            for e in master_profile.get("experience", [])
        ],
        "projects": [
            {
                "name": p["name"],
                "tech": p.get("tech", []),
                "github": p.get("github", ""),
                "tags": p.get("tags", []),
                "bullets": [{"text": b["text"], "tags": b["tags"]} for b in p.get("bullets", [])],
            }
            for p in master_profile.get("projects", [])
        ],
    }

    prompt = f"""You are an expert ATS resume optimizer. The candidate is a fresher graduating 2026, targeting Data/AI roles in India.

JOB:
Title: {job.get("title")}
Company: {job.get("company")}
Location: {job.get("location")}
Description (first 2000 chars):
{jd}

SCORING CONTEXT:
Fit summary: {score_detail.get("fit_summary", "N/A")}
Matched skills: {score_detail.get("matched_skills", [])}
Missing skills: {score_detail.get("missing_skills", [])}

PROFILE CONFIG:
Display name: {profile_config.get("display_name")}
Preferred experience tags: {profile_config.get("experience_tags", [])}
Preferred project tags: {profile_config.get("project_tags", [])}
Max experience bullets per role: {profile_config.get("max_experience_bullets", 3)}
Max projects: {profile_config.get("max_projects", 3)}
Max project bullets: {profile_config.get("max_project_bullets", 2)}
Skills order: {profile_config.get("skills_order", [])}

CANDIDATE PROFILE (JSON):
{json.dumps(profile_slim, indent=2)[:3500]}

STRICT RULES:
1. summary: exactly 2 sentences, mention the role title and company name, use keywords from JD
2. ats_keywords: exact phrases lifted verbatim from the JD that appear in the candidate's profile
3. skills_section: reorder skills within each category to surface JD keywords first; omit categories not relevant to this role
4. selected_experience: pick roles whose tags overlap with experience_tags; select up to max bullets per role; light rewrite allowed ONLY to surface a JD keyword already implied — never invent facts
5. selected_projects: pick projects whose tags overlap with project_tags; respect max_projects and max_project_bullets
6. ats_score_estimate: integer 0-100 reflecting how well this resume will pass ATS for this JD
7. NEVER include a skill or claim not present in the profile above

Respond ONLY with valid JSON — no markdown, no explanation:
{{
  "summary": "...",
  "ats_keywords": ["..."],
  "skills_section": {{
    "programming": ["..."],
    "ml_frameworks": ["..."]
  }},
  "selected_experience": [
    {{
      "company": "...",
      "role": "...",
      "dates": "...",
      "location": "...",
      "bullets": ["..."]
    }}
  ],
  "selected_projects": [
    {{
      "name": "...",
      "tech": ["..."],
      "github": "...",
      "bullets": ["..."]
    }}
  ],
  "ats_score_estimate": 0
}}"""

    raw = llm.write(prompt)
    try:
        return llm.parse_json(raw)
    except Exception:
        return {
            "summary": (
                f"Fresher Data & AI professional applying for {job.get('title')} "
                f"at {job.get('company')}. Strong Python, SQL, and ML skills with "
                f"hands-on project experience."
            ),
            "ats_keywords": score_detail.get("matched_skills", []),
            "skills_section": master_profile.get("skills", {}),
            "selected_experience": [],
            "selected_projects": [],
            "ats_score_estimate": -1,
        }
