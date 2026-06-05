import os
import re
from typing import Any

from openai import OpenAI

from services.openai_service import INVALID_API_KEY_VALUES, _extract_response_text


QUICK_PROMPTS = [
    "How do I improve this score?",
    "Rewrite my summary for this role",
    "Improve my bullets using only my real experience",
    "What keywords can I safely add?",
    "What should I not claim?",
]

COACH_SYSTEM_PROMPT = """
You are Career Match's AI Resume Coach.

Rules:
- Use only the uploaded resume, the job description, the resume match analysis, the targeted gap fixes, and the current optimized resume.
- Never invent employers, dates, metrics, certifications, tools, technologies, titles, or responsibilities.
- If a requested keyword or claim is not supported by resume evidence, respond with exactly: "I can only recommend wording supported by your resume evidence."
- After that sentence, offer a safer adjacent positioning based only on the provided evidence.
- Keep the response concise, actionable, and recruiter-friendly.
- Always include:
  1. Revised summary or positioning
  2. Revised bullet suggestions
  3. Keyword placement suggestions
  4. Why this helps ATS/recruiter match
- Return plain text only. No JSON.
""".strip()


def _demo_mode() -> bool:
    cleaned = os.getenv("OPENAI_API_KEY", "").strip().lower()
    return cleaned in INVALID_API_KEY_VALUES


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _extract_prompt_keywords(prompt: str, candidate_terms: list[str]) -> list[str]:
    lowered = (prompt or "").lower()
    found: list[str] = []
    for term in candidate_terms:
        cleaned = term.strip()
        if not cleaned:
            continue
        if cleaned.lower() in lowered:
            found.append(cleaned)
    return found


def _supported_and_unsupported_terms(prompt: str, builder: dict, analysis: dict) -> tuple[list[str], list[str]]:
    evidence_map = builder.get("resume_evidence_map", {}) or {}
    targeted_fixes = builder.get("targeted_gap_fixes", []) or []
    candidate_terms = []
    candidate_terms.extend(analysis.get("missing_keywords", []) or [])
    candidate_terms.extend(builder.get("keywords_added", []) or [])
    candidate_terms.extend(builder.get("targeted_keywords_rejected", []) or [])
    candidate_terms.extend(builder.get("explicit_skills", []) or [])
    candidate_terms.extend(builder.get("inferred_skills", []) or [])

    requested_terms = _extract_prompt_keywords(prompt, candidate_terms)
    supported_gaps = {
        item.get("gap_name", "").lower()
        for item in targeted_fixes
        if item.get("supported_by_resume_evidence")
    }
    supported: list[str] = []
    unsupported: list[str] = []
    for term in requested_terms:
        lowered = term.lower()
        if lowered in {item.lower() for item in evidence_map.keys()} or lowered in supported_gaps:
            supported.append(term)
        else:
            unsupported.append(term)
    return supported, unsupported


def _choose_gap_targets(builder: dict, analysis: dict, limit: int = 3) -> list[dict]:
    targeted = [
        item for item in (builder.get("targeted_gap_fixes", []) or [])
        if item.get("supported_by_resume_evidence")
    ]
    if targeted:
        return targeted[:limit]

    missing = analysis.get("missing_keywords", []) or []
    fallback = []
    for keyword in missing[:limit]:
        fallback.append(
            {
                "gap_name": keyword,
                "resume_evidence_used": [],
                "rewritten_bullet_suggestions": [],
            }
        )
    return fallback


def _build_safe_adjacent_positioning(builder: dict, analysis: dict) -> str:
    bridge_items = builder.get("bridge_the_gap_guidance", []) or []
    if bridge_items:
        return bridge_items[0].get("interview_bridge", "")

    evidence_map = builder.get("resume_evidence_map", {}) or {}
    evidence_terms = list(evidence_map.keys())[:4]
    if evidence_terms:
        return (
            "A safer adjacent positioning is to emphasize "
            + ", ".join(term.lower() for term in evidence_terms)
            + " because those themes are supported by the uploaded resume."
        )

    matched = analysis.get("matching_skills", []) or []
    if matched:
        return (
            "A safer adjacent positioning is to emphasize "
            + ", ".join(item.lower() for item in matched[:4])
            + " because those are already reflected in the current analysis."
        )
    return "A safer adjacent positioning is to strengthen the wording around the responsibilities already documented in your resume."


