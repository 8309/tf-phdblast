"""School search (pass 1) and recommendation router."""

from __future__ import annotations

import asyncio
import threading

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.sse import create_sse_queue, sse_event
from app.database import SessionLocal, get_db
from app.models.db import DBSession, Professor
from app.models.schemas import SchoolRecommendRequest, SchoolSearchRequest
from app.services import crawl_service, scoring_service

router = APIRouter(tags=["schools"])


# ---------------------------------------------------------------------------
# POST /schools/search  (SSE)
# ---------------------------------------------------------------------------


@router.post("/schools/search")
async def search_schools(
    req: SchoolSearchRequest,
    db: Session = Depends(get_db),
):
    """Pass-1 directory crawl for selected schools.

    Streams SSE events:
      - ``progress``: per-school crawl status updates
      - ``professors``: batch of discovered professors
      - ``scoring``: preliminary scoring progress
      - ``done``: final summary
      - ``error``: on failure
    """
    sess = db.query(DBSession).filter(DBSession.id == req.session_id).first()
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Grab profile before spawning thread (db session won't be valid there)
    profile = sess.profile

    q, push, close = create_sse_queue()

    # Adapter: crawl_service calls on_event(dict) but push expects (type, data)
    def _push_adapter(event: dict) -> None:
        event_type = event.pop("type", "message")
        push(event_type, event)

    def _run():
        # Create a fresh DB session for this thread
        thread_db = SessionLocal()
        try:
            push("info", {"message": f"Starting crawl for {len(req.schools)} school(s)..."})
            crawl_service.run_pass1(
                db_session=thread_db,
                session_id=req.session_id,
                schools=[{"domain": s.domain, "name": s.name} for s in req.schools],
                keywords=req.keywords,
                stealth=req.stealth,
                on_event=_push_adapter,
                profile=profile,
            )
            # After crawl, run preliminary scoring
            scoring_service.score_preliminary(
                db_session=thread_db,
                session_id=req.session_id,
                profile=profile or {},
                on_event=_push_adapter,
            )
            # Advance workflow step
            s = thread_db.query(DBSession).filter(DBSession.id == req.session_id).first()
            if s:
                s.workflow_step = "search"
                thread_db.commit()

            # Include scored professors in the done event so the frontend can render them
            profs = (
                thread_db.query(Professor)
                .filter(Professor.session_id == req.session_id)
                .order_by(Professor.preliminary_score.desc().nullslast())
                .all()
            )
            from app.models.schemas import ProfessorSchema
            prof_dicts = [ProfessorSchema.model_validate(p).model_dump(mode="json") for p in profs]
            push("done", {"message": "Search and scoring complete", "professors": prof_dicts})
        except Exception as exc:
            import traceback
            traceback.print_exc()
            push("error", {"message": str(exc)})
        finally:
            thread_db.close()
            close()

    async def generate():
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        while True:
            event = await asyncio.wait_for(q.get(), timeout=300)
            if event is None:
                break
            yield event

    return StreamingResponse(generate(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# POST /schools/recommend
# ---------------------------------------------------------------------------


@router.post("/schools/recommend")
def recommend_schools(
    req: SchoolRecommendRequest,
    db: Session = Depends(get_db),
):
    """Use AI to recommend best-fit schools based on the user profile."""
    sess = db.query(DBSession).filter(DBSession.id == req.session_id).first()
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not sess.profile:
        raise HTTPException(status_code=400, detail="No profile found; upload a CV first")

    recommendations = scoring_service.recommend_schools(
        profile=sess.profile,
        top_n=req.top_n,
    )
    return recommendations
