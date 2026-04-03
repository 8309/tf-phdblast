"""Ranking data loading and lookup service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Paths relative to the backend root
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_RANKINGS_DIR = _DATA_DIR / "rankings"

# ---------------------------------------------------------------------------
# Field display mapping (field_key -> human-readable label)
# ---------------------------------------------------------------------------

FIELD_DISPLAY: dict[str, str] = {
    # CS & Computing
    "computer_science": "CS - Computer Science (General)",
    "artificial_intelligence": "CS - Artificial Intelligence / ML",
    "data_science": "CS - Data Science / Analytics",
    "cybersecurity": "CS - Cybersecurity",
    "human_computer_interaction": "CS - Human-Computer Interaction",
    "robotics": "CS - Robotics",
    # Engineering
    "mechanical_engineering": "Eng - Mechanical Engineering",
    "electrical_engineering": "Eng - Electrical & Computer Engineering",
    "biomedical_engineering": "Eng - Biomedical Engineering",
    "civil_engineering": "Eng - Civil Engineering",
    "chemical_engineering": "Eng - Chemical Engineering",
    "aerospace_engineering": "Eng - Aerospace Engineering",
    "environmental_engineering": "Eng - Environmental Engineering",
    "industrial_engineering": "Eng - Industrial & Systems Engineering",
    "nuclear_engineering": "Eng - Nuclear Engineering",
    "ocean_engineering": "Eng - Ocean Engineering",
    "energy_engineering": "Eng - Energy Engineering",
    # Materials & Physical Sciences
    "materials_science": "Phys - Materials Science",
    "physics": "Phys - Physics (General)",
    "applied_physics": "Phys - Applied Physics",
    "chemistry": "Phys - Chemistry",
    "astronomy_astrophysics": "Phys - Astronomy & Astrophysics",
    "earth_sciences": "Phys - Earth Sciences / Geology",
    "quantum_computing": "Phys - Quantum Computing",
    # Mathematics & Statistics
    "mathematics": "Math - Mathematics (General)",
    "applied_mathematics": "Math - Applied Mathematics",
    "statistics": "Math - Statistics",
    "operations_research": "Math - Operations Research",
    # Life Sciences & Medical
    "biology": "Bio - Biology (General)",
    "neuroscience": "Bio - Neuroscience",
    "genetics_genomics": "Bio - Genetics & Genomics",
    "computational_biology": "Bio - Computational Biology",
    "bioinformatics": "Bio - Bioinformatics",
    "pharmacology": "Bio - Pharmacology",
    "public_health": "Bio - Public Health",
    # Social Sciences & Business
    "economics": "Social - Economics",
    "finance": "Social - Finance",
    "political_science": "Social - Political Science",
    "psychology": "Social - Psychology",
    "sociology": "Social - Sociology",
}

# ---------------------------------------------------------------------------
# Cache — populated once on first access
# ---------------------------------------------------------------------------

_rankings_cache: dict[str, Any] = {}


def _ensure_loaded() -> None:
    """Load all ranking files into ``_rankings_cache`` if not yet loaded."""
    if _rankings_cache:
        return

    # Per-field ranking files (e.g. computer_science.json)
    if _RANKINGS_DIR.is_dir():
        for path in _RANKINGS_DIR.glob("*.json"):
            if path.name == "index.json":
                continue
            key = path.stem  # field_key
            _rankings_cache[f"field:{key}"] = json.loads(path.read_text())

    # Index
    idx_path = _RANKINGS_DIR / "index.json"
    if idx_path.exists():
        _rankings_cache["_index"] = json.loads(idx_path.read_text())
    else:
        _rankings_cache["_index"] = {"sources": {}, "fields": []}

    # Global lists
    the_path = _DATA_DIR / "the_global_top200.json"
    if the_path.exists():
        _rankings_cache["global:the"] = json.loads(the_path.read_text())
    else:
        _rankings_cache["global:the"] = []

    qs_path = _DATA_DIR / "qs_global_top300.json"
    if qs_path.exists():
        _rankings_cache["global:qs"] = json.loads(qs_path.read_text())
    else:
        _rankings_cache["global:qs"] = []

    all_path = _DATA_DIR / "global_universities.json"
    if all_path.exists():
        _rankings_cache["global:all"] = json.loads(all_path.read_text())
    else:
        _rankings_cache["global:all"] = []


def load_all_rankings() -> None:
    """Explicitly pre-load all rankings (call at startup)."""
    _ensure_loaded()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_field_display() -> dict[str, str]:
    """Return the FIELD_DISPLAY mapping."""
    return FIELD_DISPLAY


def get_field_ranking(field: str, source: str) -> tuple[list[dict], str]:
    """Load ranking for a *field* + *source*.

    Returns ``(schools_list, source_url)``.
    """
    _ensure_loaded()
    data = _rankings_cache.get(f"field:{field}", {})
    rankings = data.get("rankings", {})
    if source not in rankings:
        return [], ""
    src = rankings[source]
    return src.get("schools", []), src.get("url", "")


def get_available_sources(field: str) -> list[str]:
    """Return which ranking sources are available for a given field."""
    _ensure_loaded()
    data = _rankings_cache.get(f"field:{field}", {})
    return list(data.get("rankings", {}).keys())


def get_global_schools(source: str) -> list[dict]:
    """Return schools from a global ranking list.

    *source* should be ``"the"`` or ``"qs"``.
    """
    _ensure_loaded()
    return _rankings_cache.get(f"global:{source}", [])


def filter_by_country(schools: list[dict], country_code: str) -> list[dict]:
    """Filter schools by 2-letter country code. Empty = no filter."""
    if not country_code:
        return schools
    return [s for s in schools if s.get("country", "US") == country_code]
