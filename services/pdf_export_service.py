from __future__ import annotations

from datetime import datetime
from io import BytesIO
import re
from typing import Iterable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _styles() -> StyleSheet1:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="Meta",
            parent=styles["BodyText"],
            fontSize=9,
            textColor=colors.HexColor("#475569"),
            leading=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallHeading",
            parent=styles["Heading3"],
            fontSize=11,
            textColor=colors.HexColor("#1e3a8a"),
            leading=14,
            spaceAfter=4,
        )
    )
    return styles


def _safe(text: object) -> str:
    return escape(str(text or "")).replace("\n", "<br/>")


def _clean_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", (value or "").strip())
    return cleaned.strip("_") or "career_match"


def _truncate(text: str, limit: int = 1200) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _common_metadata(package: dict, tab_name: str) -> list[tuple[str, str]]:
    analysis = package.get("analysis", {}) or {}
    return [
        ("User Email", package.get("user_email", "")),
        ("Job Title", analysis.get("job_title", "")),
        ("Company", analysis.get("company_name", "")),
        ("Job URL", package.get("job_url", "")),
        ("Active Role Profile", package.get("active_role_profile_name", "")),
        ("Resume File", package.get("resume_filename", "")),
        ("Generated", package.get("created_at", "")),
        ("Tab", tab_name),
    ]


def _score_rows(package: dict, tab_name: str = "") -> list[list[str]]:
    analysis = package.get("analysis", {}) or {}
    builder = package.get("generated", {}).get("resume_builder", {}) or {}
    job_fit = analysis.get("job_fit", {}) or {}
    keyword_before = analysis.get("keyword_coverage_score", analysis.get("ats_score", 0))
    keyword_after = builder.get("optimized_ats_score", keyword_before)
    rows = [["Metric", "Value"]]
    metrics = [
        ("Fit Score", f"{analysis.get('overall_fit_score', 0)}/100"),
        ("Direct Match", f"{analysis.get('direct_match_score', 0)}/100"),
        ("Transferable Match", f"{analysis.get('transferable_match_score', 0)}/100"),
        ("Interview Potential", f"{analysis.get('overall_interview_potential', 0)}/100"),
        ("Job Fit Recommendation", job_fit.get("recommendation", "")),
        ("Trust Score", f"{builder.get('trust_score', 0)}%"),
    ]
    if tab_name == "Resume Match":
        metrics.extend(
            [
                ("Keyword Coverage Before", f"{keyword_before}/100"),
                ("Keyword Coverage After", f"{keyword_after}/100"),
            ]
        )
    else:
        metrics.extend(
            [
                ("ATS Before", f"{builder.get('original_ats_score', analysis.get('ats_score', 0))}/100"),
                ("ATS After", f"{builder.get('optimized_ats_score', analysis.get('ats_score', 0))}/100"),
            ]
        )
    for label, value in metrics:
        if value:
            rows.append([label, str(value)])
    return rows


def _bullet_lines(items: Iterable[object]) -> list[str]:
    lines = []
    for item in items or []:
        cleaned = str(item or "").strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def _top_strengths(package: dict) -> list[str]:
    analysis = package.get("analysis", {}) or {}
    role_specific = _bullet_lines(analysis.get("role_specific_strengths", []))
    if role_specific:
        return role_specific[:3]
    reasoning = analysis.get("match_reasoning", []) or []
    return [item.get("why_it_matched", "") for item in reasoning[:3] if item.get("why_it_matched")]


def _top_gaps(package: dict) -> list[str]:
    analysis = package.get("analysis", {}) or {}
    gaps = _bullet_lines(analysis.get("gaps", []))
    if gaps:
        return gaps[:3]
    missing = _bullet_lines(analysis.get("missing_keywords", []))
    return missing[:3]


def _next_actions(package: dict) -> list[str]:
    builder = package.get("generated", {}).get("resume_builder", {}) or {}
    coach = package.get("generated", {}).get("career_coach", {}) or {}
    actions = []
    for item in builder.get("targeted_gap_fixes", [])[:3]:
        gap_name = item.get("gap_name", "")
        if item.get("supported_by_resume_evidence"):
            actions.append(f"Use resume-backed language to strengthen {gap_name}.")
        else:
            actions.append(f"Do not claim {gap_name} directly unless you can support it with real resume evidence.")
    for item in coach.get("resume_improvements", [])[:2]:
        if item.get("change"):
            actions.append(item["change"])
    return _bullet_lines(actions)[:5]


