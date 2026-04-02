"""AI scoring service — preliminary and final matching."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.models.db import Professor as DBProfessor


def _profile_summary_text(profile: dict) -> str:
    """Build a concise profile summary for LLM consumption."""
    p = profile
    return (
        f"Name: {p.get('full_name', '')}\n"
        f"Degree: {p.get('highest_degree', '')}\n"
        f"Affiliation: {p.get('current_affiliation', '')}\n"
        f"Research: {', '.join(p.get('research_interests', []))}\n"
        f"Target: {', '.join(p.get('target_direction', []))}\n"
        f"Experience: {p.get('experience_summary', '')}\n"
        f"Publications: {'; '.join(p.get('publications', []))}\n"
        f"Skills: {', '.join(p.get('skills', []))}"
    )


def _parse_json_response(raw: str) -> Any:
    """Strip markdown fences and extract JSON from an LLM response."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        text = m.group(0)
    return json.loads(text)


# ---------------------------------------------------------------------------
# Preliminary scoring (Pass 1 data only)
# ---------------------------------------------------------------------------


def score_preliminary(
    db_session: Session,
    session_id: str,
    profile: dict,
    on_event: Callable[[dict], None] | None = None,
) -> list[dict]:
    """Batch-score all Pass 1 professors for *session_id*.

    Processes professors in batches of 40.  Updates ``preliminary_score``
    and ``preliminary_reason`` in the DB.

    Returns the full list sorted by score descending.
    """
    profs: list[DBProfessor] = (
        db_session.query(DBProfessor)
        .filter(DBProfessor.session_id == session_id)
        .all()
    )

    if not profs:
        return []

    profs_for_llm = [
        {
            "idx": i,
            "name": p.name,
            "university": p.university,
            "title": p.title,
            "research": p.research_summary,
        }
        for i, p in enumerate(profs)
    ]

    oai = OpenAI()
    ranked: list[dict] = []
    profile_text = _profile_summary_text(profile)

    for start in range(0, len(profs_for_llm), 40):
        batch = profs_for_llm[start : start + 40]
        batch_ranked: list[dict] | None = None

        for attempt in range(3):
            try:
                resp = oai.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You match PhD applicants to professors based on research alignment. "
                                "This is a PRELIMINARY screening based on limited directory info. "
                                "Score 0-100. Return JSON array: "
                                '[{"idx": int, "score": int, "reason": "brief"}] '
                                "sorted desc. ONLY valid JSON."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"## Applicant\n{profile_text}\n\n"
                                f"## Professors\n{json.dumps(batch, ensure_ascii=False)}"
                            ),
                        },
                    ],
                    temperature=0,
                )
                raw = resp.choices[0].message.content.strip()
                batch_ranked = _parse_json_response(raw)
                break
            except Exception as e:
                if attempt == 2:
                    # Fallback: default score for this batch
                    batch_ranked = [
                        {"idx": b["idx"], "score": 50, "reason": "AI scoring failed"}
                        for b in batch
                    ]

        if batch_ranked:
            ranked.extend(batch_ranked)

        if on_event:
            on_event({
                "type": "scoring_progress",
                "done": min(start + 40, len(profs_for_llm)),
                "total": len(profs_for_llm),
            })

    # Build results from scored data (do NOT write scores back to DB)
    score_map = {item["idx"]: item for item in ranked}
    results: list[dict] = []

    for i, prof in enumerate(profs):
        info = score_map.get(i, {})
        results.append({
            "id": prof.id,
            "name": prof.name,
            "university": prof.university,
            "email": prof.email,
            "title": prof.title,
            "department": prof.department,
            "research_summary": prof.research_summary,
            "profile_url": prof.profile_url,
            "preliminary_score": info.get("score", 0),
            "preliminary_reason": info.get("reason", ""),
        })

    results.sort(key=lambda x: x["preliminary_score"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Final scoring (Pass 2 deep data)
# ---------------------------------------------------------------------------


def score_final(
    db_session: Session,
    session_id: str,
    profile: dict,
) -> list[dict]:
    """Score professors that have been deep-crawled (Pass 2) using detailed
    profile info.

    Updates ``final_score`` and ``final_reason`` in the DB.
    Returns sorted list.
    """
    profs: list[DBProfessor] = (
        db_session.query(DBProfessor)
        .filter(
            DBProfessor.session_id == session_id,
            DBProfessor.selected_for_deep == True,  # noqa: E712
        )
        .all()
    )

    if not profs:
        return []

    profs_for_llm = []
    for i, p in enumerate(profs):
        profs_for_llm.append({
            "idx": i,
            "name": p.name,
            "university": p.university,
            "title": p.title,
            "lab_name": p.lab_name,
            "research_summary": p.research_summary,
            "research_keywords": p.research_keywords or [],
            "recent_papers": (p.recent_papers or [])[:3],
            "funding": p.funding or [],
            "accepting_students": p.accepting_students,
            "recruiting_likelihood": p.recruiting_likelihood,
            "recruiting_signals": p.recruiting_signals or [],
            "open_positions": p.open_positions,
        })

    oai = OpenAI()
    profile_text = _profile_summary_text(profile)

    resp = oai.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You match PhD applicants to professors using DETAILED profile info. "
                    "Score 0-100 based on:\n"
                    "- Research alignment (25%)\n"
                    "- Recruiting likelihood -- HIGH >> MEDIUM >> UNKNOWN >> LOW. "
                    "Consider: accepting_students, recruiting_signals, recruiting_likelihood, "
                    "open_positions. This is the MOST important factor for actionability (30%)\n"
                    "- Active funding -- professors with grants can fund students (20%)\n"
                    "- Recent papers showing active research (15%)\n"
                    "- Skills/methods overlap (10%)\n\n"
                    "Return JSON array: "
                    '[{"idx": int, "score": int, "reason": "2 sentences explaining fit"}] '
                    "sorted desc. ONLY valid JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"## Applicant\n{profile_text}\n\n"
                    f"## Professors (with deep info)\n"
                    f"{json.dumps(profs_for_llm, ensure_ascii=False)}"
                ),
            },
        ],
        temperature=0,
    )

    raw = resp.choices[0].message.content.strip()
    try:
        scored = _parse_json_response(raw)
    except (json.JSONDecodeError, ValueError):
        scored = [
            {"idx": i, "score": 50, "reason": "AI scoring failed (parse error)"}
            for i in range(len(profs))
        ]

    results: list[dict] = []
    for item in scored:
        if not isinstance(item, dict):
            continue
        idx = item.get("idx")
        if idx is None or not (0 <= idx < len(profs)):
            continue
        p = profs[idx]
        p.final_score = item["score"]
        p.final_reason = item["reason"]
        results.append({
            "id": p.id,
            "name": p.name,
            "university": p.university,
            "email": p.email,
            "title": p.title,
            "lab_name": p.lab_name,
            "research_summary": p.research_summary,
            "research_keywords": p.research_keywords or [],
            "recent_papers": p.recent_papers or [],
            "funding": p.funding or [],
            "accepting_students": p.accepting_students,
            "recruiting_likelihood": p.recruiting_likelihood,
            "recruiting_signals": p.recruiting_signals or [],
            "open_positions": p.open_positions,
            "scholar_url": p.scholar_url,
            "profile_url": p.profile_url,
            "lab_url": p.lab_url,
            "final_score": p.final_score,
            "final_reason": p.final_reason,
        })

    db_session.commit()

    results.sort(key=lambda x: x.get("final_score", 0), reverse=True)
    return results