def _deterministic_response(prompt: str, resume_text: str, job_description_text: str, analysis: dict, builder: dict) -> str:
    del resume_text
    del job_description_text
    supported_terms, unsupported_terms = _supported_and_unsupported_terms(prompt, builder, analysis)
    gap_targets = _choose_gap_targets(builder, analysis)
    optimized_resume = builder.get("optimized_resume_text", "") or ""
    optimized_lines = [line.strip() for line in optimized_resume.splitlines() if line.strip()]
    current_summary = ""
    for index, line in enumerate(optimized_lines):
        if line.upper() == "PROFESSIONAL SUMMARY" and index + 1 < len(optimized_lines):
            current_summary = optimized_lines[index + 1]
            break
    if not current_summary:
        current_summary = "Professional with resume-backed experience aligned to the target opportunity."

    revised_summary = current_summary
    if gap_targets:
        focus_terms = ", ".join(item.get("gap_name", "").lower() for item in gap_targets[:3] if item.get("gap_name"))
        if focus_terms:
            revised_summary = (
                "Professional with resume-backed experience supporting stakeholders, users, and operational workflows, "
                f"with transferable strength in {focus_terms}. Known for clear communication, issue resolution, and cross-functional coordination."
            )

    bullet_suggestions: list[str] = []
    keyword_placement: list[str] = []
    for item in gap_targets:
        bullets = item.get("rewritten_bullet_suggestions", []) or []
        if bullets:
            bullet_suggestions.extend(bullets[:2])
        evidence = item.get("resume_evidence_used", []) or []
        if item.get("gap_name"):
            target_label = item["gap_name"]
            if evidence:
                keyword_placement.append(
                    f"{target_label}: use this language in the summary, skills section, or the bullet tied to '{evidence[0]}'."
                )
            else:
                keyword_placement.append(
                    f"{target_label}: keep this out of the resume unless you can point to direct evidence in your work history."
                )

    if not bullet_suggestions:
        for item in builder.get("rewritten_bullet_details", [])[:3]:
            improved = item.get("improved_bullet", "")
            if improved:
                bullet_suggestions.append(improved)

    why_lines = []
    why_lines.append(
        f"Current scores: ATS Before {builder.get('original_ats_score', 0)}/100, ATS After {builder.get('optimized_ats_score', 0)}/100."
    )
    if supported_terms:
        why_lines.append("Safe keywords already supported by your resume: " + ", ".join(supported_terms[:5]) + ".")
    why_lines.append(
        "These edits help by making transferable experience easier for recruiters and ATS systems to recognize without overstating your background."
    )

    sections = []
    if unsupported_terms:
        sections.append("I can only recommend wording supported by your resume evidence.")
        sections.append(_build_safe_adjacent_positioning(builder, analysis))
    sections.append("Revised summary")
    sections.append(revised_summary)
    sections.append("")
    sections.append("Revised bullet suggestions")
    for bullet in bullet_suggestions[:4]:
        sections.append(f"- {bullet}")
    sections.append("")
    sections.append("Keyword placement suggestions")
    for item in keyword_placement[:4]:
        sections.append(f"- {item}")
    sections.append("")
    sections.append("Why this helps ATS/recruiter match")
    for line in why_lines:
        sections.append(f"- {line}")
    return "\n".join(sections).strip()


def generate_resume_coach_response(
    *,
    user_prompt: str,
    resume_text: str,
    job_description_text: str,
    analysis: dict,
    builder: dict,
) -> str:
    if _demo_mode():
        return _deterministic_response(user_prompt, resume_text, job_description_text, analysis, builder)

    supported_terms, unsupported_terms = _supported_and_unsupported_terms(user_prompt, builder, analysis)
    role_label = analysis.get("job_title", "target role")
    company = analysis.get("company_name", "the company")
    prompt = f"""
User request:
{user_prompt}

Target role:
{role_label} at {company}

Missing keywords:
{analysis.get("missing_keywords", [])}

Targeted gap fixes:
{builder.get("targeted_gap_fixes", [])}

Supported requested terms:
{supported_terms}

Unsupported requested terms:
{unsupported_terms}

Current optimized resume:
{builder.get("optimized_resume_text", "")[:12000]}

Original resume text:
{resume_text[:12000]}

Job description:
{job_description_text[:12000]}

Current ATS before/after:
{builder.get("original_ats_score", 0)} / {builder.get("optimized_ats_score", 0)}
""".strip()

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            instructions=COACH_SYSTEM_PROMPT,
            input=prompt,
            temperature=0.3,
        )
        text = _normalize(_extract_response_text(response))
        if not text:
            raise ValueError("Empty resume coach response")
        if unsupported_terms and "I can only recommend wording supported by your resume evidence." not in text:
            text = (
                "I can only recommend wording supported by your resume evidence.\n"
                + _build_safe_adjacent_positioning(builder, analysis)
                + "\n\n"
                + text
            )
        return text
    except Exception:
        return _deterministic_response(user_prompt, resume_text, job_description_text, analysis, builder)