def _warnings(package: dict) -> list[str]:
    builder = package.get("generated", {}).get("resume_builder", {}) or {}
    warnings = []
    unsupported = _bullet_lines(builder.get("unsupported_added_keywords", []))
    if unsupported:
        warnings.append("Unsupported terms excluded from ATS gain: " + ", ".join(unsupported))
    remaining = _bullet_lines(builder.get("missing_keywords_remaining", []))
    if remaining:
        warnings.append("Remaining gaps: " + ", ".join(remaining[:6]))
    return warnings


def _resume_match_sections(package: dict) -> list[dict]:
    analysis = package.get("analysis", {}) or {}
    builder = package.get("generated", {}).get("resume_builder", {}) or {}
    fit_score = int(analysis.get("overall_fit_score", 0) or 0)
    direct_score = int(analysis.get("direct_match_score", 0) or 0)
    keyword_after = int(builder.get("optimized_ats_score", analysis.get("keyword_coverage_score", 0)) or 0)
    warning = analysis.get("score_consistency", {}).get("warning", "")
    if keyword_after >= fit_score + 12 and direct_score < 60:
        warning = "Keyword coverage is strong, but overall fit is limited by missing direct experience."
    sections = [
        {"heading": "Top 3 Strengths", "bullets": _top_strengths(package)},
        {"heading": "Top 3 Gaps", "bullets": _top_gaps(package)},
        {"heading": "Recommended Next Actions", "bullets": _next_actions(package)},
        {"heading": "Role-Specific Strengths", "bullets": _bullet_lines(analysis.get("role_specific_strengths", []))},
        {"heading": "Missing Keywords", "bullets": _bullet_lines(analysis.get("missing_keywords", []))},
        {
            "heading": "Keyword Coverage Snapshot",
            "bullets": [
                f"Keyword Coverage Before: {analysis.get('keyword_coverage_score', analysis.get('ats_score', 0))}/100",
                f"Keyword Coverage After: {keyword_after}/100",
            ],
        },
        {
            "heading": "Keyword Coverage Explanation",
            "bullets": [
                analysis.get("score_consistency", {}).get("explanation", "Keyword coverage is not the same as overall job fit."),
                warning,
            ],
        },
    ]
    competency_rows = [["Competency", "Direct", "Transferable", "Overall", "Evidence"]]
    for item in analysis.get("competency_scores", []) or []:
        competency_rows.append(
            [
                item.get("competency", ""),
                f"{item.get('direct_score', 0)}%",
                f"{item.get('transferable_score', 0)}%",
                f"{item.get('score', 0)}%",
                ", ".join((item.get("matched", []) or [])[:3]) or "None",
            ]
        )
    sections.append({"heading": "Recruiter Competency Scores", "table": competency_rows})

    confidence_rows = [["Competency", "Direct", "Transferable", "Overall", "Evidence", "Confidence"]]
    for item in analysis.get("recruiter_confidence_by_competency", []) or []:
        confidence_rows.append(
            [
                item.get("competency", ""),
                f"{item.get('direct_score', 0)}/100",
                f"{item.get('transferable_score', 0)}/100",
                f"{item.get('overall_score', 0)}/100",
                ", ".join((item.get("evidence", []) or [])[:3]) or "None",
                item.get("confidence_level", "Low"),
            ]
        )
    sections.append({"heading": "Recruiter Confidence", "table": confidence_rows})

    explanation_lines = []
    for item in analysis.get("score_explanation", []) or []:
        explanation_lines.append(
            f"{item.get('category', '')}: {item.get('weight', 0)}% weight | "
            f"raw {item.get('raw_score', 0)}/100 | contribution {item.get('contribution', 0)}"
        )
    sections.append({"heading": "Score Explanation", "bullets": explanation_lines})

    score_rows = [["Competency", "Weight", "Raw", "Contribution", "Evidence", "Missing Requirement"]]
    for item in analysis.get("score_breakdown", []) or []:
        score_rows.append(
            [
                item.get("competency", ""),
                str(item.get("weight", 0)),
                f"{item.get('raw_score', 0)}/100",
                f"{item.get('contribution', 0)}/100",
                item.get("confidence_level", item.get("evidence_level", "Unsupported")),
                item.get("missing_requirement", "") or "None",
            ]
        )
    sections.append({"heading": "Why This Score?", "table": score_rows})

    priority_lines = []
    for priority in ["Critical", "Important", "Nice-to-have"]:
        items = analysis.get("missing_keywords_by_priority", {}).get(priority, []) or []
        if not items:
            continue
        priority_lines.append(f"{priority}:")
        for item in items:
            priority_lines.append(
                f"{item.get('term', '')} | {item.get('competency', '')} | "
                f"JD keyword: {item.get('extracted_keyword', '')} | Confidence {item.get('confidence_score', 0)} | "
                f"Sentence: {item.get('job_description_sentence', '')}"
            )
    sections.append({"heading": "Missing Keywords by Priority", "bullets": priority_lines})

    interview_lines = []
    for item in analysis.get("reasons_to_interview", []) or []:
        evidence = " | ".join((item.get("supporting_resume_evidence", []) or [])[:2]) or "No resume evidence listed"
        interview_lines.append(
            f"{item.get('reason_title', '')} | {item.get('strength_level', '')} | "
            f"Job requirement: {item.get('relevant_job_requirement', '')} | Evidence: {evidence}"
        )
    sections.append({"heading": "Why Recruiters Will Interview", "bullets": interview_lines})

    reject_lines = []
    for item in analysis.get("reasons_to_reject", []) or []:
        reject_lines.append(
            f"{item.get('gap_name', '')} | {item.get('impact_level', '')} impact | "
            f"Missing requirement: {item.get('missing_job_requirement', '')} | "
            f"Fixability: {item.get('fixability', '')} | Why: {item.get('why_it_matters', '')}"
        )
    sections.append({"heading": "Why Recruiters May Pass", "bullets": reject_lines})

    roi_lines = []
    for item in analysis.get("resume_roi_fixes", []) or []:
        evidence = " | ".join((item.get("supporting_resume_evidence", []) or [])[:2]) or "No resume evidence listed"
        roi_lines.append(
            f"{item.get('gap_or_keyword', '')} | {item.get('expected_impact', 'Medium')} impact | +{item.get('estimated_score_impact', 0)} potential points | "
            f"{'Supported' if item.get('safely_supported') else 'Not safely supported'} | "
            f"Why: {item.get('why_it_matters', '')} | Action: {item.get('recommended_action', '')} | Evidence: {evidence}"
        )
    sections.append({"heading": "Highest ROI Fixes", "bullets": roi_lines})

    level_alignment = analysis.get("compensation_level_alignment", {}) or {}
    sections.append(
        {
            "heading": "Compensation / Level Alignment",
            "bullets": [
                f"{level_alignment.get('label', 'Moderate Alignment')} ({level_alignment.get('alignment_score', 0)}/100)"
            ] + _bullet_lines(level_alignment.get("reasoning", [])),
        }
    )

    comparison_lines = []
    for item in analysis.get("compared_with_typical_applicants", []) or []:
        comparison_lines.append(
            f"{item.get('competency', '')}: {item.get('relative_strength', 'Unknown')} | "
            f"{item.get('confidence_level', 'Low')} confidence | Evidence: {', '.join((item.get('evidence', []) or [])[:3]) or 'None'}"
        )
    sections.append({"heading": "Compared To Successful Candidates", "bullets": comparison_lines})

    recruiter_summary = analysis.get("recruiter_style_summary", {}) or {}
    sections.append(
        {
            "heading": "Recruiter-Style Summary",
            "bullets": [
                f"Best case recruiter read: {recruiter_summary.get('best_case_recruiter_read', 'Not available')}",
                f"Worst case recruiter read: {recruiter_summary.get('worst_case_recruiter_read', 'Not available')}",
                f"Most important fix before applying: {recruiter_summary.get('most_important_fix_before_applying', 'Not available')}",
            ],
        }
    )

    evidence_lines = []
    for item in analysis.get("match_reasoning", []) or []:
        evidence = item.get("resume_evidence_lines", []) or []
        if evidence:
            evidence_lines.append(
                f"{item.get('competency', 'Competency')} | {item.get('confidence_level', item.get('evidence_level', 'Unsupported'))}: {' | '.join(evidence[:2])}"
            )
    sections.append({"heading": "Exact Resume Evidence", "bullets": evidence_lines})
    return sections


