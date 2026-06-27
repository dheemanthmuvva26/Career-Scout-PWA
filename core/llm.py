"""
Groq LLM interface — two models, one client.

scoring_model : llama-3.3-70b-versatile  — high volume job scoring
writing_model : openai/gpt-oss-120b      — resume rewrites + weekly insights

Usage:
    from core.llm import score, write

    result = score(prompt)   # returns raw text, caller parses JSON
    result = write(prompt)   # returns raw text
"""

import os
import json
import yaml
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    cfg_path = Path(__file__).parent.parent / "config.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)

_cfg = _load_config()
_SCORING_MODEL = _cfg["llm"]["scoring_model"]
_WRITING_MODEL = _cfg["llm"]["writing_model"]

_client: Groq | None = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY env var not set")
        _client = Groq(api_key=api_key)
    return _client


# ── Core call ─────────────────────────────────────────────────────────────────

def _call(model: str, prompt: str, max_tokens: int = 1024,
          system: str = "You are a helpful assistant.",
          json_mode: bool = False) -> str:
    """Raw LLM call. Returns the response text or raises on failure."""
    client = _get_client()
    kwargs: dict = dict(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content.strip()


# ── Public interface ──────────────────────────────────────────────────────────

def score(prompt: str) -> str:
    """
    Call the scoring model (llama-3.3-70b-versatile).
    Used for: job scoring per JD.
    Returns raw text — caller is responsible for JSON parsing.
    Falls back to score=-1 string on failure so pipeline never crashes.
    """
    try:
        return _call(
            model=_SCORING_MODEL,
            prompt=prompt,
            max_tokens=512,
            system=(
                "You are a job-fit evaluator. Always respond with valid JSON only. "
                "No explanation, no markdown, no code fences."
            ),
        )
    except Exception as e:
        # Return a valid fallback JSON so caller can store score=-1 and retry later
        return json.dumps({
            "score": -1,
            "fit_summary": f"Scoring failed: {str(e)[:100]}",
            "matched_skills": [],
            "missing_skills": [],
            "seniority_fit": False,
            "location_fit": False,
        })


def write(prompt: str, max_tokens: int = 2048, json_mode: bool = False) -> str:
    """
    Call the writing model (gpt-oss-120b).
    Used for: resume ATS optimization, weekly insights, skill gap roadmap.
    Raises on failure — caller handles (these are user-triggered, not background).
    json_mode=True enforces valid JSON output via response_format.
    """
    return _call(
        model=_WRITING_MODEL,
        prompt=prompt,
        max_tokens=max_tokens,
        system=(
            "You are an expert career coach and resume writer. "
            "Be specific, factual, and concise. Never invent skills or experience."
        ),
        json_mode=json_mode,
    )


def parse_json(text: str) -> dict:
    """
    Safely parse JSON from LLM response.
    Handles cases where model wraps output in markdown code fences.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])   # strip ```json ... ```
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Find the first { ... } block and try again
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
        raise
