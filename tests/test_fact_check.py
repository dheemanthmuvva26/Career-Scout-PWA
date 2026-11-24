"""Offline tests for forge/fact_check.py — no DB, network, or LLM calls."""

import json
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from forge.fact_check import (  # noqa: E402
    check_resume, extract_numbers, graduation_status, unsupported_numbers,
)

FIX = Path(__file__).parent / "fixtures"
MASTER = yaml.safe_load((ROOT / "forge" / "master_profile.yaml").read_text(encoding="utf-8"))
ROLE_CERTS = yaml.safe_load((ROOT / "forge" / "certs_by_role.yaml").read_text(encoding="utf-8"))


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _all_role_certs():
    return [c for certs in ROLE_CERTS.values() for c in (certs or [])]


# ── Number extraction ─────────────────────────────────────────────────────────

def test_extract_normalises_suffixes_and_commas():
    vals = {(v, u) for v, u, _ in extract_numbers("225,000+ pregnancies, 225k rows, 2.7M+ edges, 5.5+ crore people")}
    assert (225000.0, "n") in vals
    assert (2700000.0, "n") in vals
    assert (55000000.0, "n") in vals


def test_units_are_distinct():
    # "20%" must not pass just because the source says "20,000+" or "20".
    allowed = extract_numbers("EDA on 20,000+ records across 20 regions")
    assert unsupported_numbers("cut time by 20%", allowed) == ["20%"]


def test_unicode_minus_and_sign_ignored():
    allowed = extract_numbers("validated on two real years (−17.3% in 2025, +17.0% in 2026)")
    assert unsupported_numbers("(-17.3% in 2025, 17.0% in 2026)", allowed) == []


def test_range_shares_unit_and_rounding_allowed():
    allowed = extract_numbers("within 15.1% (Urea) and 17.0% (DAP)")
    assert unsupported_numbers("a forecast within 15-17% of real sales", allowed) == []


def test_years_always_allowed():
    assert unsupported_numbers("forecast July 2026 demand", []) == []


# ── Acceptance: today's real first draft ──────────────────────────────────────

FABRICATED = ["15%", "20%", "30%", "8", "2", "92%", "40%", "35%", "18%", "27%"]


def test_first_draft_numbers_all_flagged():
    _, report = check_resume(_load("pwc_first_draft.json"), MASTER, mode="warn",
                             allowed_certs=_all_role_certs())
    flagged_text = " ".join(i["reason"] for i in report["issues"])
    for raw in FABRICATED:
        assert raw in flagged_text, f"{raw} was not flagged"
    # Real numbers must not be flagged.
    for real in ("225k", "20k", "2.7M", "9", "10"):
        assert f" {real}," not in flagged_text + "," and not flagged_text.endswith(f" {real}")


def test_first_draft_repair_leaves_no_fabricated_numbers():
    fixed, report = check_resume(_load("pwc_first_draft.json"), MASTER, mode="repair",
                                 allowed_certs=_all_role_certs())
    # Every bullet left must now pass the number check.
    _, recheck = check_resume(fixed, MASTER, mode="warn", allowed_certs=_all_role_certs())
    assert not [i for i in recheck["issues"] if "numbers" in i["reason"]], recheck["issues"]
    # Fabricated bullets were replaced by the user's own verbatim bullets.
    actions = {i["action"] for i in report["issues"]}
    assert "replaced with your original bullet" in actions
    # The "15% data quality" bullet must come back as its own Citizen 360
    # source bullet, not an unrelated one from the same role.
    rtg = fixed["selected_experience"][0]["bullets"]
    assert any("Citizen 360" in b for b in rtg)
    # No entry may end up stating the same source fact twice.
    for e in fixed["selected_experience"] + fixed["selected_projects"]:
        heads = [b.split()[0:4] for b in e["bullets"]]
        assert len(e["bullets"]) == len({tuple(h) for h in heads}), e["bullets"]
    innologic = fixed["selected_experience"][1]["bullets"]
    assert sum("exploratory data analysis" in b.lower() for b in innologic) == 1, innologic


