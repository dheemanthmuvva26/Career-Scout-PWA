"""Offline tests for the ATS-fix honesty filter in forge/forge.py."""

import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from forge.fact_check import graduation_status  # noqa: E402
from forge.forge import _vet_fix, honest_hints  # noqa: E402

MASTER = yaml.safe_load((ROOT / "forge" / "master_profile.yaml").read_text(encoding="utf-8"))
GRADUATED = graduation_status(MASTER, date(2026, 11, 24))


def test_final_year_fix_rejected_after_graduation():
    # Suggested twice by the real ATS check on 2026-11-24.
    f = _vet_fix({"section": "Summary", "issue": "No final year status",
                  "fix": 'Add "Currently in final year of B.Tech"', "honest": True}, MASTER, GRADUATED)
    assert f["honest"] is False
    assert "2026" in f["why_not"]
    assert f["alternative"]


def test_client_work_fix_rejected():
    f = _vet_fix({"section": "Skills", "issue": "No consulting context",
                  "fix": 'Add "Power BI, Tableau – used for client dashboards"', "honest": True},
                 MASTER, GRADUATED)
    assert f["honest"] is False
    assert "Forage" in f["alternative"]


def test_invented_number_fix_rejected():
    f = _vet_fix({"section": "Experience", "issue": "No impact",
                  "fix": "Say the dashboards cut reporting time by 45%", "honest": True},
                 MASTER, GRADUATED)
    assert f["honest"] is False


def test_honest_rewording_kept():
    f = _vet_fix({"section": "Experience", "issue": "No teamwork shown",
                  "fix": "Mention collaborating with department domain experts on BRDs", "honest": True},
                 MASTER, GRADUATED)
    assert f["honest"] is True


def test_model_dishonest_flag_respected():
    f = _vet_fix({"section": "Experience", "issue": "x", "fix": "reword", "honest": False}, MASTER, GRADUATED)
    assert f["honest"] is False and f["why_not"]


def test_honest_hints_strips_dishonest_fixes_before_reforge():
    hints = {"flagged": [
        {"fix": "Add 'currently in final year'", "honest": True},   # old client, no vetting
        {"fix": "Lead with Python and SQL", "honest": True},
        {"fix": "Claim client work", "honest": False},
    ], "missing_keywords": ["SQL"]}
    kept = honest_hints(hints)["flagged"]
    assert [f["fix"] for f in kept] == ["Lead with Python and SQL"]
