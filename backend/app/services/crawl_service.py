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

from sqlalchemy import func
from sqlalchemy.orm import Session
from tinyfish import TinyFish

from openai import OpenAI

from app.config import settings
from app.services.ranking_service import FIELD_DISPLAY
from app.models.db import (
    CachedCrawlRecord,
    CachedDepartment,
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


def _parse_iso_dt(val: str | None) -> datetime | None:
    """Parse an ISO 8601 string to a datetime, or return None."""
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None


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
        crawled_at=_parse_iso_dt(d.get("crawled_at")),
        source=d.get("source", "faculty_directory"),
        phase=phase,
    )


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

_now = lambda: datetime.now(timezone.utc)  # noqa: E731


_FIELD_LABELS = list(FIELD_DISPLAY.values())


# Reverse index: common keyword fragments → standard label
_KEYWORD_ALIAS: dict[str, str] = {}
for _key, _label in FIELD_DISPLAY.items():
    _KEYWORD_ALIAS[_key] = _label          # "computer_science" → label
    _KEYWORD_ALIAS[_label.lower()] = _label  # full label lowercase
    # Extract the part after " - " as an alias
    if " - " in _label:
        _short = _label.split(" - ", 1)[1].lower()
        _KEYWORD_ALIAS[_short] = _label  # "computer science (general)" → label
        # Also without parenthetical
        _base = _short.split("(")[0].strip()
        if _base:
            _KEYWORD_ALIAS[_base] = _label  # "computer science" → label
        # Slash variants: "artificial intelligence / ml" → also "ai", "ml"
        for _part in _short.replace("/", ",").split(","):
            _part = _part.strip()
            if len(_part) >= 2:
                _KEYWORD_ALIAS[_part] = _label

# Common synonyms that don't appear in FIELD_DISPLAY labels
_EXTRA_ALIASES: dict[str, str] = {
    "machine learning": "CS - Artificial Intelligence / ML",
    "deep learning": "CS - Artificial Intelligence / ML",
    "nlp": "CS - Artificial Intelligence / ML",
    "natural language processing": "CS - Artificial Intelligence / ML",
    "computer vision": "CS - Artificial Intelligence / ML",
    "cv": "CS - Artificial Intelligence / ML",
    "reinforcement learning": "CS - Artificial Intelligence / ML",
    "neural networks": "CS - Artificial Intelligence / ML",
    "llm": "CS - Artificial Intelligence / ML",
    "large language models": "CS - Artificial Intelligence / ML",
    "generative ai": "CS - Artificial Intelligence / ML",
    "data mining": "CS - Data Science / Analytics",
    "big data": "CS - Data Science / Analytics",
    "databases": "CS - Data Science / Analytics",
    "information retrieval": "CS - Data Science / Analytics",
    "security": "CS - Cybersecurity",
    "cryptography": "CS - Cybersecurity",
    "network security": "CS - Cybersecurity",
    "ux": "CS - Human-Computer Interaction",
    "user interface": "CS - Human-Computer Interaction",
    "ui": "CS - Human-Computer Interaction",
    "autonomous systems": "CS - Robotics",
    "drones": "CS - Robotics",
    "control systems": "CS - Robotics",
    "mems": "Eng - Mechanical Engineering",
    "thermodynamics": "Eng - Mechanical Engineering",
    "vlsi": "Eng - Electrical & Computer Engineering",
    "circuits": "Eng - Electrical & Computer Engineering",
    "signal processing": "Eng - Electrical & Computer Engineering",
    "semiconductors": "Eng - Electrical & Computer Engineering",
    "genomics": "Bio - Genetics & Genomics",
    "gene editing": "Bio - Genetics & Genomics",
    "crispr": "Bio - Genetics & Genomics",
    "brain": "Bio - Neuroscience",
    "cognitive science": "Bio - Neuroscience",
    "systems biology": "Bio - Computational Biology",
    "protein": "Bio - Computational Biology",
    "drug discovery": "Bio - Pharmacology",
    "epidemiology": "Bio - Public Health",
    "quant": "Social - Finance",
    "quantitative finance": "Social - Finance",
    "econometrics": "Social - Economics",
    "bayesian": "Math - Statistics",
    "probability": "Math - Statistics",
    "optimization": "Math - Operations Research",
    "linear programming": "Math - Operations Research",
    "climate": "Eng - Environmental Engineering",
    "sustainability": "Eng - Environmental Engineering",
    "biomechanics": "Eng - Biomedical Engineering",
    "medical imaging": "Eng - Biomedical Engineering",
    "tissue engineering": "Eng - Biomedical Engineering",
    "photonics": "Phys - Applied Physics",
    "optics": "Phys - Applied Physics",
    "condensed matter": "Phys - Physics (General)",
    "particle physics": "Phys - Physics (General)",
    "astrophysics": "Phys - Astronomy & Astrophysics",
    "cosmology": "Phys - Astronomy & Astrophysics",
    "nanotechnology": "Phys - Materials Science",
    "polymer": "Phys - Materials Science",
    "qubits": "Phys - Quantum Computing",
    "quantum information": "Phys - Quantum Computing",
    "software engineering": "CS - Computer Science (General)",
    "distributed systems": "CS - Computer Science (General)",
    "operating systems": "CS - Computer Science (General)",
    "compilers": "CS - Computer Science (General)",
    "algorithms": "CS - Computer Science (General)",
    "programming languages": "CS - Computer Science (General)",
    "theory of computation": "CS - Computer Science (General)",
    "computer architecture": "CS - Computer Science (General)",
    "cloud computing": "CS - Computer Science (General)",
    "parallel computing": "CS - Computer Science (General)",
}
_KEYWORD_ALIAS.update(_EXTRA_ALIASES)