# ---------------------------------------------------------------------------
# AI school recommendation
# ---------------------------------------------------------------------------


def recommend_schools(profile: dict, top_n: int = 15) -> list[dict]:
    """Use OpenAI to recommend universities based on the applicant profile.

    Reads the global school list (THE top 200) and returns a ranked subset.
    """
    from app.services.ranking_service import get_global_schools

    the_schools = get_global_schools("the")
    school_list = json.dumps(
        [{"name": s["name"], "domain": s["domain"]} for s in the_schools],
        ensure_ascii=False,
    )

    client = OpenAI()
    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are an academic advisor. Given a PhD applicant's profile, "
                    f"select the top {top_n} best-fit universities from the provided list. "
                    f"Consider: research alignment, department strength in the applicant's "
                    f"target directions, and overall program quality.\n\n"
                    f"Return a JSON array of objects: "
                    f'[{{"name": "...", "domain": "...", "reason": "1 sentence"}}] '
                    f"sorted by fit. ONLY valid JSON, no markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"## Applicant\n"
                    f"Research interests: {', '.join(profile.get('research_interests', []))}\n"
                    f"Target directions: {', '.join(profile.get('target_direction', []))}\n"
                    f"Degree: {profile.get('highest_degree', '')}\n"
                    f"Skills: {', '.join(profile.get('skills', []))}\n"
                    f"Experience: {profile.get('experience_summary', '')}\n\n"
                    f"## Available Universities\n{school_list}"
                ),
            },
        ],
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()
    try:
        return _parse_json_response(raw)
    except (json.JSONDecodeError, ValueError):
        return []
