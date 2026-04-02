"""Outreach email generation router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

limiter = Limiter(key_func=get_remote_address)

from app.database import get_db
from app.models.db import DBSession, OutreachEmail, Professor
from app.models.schemas import OutreachEmailSchema, OutreachRequest

router = APIRouter(tags=["outreach"])


@router.post("/outreach/generate")
@limiter.limit("5/minute")
def generate_outreach_emails(
    request: Request,
    req: OutreachRequest,
    db: Session = Depends(get_db),
):
    """Generate personalised outreach emails for selected professors.

    Results are persisted to the outreach_emails table and returned.
    """
    sess = db.query(DBSession).filter(DBSession.id == req.session_id).first()
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not sess.profile:
        raise HTTPException(status_code=400, detail="No profile found; upload a CV first")

    professors = (
        db.query(Professor)
        .filter(
            Professor.session_id == req.session_id,
            Professor.id.in_(req.professor_ids),
        )
        .all()
    )
    if not professors:
        raise HTTPException(status_code=404, detail="No matching professors found")

    # Convert ORM rows to dicts for the outreach module
    prof_dicts = []
    for p in professors:
        prof_dicts.append(
            {
                "name": p.name,
                "email": p.email,
                "title": p.title,
                "department": p.department,
                "university": p.university,
                "profile_url": p.profile_url,
                "research_summary": p.research_summary,
                "research_keywords": p.research_keywords or [],
                "recent_papers": p.recent_papers or [],
                "lab_name": p.lab_name,
                "lab_url": p.lab_url,
                "accepting_students": p.accepting_students,
                "open_positions": p.open_positions,
                "funding": p.funding or [],
                "recruiting_signals": p.recruiting_signals or [],
            }
        )

    # Import outreach_agents from the backend root (not inside app/)
    import outreach_agents

    results = outreach_agents.generate_outreach(
        profile=sess.profile,
        resume_text=sess.resume_text or "",
        professors=prof_dicts,
    )

    # Persist generated emails to DB
    saved: list[dict] = []
    for res, prof in zip(results, professors):
        email_row = OutreachEmail(
            session_id=req.session_id,
            professor_id=prof.id,
            subject=res.get("email_subject", ""),
            body=res.get("email_body", ""),
            alignment=res.get("alignment", ""),
            cv_md=res.get("cv_md", ""),
            status="draft",
        )
        db.add(email_row)
        db.flush()
        saved.append({
            "professor_name": prof.name,
            "professor_email": prof.email,
            "email": OutreachEmailSchema.model_validate(email_row).model_dump(),
        })
    db.commit()

    # Update session workflow step
    sess.workflow_step = "outreach"
    db.commit()

    return {"results": saved}


@router.get("/outreach/emails")
def list_outreach_emails(
    session_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """List all generated outreach emails for a session."""
    emails = (
        db.query(OutreachEmail)
        .filter(OutreachEmail.session_id == session_id)
        .order_by(OutreachEmail.created_at.desc())
        .all()
    )
    results = []
    for e in emails:
        prof = db.query(Professor).filter(Professor.id == e.professor_id).first()
        results.append({
            "professor_name": prof.name if prof else "",
            "professor_email": prof.email if prof else "",
            "email": OutreachEmailSchema.model_validate(e).model_dump(),
        })
    return {"results": results}
