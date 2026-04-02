"""CV upload and parsing router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

limiter = Limiter(key_func=get_remote_address)

from app.database import get_db
from app.models.db import DBSession
from app.models.schemas import CVParseResponse
from app.services.cv_service import extract_profile, parse_pdf_bytes

router = APIRouter(tags=["cv"])


@router.post("/cv/parse", response_model=CVParseResponse)
@limiter.limit("10/minute")
async def parse_cv(
    request: Request,
    file: UploadFile = File(...),
    session_id: str = Form(...),
    research_direction: str = Form(""),
    db: Session = Depends(get_db),
):
    """Upload a PDF resume, parse it via OpenAI, and persist the profile."""
    sess = db.query(DBSession).filter(DBSession.id == session_id).first()
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    text = parse_pdf_bytes(data)
    if not text:
        raise HTTPException(status_code=422, detail="Could not extract text from PDF")

    profile = extract_profile(text, research_direction=research_direction)

    # Persist resume text, profile, and research direction on the session row
    sess.resume_text = text
    sess.profile = profile
    if research_direction:
        sess.research_direction = research_direction
    sess.workflow_step = "search"
    db.commit()

    return CVParseResponse(profile=profile)
