"""Cache management router — view and clear the global crawl cache."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import CachedDepartment, CachedProfessor, CachedSchool
from app.models.schemas import CachedSchoolSchema, CacheStatsResponse
from app.services.crawl_service import _normalize_domain

router = APIRouter(tags=["cache"])


@router.get("/cache/stats", response_model=CacheStatsResponse)
def cache_stats(db: Session = Depends(get_db)):
    """Return summary of all cached schools, departments, and professor counts."""
    schools = (
        db.query(CachedSchool)
        .order_by(CachedSchool.last_crawled_at.desc())
        .all()
    )
    total_depts = db.query(CachedDepartment).count()
    total_profs = db.query(CachedProfessor).count()
    return CacheStatsResponse(
        total_schools=len(schools),
        total_departments=total_depts,
        total_professors=total_profs,
        schools=[CachedSchoolSchema.model_validate(s) for s in schools],
    )


@router.delete("/cache/school")
def clear_school_cache(
    domain: str = Query(..., description="School domain to clear, e.g. mit.edu"),
    db: Session = Depends(get_db),
):
    """Clear cache for a specific school (forces re-crawl next time)."""
    cached = db.query(CachedSchool).filter(CachedSchool.domain == _normalize_domain(domain)).first()
    if not cached:
        return {"deleted": False, "message": f"No cache for {domain}"}
    db.delete(cached)  # cascade deletes departments + professors
    db.commit()
    return {"deleted": True, "domain": domain}


@router.delete("/cache/all")
def clear_all_cache(db: Session = Depends(get_db)):
    """Clear the entire crawl cache."""
    n_profs = db.query(CachedProfessor).delete()
    n_depts = db.query(CachedDepartment).delete()
    n_schools = db.query(CachedSchool).delete()
    db.commit()
    return {
        "deleted_schools": n_schools,
        "deleted_departments": n_depts,
        "deleted_professors": n_profs,
    }