def _tailored_resume_sections(package: dict) -> list[dict]:
    generated = package.get("generated", {}) or {}
    return [
        {"heading": "Professional Summary", "body": generated.get("professional_summary", "")},
        {"heading": "Tailored Resume Bullet Points", "bullets": _bullet_lines(generated.get("tailored_resume_bullets", []))},
        {"heading": "Evidence-Backed Recommendations", "bullets": _next_actions(package)},
        {"heading": "Warnings", "bullets": _warnings(package)},
    ]


def _resume_builder_sections(package: dict) -> list[dict]:
    builder = package.get("generated", {}).get("resume_builder", {}) or {}
    gain_rows = [["Category", "Gain", "Matched After"]]
    for item in builder.get("category_improvements", []) or []:
        gain_rows.append(
            [
                item.get("category", ""),
                f"+{item.get('delta', 0)}",
                ", ".join((item.get("matched_terms_after", []) or [])[:4]) or "None",
            ]
        )
    validation_rows = [["Term", "Support", "ATS Gain", "Remaining Gap"]]
    for item in builder.get("term_validation_report", []) or []:
        validation_rows.append(
            [
                item.get("term", ""),
                item.get("support_level", ""),
                str(item.get("ats_gain", 0)),
                "Yes" if item.get("remaining_gap_flag") else "No",
            ]
        )
    sections = [
        {"heading": "Summary of Improvements", "bullets": _bullet_lines(builder.get("improvements_summary", []))},
        {"heading": "Keywords Added", "bullets": _bullet_lines(builder.get("keywords_added", []))},
        {"heading": "Terms Repositioned", "bullets": _bullet_lines(builder.get("terms_repositioned", []))},
        {"heading": "Terms Not Added Due To Insufficient Evidence", "bullets": _bullet_lines(builder.get("terms_not_added_due_to_insufficient_evidence", []))},
        {"heading": "ATS Gain Contribution", "table": gain_rows},
        {"heading": "ATS Validation Report", "table": validation_rows},
    ]
    gap_lines = []
    for item in builder.get("remaining_gap_details", []) or []:
        gap_lines.append(
            f"{item.get('term', '')} | JD evidence: {item.get('extracted_keyword', '')} | "
            f"Confidence {item.get('confidence_score', 0)} | Sentence: {item.get('job_description_sentence', '')}"
        )
    sections.append({"heading": "Remaining Gap Evidence", "bullets": gap_lines})
    target_lines = []
    for item in builder.get("targeted_gap_fixes", []) or []:
        target_lines.append(
            f"{item.get('gap_name', '')}: "
            + ("supported" if item.get("supported_by_resume_evidence") else "not resume-backed")
        )
        for suggestion in item.get("rewritten_bullet_suggestions", [])[:2]:
            target_lines.append(f"Suggestion: {suggestion}")
    sections.append({"heading": "Targeted Gap Fixes", "bullets": target_lines})
    return sections