def _normalize_keywords(raw_keywords: list[str]) -> list[str]:
    """Map user-supplied keywords to standard field labels.

    Uses local substring matching against FIELD_DISPLAY — no LLM call.
    Returns at most 3 canonical labels so cache matching is consistent.
    """
    if not raw_keywords:
        return raw_keywords

    matched: list[str] = []
    seen: set[str] = set()

    for kw in raw_keywords:
        kw_lower = kw.strip().lower()
        if not kw_lower:
            continue

        # 1. Exact alias hit
        if kw_lower in _KEYWORD_ALIAS:
            label = _KEYWORD_ALIAS[kw_lower]
            if label not in seen:
                matched.append(label)
                seen.add(label)
            continue

        # 2. Substring: find best match (shortest label that contains the keyword,
        #    or keyword that contains an alias)
        best: str | None = None
        for alias, label in _KEYWORD_ALIAS.items():
            if label in seen:
                continue
            if kw_lower in alias or alias in kw_lower:
                if best is None or len(alias) > len(best):
                    best = label
        if best:
            matched.append(best)
            seen.add(best)

    return matched[:3] if matched else raw_keywords[:3]


def _cache_is_fresh(cached: CachedSchool, ttl_days: int) -> bool:
    """Return True if the cached school was crawled within *ttl_days*."""
    if cached.status != "done" or cached.last_crawled_at is None:
        return False
    last = cached.last_crawled_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return (_now() - last) < timedelta(days=ttl_days)


def _departments_are_stale(
    db: Session,
    cached_school: CachedSchool,
    dept_ids: list[int] | None,
) -> bool:
    """Return True if ANY of the relevant departments haven't been updated
    in more than CACHE_STALE_DAYS (default 30 days)."""
    stale_cutoff = _now() - timedelta(days=settings.CACHE_STALE_DAYS)
    query = db.query(CachedDepartment).filter(
        CachedDepartment.cached_school_id == cached_school.id,
    )
    if dept_ids is not None:
        query = query.filter(CachedDepartment.id.in_(dept_ids))

    stale = query.filter(
        (CachedDepartment.last_crawled_at == None)  # noqa: E711
        | (CachedDepartment.last_crawled_at < stale_cutoff)
    ).count()
    return stale > 0


