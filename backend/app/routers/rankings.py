"""Rankings data router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import RankingResponse, RankingSchool
from app.services.ranking_service import (
    FIELD_DISPLAY,
    filter_by_country,
    get_available_sources,
    get_field_ranking,
    get_global_schools,
)

router = APIRouter(tags=["rankings"])


# ---------------------------------------------------------------------------
# GET /rankings/fields
# ---------------------------------------------------------------------------


@router.get("/rankings/fields")
def list_fields():
    """Return the FIELD_DISPLAY dict (field_key -> human-readable label)."""
    return FIELD_DISPLAY


@router.get("/rankings/fields/{field}/sources")
def list_field_sources(field: str):
    """Return available ranking sources for a field."""
    if field not in FIELD_DISPLAY:
        raise HTTPException(status_code=404, detail=f"Unknown field: {field}")
    sources = get_available_sources(field)
    # Return with display names from index
    SOURCE_NAMES = {
        "usnews": "US News",
        "qs": "QS",
        "arwu": "ARWU (Shanghai)",
        "csrankings": "CSRankings",
        "the_overall": "THE",
    }
    return [{"key": s, "name": SOURCE_NAMES.get(s, s)} for s in sources]


# ---------------------------------------------------------------------------
# GET /rankings/global/{source}
# ---------------------------------------------------------------------------


@router.get("/rankings/global/{source}", response_model=RankingResponse)
def global_ranking(
    source: str,
    country: str = Query("", description="2-letter country code filter"),
):
    """Return QS or THE global school list, with optional country filter.

    ``source`` must be ``"qs"`` or ``"the"``.
    """
    if source not in ("qs", "the", "all"):
        raise HTTPException(status_code=400, detail="source must be 'qs', 'the', or 'all'")

    schools = get_global_schools(source)
    if country:
        schools = filter_by_country(schools, country)

    return RankingResponse(
        schools=[RankingSchool(**s) for s in schools],
        source_url="",
    )


# ---------------------------------------------------------------------------
# GET /rankings/{field}
# ---------------------------------------------------------------------------


@router.get("/rankings/{field}", response_model=RankingResponse)
def field_ranking(
    field: str,
    source: str = Query("", description="Ranking source key (usnews, qs, arwu, csrankings). Empty = first available."),
    country: str = Query("", description="2-letter country code filter"),
):
    """Return schools for a specific field + ranking source."""
    if field not in FIELD_DISPLAY:
        raise HTTPException(status_code=404, detail=f"Unknown field: {field}")

    # If no source specified, pick the first available one
    if not source:
        available = get_available_sources(field)
        source = available[0] if available else ""

    if not source:
        return RankingResponse(schools=[], source_url="")

    schools, source_url = get_field_ranking(field, source)
    if country:
        schools = filter_by_country(schools, country)

    # Fallback: if country filter yields no field-specific results,
    # return all schools from that country in the global database
    if not schools and country:
        global_schools = get_global_schools("all")
        schools = filter_by_country(global_schools, country)
        source_url = ""

    return RankingResponse(
        schools=[RankingSchool(**s) for s in schools],
        source_url=source_url,
    )