def _evidence_sections(package: dict) -> list[dict]:
    builder = package.get("generated", {}).get("resume_builder", {}) or {}
    bridge_lines = []
    for item in builder.get("bridge_the_gap_guidance", []) or []:
        bridge_lines.append(
            f"{item.get('competency', '')}: {item.get('interview_bridge', '')} | Resume evidence: {item.get('resume_evidence', '')}"
        )
    explanation_lines = []
    for item in builder.get("added_keyword_explanations", []) or []:
        explanation_lines.append(
            f"{item.get('keyword', '')} | {item.get('support_level', '')} | {item.get('source_resume_evidence', '')}"
        )
    return [
        {"heading": "Added Keywords", "bullets": _bullet_lines(builder.get("keywords_added", []))},
        {"heading": "Bridge the Gap Guidance", "bullets": bridge_lines},
        {"heading": "Evidence-Backed Recommendations", "bullets": explanation_lines},
        {"heading": "Warnings", "bullets": _warnings(package)},
    ]


def _career_coach_sections(package: dict) -> list[dict]:
    coach = package.get("generated", {}).get("career_coach", {}) or {}
    sections = [
        {"heading": "Overview", "body": coach.get("overview", "")},
        {"heading": "Missing Skills", "bullets": _bullet_lines(coach.get("missing_skills", []))},
        {"heading": "Missing Certifications", "bullets": _bullet_lines(coach.get("missing_certifications", []))},
        {"heading": "Missing Technologies", "bullets": _bullet_lines(coach.get("missing_technologies", []))},
        {"heading": "Missing Industry Experience", "bullets": _bullet_lines(coach.get("missing_industry_experience", []))},
    ]
    for heading, key, title_key in [
        ("30-Day Improvement Plan", "thirty_day_plan", "action"),
        ("90-Day Improvement Plan", "ninety_day_plan", "action"),
        ("Recommended Certifications", "recommended_certifications", "name"),
        ("Recommended Courses", "recommended_courses", "name"),
        ("Resume Improvements", "resume_improvements", "change"),
    ]:
        bullets = []
        for item in coach.get(key, []) or []:
            title = item.get(title_key, "")
            reason = item.get("why_it_matters") or item.get("reason") or ""
            gain = item.get("estimated_job_fit_increase", 0)
            bullets.append(f"{title} | Why: {reason} | Estimated fit impact: +{gain}")
        sections.append({"heading": heading, "bullets": bullets})
    return sections


