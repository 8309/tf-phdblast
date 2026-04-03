"""Professor deep-crawl and matching router."""

from __future__ import annotations

import asyncio
import threading

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.sse import create_sse_queue, sse_event
from app.database import SessionLocal, get_db
from app.models.db import DBSession
from app.models.schemas import DeepCrawlRequest, MatchRequest, ScorePreliminaryRequest
from app.services import crawl_service, scoring_service

router = APIRouter(tags=["professors"])


# ---------------------------------------------------------------------------
# POST /professors/score-preliminary  (SSE)
# ---------------------------------------------------------------------------


@router.post("/professors/score-preliminary")
async def score_preliminary(
    req: ScorePreliminaryRequest,
    db: Session = Depends(get_db),
):
    """Run preliminary AI scoring on Pass-1 professors.

    Streams SSE events:
      - ``scoring_progress``: batch progress
      - ``done``: scored professor list
      - ``error``: on failure
    """
    sess = db.query(DBSession).filter(DBSession.id == req.session_id).first()
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found")

    profile = sess.profile
    q, push, close = create_sse_queue()

    def _push_adapter(event: dict) -> None:
        event_type = event.pop("type", "message")
        push(event_type, event)

    def _run():
        thread_db = SessionLocal()
        try:
            scored_results = scoring_service.score_preliminary(
                db_session=thread_db,
                session_id=req.session_id,
                profile=profile or {},
                on_event=_push_adapter,
            )
            push("done", {"message": "Scoring complete", "professors": scored_results})
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
# POST /professors/deep-crawl  (SSE)
# ---------------------------------------------------------------------------


@router.post("/professors/deep-crawl")
async def deep_crawl(
    req: DeepCrawlRequest,
    db: Session = Depends(get_db),
):
    """Pass-2 deep crawl for selected professors.

    Streams SSE events:
      - ``progress``: per-professor crawl status
      - ``card``: detailed professor card data as it arrives
      - ``done``: final summary
      - ``error``: on failure
    """
    sess = db.query(DBSession).filter(DBSession.id == req.session_id).first()
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found")

    q, push, close = create_sse_queue()

    # Adapter: crawl_service calls on_event(dict) but push expects (type, data)
    def _push_adapter(event: dict) -> None:
        event_type = event.pop("type", "message")
        push(event_type, event)

    def _run():
        thread_db = SessionLocal()
        try:
            crawl_service.run_pass2(
                db_session=thread_db,
                session_id=req.session_id,
                professor_ids=req.professor_ids,
                stealth=req.stealth,
                on_event=_push_adapter,
            )
            # Advance workflow step
            s = thread_db.query(DBSession).filter(DBSession.id == req.session_id).first()
            if s:
                s.workflow_step = "deep"
                thread_db.commit()

            push("done", {"message": "Deep crawl complete"})
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
# POST /professors/match
# ---------------------------------------------------------------------------


@router.post("/professors/match")
def match_professors(
    req: MatchRequest,
    db: Session = Depends(get_db),
):
    """Run final scoring / matching on deep-crawled professors."""
    sess = db.query(DBSession).filter(DBSession.id == req.session_id).first()
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not sess.profile:
        raise HTTPException(status_code=400, detail="No profile found; upload a CV first")

    ranked = scoring_service.score_final(
        db_session=db,
        session_id=req.session_id,
        profile=sess.profile,
    )

    sess.workflow_step = "match"
    db.commit()

    return {"ranked": ranked}
