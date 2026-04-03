"""Data export router."""

from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import DBSession, Professor
from app.models.schemas import ProfessorSchema

router = APIRouter(tags=["export"])


@router.get("/export/{fmt}")
def export_data(
    fmt: str,
    session_id: str = Query(...),
    phase: str = Query("pass1"),
    db: Session = Depends(get_db),
):
    """Download professors as CSV or JSON for the given session and phase."""
    sess = db.query(DBSession).filter(DBSession.id == session_id).first()
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if fmt not in ("csv", "json"):
        raise HTTPException(status_code=400, detail="format must be 'csv' or 'json'")

    query = db.query(Professor).filter(Professor.session_id == session_id)

    # Map frontend phase names to DB filters
    if phase == "deep":
        query = query.filter(Professor.selected_for_deep.is_(True))
    elif phase == "final":
        query = query.filter(Professor.final_score.isnot(None))
    # "preliminary" or default: return all professors in session

    professors = query.all()
    rows = [ProfessorSchema.model_validate(p).model_dump() for p in professors]

    if fmt == "json":
        content = json.dumps(rows, ensure_ascii=False, indent=2, default=str)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="professors_{phase}.json"'
            },
        )

    # CSV
    if not rows:
        content = ""
    else:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        for row in rows:
            # Flatten list fields to semicolon-separated strings
            flat = {}
            for k, v in row.items():
                if isinstance(v, list):
                    flat[k] = "; ".join(str(item) for item in v)
                else:
                    flat[k] = v
            writer.writerow(flat)
        content = buf.getvalue()

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="professors_{phase}.csv"'
        },
    )