def _cover_letter_sections(package: dict) -> list[dict]:
    generated = package.get("generated", {}) or {}
    return [
        {"heading": "Cover Letter", "body": generated.get("cover_letter", "")},
        {"heading": "Top Strengths", "bullets": _top_strengths(package)},
        {"heading": "Remaining Gaps", "bullets": _top_gaps(package)},
    ]


def _interview_sections(package: dict) -> list[dict]:
    dashboard = package.get("generated", {}).get("interview_dashboard", {}) or {}
    top_question_lines = []
    for item in dashboard.get("top_25_likely_questions", [])[:10]:
        top_question_lines.append(
            f"Q: {item.get('question', '')} | Confidence {item.get('confidence_score', 0)} | "
            f"A: {item.get('answer_summary', '')}"
        )
    technical_lines = []
    for item in dashboard.get("technical_questions", [])[:8]:
        technical_lines.append(
            f"Q: {item.get('question', '')} | Confidence {item.get('confidence_score', 0)} | "
            f"A: {item.get('answer_summary', '')}"
        )
    behavioral_lines = []
    for item in dashboard.get("behavioral_questions", [])[:8]:
        behavioral_lines.append(
            f"Q: {item.get('question', '')} | Confidence {item.get('confidence_score', 0)} | "
            f"A: {item.get('answer_summary', '')}"
        )
    challenge_lines = []
    for item in dashboard.get("potential_challenges", [])[:8]:
        challenge_lines.append(
            f"{item.get('challenge', '')} | Why: {item.get('why_it_may_come_up', '')} | "
            f"Suggested response: {item.get('suggested_response', '')}"
        )
    return [
        {"heading": "Overview", "body": dashboard.get("overview", "")},
        {"heading": "Top Likely Interview Questions", "bullets": top_question_lines},
        {"heading": "Technical Interview Questions", "bullets": technical_lines},
        {"heading": "Behavioral Interview Questions", "bullets": behavioral_lines},
        {"heading": "Questions To Ask The Interviewer", "bullets": _bullet_lines(dashboard.get("questions_for_interviewer", []))},
        {"heading": "Potential Weaknesses Or Challenges", "bullets": challenge_lines},
    ]


def _linkedin_sections(package: dict) -> list[dict]:
    generated = package.get("generated", {}) or {}
    return [
        {"heading": "LinkedIn Recruiter Message", "body": generated.get("linkedin_recruiter_message", "")},
        {"heading": "Why This Outreach Fits", "bullets": _top_strengths(package)},
    ]


