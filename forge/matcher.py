"""
Profile selector — maps job tags_matched to the best forge profile.

Profiles live in forge/profiles/*.yaml.
The profile with the most tag overlap wins; ties fall back to default.
"""

from pathlib import Path
import yaml

_PROFILES_DIR = Path(__file__).parent / "profiles"


def _load_all() -> list[dict]:
    profiles = []
    for f in sorted(_PROFILES_DIR.glob("*.yaml")):
        p = yaml.safe_load(f.read_text())
        profiles.append(p)
    # Put default last so explicit profiles always win ties
    return sorted(profiles, key=lambda p: p.get("id") == "default")


def get_profile_by_id(profile_id: str) -> dict | None:
    """Return a specific profile by id, or None if not found."""
    for f in sorted(_PROFILES_DIR.glob("*.yaml")):
        p = yaml.safe_load(f.read_text())
        if p.get("id") == profile_id:
            return p
    return None


def select_profile(tags_matched: list[str]) -> dict:
    """
    Return the profile dict that best matches the given job tags.
    Falls back to the 'default' profile if nothing overlaps.
    """
    profiles = _load_all()
    tags = {t.lower() for t in tags_matched}

    default = next((p for p in profiles if p.get("id") == "default"), profiles[-1])
    best, best_score = default, 0

    for profile in profiles:
        if profile.get("id") == "default":
            continue
        match_tags = {t.lower() for t in profile.get("match_tags", [])}
        score = len(tags & match_tags)
        if score > best_score:
            best, best_score = profile, score

    return best
