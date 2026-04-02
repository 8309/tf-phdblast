"""Session management router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import DBSession, Professor
from app.models.schemas import ProfessorCounts, SessionCreate, SessionResponse

router = APIRouter(tags=["session"])


@router.post("/session", response_model=SessionResponse)
def create_session(db: Session = Depends(get_db)):
    """Create a new empty session and return its id + created_at."""
    sess = DBSession()
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return SessionResponse(
        id=sess.id,
        profile=sess.profile,
        research_direction=sess.research_direction or "",
        workflow_step=sess.workflow_step or "upload",
        created_at=sess.created_at,
        professor_counts=ProfessorCounts(),
    )


@router.get("/session", response_model=SessionResponse)
def get_session(
    session_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """Return session state including profile and professor counts per phase."""
    sess = db.query(DBSession).filter(DBSession.id == session_id).first()
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found")

    counts = ProfessorCounts(
        pass1=db.query(Professor)
        .filter(Professor.session_id == session_id, Professor.phase == "pass1")
        .count(),
        pass2=db.query(Professor)
        .filter(Professor.session_id == session_id, Professor.phase == "pass2")
        .count(),
        scored=db.query(Professor)
        .filter(
            Professor.session_id == session_id,
            Professor.preliminary_score.isnot(None),
        )
        .count(),
        deep=db.query(Professor)
        .filter(
            Professor.session_id == session_id,
            Professor.selected_for_deep.is_(True),
        )
        .count(),
    )

    return SessionResponse(
        id=sess.id,
        profile=sess.profile,
        research_direction=sess.research_direction or "",
        workflow_step=sess.workflow_step or "upload",
        created_at=sess.created_at,
        professor_counts=counts,
    )