def _resolve_relevant_dept_ids(
    db: Session,
    cached_school: CachedSchool,
    keywords: list[str],
) -> list[int] | None:
    """Return CachedDepartment IDs relevant to *keywords*, or None for 'all'.

    Looks at CachedCrawlRecords whose keywords overlap, collects their
    ``departments_found``, then resolves to department IDs.
    Returns None if no records exist (legacy data → copy everything).
    """
    records = (
        db.query(CachedCrawlRecord)
        .filter(CachedCrawlRecord.cached_school_id == cached_school.id)
        .all()
    )
    if not records:
        return None  # no records → legacy, copy all

    # Collect department names from matching records
    matched_depts: set[str] = set()
    kw_lower = {k.lower() for k in keywords}

    for rec in records:
        rec_kw_lower = {k.lower() for k in (rec.keywords or [])}
        # Match if any keyword overlaps (substring either direction)
        if any(
            any(n in r or r in n for r in rec_kw_lower)
            for n in kw_lower
        ):
            matched_depts.update(rec.departments_found or [])

    # If substring match found nothing, try LLM
    if not matched_depts:
        try:
            client = OpenAI()
            all_records_info = [
                {"keywords": r.keywords, "departments": r.departments_found}
                for r in records
            ]
            resp = client.chat.completions.create(
                model=settings.KEYWORD_MATCH_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Given crawl records (each with keywords and departments found) "
                            "and a new set of keywords, return ONLY the department names "
                            "that are relevant to the new keywords.\n"
                            "Reply with a JSON array of department name strings. "
                            "If none match, reply with []."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Crawl records: {all_records_info}\n"
                            f"New keywords: {keywords}"
                        ),
                    },
                ],
                temperature=0,
                max_tokens=200,
            )
            import json
            answer = resp.choices[0].message.content.strip()
            dept_names = json.loads(answer)
            if isinstance(dept_names, list):
                matched_depts.update(dept_names)
        except Exception:
            pass

    if not matched_depts:
        return None  # can't determine → copy all (safe fallback)

    # Resolve names to IDs
    dept_rows = (
        db.query(CachedDepartment.id)
        .filter(
            CachedDepartment.cached_school_id == cached_school.id,
            CachedDepartment.name.in_(matched_depts),
        )
        .all()
    )
    return [r[0] for r in dept_rows] if dept_rows else None


def _copy_cached_to_session(
    db: Session,
    cached_school: CachedSchool,
    session_id: str,
    dept_ids: list[int] | None = None,
) -> list[DBProfessor]:
    """Copy CachedProfessors for a school into session-scoped professors.

    If *dept_ids* is given, only professors in those departments are copied.
    If None, all professors are copied (legacy / fallback).
    """
    query = db.query(CachedProfessor).filter(
        CachedProfessor.cached_school_id == cached_school.id
    )
    if dept_ids is not None:
        query = query.filter(CachedProfessor.cached_department_id.in_(dept_ids))
    cached_profs = query.all()
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
            crawled_at=cp.crawled_at,
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


import re

# ---------------------------------------------------------------------------
# Domain normalization — strip common prefixes so "web.mit.edu" == "mit.edu"
# ---------------------------------------------------------------------------
_DOMAIN_PREFIX_RE = re.compile(r"^(?:www\d?|web|m|mobile)\.", re.IGNORECASE)


def _normalize_domain(domain: str) -> str:
    """Strip www./web./m. prefixes from a domain for consistent cache lookup."""
    return _DOMAIN_PREFIX_RE.sub("", domain.strip().lower())


# ---------------------------------------------------------------------------
# Department name normalization
# ---------------------------------------------------------------------------