def test_claim_judge_catches_numberless_fabrication():
    def fake_judge(items):
        return {it["id"]: "pricing strategy is not in the source"
                for it in items if "pricing strategy" in it["text"]}
    fixed, report = check_resume(_load("pwc_first_draft.json"), MASTER, mode="repair",
                                 allowed_certs=_all_role_certs(), judge=fake_judge)
    assert report["claim_check"] == "ok"
    texts = [b for e in fixed["selected_experience"] for b in e["bullets"]]
    assert not any("pricing strategy" in b for b in texts)


def test_judge_failure_fails_open_with_warning():
    def broken_judge(items):
        raise RuntimeError("429 rate limited")
    _, report = check_resume(_load("pwc_first_draft.json"), MASTER, mode="repair", judge=broken_judge)
    assert report["claim_check"].startswith("skipped")
    assert report["warnings"]


def test_role_pool_cert_kept_but_warned():
    _, report = check_resume(_load("pwc_first_draft.json"), MASTER, mode="repair",
                             allowed_certs=_all_role_certs())
    assert any("enroll" in w for w in report["warnings"])


# ── Acceptance: the final hand-corrected resume ──────────────────────────────

def test_hand_corrected_resume_has_no_number_issues():
    _, report = check_resume(_load("pwc_final_hand_corrected.json"), MASTER, mode="warn")
    number_issues = [i for i in report["issues"] if "numbers" in i["reason"]]
    assert number_issues == [], number_issues


# ── Graduation guard ─────────────────────────────────────────────────────────

def test_graduation_status():
    assert graduation_status(MASTER, date(2026, 11, 24))["graduated"] is True
    assert graduation_status(MASTER, date(2026, 3, 1))["graduated"] is False


# ── Ongoing projects keep in-progress tense ──────────────────────────────────

def test_ongoing_project_past_tense_restored_without_judge():
    # Real output from the 2026-11-25 Matrix Missions forge.
    resume = {"selected_projects": [{
        "name": "Agentic Credit Risk Analyst", "tech": ["Python"],
        "bullets": ["Built an XGBoost credit default model with SHAP explanations, providing transparent risk scores for individual borrowers.",
                    "Building a Power BI dashboard for risk officers with portfolio and case-level views"],
    }]}
    fixed, report = check_resume(resume, MASTER, mode="repair")
    bullets = fixed["selected_projects"][0]["bullets"]
    assert any(b.startswith("Building an XGBoost") for b in bullets), bullets
    assert not any(b.startswith("Built") for b in bullets)
    assert any("in progress" in i["reason"] for i in report["issues"])


def test_finished_project_past_tense_is_fine():
    resume = {"selected_projects": [{
        "name": "AI-Assisted Citizen-Centric Knowledge Graph (CCKG)", "tech": [],
        "bullets": ["Built a Streamlit analytics dashboard enabling stakeholders to explore governance data"],
    }]}
    _, report = check_resume(resume, MASTER, mode="warn")
    assert report["issues"] == []


def test_judge_sees_project_status_and_summary_sees_skills():
    seen = {}
    def spy(items):
        seen.update({it["id"]: it["sources"] for it in items})
        return {}
    resume = {"summary": "Skilled in Python and SQL.",
              "selected_projects": [{"name": "Agentic Credit Risk Analyst", "tech": [],
                                     "bullets": ["Designing a four-agent LangChain pipeline"]}]}
    check_resume(resume, MASTER, mode="warn", judge=spy)
    proj = next(v for k, v in seen.items() if k.startswith("projects|"))
    assert any("IN PROGRESS" in s for s in proj) and any(s.startswith("Tech:") for s in proj)
    assert any(s.startswith("Skills:") and "SQL" in s for s in seen["summary"])
