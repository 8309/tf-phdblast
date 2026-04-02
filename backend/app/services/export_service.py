"""Export service -- CSV and JSON export of professor data."""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.db import Professor as DBProfessor


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_PRELIMINARY_FIELDS = [
    "score", "name", "university", "email", "department", "title",
    "research_summary", "profile_url", "reason",
]

_DEEP_FIELDS = [
    "name", "university", "email", "title", "lab_name", "lab_url",
    "research_summary", "research_keywords", "funding",
    "accepting_students", "recruiting_likelihood", "recruiting_signals",
    "recent_papers", "profile_url", "scholar_url", "open_positions",
]


def _query_professors(
    db_session: Session, session_id: str, phase: str,
) -> list[DBProfessor]:
    """Load professors for a session, optionally filtered by phase."""
    q = db_session.query(DBProfessor).filter(
        DBProfessor.session_id == session_id,
    )
    if phase == "deep":
        q = q.filter(DBProfessor.selected_for_deep == True)  # noqa: E712
    return q.order_by(
        DBProfessor.preliminary_score.desc().nullslast(),
    ).all()


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


def export_professors_csv(
    db_session: Session, session_id: str, phase: str = "preliminary",
) -> str:
    """Write professors to a CSV file in /tmp and return the file path.

    *phase*: ``"preliminary"`` exports Pass 1 scored data;
             ``"deep"`` exports Pass 2 deep-crawled data.
    """
    profs = _query_professors(db_session, session_id, phase)
    if not profs:
        return ""

    if phase == "deep":
        return _write_deep_csv(profs)
    return _write_preliminary_csv(profs)


def _write_preliminary_csv(profs: list[DBProfessor]) -> str:
    path = Path(tempfile.gettempdir()) / "phd_outreach_professors.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_PRELIMINARY_FIELDS)
        writer.writeheader()
        for p in profs:
            writer.writerow({
                "score": p.preliminary_score or 0,
                "name": p.name,
                "university": p.university,
                "email": p.email,
                "department": p.department,
                "title": p.title,
                "research_summary": p.research_summary,
                "profile_url": p.profile_url,
                "reason": p.preliminary_reason,
            })
    return str(path)


def _write_deep_csv(profs: list[DBProfessor]) -> str:
    path = Path(tempfile.gettempdir()) / "phd_outreach_deep_analysis.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_DEEP_FIELDS)
        writer.writeheader()
        for p in profs:
            writer.writerow({
                "name": p.name,
                "university": p.university,
                "email": p.email,
                "title": p.title,
                "lab_name": p.lab_name,
                "lab_url": p.lab_url,
                "research_summary": p.research_summary,
                "research_keywords": ", ".join(p.research_keywords or []),
                "funding": " | ".join(p.funding or []),
                "accepting_students": p.accepting_students,
                "recruiting_likelihood": p.recruiting_likelihood,
                "recruiting_signals": " | ".join(p.recruiting_signals or []),
                "recent_papers": " | ".join(p.recent_papers or []),
                "profile_url": p.profile_url,
                "scholar_url": p.scholar_url,
                "open_positions": p.open_positions,
            })
    return str(path)


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------


def export_professors_json(
    db_session: Session, session_id: str, phase: str = "preliminary",
) -> str:
    """Write professors to a JSON file in /tmp and return the file path.

    *phase*: ``"preliminary"`` or ``"deep"``.
    """
    profs = _query_professors(db_session, session_id, phase)
    if not profs:
        return ""

    if phase == "deep":
        return _write_deep_json(profs)
    return _write_preliminary_json(profs)


def _write_preliminary_json(profs: list[DBProfessor]) -> str:
    export = []
    for p in profs:
        export.append({
            "score": p.preliminary_score or 0,
            "name": p.name,
            "university": p.university,
            "email": p.email,
            "department": p.department,
            "title": p.title,
            "research_summary": p.research_summary,
            "profile_url": p.profile_url,
            "reason": p.preliminary_reason,
        })
    path = Path(tempfile.gettempdir()) / "phd_outreach_professors.json"
    path.write_text(json.dumps(export, indent=2, ensure_ascii=False))
    return str(path)


def _write_deep_json(profs: list[DBProfessor]) -> str:
    export = []
    for p in profs:
        export.append({
            "name": p.name,
            "university": p.university,
            "email": p.email,
            "title": p.title,
            "lab_name": p.lab_name,
            "lab_url": p.lab_url,
            "research_summary": p.research_summary,
            "research_keywords": p.research_keywords or [],
            "funding": p.funding or [],
            "accepting_students": p.accepting_students,
            "recruiting_likelihood": p.recruiting_likelihood,
            "recruiting_signals": p.recruiting_signals or [],
            "recent_papers": p.recent_papers or [],
            "profile_url": p.profile_url,
            "scholar_url": p.scholar_url,
            "open_positions": p.open_positions,
            "preliminary_score": p.preliminary_score,
            "preliminary_reason": p.preliminary_reason,
            "final_score": p.final_score,
            "final_reason": p.final_reason,
        })
    path = Path(tempfile.gettempdir()) / "phd_outreach_deep_analysis.json"
    path.write_text(json.dumps(export, indent=2, ensure_ascii=False, default=str))
    return str(path)