# Matches ", University of X" AND ", X University" / ", X Institute of Technology"
_UNI_SUFFIX_RE = re.compile(
    r",\s*(?:"
    r"(?:University of |School of |Department of |The |College of |"
    r"Institute of |Faculty of ).*"
    r"|"
    r".*\b(?:University|Institute of Technology|Polytechnic)\b.*"
    r")$",
    re.IGNORECASE,
)

# Bracket annotations like "[CS And AI+D]"
_BRACKET_RE = re.compile(r"\s*\[.*?\]\s*")

# Common abbreviations to restore after title-casing
_ABBR_RESTORE = (
    "Ai", "Ml", "Nlp", "Cs", "Ece", "Eecs", "Bme", "Hci",
    "Mit", "Ucsd", "Ucla", "Gse", "Cse", "Imes",
)


def _normalize_dept_name(raw: str) -> str:
    """Normalize a department name for consistent storage.

    1. Strip bracket annotations  ("[CS And AI+D]" → "")
    2. Strip trailing university / school suffixes
       ("Computer Science, Columbia University" → "Computer Science")
    3. If still has commas (multi-dept cross-appointment), take first part
    4. Normalize " & " → " and " for consistency
    5. Title-case with abbreviation restoration
    """
    if isinstance(raw, list):
        raw = ", ".join(str(x) for x in raw)
    s = (raw or "").strip()
    if not s:
        return "Unknown"

    # 1. Strip bracket annotations
    s = _BRACKET_RE.sub("", s).strip()

    # 2. Strip university suffixes  ", Carnegie Mellon University" etc.
    s = _UNI_SUFFIX_RE.sub("", s).strip()

    # 3. Multi-dept comma split — take primary (first) department only
    #    e.g. "Computer Science, Electrical and Computer Engineering" → "Computer Science"
    if "," in s:
        s = s.split(",", 1)[0].strip()

    # 4. Normalize & → and for dedup ("Information & CS" == "Information and CS")
    s = s.replace(" & ", " and ")

    # 5. Collapse whitespace
    s = " ".join(s.split())

    # Reject ultra-short / abbreviation-only results
    if not s or len(s) < 3:
        return "Unknown"

    # 6. Title-case then restore common abbreviations
    s = s.title()
    for abbr in _ABBR_RESTORE:
        s = s.replace(abbr, abbr.upper())
    return s


def _upsert_cache_school(
    db: Session,
    domain: str,
    name: str,
    crawl_profs: list[CrawlProfessor],
    error: str | None,
    keywords: list[str] | None = None,
) -> None:
    """Insert or *merge* crawl results into the global cache for a school.

    New professors are added; existing professors (matched by name) are
    skipped to avoid overwriting deep-crawl data.  Departments are
    created on demand.  A ``CachedCrawlRecord`` is appended so future
    sessions can check keyword coverage.
    """
    norm_domain = _normalize_domain(domain)
    cached = db.query(CachedSchool).filter(CachedSchool.domain == norm_domain).first()
    is_new_school = cached is None
    if is_new_school:
        cached = CachedSchool(domain=norm_domain, name=name)
        db.add(cached)
        db.flush()

    now = _now()

    # Build set of already-cached professor names for dedup
    existing_names: set[str] = set()
    if not is_new_school:
        rows = (
            db.query(CachedProfessor.name)
            .filter(CachedProfessor.cached_school_id == cached.id)
            .all()
        )
        existing_names = {r[0] for r in rows}

    # Group new professors by normalized department name
    dept_map: dict[str, list[CrawlProfessor]] = {}
    for cp in crawl_profs:
        dept_name = _normalize_dept_name(cp.department)
        dept_map.setdefault(dept_name, []).append(cp)

    new_count = 0
    depts_found: list[str] = []

    for dept_name, profs in dept_map.items():
        # Get or create department (case-insensitive lookup)
        dept = (
            db.query(CachedDepartment)
            .filter(
                CachedDepartment.cached_school_id == cached.id,
                func.lower(CachedDepartment.name) == dept_name.lower(),
            )
            .first()
        )
        if not dept:
            dept = CachedDepartment(
                cached_school_id=cached.id,
                name=dept_name,
                professor_count=0,
                last_crawled_at=now,
            )
            db.add(dept)
            db.flush()

        depts_found.append(dept_name)
        added_in_dept = 0

        for cp in profs:
            if cp.name in existing_names:
                continue  # skip duplicate
            existing_names.add(cp.name)
            db.add(CachedProfessor(
                cached_school_id=cached.id,
                cached_department_id=dept.id,
                name=cp.name,
                email=cp.email,
                title=cp.title,
                department=cp.department,
                university=cp.university,
                university_domain=_normalize_domain(cp.university_domain or domain),
                profile_url=cp.profile_url,
                research_summary=cp.research_summary,
                source=cp.source,
                crawled_at=now,
            ))
            new_count += 1
            added_in_dept += 1

        dept.professor_count += added_in_dept
        dept.last_crawled_at = now

    # Update school-level counts
    cached.name = name
    cached.status = "error" if error else "done"
    cached.error_message = error or ""
    cached.professor_count = (
        db.query(CachedProfessor)
        .filter(CachedProfessor.cached_school_id == cached.id)
        .count()
    )
    cached.department_count = (
        db.query(CachedDepartment)
        .filter(CachedDepartment.cached_school_id == cached.id)
        .count()
    )
    cached.last_crawled_at = now

    # Record this crawl's keywords
    if keywords:
        db.add(CachedCrawlRecord(
            cached_school_id=cached.id,
            keywords=keywords,
            departments_found=depts_found,
            professor_count=new_count,
        ))

    db.commit()


