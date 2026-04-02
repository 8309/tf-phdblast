"""SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.types import JSON as GenericJSON

# Use JSONB on PostgreSQL (GIN-indexable), fall back to JSON on SQLite
try:
    from app.config import settings
    JSON = PG_JSONB if settings.DATABASE_URL.startswith("postgresql") else GenericJSON
except Exception:
    JSON = GenericJSON

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class DBSession(Base):
    """A user session (resume upload + crawl run)."""

    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=_new_uuid)
    resume_text = Column(Text, default="")
    profile = Column(JSON, nullable=True)
    research_direction = Column(String, default="")
    workflow_step = Column(
        String, default="upload"
    )  # upload | search | deep | match | outreach
    crawl_running = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    professors = relationship(
        "Professor", back_populates="session", cascade="all, delete-orphan"
    )
    crawled_schools = relationship(
        "CrawledSchool", back_populates="session", cascade="all, delete-orphan"
    )
    outreach_emails = relationship(
        "OutreachEmail", back_populates="session", cascade="all, delete-orphan"
    )


class CrawledSchool(Base):
    """A school that was crawled in a session (tracks per-school progress)."""

    __tablename__ = "crawled_schools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    name = Column(String, default="")
    domain = Column(String, default="")
    status = Column(String, default="pending")  # pending | crawling | done | error
    professor_count = Column(Integer, default=0)
    error_message = Column(Text, default="")
    crawled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    # Relationship
    session = relationship("DBSession", back_populates="crawled_schools")

    __table_args__ = (
        Index("ix_crawled_school_session", "session_id"),
    )


class Professor(Base):
    """A professor discovered during crawling."""

    __tablename__ = "professors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)

    # Basic info (from directory page — pass 1)
    name = Column(String, default="")
    email = Column(String, default="")
    title = Column(String, default="")
    department = Column(String, default="")
    university = Column(String, default="")
    university_domain = Column(String, default="")
    profile_url = Column(String, default="")

    # Deep info (from profile page — pass 2)
    lab_name = Column(String, default="")
    lab_url = Column(String, default="")
    research_summary = Column(Text, default="")
    research_keywords = Column(JSON, default=list)
    recent_papers = Column(JSON, default=list)
    scholar_url = Column(String, default="")
    accepting_students = Column(Boolean, nullable=True)
    open_positions = Column(String, default="")
    funding = Column(JSON, default=list)
    recruiting_signals = Column(JSON, default=list)
    lab_size = Column(Integer, nullable=True)
    recent_graduates = Column(Integer, nullable=True)
    recruiting_likelihood = Column(String, default="unknown")

    # Metadata
    crawled_at = Column(DateTime, nullable=True)
    source = Column(String, default="faculty_directory")

    # Scoring
    preliminary_score = Column(Float, nullable=True)
    preliminary_reason = Column(Text, default="")
    final_score = Column(Float, nullable=True)
    final_reason = Column(Text, default="")

    # Workflow
    selected_for_deep = Column(Boolean, default=False)
    phase = Column(String, default="pass1")

    # Relationships
    session = relationship("DBSession", back_populates="professors")
    outreach_emails = relationship(
        "OutreachEmail", back_populates="professor", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_professor_session_id", "session_id"),
        Index("ix_professor_session_phase", "session_id", "phase"),
    )


class OutreachEmail(Base):
    """A generated outreach email for a professor."""

    __tablename__ = "outreach_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    professor_id = Column(Integer, ForeignKey("professors.id"), nullable=False)
    subject = Column(String, default="")
    body = Column(Text, default="")
    alignment = Column(Text, default="")
    cv_md = Column(Text, default="")
    status = Column(String, default="draft")  # draft | sent | failed
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    session = relationship("DBSession", back_populates="outreach_emails")
    professor = relationship("Professor", back_populates="outreach_emails")

    __table_args__ = (
        Index("ix_outreach_session", "session_id"),
        Index("ix_outreach_professor", "professor_id"),
    )


# ===================================================================
# Global cache tables — shared across sessions
# ===================================================================


class CachedSchool(Base):
    """Global school cache. Keyed by domain, shared across all sessions."""

    __tablename__ = "cached_schools"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, default="")
    professor_count = Column(Integer, default=0)
    department_count = Column(Integer, default=0)
    status = Column(String, default="pending")  # pending | crawling | done | error
    error_message = Column(Text, default="")
    last_crawled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    # Relationships
    departments = relationship(
        "CachedDepartment", back_populates="school", cascade="all, delete-orphan"
    )
    crawl_records = relationship(
        "CachedCrawlRecord", back_populates="school", cascade="all, delete-orphan"
    )


class CachedCrawlRecord(Base):
    """Tracks which keyword sets have been crawled for a school.

    Each Pass 1 crawl creates a record so future sessions with overlapping
    research directions can skip re-crawling.
    """

    __tablename__ = "cached_crawl_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cached_school_id = Column(
        Integer, ForeignKey("cached_schools.id"), nullable=False
    )
    keywords = Column(JSON, default=list)  # e.g. ["NLP", "machine learning"]
    departments_found = Column(JSON, default=list)  # e.g. ["EECS", "Linguistics"]
    professor_count = Column(Integer, default=0)
    crawled_at = Column(DateTime, default=_utcnow)

    # Relationship
    school = relationship("CachedSchool", back_populates="crawl_records")

    __table_args__ = (
        Index("ix_crawl_record_school", "cached_school_id"),
    )


class CachedDepartment(Base):
    """A department discovered at a university. Groups cached professors."""

    __tablename__ = "cached_departments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cached_school_id = Column(
        Integer, ForeignKey("cached_schools.id"), nullable=False
    )
    name = Column(String, default="")
    url = Column(String, default="")  # faculty listing page URL
    professor_count = Column(Integer, default=0)
    last_crawled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    school = relationship("CachedSchool", back_populates="departments")
    cached_professors = relationship(
        "CachedProfessor", back_populates="cached_department", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_cached_dept_school", "cached_school_id"),
        Index(
            "ix_cached_dept_unique",
            "cached_school_id",
            "name",
            unique=True,
        ),
    )


class CachedProfessor(Base):
    """Global professor cache. Factual data only, no per-session scores."""

    __tablename__ = "cached_professors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cached_school_id = Column(
        Integer, ForeignKey("cached_schools.id"), nullable=False
    )
    cached_department_id = Column(
        Integer, ForeignKey("cached_departments.id"), nullable=True
    )

    # Basic info (pass 1)
    name = Column(String, default="")
    email = Column(String, default="")
    title = Column(String, default="")
    department = Column(String, default="")
    university = Column(String, default="")
    university_domain = Column(String, default="")
    profile_url = Column(String, default="")
    research_summary = Column(Text, default="")
    source = Column(String, default="faculty_directory")
    crawled_at = Column(DateTime, nullable=True)

    # Deep info (pass 2) — filled later when any session deep-crawls
    lab_name = Column(String, default="")
    lab_url = Column(String, default="")
    research_keywords = Column(JSON, default=list)
    recent_papers = Column(JSON, default=list)
    scholar_url = Column(String, default="")
    accepting_students = Column(Boolean, nullable=True)
    open_positions = Column(String, default="")
    funding = Column(JSON, default=list)
    recruiting_signals = Column(JSON, default=list)
    lab_size = Column(Integer, nullable=True)
    recent_graduates = Column(Integer, nullable=True)
    recruiting_likelihood = Column(String, default="unknown")
    deep_crawled_at = Column(DateTime, nullable=True)

    # Relationships
    school = relationship("CachedSchool")
    cached_department = relationship("CachedDepartment", back_populates="cached_professors")

    __table_args__ = (
        Index("ix_cached_prof_school", "cached_school_id"),
        Index("ix_cached_prof_dept", "cached_department_id"),
        Index("ix_cached_prof_domain", "university_domain"),
    )
