#!/usr/bin/env python3
"""
PhD Outreach -- personalized email & CV generation agents.

Standalone module: no Gradio dependency.
Imports only the Professor dataclass from crawl.py and standard libs.

Model strategy:
  - EMAIL_MODEL (GPT-4o default): high-quality cold emails
  - CV_MODEL   (GPT-4o-mini default): cheap alignment analysis & CV tailoring

Usage:
    from outreach_agents import generate_outreach

    results = generate_outreach(
        profile={"full_name": ..., "research_interests": ..., ...},
        resume_text=open("resume.md").read(),
        professors=[prof_dict_1, prof_dict_2],
        on_progress=lambda msg: print(msg),
    )
"""

from __future__ import annotations

import logging
import os
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from openai import OpenAI

from crawl import Professor

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model configuration
# ---------------------------------------------------------------------------

EMAIL_MODEL: str = os.getenv("EMAIL_MODEL", "gpt-4o")
CV_MODEL: str = os.getenv("CV_MODEL", "gpt-4o-mini")

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Lazy-init OpenAI client."""
    global _client
    if _client is None:
        _client = OpenAI()  # reads OPENAI_API_KEY from env
    return _client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MAX_RETRIES = 2


def _chat(model: str, system: str, user: str, *, retries: int = _MAX_RETRIES) -> str:
    """Call the OpenAI chat API with simple retry logic."""
    client = _get_client()
    last_err: Exception | None = None
    for attempt in range(1 + retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.7,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            last_err = exc
            logger.warning("LLM call failed (attempt %d/%d): %s", attempt + 1, 1 + retries, exc)
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"LLM call failed after {1 + retries} attempts") from last_err


def _to_dict(obj: Any) -> dict:
    """Convert a Professor (or dict) to a plain dict."""
    if isinstance(obj, Professor):
        return asdict(obj)
    if isinstance(obj, dict):
        return obj
    raise TypeError(f"Expected dict or Professor, got {type(obj).__name__}")


def _prof_summary(prof: dict) -> str:
    """Build a concise text block describing a professor for LLM prompts."""
    parts = [
        f"Name: {prof.get('name', 'N/A')}",
        f"University: {prof.get('university', 'N/A')}",
    ]
    if prof.get("lab_name"):
        parts.append(f"Lab: {prof['lab_name']}")
    if prof.get("research_summary"):
        parts.append(f"Research summary: {prof['research_summary']}")
    if prof.get("research_keywords"):
        kw = prof["research_keywords"]
        if isinstance(kw, list):
            kw = ", ".join(kw)
        parts.append(f"Research keywords: {kw}")
    if prof.get("recent_papers"):
        papers = prof["recent_papers"]
        if isinstance(papers, list):
            papers = "\n  - ".join(papers[:8])
        parts.append(f"Recent papers:\n  - {papers}")
    if prof.get("funding"):
        funding = prof["funding"]
        if isinstance(funding, list):
            funding = "; ".join(funding[:5])
        parts.append(f"Funding/grants: {funding}")
    return "\n".join(parts)


def _profile_summary(profile: dict) -> str:
    """Build a concise text block describing the applicant for LLM prompts."""
    parts = [f"Name: {profile.get('full_name', 'N/A')}"]
    if profile.get("research_interests"):
        parts.append(f"Research interests: {profile['research_interests']}")
    if profile.get("skills"):
        parts.append(f"Skills: {profile['skills']}")
    if profile.get("publications"):
        parts.append(f"Publications: {profile['publications']}")
    if profile.get("experience_summary"):
        parts.append(f"Experience: {profile['experience_summary']}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def analyze_alignment(profile: dict, professor: dict | Professor) -> str:
    """Identify specific research overlaps between applicant and professor.

    Args:
        profile: Applicant profile dict with keys: full_name,
            research_interests, skills, publications, experience_summary.
        professor: Professor dict or Professor dataclass with keys: name,
            university, lab_name, research_summary, research_keywords,
            recent_papers, funding.

    Returns:
        2-3 paragraph alignment analysis string.
    """
    prof = _to_dict(professor)

    system = (
        "You are a research alignment analyst. Given an applicant's profile and a "
        "professor's research information, write a concise 2-3 paragraph analysis of "
        "how the applicant's background aligns with the professor's research.\n\n"
        "Be specific: mention the professor's paper titles, projects, or keywords and "
        "map them to the applicant's concrete skills, publications, or experience. "
        "Identify the strongest overlaps and any complementary strengths. "
        "Do NOT fabricate information about either party."
    )

    user = (
        f"=== Applicant ===\n{_profile_summary(profile)}\n\n"
        f"=== Professor ===\n{_prof_summary(prof)}\n\n"
        "Write a 2-3 paragraph alignment analysis."
    )

    return _chat(CV_MODEL, system, user)


def draft_email(alignment: str, profile: dict, professor: dict | Professor) -> str:
    """Generate a personalized cold outreach email.

    Args:
        alignment: Output of analyze_alignment.
        profile: Applicant profile dict.
        professor: Professor dict or Professor dataclass.

    Returns:
        Email string with ``Subject: ...`` as the first line.
    """
    prof = _to_dict(professor)

    system = (
        "You are an expert at writing PhD cold outreach emails. "
        "Write a professional, specific, and concise cold email (200-300 words) "
        "from the applicant to the professor.\n\n"
        "Requirements:\n"
        "- First line must be: Subject: <specific subject line>\n"
        "- Reference the professor's specific research, papers, or projects\n"
        "- Highlight the applicant's relevant skills and experience\n"
        "- Explain why this is a strong research fit\n"
        "- Tone: confident and professional, NOT groveling or generic\n"
        "- End with the applicant's full name and email\n"
        "- Do NOT use filler phrases like 'I hope this finds you well'"
    )

    email_addr = profile.get("email", "")
    user = (
        f"=== Alignment Analysis ===\n{alignment}\n\n"
        f"=== Applicant ===\n{_profile_summary(profile)}\n"
        f"Email: {email_addr}\n\n"
        f"=== Professor ===\n{_prof_summary(prof)}\n\n"
        "Write the outreach email."
    )

    return _chat(EMAIL_MODEL, system, user)


def tailor_cv(
    alignment: str, resume_text: str, professor: dict | Professor
) -> str:
    """Reorganize and rephrase a resume to emphasize fit with a professor.

    Args:
        alignment: Output of analyze_alignment.
        resume_text: Full resume in Markdown format.
        professor: Professor dict or Professor dataclass.

    Returns:
        Modified resume in Markdown format.
    """
    prof = _to_dict(professor)

    system = (
        "You are a CV tailoring specialist. Given an alignment analysis, "
        "a resume in Markdown, and professor information, produce a tailored "
        "version of the resume.\n\n"
        "Strategy:\n"
        "- Reorder sections to put the most relevant experience and projects first\n"
        "- Adjust the research interests / objective wording to align with the "
        "professor's keywords\n"
        "- Highlight skills that match the professor's research needs\n"
        "- Do NOT fabricate any content -- only reorganize and rephrase what exists\n"
        "- Keep the Markdown format intact\n"
        "- Preserve all factual details (dates, institutions, titles)"
    )

    user = (
        f"=== Alignment Analysis ===\n{alignment}\n\n"
        f"=== Professor ===\n{_prof_summary(prof)}\n\n"
        f"=== Current Resume (Markdown) ===\n{resume_text}\n\n"
        "Produce the tailored resume in Markdown."
    )

    return _chat(CV_MODEL, system, user)


def render_cv_pdf(cv_markdown: str, output_path: str) -> str:
    """Render Markdown CV to PDF, with graceful fallback.

    Attempts weasyprint via markdown2 first. If unavailable, saves the raw
    Markdown file instead.

    Args:
        cv_markdown: Resume content in Markdown.
        output_path: Desired output file path (should end in .pdf).

    Returns:
        Actual path of the written file (.pdf or .md).
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Attempt 1: markdown2 + weasyprint
    try:
        import markdown2  # type: ignore
        from weasyprint import HTML  # type: ignore

        html_body = markdown2.markdown(
            cv_markdown, extras=["tables", "fenced-code-blocks"]
        )
        html_full = (
            "<!DOCTYPE html><html><head>"
            '<meta charset="utf-8">'
            "<style>"
            "body { font-family: 'Helvetica Neue', Arial, sans-serif; "
            "font-size: 11pt; line-height: 1.4; margin: 40px; }"
            "h1 { font-size: 18pt; margin-bottom: 4px; }"
            "h2 { font-size: 14pt; border-bottom: 1px solid #ccc; "
            "padding-bottom: 3px; margin-top: 16px; }"
            "ul { margin-top: 4px; }"
            "</style></head><body>"
            f"{html_body}</body></html>"
        )
        pdf_path = out.with_suffix(".pdf")
        HTML(string=html_full).write_pdf(str(pdf_path))
        logger.info("PDF rendered via weasyprint: %s", pdf_path)
        return str(pdf_path)
    except ImportError:
        logger.info("weasyprint or markdown2 not available, falling back to .md")
    except Exception as exc:
        logger.warning("weasyprint rendering failed: %s -- falling back to .md", exc)

    # Fallback: save as Markdown
    md_path = out.with_suffix(".md")
    md_path.write_text(cv_markdown, encoding="utf-8")
    logger.info("CV saved as Markdown: %s", md_path)
    return str(md_path)