def _thank_you_sections(package: dict) -> list[dict]:
    generated = package.get("generated", {}) or {}
    return [
        {"heading": "Thank You Email", "body": generated.get("thank_you_email", "")},
        {"heading": "Recommended Next Actions", "bullets": _next_actions(package)},
    ]


def _full_report_sections(package: dict) -> list[dict]:
    generated = package.get("generated", {}) or {}
    sections = []
    sections.extend(_resume_match_sections(package))
    sections.append({"page_break": True})
    sections.extend(_tailored_resume_sections(package))
    sections.append({"page_break": True})
    sections.extend(_resume_builder_sections(package))
    sections.append({"page_break": True})
    sections.extend(_evidence_sections(package))
    sections.append({"page_break": True})
    sections.extend(_career_coach_sections(package))
    sections.append({"page_break": True})
    sections.extend(_cover_letter_sections(package))
    sections.append({"page_break": True})
    sections.extend(_interview_sections(package))
    sections.append({"page_break": True})
    sections.extend(_linkedin_sections(package))
    sections.extend(_thank_you_sections(package))
    if generated.get("results_summary_email"):
        sections.append({"heading": "Results Summary Email", "body": generated.get("results_summary_email", "")})
    return sections


TAB_SECTION_BUILDERS = {
    "Resume Match": _resume_match_sections,
    "Tailored Resume": _tailored_resume_sections,
    "Resume Builder": _resume_builder_sections,
    "Evidence": _evidence_sections,
    "Career Coach": _career_coach_sections,
    "Cover Letter": _cover_letter_sections,
    "Interview Intelligence": _interview_sections,
    "LinkedIn Message": _linkedin_sections,
    "Thank You Email": _thank_you_sections,
    "Export": _full_report_sections,
}


def build_pdf_payload(tab_name: str, package: dict) -> dict:
    package = dict(package or {})
    analysis = package.get("analysis", {}) or {}
    builder = package.get("generated", {}).get("resume_builder", {}) or {}
    role_profile = (
        package.get("active_role_profile_name")
        or analysis.get("active_role_profile", {}).get("headline")
        or analysis.get("role_family", "")
    )
    package["active_role_profile_name"] = role_profile
    if not package.get("created_at"):
        package["created_at"] = datetime.now().isoformat(timespec="seconds")

    builder_fn = TAB_SECTION_BUILDERS.get(tab_name, _resume_match_sections)
    sections = builder_fn(package)
    summary_lines = [
        f"Role: {analysis.get('job_title', '')} at {analysis.get('company_name', '')}",
        f"Active Role Profile: {role_profile}",
        f"Fit Score: {analysis.get('overall_fit_score', 0)}/100",
        f"Direct Match: {analysis.get('direct_match_score', 0)}/100",
        f"Transferable Match: {analysis.get('transferable_match_score', 0)}/100",
        f"ATS Before/After: {builder.get('original_ats_score', analysis.get('ats_score', 0))}/100 -> {builder.get('optimized_ats_score', analysis.get('ats_score', 0))}/100",
    ]
    text_dump = "\n".join(summary_lines)
    for section in sections:
        if section.get("heading"):
            text_dump += f"\n{section['heading']}"
        if section.get("body"):
            text_dump += f"\n{section['body']}"
        for bullet in section.get("bullets", []) or []:
            text_dump += f"\n- {bullet}"
        for row in section.get("table", [])[1:] if section.get("table") else []:
            text_dump += "\n" + " | ".join(str(cell) for cell in row)

    date_label = datetime.now().strftime("%Y-%m-%d")
    title_label = analysis.get("job_title", "job")
    file_name = f"{_clean_filename(tab_name)}_{_clean_filename(title_label)}_{date_label}.pdf"
    if tab_name == "Export":
        file_name = f"Career_Match_Full_AI_Review_{_clean_filename(title_label)}_{date_label}.pdf"
    return {
        "tab_name": tab_name,
        "title": f"Career Match — {tab_name}",
        "file_name": file_name,
        "metadata_rows": _common_metadata(package, tab_name),
        "score_rows": _score_rows(package, tab_name),
        "sections": sections,
        "text_dump": text_dump,
        "package": package,
    }


