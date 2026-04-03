#!/usr/bin/env python3
"""
PhD Outreach – TinyFish Web Agent crawler.

Two-pass crawl:
  Pass 1 (directory):  faculty directory → basic professor list
  Pass 2 (deep):       each professor's profile page → detailed info

Usage:
    python crawl.py --keywords keywords.txt --domains domains.txt --names names.txt \
                    --output runs/output.json [--max-schools 5] [--stealth] [--proxy US] \
                    [--deep] [--deep-top 50]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from tinyfish import RunStatus, TinyFish
from tinyfish.agent.types import ProxyConfig, ProxyCountryCode

load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# File logger for debugging (auto-flush)
_LOG_PATH = Path(__file__).parent / "crawl_debug.log"
def _log(msg: str) -> None:
    with open(_LOG_PATH, "a") as f:
        f.write(f"{msg}\n")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Professor:
    # Basic info (from directory page)
    name: str
    email: str
    title: str = ""
    department: str = ""
    university: str = ""
    university_domain: str = ""
    profile_url: str = ""

    # Deep info (from profile page, pass 2)
    lab_name: str = ""
    lab_url: str = ""
    research_summary: str = ""
    research_keywords: list[str] = field(default_factory=list)
    recent_papers: list[str] = field(default_factory=list)
    scholar_url: str = ""
    accepting_students: bool | None = None
    open_positions: str = ""
    funding: list[str] = field(default_factory=list)
    recruiting_signals: list[str] = field(default_factory=list)
    lab_size: int | None = None
    recent_graduates: int | None = None
    recruiting_likelihood: str = "unknown"  # high / medium / low / unknown

    # Raw TinyFish deep-crawl response (preserved as-is)
    raw_deep_json: dict | None = None

    # Metadata
    crawled_at: str = ""
    source: str = "faculty_directory"


@dataclass
class SchoolResult:
    university: str
    domain: str
    professors: list[Professor] = field(default_factory=list)
    error: str | None = None
    tinyfish_run_id: str | None = None


# ---------------------------------------------------------------------------
# Pass 1 — directory crawl
# ---------------------------------------------------------------------------

def build_directory_goal(
    keywords: list[str],
    domain: str = "",
    university_name: str = "",
    profile_summary: str = "",
    **_kwargs,
) -> str:
    """Use LLM to generate a targeted TinyFish goal for this specific school.

    Strategy: find the department faculty listing page and scrape ALL professors,
    not filtered by research direction. AI scoring handles matching later.
    """
    kw_str = ", ".join(keywords[:3])

    client = OpenAI()
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You generate step-by-step browser instructions for a web agent "
                    "to scrape a university department's FULL faculty list. "
                    "The agent executes your instructions literally in a browser.\n\n"
                    "IMPORTANT STRATEGY:\n"
                    "- The goal is to get ALL professors in the relevant department, "
                    "NOT to search by research topic. Do NOT filter by keywords.\n"
                    "- Based on the applicant's field, decide which department's "
                    "faculty page to target (e.g. CS, ME, BME, ECE, Physics...).\n"
                    "- The agent starts on the university homepage (https://www.{domain}). "
                    "Navigate directly to the department's people/faculty page. "
                    "Do NOT use Google. Do NOT use the site search.\n"
                    "- Common URL patterns: /people, /faculty, /directory, "
                    "/about/people, /department/faculty\n"
                    "- Scroll through the ENTIRE listing and extract ALL professors. "
                    "There is NO limit — get every single one.\n"
                    "- Do NOT click into individual profiles — just read the listing page\n"
                    "- If the listing is paginated, go through ALL pages until no more remain\n"
                    "- Output: JSON array with keys: name, email, title, department, "
                    "research (brief, from listing), profile_url\n"
                    "- email = empty string if not visible on listing page\n"
                    "- Only faculty/researchers, not admin staff\n"
                    "- Keep instructions to 4-6 numbered steps\n"
                    "- Return ONLY the instruction text, no markdown fences"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"University: {university_name}\n"
                    f"Domain: {domain}\n"
                    f"Applicant's field: {kw_str}\n"
                    f"Applicant context: {profile_summary[:500] if profile_summary else 'N/A'}"
                ),
            },
        ],
        temperature=0.3,
    )
    goal = resp.choices[0].message.content.strip()
    if goal.startswith("```"):
        goal = goal.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return goal


def build_directory_goal_fallback(
    keywords: list[str], domain: str = "", **_kwargs,
) -> str:
    """Fallback fixed template if LLM call fails."""
    kw_str = ", ".join(keywords[:3])
    return (
        f"1. From this university homepage, navigate to the department most "
        f"relevant to: {kw_str}.\n"
        f"2. Find the faculty / people / directory page of that department.\n"
        f"3. Scroll through the ENTIRE listing and extract ALL professors. "
        f"There is NO limit — get every single one. Do NOT search individual names.\n"
        f"4. If the listing is paginated, go through ALL pages.\n"
        f"5. For each professor, extract: name, email (empty string if hidden), "
        f"title, department, research (brief), profile_url.\n"
        f"6. Return a JSON array with those keys. Only faculty/researchers, not staff."
    )


def _make_proxy_config(proxy_country: str | None) -> ProxyConfig | None:
    """Build a TinyFish ProxyConfig for SDKs that expect typed models."""
    if not proxy_country:
        return None

    country_code = proxy_country.upper()
    try:
        parsed_country = ProxyCountryCode(country_code)
    except ValueError:
        return ProxyConfig(enabled=True)

    return ProxyConfig(enabled=True, country_code=parsed_country)


# Keep backward-compatible alias
build_goal = build_directory_goal


def crawl_school(
    client: TinyFish,
    domain: str,
    university_name: str,
    keywords: list[str],
    *,
    stealth: bool = False,
    proxy_country: str | None = None,
    on_progress: "Callable[[str], None] | None" = None,
    profile_summary: str = "",
    **_kwargs,
) -> SchoolResult:
    """Pass 1: crawl faculty directory page.

    Args:
        on_progress: optional callback invoked with a short status string
                     each time TinyFish reports a progress event.
        profile_summary: applicant profile text to help LLM generate a better goal.
    """

    url = f"https://www.{domain}"

    def _emit(msg: str) -> None:
        print(msg)
        if on_progress:
            on_progress(msg)

    # Generate targeted goal with LLM (retry up to 3 times)
    _emit(f"[{university_name}] 正在生成搜索策略...")
    goal = None
    for attempt in range(1, 4):
        try:
            goal = build_directory_goal(
                keywords,
                domain=domain,
                university_name=university_name,
                profile_summary=profile_summary,
            )
            first_line = goal.split("\n")[0][:80]
            _emit(f"[{university_name}] 策略: {first_line}...")
            break
        except Exception as exc:
            _emit(f"[{university_name}] LLM 第{attempt}次失败: {exc}")
            if attempt < 3:
                time.sleep(1)
    if goal is None:
        goal = build_directory_goal_fallback(keywords, domain=domain)
        _emit(f"[{university_name}] 3次均失败，使用默认策略")
    result = SchoolResult(university=university_name, domain=domain)

    kwargs: dict = {"url": url, "goal": goal}
    if stealth:
        kwargs["browser_profile"] = "stealth"
    proxy_config = _make_proxy_config(proxy_country)
    if proxy_config:
        kwargs["proxy_config"] = proxy_config

    _emit(f"[{university_name}] 开始搜索 ({domain})")

    now = datetime.now(timezone.utc).isoformat()

    try:
        response = client.agent.run(**kwargs)
        result.tinyfish_run_id = response.run_id
        if response.status == RunStatus.COMPLETED:
            raw = response.result
            if raw is not None:
                result.professors = _parse_professors(
                    raw, university_name, domain, now,
                )
            _emit(f"[{university_name}] 解析到 {len(result.professors)} 位教授")
        else:
            err = response.error
            result.error = str(err) if err else "Unknown failure"
            _emit(f"[{university_name}] 失败: {result.error}")
    except Exception as exc:
        result.error = str(exc)
        _emit(f"[{university_name}] 错误: {exc}")

    return result


# ---------------------------------------------------------------------------
# Pass 2 — deep profile crawl
# ---------------------------------------------------------------------------

DEEP_GOAL = (
    "Extract detailed information about this professor. Follow these steps:\n\n"
    "STEP 1 — Profile page: Extract from the professor's profile/bio page:\n"
    "- lab_name: name of their research lab/group (empty string if not found)\n"
    "- lab_url: URL to their lab website (empty string if not found)\n"
    "- research_summary: 2-3 sentence description of their research focus\n"
    "- research_keywords: list of specific research topic strings\n"
    "- recent_papers: list of up to 5 recent publication titles (most recent first)\n"
    "- scholar_url: Google Scholar profile URL (empty string if not found)\n"
    "- accepting_students: true if they mention accepting PhD students, "
    "false if they say not accepting, null if not mentioned\n"
    "- open_positions: text of any open position listing (empty string if none)\n"
    "- funding: list of active grants, funding sources, or sponsored projects "
    "(e.g. 'NSF CAREER Award 2024', 'NIH R01 Grant', 'DOE funded project on X'). "
    "Include grant name, funder, year if visible. Empty list if not found.\n\n"
    "STEP 2 — Recruiting signals: If accepting_students is still null after Step 1, "
    "do additional checks:\n"
    "  a) Visit the lab website (if found) and look for 'Join', 'Openings', "
    "'Prospective Students', 'Positions' pages.\n"
    "  b) Check the department graduate admissions page for any mentions of this professor.\n"
    "  c) Look for recent news or announcements about new grants (new funding often means recruiting).\n"
    "Based on ALL evidence gathered, also provide:\n"
    "- recruiting_signals: list of text evidence found about student recruiting "
    "(e.g. 'Lab website says: We are looking for motivated PhD students', "
    "'New NIH R01 awarded 2025', 'Recent PhD student graduated 2024'). Empty list if none found.\n"
    "- lab_size: number of current PhD students/postdocs in the lab if visible, null if not found.\n"
    "- recent_graduates: number of students who graduated in the last 2 years if visible, null if not.\n\n"
    "STEP 3 — Source URLs: Record EVERY page you actually visited to gather the above information.\n"
    "- sources: list of objects, each with:\n"
    "  - url: the full URL of the page you visited\n"
    "  - label: short description of what this page is (e.g. 'Faculty profile', "
    "'Lab website', 'Google Scholar', 'Department openings page', 'Lab people page')\n"
    "Include ALL pages visited, even if they didn't contain useful info. "
    "Order by visit sequence.\n\n"
    "Return ONLY valid JSON with all keys above, no markdown."
)


def crawl_deep(
    client: TinyFish,
    professor: Professor,
    *,
    stealth: bool = False,
    proxy_country: str | None = None,
    on_progress: "Callable[[str], None] | None" = None,
) -> Professor:
    """Pass 2: enrich a professor with deep profile info."""

    def _emit(msg: str) -> None:
        print(msg)
        if on_progress:
            on_progress(msg)

    if not professor.profile_url:
        _emit(f"[{professor.name}] 无 profile_url，跳过深度爬取")
        return professor

    kwargs: dict = {"url": professor.profile_url, "goal": DEEP_GOAL}
    if stealth:
        kwargs["browser_profile"] = "stealth"
    proxy_config = _make_proxy_config(proxy_country)
    if proxy_config:
        kwargs["proxy_config"] = proxy_config

    _emit(f"[{professor.name}] 开始深度爬取 — {professor.profile_url}")

    try:
        response = client.agent.run(**kwargs)
        if response.status == RunStatus.COMPLETED:
            raw = response.result
            _merge_deep(professor, raw)
            professor.source = "profile_page"
            professor.crawled_at = datetime.now(timezone.utc).isoformat()
            _emit(f"[{professor.name}] 正在评估招生可能性...")
            professor.recruiting_likelihood = _assess_recruiting(professor)
            _emit(f"[{professor.name}] 完成 (funding: {len(professor.funding)}, "
                  f"papers: {len(professor.recent_papers)}, "
                  f"accepting: {professor.accepting_students}, "
                  f"recruiting: {professor.recruiting_likelihood})")
        else:
            _emit(f"[{professor.name}] 深度爬取失败: {response.error}")
    except Exception as exc:
        _emit(f"[{professor.name}] 深度爬取错误: {exc}")

    return professor


def _assess_recruiting(professor: Professor) -> str:
    """Use LLM to assess recruiting likelihood from all available signals."""
    signals = {
        "accepting_students": professor.accepting_students,
        "open_positions": professor.open_positions,
        "recruiting_signals": professor.recruiting_signals,
        "funding": professor.funding,
        "recent_papers": len(professor.recent_papers),
        "lab_size": professor.lab_size,
        "recent_graduates": professor.recent_graduates,
    }

    # Short-circuit: explicit yes/no
    if professor.accepting_students is True:
        return "high"
    if professor.accepting_students is False and not professor.open_positions:
        return "low"

    try:
        oai = OpenAI()
        resp = oai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You assess whether a professor is likely recruiting PhD students. "
                        "Based on the signals provided, respond with ONLY one word: "
                        "high, medium, low, or unknown.\n\n"
                        "Guidelines:\n"
                        "- high: explicit mention of accepting students, open positions listed, "
                        "or new large grant awarded recently\n"
                        "- medium: active funding exists, recent publications show active research, "
                        "lab has students but no explicit recruitment info\n"
                        "- low: explicitly not accepting, no funding, inactive research\n"
                        "- unknown: insufficient information to judge"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(signals, ensure_ascii=False, default=str),
                },
            ],
            temperature=0,
            max_tokens=10,
        )
        answer = resp.choices[0].message.content.strip().lower()
        if answer in ("high", "medium", "low", "unknown"):
            return answer
        return "unknown"
    except Exception:
        # Fallback: rule-based
        if professor.funding:
            return "medium"
        return "unknown"


def _merge_deep(professor: Professor, raw: object) -> None:
    """Merge deep crawl result into Professor."""
    data: dict = {}
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
    else:
        return

    professor.lab_name = str(data.get("lab_name", "") or "").strip()
    professor.lab_url = str(data.get("lab_url", "") or "").strip()
    professor.research_summary = str(data.get("research_summary", "") or "").strip()

    kw = data.get("research_keywords", [])
    professor.research_keywords = kw if isinstance(kw, list) else []

    papers = data.get("recent_papers", [])
    professor.recent_papers = papers if isinstance(papers, list) else []

    professor.scholar_url = str(data.get("scholar_url", "") or "").strip()
    professor.accepting_students = data.get("accepting_students")

    professor.open_positions = str(data.get("open_positions", "") or "").strip()

    funding = data.get("funding", [])
    professor.funding = funding if isinstance(funding, list) else []

    signals = data.get("recruiting_signals", [])
    professor.recruiting_signals = signals if isinstance(signals, list) else []

    professor.lab_size = data.get("lab_size")
    professor.recent_graduates = data.get("recent_graduates")

    # Preserve the full raw response
    professor.raw_deep_json = data


# ---------------------------------------------------------------------------
# Parse directory results (pass 1)
# ---------------------------------------------------------------------------

def _parse_professors(
    raw: object, university: str, domain: str, crawled_at: str,
) -> list[Professor]:
    items: list[dict] = []

    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        for key in ("professors", "faculty", "result", "data", "results"):
            val = raw.get(key)
            if isinstance(val, list):
                items = val
                break
            if isinstance(val, str):
                return _parse_professors(val, university, domain, crawled_at)
        if not items:
            items = [raw]
    elif isinstance(raw, str):
        # Try direct JSON parse
        try:
            parsed = json.loads(raw)
            return _parse_professors(parsed, university, domain, crawled_at)
        except json.JSONDecodeError:
            pass
        # Extract JSON from markdown code blocks (```json ... ```)
        import re
        m = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", raw)
        if m:
            try:
                parsed = json.loads(m.group(1))
                return _parse_professors(parsed, university, domain, crawled_at)
            except json.JSONDecodeError:
                pass
        return []
    else:
        return []

    professors = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = (
            item.get("name")
            or item.get("full_name")
            or item.get("professor_name")
            or ""
        ).strip()
        if not name:
            continue
        professors.append(
            Professor(
                name=name,
                email=(
                    item.get("email")
                    or item.get("email_address")
                    or ""
                ).strip(),
                title=(
                    item.get("title")
                    or item.get("title_position")
                    or item.get("position")
                    or ""
                ).strip(),
                department=(
                    item.get("department") or item.get("dept") or ""
                ).strip(),
                research_summary=(
                    item.get("research")
                    or item.get("research_interests")
                    or item.get("research_area_interests")
                    or item.get("research_areas")
                    or ""
                ).strip(),
                profile_url=(
                    item.get("profile_url")
                    or item.get("profile_page_url")
                    or item.get("url")
                    or ""
                ).strip(),
                university=university,
                university_domain=domain,
                crawled_at=crawled_at,
                source="faculty_directory",
            )
        )
    return professors


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_lines(path: str) -> list[str]:
    return [
        line.strip()
        for line in Path(path).read_text().splitlines()
        if line.strip()
    ]


def save_results(results: list[SchoolResult], output_path: str) -> None:
    out = []
    for r in results:
        out.append(
            {
                "university": r.university,
                "domain": r.domain,
                "professors": [asdict(p) for p in r.professors],
                "error": r.error,
                "tinyfish_run_id": r.tinyfish_run_id,
            }
        )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\nSaved {sum(len(r.professors) for r in results)} professors "
          f"from {len(results)} schools to {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="TinyFish PhD faculty crawler")
    parser.add_argument("--keywords", required=True, help="Keywords file (one per line)")
    parser.add_argument("--domains", required=True, help="University domains file")
    parser.add_argument("--names", required=True, help="University names file")
    parser.add_argument("--output", default="runs/output.json", help="Output JSON path")
    parser.add_argument("--max-schools", type=int, default=0, help="Limit schools (0=all)")
    # --max-professors removed: we now crawl ALL professors in the department
    parser.add_argument("--stealth", action="store_true", help="Anti-detection browser")
    parser.add_argument("--proxy", default=None, help="Proxy country code (US, GB, etc.)")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between schools")
    parser.add_argument("--deep", action="store_true", help="Enable pass-2 deep crawl")
    parser.add_argument("--deep-top", type=int, default=50,
                        help="Only deep-crawl top N professors (by email availability)")
    args = parser.parse_args()

    keywords = load_lines(args.keywords)
    domains = load_lines(args.domains)
    names = load_lines(args.names)

    if len(domains) != len(names):
        print(f"ERROR: domains ({len(domains)}) and names ({len(names)}) count mismatch")
        sys.exit(1)

    if args.max_schools > 0:
        domains = domains[: args.max_schools]
        names = names[: args.max_schools]

    print(f"Keywords:   {keywords}")
    print(f"Schools:    {len(domains)}")
    print(f"Stealth:    {args.stealth}")
    print(f"Proxy:      {args.proxy or 'none'}")
    print(f"Deep crawl: {args.deep} (top {args.deep_top})")

    client = TinyFish()
    results: list[SchoolResult] = []

    # Pass 1: directory crawl
    for i, (domain, name) in enumerate(zip(domains, names)):
        result = crawl_school(
            client, domain, name, keywords,
            stealth=args.stealth,
            proxy_country=args.proxy,
        )
        results.append(result)
        save_results(results, args.output)

        if i < len(domains) - 1:
            time.sleep(args.delay)

    # Pass 2: deep crawl
    if args.deep:
        # Prioritise professors with email, then by order
        all_profs = [
            (r, p) for r in results for p in r.professors
        ]
        all_profs.sort(key=lambda x: (not bool(x[1].email), 0))
        deep_targets = all_profs[: args.deep_top]

        print(f"\n{'='*60}")
        print(f"  DEEP CRAWL: {len(deep_targets)} professors")
        print(f"{'='*60}")

        for i, (_, prof) in enumerate(deep_targets):
            crawl_deep(
                client, prof,
                stealth=args.stealth,
                proxy_country=args.proxy,
            )
            if i < len(deep_targets) - 1:
                time.sleep(args.delay)

        save_results(results, args.output)

    # Summary
    total = sum(len(r.professors) for r in results)
    with_email = sum(1 for r in results for p in r.professors if p.email)
    with_funding = sum(1 for r in results for p in r.professors if p.funding)
    deep_done = sum(1 for r in results for p in r.professors if p.source == "profile_page")
    failed = sum(1 for r in results if r.error)

    print(f"\n{'='*60}")
    print(f"  DONE")
    print(f"  Professors:   {total} ({with_email} with email)")
    print(f"  Deep crawled:  {deep_done}")
    print(f"  With funding:  {with_funding}")
    print(f"  Schools failed: {failed}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
