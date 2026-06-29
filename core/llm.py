"""
LLM interface — Groq (scoring) + configurable writing provider.

Provider is auto-detected from env vars:
  OPENROUTER_API_KEY set → writing model uses OpenRouter (openrouter.ai/api/v1)
  Otherwise             → writing model uses Groq

scoring_model : llama-3.3-70b-versatile  (always Groq — fast, no rate issues)
writing_model : configured in config.yaml
  Groq options     : llama-3.3-70b-versatile, openai/gpt-oss-120b
  OpenRouter free  : google/gemma-4-31b-it:free, meta-llama/llama-3.3-70b-instruct:free

Usage:
    from core.llm import score, write
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
_SCORING_MODEL  = _cfg["llm"]["scoring_model"]
_WRITING_MODEL  = _cfg["llm"]["writing_model"]
_WRITING_PROVIDER = _cfg["llm"].get("writing_provider", "groq")  # groq | openrouter

# ── Groq key pool — rotates on 429 rate-limit errors ─────────────────────────
# Add GROQ_API_KEY_2, GROQ_API_KEY_3 in Render env vars for extra capacity.
# Each key adds 100k tokens/day (normal usage ~35k/day, so 3 keys = plenty).

def _groq_keys() -> list[str]:
    """Return all configured Groq API keys in priority order."""
    candidates = [
        os.getenv("GROQ_API_KEY"),
        os.getenv("GROQ_API_KEY_2"),
        os.getenv("GROQ_API_KEY_3"),
        os.getenv("GROQ_API_KEY_4"),
        os.getenv("GROQ_API_KEY_5"),
    ]
    keys = [k for k in candidates if k]
    if not keys:
        raise RuntimeError("No GROQ_API_KEY configured")
    return keys

def _get_groq_client() -> Groq:
    """Return a Groq client for the primary key (used for scoring)."""
    return Groq(api_key=_groq_keys()[0])


# ── Core call ─────────────────────────────────────────────────────────────────

def _call_openrouter(model: str, prompt: str, max_tokens: int,
                     system: str, temperature: float = 0.2) -> str:
    """Direct HTTP call to OpenRouter — bypasses Groq SDK for correct headers."""
    import requests as _req
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY env var not set")
    resp = _req.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://career-scout-red.vercel.app",
            "X-Title": "Career Scout",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _is_rate_limit(e: Exception) -> bool:
    s = str(e).lower()
    return "429" in s or "rate_limit" in s or "rate limit" in s or "too many requests" in s


def _call(model: str, prompt: str, max_tokens: int = 1024,
          system: str = "You are a helpful assistant.",
          json_mode: bool = False,
          use_writing_client: bool = False) -> str:
    """Raw LLM call. Rotates Groq API keys on 429. Uses OpenRouter if writing_provider=openrouter."""
    if use_writing_client and _WRITING_PROVIDER == "openrouter":
        return _call_openrouter(model, prompt, max_tokens, system)

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

    keys = _groq_keys()
    last_err: Exception | None = None
    for i, key in enumerate(keys):
        try:
            client = Groq(api_key=key)
            resp = client.chat.completions.create(**kwargs)
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            if _is_rate_limit(e) and i < len(keys) - 1:
                print(f"[llm] key {i+1} rate-limited, trying key {i+2}…", flush=True)
                last_err = e
                continue
            raise   # non-rate-limit error, or last key — propagate immediately
    raise last_err  # all keys exhausted


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
    Call the writing model (provider determined by env vars).
    Uses OpenRouter if OPENROUTER_API_KEY is set, else Groq.
    Raises on failure — caller handles (user-triggered, not background).
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
        use_writing_client=True,
    )


def _repair_json(text: str) -> str:
    """Fix common gpt-oss-120b JSON issues: missing commas between elements."""
    import re
    # Missing comma between string/object/array elements across a newline
    # e.g.  "foo"\n  "bar"  →  "foo",\n  "bar"
    text = re.sub(r'(["\}\]])([ \t]*\n[ \t]*)(["\{\[])', r'\1,\2\3', text)
    return text


def parse_json(text: str) -> dict:
    """
    Safely parse JSON from LLM response.
    Handles markdown fences, missing commas, and truncated output.
    """
    import re as _re
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    # 1. Standard parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Fix missing commas (most common gpt-oss-120b issue) then parse
    try:
        return json.loads(_repair_json(text))
    except json.JSONDecodeError:
        pass

    # 3. Extract { ... } block and try both raw and repaired
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start != -1 and end > start:
        block = text[start:end]
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            return json.loads(_repair_json(block))

    raise json.JSONDecodeError("Could not parse LLM output as JSON", text, 0)