def _draw_page_number(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawRightString(7.3 * inch, 0.5 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _append_table(story: list, rows: list[list[str]], styles: StyleSheet1) -> None:
    if len(rows) <= 1:
        return
    data = [[Paragraph(_safe(cell), styles["BodyText"]) for cell in row] for row in rows]
    column_count = max(len(rows[0]), 1)
    total_width = 7.0 * inch
    if column_count == 2:
        col_widths = [2.1 * inch, total_width - 2.1 * inch]
    elif column_count == 3:
        col_widths = [1.8 * inch, 1.4 * inch, total_width - 3.2 * inch]
    elif column_count == 4:
        col_widths = [1.7 * inch, 1.1 * inch, 1.1 * inch, total_width - 3.9 * inch]
    else:
        narrow = 0.95 * inch
        col_widths = [1.5 * inch, narrow, narrow, narrow, total_width - (1.5 * inch + narrow * 3)]
    table = Table(data, repeatRows=1, colWidths=col_widths[:column_count])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12))


def render_pdf_bytes(payload: dict) -> bytes:
    styles = _styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=42,
        bottomMargin=42,
    )
    story = []

    story.append(Paragraph(_safe(payload.get("title", "Career Match PDF")), styles["Title"]))
    story.append(Spacer(1, 8))

    metadata_rows = [["Field", "Value"]] + [[label, value or ""] for label, value in payload.get("metadata_rows", []) if value or label == "Tab"]
    _append_table(story, metadata_rows, styles)
    _append_table(story, payload.get("score_rows", []), styles)

    summary_heading = Paragraph("Executive Summary", styles["Heading2"])
    story.append(summary_heading)
    story.append(Spacer(1, 4))
    for line in _bullet_lines(_top_strengths(payload.get("package", {})) + _top_gaps(payload.get("package", {})) + _next_actions(payload.get("package", {}))):
        story.append(Paragraph(_safe(f"• {line}"), styles["BodyText"]))
        story.append(Spacer(1, 4))
    story.append(Spacer(1, 8))

    for section in payload.get("sections", []):
        if section.get("page_break"):
            story.append(PageBreak())
            continue
        heading = section.get("heading", "")
        if heading:
            story.append(Paragraph(_safe(heading), styles["Heading2"]))
            story.append(Spacer(1, 4))
        if section.get("body"):
            story.append(Paragraph(_safe(_truncate(section["body"], 4000)), styles["BodyText"]))
            story.append(Spacer(1, 8))
        if section.get("bullets"):
            for bullet in section["bullets"]:
                story.append(Paragraph(_safe(f"• {bullet}"), styles["BodyText"]))
                story.append(Spacer(1, 4))
            story.append(Spacer(1, 6))
        if section.get("table"):
            _append_table(story, section["table"], styles)

    appendix_resume = _truncate(payload.get("package", {}).get("resume_text", ""), 1800)
    appendix_job = _truncate(payload.get("package", {}).get("job_text", ""), 1800)
    if appendix_resume or appendix_job:
        story.append(PageBreak())
        story.append(Paragraph("Appendix", styles["Heading1"]))
        story.append(Spacer(1, 6))
        if appendix_resume:
            story.append(Paragraph("Resume Excerpt", styles["Heading2"]))
            story.append(Paragraph(_safe(appendix_resume), styles["BodyText"]))
            story.append(Spacer(1, 10))
        if appendix_job:
            story.append(Paragraph("Job Description Excerpt", styles["Heading2"]))
            story.append(Paragraph(_safe(appendix_job), styles["BodyText"]))
            story.append(Spacer(1, 10))

    doc.build(story, onFirstPage=_draw_page_number, onLaterPages=_draw_page_number)
    buffer.seek(0)
    return buffer.getvalue()


def build_tab_pdf(tab_name: str, package: dict) -> tuple[bytes, str, dict]:
    payload = build_pdf_payload(tab_name, package)
    return render_pdf_bytes(payload), payload["file_name"], payload


def build_full_ai_review_pdf(package: dict) -> tuple[bytes, str, dict]:
    return build_tab_pdf("Export", package)
