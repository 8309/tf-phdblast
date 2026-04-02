"""Crawl orchestration service — Pass 1 (directory) and Pass 2 (deep).

Includes a global cache layer: schools and professors crawled by any session
are stored in ``cached_schools`` / ``cached_professors``.  Subsequent sessions
reuse cached data if it is younger than the configured TTL.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy.orm import Session
from tinyfish import TinyFish

from app.config import settings
from app.models.db import (
    CachedProfessor,
    CachedSchool,
    CrawledSchool,
    Professor as DBProfessor,
)

# Import crawl helpers from the crawl module (installed or vendored)
from crawl import SchoolResult, crawl_deep, crawl_school
from crawl import Professor as CrawlProfessor


def _profile_summary_text(profile: dict) -> str:
    """Build a concise profile summary for LLM consumption."""
    p = profile
    return (
        f"Name: {p.get('full_name', '')}\n"
        f"Degree: {p.get('highest_degree', '')}\n"
        f"Affiliation: {p.get('current_affiliation', '')}\n"
        f"Research: {', '.join(p.get('research_interests', []))}\n"
        f"Target: {', '.join(p.get('target_direction', []))}\n"
        f"Experience: {p.get('experience_summary', '')}\n"
        f"Publications: {'; '.join(p.get('publications', []))}\n"
        f"Skills: {', '.join(p.get('skills', []))}"
    )


def _crawl_prof_to_db(
    cp: CrawlProfessor, session_id: str, phase: str = "pass1",
) -> DBProfessor:
    """Convert a crawl.Professor dataclass to a DB Professor row."""
    d = asdict(cp)
    d.pop("university_domain", None)
    return DBProfessor(
        session_id=session_id,
        name=d.get("name", ""),
        email=d.get("email", ""),
        title=d.get("title", ""),
        department=d.get("department", ""),
        university=d.get("university", ""),
        university_domain=cp.university_domain,
        profile_url=d.get("profile_url", ""),
        research_summary=d.get("research_summary", ""),
        crawled_at=d.get("crawled_at", ""),
        source=d.get("source", "faculty_directory"),
        phase=phase,
    )


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

_now = lambda: datetime.now(timezone.utc)  # noqa: E731


def _cache_is_fresh(cached: CachedSchool, ttl_days: int) -> bool:
    """Return True if the cached school was crawled within *ttl_days*."""
    if cached.status != "done" or cached.last_crawled_at is None:
        return False
    return (_now() - cached.last_crawled_at) < timedelta(days=ttl_days)


def _copy_cached_to_session(
    db: Session,
    cached_school: CachedSchool,
    session_id: str,
) -> list[DBProfessor]:
    """Copy all CachedProfessors for a school into session-scoped professors."""
    cached_profs = (
        db.query(CachedProfessor)
        .filter(CachedProfessor.cached_school_id == cached_school.id)
        .all()
    )
    db_profs: list[DBProfessor] = []
    for cp in cached_profs:
        dbp = DBProfessor(
            session_id=session_id,
            name=cp.name,
            email=cp.email,
            title=cp.title,
            department=cp.department,
            university=cp.university,
            university_domain=cp.university_domain,
            profile_url=cp.profile_url,
            research_summary=cp.research_summary,
            crawled_at=cp.crawled_at.isoformat() if cp.crawled_at else "",
            source=cp.source,
            phase="pass1",
        )
        # Copy deep info if available
        if cp.deep_crawled_at:
            dbp.lab_name = cp.lab_name
            dbp.lab_url = cp.lab_url
            dbp.research_keywords = cp.research_keywords
            dbp.recent_papers = cp.recent_papers
            dbp.scholar_url = cp.scholar_url
            dbp.accepting_students = cp.accepting_students
            dbp.open_positions = cp.open_positions
            dbp.funding = cp.funding
            dbp.recruiting_signals = cp.recruiting_signals
            dbp.lab_size = cp.lab_size
            dbp.recent_graduates = cp.recent_graduates
            dbp.recruiting_likelihood = cp.recruiting_likelihood
        db.add(dbp)
        db_profs.append(dbp)
    db.commit()
    return db_profs


def _upsert_cache_school(
    db: Session,
    domain: str,
    name: str,
    crawl_profs: list[CrawlProfessor],
    error: str | None,
) -> None:
    """Insert or update the global cache for a school after a fresh crawl."""
    cached = db.query(CachedSchool).filter(CachedSchool.domain == domain).first()
    if not cached:
        cached = CachedSchool(domain=domain, name=name)
        db.add(cached)
        db.flush()

    cached.name = name
    cached.status = "error" if error else "done"
    cached.error_message = error or ""
    cached.professor_count = len(crawl_profs)
    cached.last_crawled_at = _now()

    # Replace old cached professors with fresh ones
    db.query(CachedProfessor).filter(
        CachedProfessor.cached_school_id == cached.id
    ).delete()

    now = _now()
    for cp in crawl_profs:
        db.add(CachedProfessor(
            cached_school_id=cached.id,
            name=cp.name,
            email=cp.email,
            title=cp.title,
            department=cp.department,
            university=cp.university,
            university_domain=cp.university_domain,
            profile_url=cp.profile_url,
            research_summary=cp.research_summary,
            source=cp.source,
            crawled_at=now,
        ))
    db.commit()


def _update_cache_deep(
    db: Session,
    domain: str,
    deep_prof: CrawlProfessor,
) -> None:
    """Write deep-crawl data back to the global cache for a professor."""
    cached = (
        db.query(CachedProfessor)
        .filter(
            CachedProfessor.university_domain == domain,
            CachedProfessor.name == deep_prof.name,
        )
        .first()
    )
    if not cached:
        return
    cached.lab_name = deep_prof.lab_name
    cached.lab_url = deep_prof.lab_url
    cached.research_summary = deep_prof.research_summary
    cached.research_keywords = deep_prof.research_keywords
    cached.recent_papers = deep_prof.recent_papers
    cached.scholar_url = deep_prof.scholar_url
    cached.accepting_students = deep_prof.accepting_students
    cached.open_positions = deep_prof.open_positions
    cached.funding = deep_prof.funding
    cached.recruiting_signals = deep_prof.recruiting_signals
    cached.lab_size = deep_prof.lab_size
    cached.recent_graduates = deep_prof.recent_graduates
    cached.recruiting_likelihood = deep_prof.recruiting_likelihood
    cached.deep_crawled_at = _now()
    # commit handled by caller


# ---------------------------------------------------------------------------
# Pass 1 — Directory crawl (with cache)
# ---------------------------------------------------------------------------


def run_pass1(
    db_session: Session,
    session_id: str,
    schools: list[dict],
    keywords: list[str],
    stealth: bool,
    on_event: Callable[[dict], None],
    profile: dict | None = None,
) -> list[DBProfessor]:
    """Run Pass 1 directory crawl with global cache.

    For each school:
      1. If a fresh cache entry exists (< TTL), copy professors from cache.
      2. Otherwise, crawl live and update the cache.

    Returns the list of session-scoped DBProfessor rows.
    """
    MAX_CONCURRENT = settings.MAX_CONCURRENT_CRAWL
    TTL = settings.CACHE_TTL_PASS1_DAYS
    client = TinyFish()
    kw_trimmed = sorted(keywords, key=len)[:3]
    profile_text = _profile_summary_text(profile) if profile else ""

    all_db_profs: list[DBProfessor] = []

    school_list = [(s["domain"], s["name"]) for s in schools]

    # Pre-create per-session CrawledSchool rows
    session_school_rows: dict[int, CrawledSchool] = {}
    for idx, (domain, name) in enumerate(school_list):
        row = CrawledSchool(
            session_id=session_id, name=name, domain=domain, status="pending",
        )
        db_session.add(row)
        session_school_rows[idx] = row
    db_session.commit()

    # --- Separate cached vs. need-to-crawl ---
    to_crawl: list[tuple[int, str, str]] = []  # (idx, domain, name)

    for idx, (domain, name) in enumerate(school_list):
        cached = (
            db_session.query(CachedSchool)
            .filter(CachedSchool.domain == domain)
            .first()
        )
        if cached and _cache_is_fresh(cached, TTL):
            # Cache hit — copy professors to this session
            on_event({
                "type": "progress",
                "school": name,
                "message": f"Using cached data ({cached.professor_count} professors, "
                           f"crawled {cached.last_crawled_at:%Y-%m-%d})",
            })
            copied = _copy_cached_to_session(db_session, cached, session_id)
            all_db_profs.extend(copied)

            cs = session_school_rows[idx]
            cs.status = "done"
            cs.professor_count = len(copied)
            cs.crawled_at = cached.last_crawled_at
            db_session.commit()

            on_event({
                "type": "school_done",
                "school": name,
                "count": len(copied),
                "cached": True,
            })
        else:
            to_crawl.append((idx, domain, name))

    # --- Live crawl for cache misses ---
    if not to_crawl:
        on_event({"type": "pass1_done", "total": len(all_db_profs)})
        return all_db_profs

    results_map: dict[int, SchoolResult] = {}
    q: queue.Queue[tuple[int, str | None]] = queue.Queue()

    def _make_thread(idx: int, domain: str, name: str) -> threading.Thread:
        def _do() -> None:
            def _cb(msg: str) -> None:
                if msg is not None:
                    q.put((idx, msg))
            try:
                r = crawl_school(
                    client,
                    domain=domain,
                    university_name=name,
                    keywords=kw_trimmed,
                    stealth=stealth,
                    max_professors=50,
                    on_progress=_cb,
                    profile_summary=profile_text,
                )
                results_map[idx] = r
            except Exception as e:
                results_map[idx] = SchoolResult(
                    university=name, domain=domain, error=str(e),
                )
            q.put((idx, None))
        return threading.Thread(target=_do, daemon=True)

    # Build lookup from idx to (domain, name) for the to_crawl set
    crawl_lookup = {idx: (domain, name) for idx, domain, name in to_crawl}

    for batch_start in range(0, len(to_crawl), MAX_CONCURRENT):
        batch = to_crawl[batch_start : batch_start + MAX_CONCURRENT]
        batch_indices = [idx for idx, _, _ in batch]
        pending = set(batch_indices)

        # Mark batch as crawling
        for idx in batch_indices:
            session_school_rows[idx].status = "crawling"
        db_session.commit()

        threads: list[threading.Thread] = []
        for idx, domain, name in batch:
            th = _make_thread(idx, domain, name)
            th.start()
            threads.append(th)

        while pending:
            try:
                idx, msg = q.get(timeout=0.5)
            except queue.Empty:
                continue

            domain, name = crawl_lookup[idx]

            if msg is None:
                pending.discard(idx)
                r = results_map.get(idx)
                cs = session_school_rows[idx]
                if r:
                    # Persist professors to session
                    for cp in r.professors:
                        db_prof = _crawl_prof_to_db(cp, session_id, phase="pass1")
                        db_session.add(db_prof)
                        all_db_profs.append(db_prof)

                    cs.status = "error" if r.error else "done"
                    cs.professor_count = len(r.professors)
                    cs.error_message = r.error or ""
                    cs.crawled_at = _now()
                    db_session.commit()

                    # Update global cache
                    _upsert_cache_school(
                        db_session, domain, name, r.professors, r.error,
                    )

                    on_event({
                        "type": "school_done",
                        "school": name,
                        "count": len(r.professors),
                        "error": r.error,
                    })
                else:
                    cs.status = "error"
                    cs.error_message = "No result"
                    cs.crawled_at = _now()
                    db_session.commit()

                    on_event({
                        "type": "school_done",
                        "school": name,
                        "count": 0,
                        "error": "No result",
                    })
            else:
                on_event({
                    "type": "progress",
                    "school": name,
                    "message": msg,
                })

        for th in threads:
            th.join(timeout=5)

    on_event({"type": "pass1_done", "total": len(all_db_profs)})
    return all_db_profs


# ---------------------------------------------------------------------------
# Pass 2 — Deep profile crawl (with cache write-back)
# ---------------------------------------------------------------------------


def run_pass2(
    db_session: Session,
    session_id: str,
    professor_ids: list[int],
    stealth: bool,
    on_event: Callable[[dict], None],
) -> list[DBProfessor]:
    """Run Pass 2 deep crawl for selected professors.

    After enriching each professor, the deep data is written back to the
    global cache so future sessions can reuse it.
    """
    DEEP_CONCURRENT = settings.DEEP_CONCURRENT
    client = TinyFish()

    db_profs: list[DBProfessor] = (
        db_session.query(DBProfessor)
        .filter(
            DBProfessor.id.in_(professor_ids),
            DBProfessor.session_id == session_id,
        )
        .all()
    )

    if not db_profs:
        on_event({"type": "pass2_done", "total": 0})
        return []

    # Check cache for deep data before crawling
    to_crawl_indices: list[int] = []
    crawl_profs: list[CrawlProfessor | None] = [None] * len(db_profs)

    for i, dbp in enumerate(db_profs):
        cached = (
            db_session.query(CachedProfessor)
            .filter(
                CachedProfessor.university_domain == dbp.university_domain,
                CachedProfessor.name == dbp.name,
            )
            .first()
        )
        if (
            cached
            and cached.deep_crawled_at
            and (_now() - cached.deep_crawled_at)
            < timedelta(days=settings.CACHE_TTL_PASS2_DAYS)
        ):
            # Cache hit — copy deep info directly
            dbp.lab_name = cached.lab_name
            dbp.lab_url = cached.lab_url
            dbp.research_summary = cached.research_summary
            dbp.research_keywords = cached.research_keywords
            dbp.recent_papers = cached.recent_papers
            dbp.scholar_url = cached.scholar_url
            dbp.accepting_students = cached.accepting_students
            dbp.open_positions = cached.open_positions
            dbp.funding = cached.funding
            dbp.recruiting_signals = cached.recruiting_signals
            dbp.lab_size = cached.lab_size
            dbp.recent_graduates = cached.recent_graduates
            dbp.recruiting_likelihood = cached.recruiting_likelihood
            dbp.phase = "pass2"
            dbp.selected_for_deep = True
            on_event({
                "type": "prof_done",
                "professor": dbp.name,
                "cached": True,
                "papers_count": len(cached.recent_papers or []),
            })
        else:
            # Need live deep crawl
            cp = CrawlProfessor(
                name=dbp.name,
                email=dbp.email,
                title=dbp.title,
                department=dbp.department,
                university=dbp.university,
                university_domain=dbp.university_domain,
                profile_url=dbp.profile_url,
                research_summary=dbp.research_summary,
                crawled_at=dbp.crawled_at,
                source=dbp.source,
            )
            crawl_profs[i] = cp
            to_crawl_indices.append(i)

    db_session.commit()

    if not to_crawl_indices:
        on_event({"type": "pass2_done", "total": len(db_profs)})
        return db_profs

    # --- Live deep crawl for cache misses ---
    q: queue.Queue[tuple[int, str | None]] = queue.Queue()

    def _make_thread(idx: int, prof: CrawlProfessor) -> threading.Thread:
        def _do() -> None:
            def _cb(msg: str) -> None:
                if msg is not None:
                    q.put((idx, msg))
            try:
                crawl_deep(client, prof, stealth=stealth, on_progress=_cb)
            except Exception as e:
                q.put((idx, f"[{prof.name}] error: {e}"))
            q.put((idx, None))
        return threading.Thread(target=_do, daemon=True)

    for batch_start in range(0, len(to_crawl_indices), DEEP_CONCURRENT):
        batch = to_crawl_indices[batch_start : batch_start + DEEP_CONCURRENT]
        pending = set(batch)

        threads: list[threading.Thread] = []
        for idx in batch:
            th = _make_thread(idx, crawl_profs[idx])  # type: ignore[arg-type]
            th.start()
            threads.append(th)

        while pending:
            try:
                idx, msg = q.get(timeout=0.5)
            except queue.Empty:
                continue

            if msg is None:
                pending.discard(idx)
                cp = crawl_profs[idx]
                dbp = db_profs[idx]

                # Merge deep info into session professor
                dbp.lab_name = cp.lab_name
                dbp.lab_url = cp.lab_url
                dbp.research_summary = cp.research_summary
                dbp.research_keywords = cp.research_keywords
                dbp.recent_papers = cp.recent_papers
                dbp.scholar_url = cp.scholar_url
                dbp.accepting_students = cp.accepting_students
                dbp.open_positions = cp.open_positions
                dbp.funding = cp.funding
                dbp.recruiting_signals = cp.recruiting_signals
                dbp.lab_size = cp.lab_size
                dbp.recent_graduates = cp.recent_graduates
                dbp.recruiting_likelihood = cp.recruiting_likelihood
                dbp.source = cp.source
                dbp.crawled_at = cp.crawled_at
                dbp.phase = "pass2"
                dbp.selected_for_deep = True
                db_session.commit()

                # Write deep data back to global cache
                _update_cache_deep(db_session, dbp.university_domain, cp)
                db_session.commit()

                on_event({
                    "type": "prof_done",
                    "professor": cp.name,
                    "funding_count": len(cp.funding),
                    "papers_count": len(cp.recent_papers),
                    "accepting": cp.accepting_students,
                    "recruiting": cp.recruiting_likelihood,
                })
            else:
                prof = crawl_profs[idx]
                on_event({
                    "type": "progress",
                    "professor": prof.name if prof else "?",
                    "message": msg,
                })

        for th in threads:
            th.join(timeout=5)

    on_event({"type": "pass2_done", "total": len(db_profs)})
    return db_profs
