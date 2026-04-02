"""Pydantic models for API request / response."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class SessionCreate(BaseModel):
    """Body for POST /api/sessions (intentionally empty)."""
    pass


class ProfessorCounts(BaseModel):
    pass1: int = 0
    pass2: int = 0
    scored: int = 0
    deep: int = 0


class SessionResponse(BaseModel):
    id: str
    profile: dict[str, Any] | None = None
    research_direction: str = ""
    workflow_step: str = "upload"
    created_at: datetime
    professor_counts: ProfessorCounts = Field(default_factory=ProfessorCounts)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# CV parsing
# ---------------------------------------------------------------------------


class CVParseRequest(BaseModel):
    session_id: str
    research_direction: str | None = None


class CVParseResponse(BaseModel):
    profile: dict[str, Any]


# ---------------------------------------------------------------------------
# Professor
# ---------------------------------------------------------------------------


class ProfessorSchema(BaseModel):
    id: int
    session_id: str

    # Basic
    name: str = ""
    email: str = ""
    title: str = ""
    department: str = ""
    university: str = ""
    university_domain: str = ""
    profile_url: str = ""

    # Deep
    lab_name: str = ""
    lab_url: str = ""
    research_summary: str = ""
    research_keywords: list[str] = Field(default_factory=list)
    recent_papers: list[str] = Field(default_factory=list)
    scholar_url: str = ""
    accepting_students: bool | None = None
    open_positions: str = ""
    funding: list[str] = Field(default_factory=list)
    recruiting_signals: list[str] = Field(default_factory=list)
    lab_size: int | None = None
    recent_graduates: int | None = None
    recruiting_likelihood: str = "unknown"

    # Metadata
    crawled_at: datetime | None = None
    source: str = "faculty_directory"

    # Scores
    preliminary_score: float | None = None
    preliminary_reason: str = ""
    final_score: float | None = None
    final_reason: str = ""

    # Workflow
    selected_for_deep: bool = False
    phase: str = "pass1"

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Crawled school
# ---------------------------------------------------------------------------


class CrawledSchoolSchema(BaseModel):
    id: int
    session_id: str
    name: str = ""
    domain: str = ""
    status: str = "pending"
    professor_count: int = 0
    error_message: str = ""
    crawled_at: datetime | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Outreach email
# ---------------------------------------------------------------------------


class OutreachEmailSchema(BaseModel):
    id: int
    session_id: str
    professor_id: int
    subject: str = ""
    body: str = ""
    alignment: str = ""
    cv_md: str = ""
    status: str = "draft"
    created_at: datetime

    model_config = {"from_attributes": True}


class OutreachEmailResponse(BaseModel):
    professor_name: str
    professor_email: str
    email: OutreachEmailSchema


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class CachedDepartmentSchema(BaseModel):
    id: int
    cached_school_id: int
    name: str = ""
    url: str = ""
    professor_count: int = 0
    last_crawled_at: datetime | None = None

    model_config = {"from_attributes": True}


class CachedCrawlRecordSchema(BaseModel):
    id: int
    cached_school_id: int
    keywords: list[str] = Field(default_factory=list)
    departments_found: list[str] = Field(default_factory=list)
    professor_count: int = 0
    crawled_at: datetime | None = None

    model_config = {"from_attributes": True}


class CachedSchoolSchema(BaseModel):
    id: int
    domain: str
    name: str = ""
    professor_count: int = 0
    department_count: int = 0
    status: str = "pending"
    last_crawled_at: datetime | None = None
    departments: list[CachedDepartmentSchema] = Field(default_factory=list)
    crawl_records: list[CachedCrawlRecordSchema] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CachedProfessorSchema(BaseModel):
    id: int
    cached_school_id: int
    cached_department_id: int | None = None
    name: str = ""
    email: str = ""
    title: str = ""
    department: str = ""
    university: str = ""
    university_domain: str = ""
    profile_url: str = ""
    research_summary: str = ""
    crawled_at: datetime | None = None
    deep_crawled_at: datetime | None = None

    model_config = {"from_attributes": True}


class CacheStatsResponse(BaseModel):
    total_schools: int = 0
    total_departments: int = 0
    total_professors: int = 0
    schools: list[CachedSchoolSchema] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Crawl requests
# ---------------------------------------------------------------------------


class SchoolItem(BaseModel):
    name: str
    domain: str = Field(..., pattern=r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class SchoolSearchRequest(BaseModel):
    session_id: str
    schools: list[SchoolItem]
    keywords: list[str] = Field(default_factory=list)
    stealth: bool = False


class DeepCrawlRequest(BaseModel):
    session_id: str
    professor_ids: list[int]
    stealth: bool = False


# ---------------------------------------------------------------------------
# Matching / ranking
# ---------------------------------------------------------------------------


class MatchRequest(BaseModel):
    session_id: str


class RankingSchool(BaseModel):
    rank: int
    name: str
    domain: str
    country: str = "US"


class RankingResponse(BaseModel):
    schools: list[RankingSchool]
    source_url: str = ""


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class ExportRequest(BaseModel):
    session_id: str
    phase: str = "pass1"
    format: str = "json"  # "json" | "csv"


# ---------------------------------------------------------------------------
# School recommendation
# ---------------------------------------------------------------------------


class SchoolRecommendRequest(BaseModel):
    session_id: str
    top_n: int = 15


# ---------------------------------------------------------------------------
# Outreach
# ---------------------------------------------------------------------------


class OutreachRequest(BaseModel):
    session_id: str
    professor_ids: list[int]
