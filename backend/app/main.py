"""FastAPI application entry-point."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import Base, engine
import app.models.db  # noqa: F401 — ensure all ORM models are registered before create_all

# ---------------------------------------------------------------------------
# Rankings cache (loaded once at startup)
# ---------------------------------------------------------------------------

RANKINGS_CACHE: dict[str, dict] = {}
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RANKINGS_DIR = DATA_DIR / "rankings"


def _load_rankings() -> None:
    """Populate RANKINGS_CACHE from data/rankings/*.json files."""
    if not RANKINGS_DIR.is_dir():
        return
    for path in RANKINGS_DIR.glob("*.json"):
        try:
            RANKINGS_CACHE[path.stem] = json.loads(path.read_text())
        except Exception:
            pass  # skip malformed files


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: create tables + load rankings
    Base.metadata.create_all(bind=engine)
    _load_rankings()
    yield
    # Shutdown: nothing to clean up


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="PhD Outreach API",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
from app.routers import cache, cv, export, outreach, professors, rankings, schools, session

app.include_router(session.router, prefix="/api")
app.include_router(cv.router, prefix="/api")
app.include_router(schools.router, prefix="/api")
app.include_router(professors.router, prefix="/api")
app.include_router(rankings.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(outreach.router, prefix="/api")
app.include_router(cache.router, prefix="/api")


# --- Health check ---


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