# A "General" field covers all sub-fields in the same category.
# e.g. "CS - Computer Science (General)" covers "CS - AI / ML", "CS - Robotics", etc.
_GENERAL_COVERS: dict[str, list[str]] = {}
for _key, _label in FIELD_DISPLAY.items():
    if " - " in _label:
        _prefix = _label.split(" - ", 1)[0]  # "CS", "Eng", "Phys", etc.
        _GENERAL_COVERS.setdefault(_prefix, []).append(_label)


def _is_covered_by_general(prev_keywords: set[str], new_kw: str) -> bool:
    """Return True if *new_kw* is a sub-field covered by a '(General)' entry in prev."""
    if new_kw in prev_keywords:
        return True
    if " - " not in new_kw:
        return False
    prefix = new_kw.split(" - ", 1)[0]
    # Check if the General label for this category was previously crawled
    general_label = next(
        (lbl for lbl in _GENERAL_COVERS.get(prefix, []) if "(General)" in lbl),
        None,
    )
    return general_label is not None and general_label in prev_keywords


def _keywords_already_covered(
    db: Session,
    cached_school: CachedSchool,
    new_keywords: list[str],
) -> bool:
    """Check if *new_keywords* are semantically covered by existing crawl records.

    Uses gpt-4o-mini for a cheap yes/no judgement.  Falls back to simple
    substring matching if the LLM call fails.
    """
    records = (
        db.query(CachedCrawlRecord)
        .filter(CachedCrawlRecord.cached_school_id == cached_school.id)
        .all()
    )
    if not records:
        return False

    # Gather all previously crawled keywords (flat set)
    prev_flat: set[str] = set()
    for r in records:
        prev_flat.update(r.keywords or [])

    # Fast path: general-field coverage (e.g. "CS General" covers "CS - AI/ML")
    if all(_is_covered_by_general(prev_flat, kw) for kw in new_keywords):
        return True

    # Substring match (case-insensitive)
    prev_lower = {k.lower() for k in prev_flat}
    new_lower = [k.lower() for k in new_keywords]
    if all(any(n in p or p in n for p in prev_lower) for n in new_lower):
        return True

    # LLM semantic check
    try:
        client = OpenAI()
        resp = client.chat.completions.create(
            model=settings.KEYWORD_MATCH_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You decide whether a NEW set of research keywords is already "
                        "covered by PREVIOUS crawl keyword sets. 'Covered' means the "
                        "previous crawls would have targeted the same university "
                        "departments that the new keywords would target.\n"
                        "Reply with ONLY 'yes' or 'no'."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Previous crawl keyword sets: {all_prev}\n"
                        f"New keywords: {new_keywords}\n"
                        "Are the new keywords already covered?"
                    ),
                },
            ],
            temperature=0,
            max_tokens=3,
        )
        answer = resp.choices[0].message.content.strip().lower()
        return answer.startswith("yes")
    except Exception:
        return False