def generate_outreach(
    profile: dict,
    resume_text: str,
    professors: list[dict | Professor],
    on_progress: Callable[[str], None] | None = None,
    output_dir: str | None = None,
) -> list[dict]:
    """Main entry point: generate emails and tailored CVs for a list of professors.

    Args:
        profile: Applicant profile dict (full_name, research_interests,
            skills, publications, experience_summary, email).
        resume_text: Raw resume in Markdown.
        professors: List of professor dicts or Professor objects.
        on_progress: Optional callback ``(message: str) -> None``.
        output_dir: Directory for PDF/MD output. Defaults to a temp directory.

    Returns:
        List of result dicts, one per professor::

            {
                "professor": str,
                "email_subject": str,
                "email_body": str,
                "cv_md": str,
                "cv_pdf_path": str,
                "alignment": str,
            }
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="phd_outreach_")
    out_root = Path(output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []

    for i, raw_prof in enumerate(professors, 1):
        prof = _to_dict(raw_prof)
        prof_name = prof.get("name", f"professor_{i}")
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in prof_name).strip().replace(" ", "_")

        def _progress(msg: str) -> None:
            if on_progress:
                on_progress(f"[{prof_name}] {msg}")

        try:
            # Step 1 -- alignment analysis
            _progress("analyzing alignment...")
            alignment = analyze_alignment(profile, prof)

            # Step 2 -- draft email
            _progress("generating email...")
            email_text = draft_email(alignment, profile, prof)

            # Parse subject line from email
            lines = email_text.strip().splitlines()
            email_subject = ""
            email_body = email_text
            if lines and lines[0].lower().startswith("subject:"):
                email_subject = lines[0].split(":", 1)[1].strip()
                email_body = "\n".join(lines[1:]).strip()

            # Step 3 -- tailor CV
            _progress("tailoring CV...")
            cv_md = tailor_cv(alignment, resume_text, prof)

            # Step 4 -- render PDF
            _progress("rendering CV PDF...")
            pdf_path = render_cv_pdf(
                cv_md,
                str(out_root / f"cv_{safe_name}.pdf"),
            )

            results.append({
                "professor": prof_name,
                "email_subject": email_subject,
                "email_body": email_body,
                "cv_md": cv_md,
                "cv_pdf_path": pdf_path,
                "alignment": alignment,
            })
            _progress("done.")

        except Exception as exc:
            logger.error("Failed for %s: %s", prof_name, exc, exc_info=True)
            _progress(f"ERROR: {exc}")
            results.append({
                "professor": prof_name,
                "email_subject": "",
                "email_body": "",
                "cv_md": "",
                "cv_pdf_path": "",
                "alignment": "",
                "error": str(exc),
            })

    return results
