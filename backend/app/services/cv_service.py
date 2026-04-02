"""CV parsing and profile extraction service."""

from __future__ import annotations

import json

import fitz  # pymupdf
from openai import OpenAI

from app.config import settings
from app.services.ranking_service import get_field_display


def parse_pdf_bytes(data: bytes) -> str:
    """Extract text from a PDF byte buffer using pymupdf."""
    doc = fitz.open(stream=data, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text.strip()


def extract_profile(text: str, research_direction: str = "") -> dict:
    """Call OpenAI to extract a structured applicant profile from resume text.

    Returns a dict with keys: full_name, email, current_affiliation,
    highest_degree, research_interests, experience_summary, publications,
    skills, suggested_directions, suggested_field.
    """
    client = OpenAI()

    field_display = get_field_display()
    field_keys_list = "\n".join(f"  - {k}" for k in field_display.keys())

    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a resume parser. Extract these fields from the resume "
                    "and return ONLY valid JSON (no markdown fences):\n"
                    "- full_name (string)\n- email (string)\n"
                    "- current_affiliation (string)\n- highest_degree (string)\n"
                    "- research_interests (list[str])\n"
                    "- experience_summary (1-2 sentences)\n"
                    "- publications (list[str], empty if none)\n"
                    "- skills (list[str])\n"
                    "- suggested_directions (list[str]): 3-5 PhD research directions "
                    "that best match this person's background, skills, and publications. "
                    "Be specific (e.g. 'computational biomechanics' not just 'engineering'). "
                    "These will be used as search keywords to find matching professors.\n"
                    "- suggested_field (string): pick EXACTLY ONE key from the list below "
                    "that best matches this person's background. Use the key as-is.\n"
                    f"Valid field keys:\n{field_keys_list}"
                ),
            },
            {"role": "user", "content": text[:8000]},
        ],
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    profile = json.loads(raw)

    # Apply LLM-suggested directions as target_direction
    suggested = profile.get("suggested_directions", [])
    profile["target_direction"] = suggested or profile.get("research_interests", [])

    return profile