def _update_cache_deep(
    db: Session,
    domain: str,
    deep_prof: CrawlProfessor,
) -> None:
    """Write deep-crawl data back to the global cache for a professor."""
    norm_domain = _normalize_domain(domain)
    cached = (
        db.query(CachedProfessor)
        .filter(
            CachedProfessor.university_domain == norm_domain,
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
    # Normalize user keywords to standard field labels for consistent caching
    kw_trimmed = _normalize_keywords(keywords)
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
        norm_domain = _normalize_domain(domain)
        cached = (
            db_session.query(CachedSchool)
            .filter(CachedSchool.domain == norm_domain)
            .first()
        )
        if cached and _cache_is_fresh(cached, TTL):
            # School exists in cache — check if keywords are covered
            if _keywords_already_covered(db_session, cached, kw_trimmed):
                # Keywords covered — but check if departments are stale (>30d)
                relevant_ids = _resolve_relevant_dept_ids(
                    db_session, cached, kw_trimmed,
                )
                if _departments_are_stale(db_session, cached, relevant_ids):
                    # Data too old — re-crawl
                    on_event({
                        "type": "progress",
                        "school": name,
                        "message": f"Cached data older than {settings.CACHE_STALE_DAYS} days — re-crawling",
                    })
                    to_crawl.append((idx, domain, name))
                else:
                    # Fresh cache hit
                    on_event({
                        "type": "progress",
                        "school": name,
                        "message": f"Using cached data (crawled {cached.last_crawled_at:%Y-%m-%d})",
                    })
                    copied = _copy_cached_to_session(
                        db_session, cached, session_id, dept_ids=relevant_ids,
                    )
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
                # School cached but keywords NOT covered — incremental crawl
                on_event({
                    "type": "progress",
                    "school": name,
                    "message": "Cached school found but new research direction — crawling additional departments",
                })
                to_crawl.append((idx, domain, name))
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
                    # Update global cache first (incremental merge + record keywords)
                    _upsert_cache_school(
                        db_session, domain, name, r.professors, r.error,
                        keywords=kw_trimmed,
                    )

                    # Copy only THIS crawl's professors to session
                    for cp in r.professors:
                        db_prof = _crawl_prof_to_db(cp, session_id, phase="pass1")
                        db_session.add(db_prof)
                        all_db_profs.append(db_prof)
                    total = len(r.professors)

                    cs.status = "error" if r.error else "done"
                    cs.professor_count = total
                    cs.error_message = r.error or ""
                    cs.crawled_at = _now()
                    db_session.commit()

                    on_event({
                        "type": "school_done",
                        "school": name,
                        "count": total,
                        "new_from_crawl": len(r.professors),
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
        norm_dom = _normalize_domain(dbp.university_domain or "")
        cached = (
            db_session.query(CachedProfessor)
            .filter(
                CachedProfessor.university_domain == norm_dom,
                CachedProfessor.name == dbp.name,
            )
            .first()
        )
        _deep_at = cached.deep_crawled_at if cached else None
        if _deep_at and _deep_at.tzinfo is None:
            _deep_at = _deep_at.replace(tzinfo=timezone.utc)
        if (
            cached
            and _deep_at
            and (_now() - _deep_at)
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
                crawled_at=dbp.crawled_at.isoformat() if dbp.crawled_at else "",
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
                dbp.crawled_at = _parse_iso_dt(cp.crawled_at)
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
