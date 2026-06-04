import re

from services.analysis_service import compare_resume_to_job


SECTION_ALIASES = {
    "professional summary": "professional summary",
    "summary": "professional summary",
    "experience": "experience",
    "professional experience": "experience",
    "work experience": "experience",
    "education": "education",
    "skills": "skills",
    "technical skills": "skills",
    "core skills": "skills",
    "certifications": "certifications",
    "projects": "projects",
}

INFERRED_EVIDENCE_RULES = {
    "Stakeholder Management": [
        (r"\bpartnered with\b|\bworked with\b|\bstakeholders?\b|\bleadership\b|\bboard-ready\b", "The resume shows coordination with business leaders or stakeholders."),
    ],
    "Cross-Functional Collaboration": [
        (r"\bpartnered with\b|\bworked with\b|\bcollaborat(ed|ion)\b", "The resume shows collaboration across teams."),
    ],
    "Dashboard Reporting": [
        (r"\bkpi reporting\b|\breporting\b|\bdashboard\b", "The resume shows reporting or KPI delivery work."),
    ],
    "Executive Reporting": [
        (r"\bboard-ready\b|\bleadership reviews?\b|\bpresentations?\b", "The resume shows reporting prepared for leadership audiences."),
    ],
    "Data Analysis": [
        (r"\banalysis\b|\bvariance\b|\bforecast\b|\btracking\b", "The resume shows analytical work and interpretation."),
    ],
    "Process Improvement": [
        (r"\bautomated\b|\bimprov(ed|ing)\b|\breducing\b|\breduced\b", "The resume shows process improvement or efficiency gains."),
    ],
    "Account Management": [
        (r"\baccounts?\b|\bpartners?\b", "The resume shows experience supporting account- or partner-facing work."),
    ],
    "User Training": [
        (r"\btraining\b|\bonboarding\b", "The resume shows onboarding or training-related language."),
    ],
    "Client Communication": [
        (r"\bcommunication\b|\bpresenting insights\b|\bleadership reviews?\b", "The resume shows communication of analysis or updates to stakeholders."),
    ],
}

BRIDGE_GUIDANCE_TEMPLATES = {
    "Customer Success": "While my title was not directly in customer success, much of my work supported customer-success outcomes through {evidence_terms}.",
    "Account Management": "Although I did not hold a formal account-management title, my work relied on {evidence_terms}, which are central to maintaining strong client relationships and protecting growth opportunities.",
    "Stakeholder Management": "My experience regularly required {evidence_terms}, which maps well to the stakeholder coordination this role needs.",
    "Client Communication": "I can reposition my experience by showing how {evidence_terms} helped me communicate clearly, manage expectations, and keep users or partners informed.",
    "Risk Management": "I can connect my background in {evidence_terms} to proactive risk management, issue prevention, and service protection.",
    "Training & Adoption": "Even without a formal onboarding title, my work included {evidence_terms}, which supports training, adoption, and ongoing enablement outcomes.",
}


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def _is_section_heading(line: str) -> bool:
    cleaned = _normalize_line(line)
    if not cleaned:
        return False
    lowered = cleaned.lower().rstrip(":")
    if lowered in SECTION_ALIASES:
        return True
    return cleaned.isupper() and len(cleaned.split()) <= 4 and lowered in SECTION_ALIASES


def _split_resume_sections(resume_text: str) -> tuple[list[str], dict[str, list[str]]]:
    lines = resume_text.splitlines()
    header: list[str] = []
    sections: dict[str, list[str]] = {}
    current_section: str | None = None

    for raw_line in lines:
        line = raw_line.rstrip()
        if _is_section_heading(line):
            current_section = SECTION_ALIASES[_normalize_line(line).rstrip(":").lower()]
            sections.setdefault(current_section, [])
            continue

        if current_section is None:
            header.append(line)
        else:
            sections.setdefault(current_section, []).append(line)
    return header, sections


def _compact_lines(lines: list[str]) -> list[str]:
    compacted: list[str] = []
    previous_blank = False
    for line in lines:
        stripped = line.rstrip()
        is_blank = stripped == ""
        if is_blank and previous_blank:
            continue
        compacted.append(stripped)
        previous_blank = is_blank
    return compacted


def _extract_original_skills(sections: dict[str, list[str]], analysis: dict) -> list[str]:
    skill_lines = sections.get("skills", [])
    if skill_lines:
        skill_text = "\n".join(skill_lines)
        parts = re.split(r"[,;\n|]", skill_text)
        skills = [_normalize_line(part) for part in parts if _normalize_line(part)]
        return skills

    categories = analysis.get("resume_explicit_keyword_categories", {})
    fallback = (
        categories.get("skills", [])
        + categories.get("technologies", [])
        + categories.get("certifications", [])
    )
    return [_normalize_line(item) for item in fallback if _normalize_line(item)]


def _contains_term(line: str, term: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])"
    return bool(re.search(pattern, line.lower()))


def _clean_resume_lines(resume_text: str) -> list[str]:
    lines: list[str] = []
    for line in resume_text.splitlines():
        cleaned = _normalize_line(line)
        if not cleaned or _is_section_heading(cleaned):
            continue
        lines.append(cleaned)
    return lines


def _build_resume_evidence_map(resume_text: str, analysis: dict) -> dict[str, dict]:
    lines = _clean_resume_lines(resume_text)
    explicit_categories = analysis.get("resume_explicit_keyword_categories", {})
    supported_categories = analysis.get("resume_supported_keyword_categories", {})
    evidence_map: dict[str, dict] = {}

    def add_evidence(term: str, reason: str, evidence_line: str, confidence: int, evidence_type: str) -> None:
        if term in evidence_map:
            return
        evidence_map[term] = {
            "source_resume_evidence": reason,
            "exact_resume_line": evidence_line,
            "confidence_score": confidence,
            "evidence_type": evidence_type,
        }

    explicit_terms = set(
        explicit_categories.get("skills", [])
        + explicit_categories.get("technologies", [])
        + explicit_categories.get("certifications", [])
        + explicit_categories.get("responsibilities", [])
        + explicit_categories.get("industry_terms", [])
    )

    for term in explicit_terms:
        for line in lines:
            if _contains_term(line, term):
                add_evidence(
                    term=term,
                    reason="Found directly in the uploaded resume.",
                    evidence_line=line,
                    confidence=98,
                    evidence_type="explicit",
                )
                break

    supported_terms = set(
        supported_categories.get("skills", [])
        + supported_categories.get("technologies", [])
        + supported_categories.get("certifications", [])
        + supported_categories.get("responsibilities", [])
        + supported_categories.get("industry_terms", [])
    )
    inferred_only = [term for term in supported_terms if term not in evidence_map]

    for term in inferred_only:
        for pattern, reason in INFERRED_EVIDENCE_RULES.get(term, []):
            for line in lines:
                if re.search(pattern, line, re.IGNORECASE):
                    add_evidence(
                        term=term,
                        reason=reason,
                        evidence_line=line,
                        confidence=88,
                        evidence_type="inferred",
                    )
                    break
            if term in evidence_map:
                break

    return evidence_map


def _build_optimized_summary(analysis: dict, evidence_map: dict[str, dict]) -> str:
    job_categories = analysis.get("job_keyword_categories", {})
    supported_terms = [
        term
        for term in evidence_map
        if term in job_categories.get("responsibilities", []) or term in job_categories.get("skills", [])
    ]
    supported_terms = [term for term in supported_terms if evidence_map[term]["evidence_type"] in {"explicit", "inferred"}]
    highlights = supported_terms[:4]
    role_family = analysis.get("role_family", "")
    if highlights and role_family == "SaaS Customer Success / Account Management":
        return (
            "Analytical professional with resume-backed experience in "
            f"{', '.join(highlights)}, known for supporting stakeholders, communicating clearly, "
            "and improving reporting and issue-resolution outcomes in complex environments."
        )
    if highlights:
        return f"Professional with resume-backed experience in {', '.join(highlights)}, aligned to the target opportunity."
    return "Professional with resume-backed analytical, reporting, and stakeholder-facing experience aligned to the target opportunity."


def _build_optimized_skills(original_skills: list[str], analysis: dict, evidence_map: dict[str, dict]) -> list[str]:
    explicit_categories = analysis.get("resume_explicit_keyword_categories", {})
    job_categories = analysis.get("job_keyword_categories", {})

    explicit_terms = (
        original_skills
        + explicit_categories.get("skills", [])
        + explicit_categories.get("technologies", [])
        + explicit_categories.get("certifications", [])
    )
    inferred_terms = [
        term
        for term, payload in evidence_map.items()
        if payload["evidence_type"] == "inferred"
        and (term in job_categories.get("skills", []) or term in job_categories.get("responsibilities", []))
    ]

    combined: list[str] = []
    seen: set[str] = set()
    for item in explicit_terms + inferred_terms:
        cleaned = _normalize_line(item)
        lowered = cleaned.lower()
        if cleaned and lowered not in seen:
            combined.append(cleaned)
            seen.add(lowered)
    return combined[:18]


def _rewrite_experience_lines(sections: dict[str, list[str]], analysis: dict, evidence_map: dict[str, dict]) -> None:
    experience_lines = sections.get("experience", [])
    if not experience_lines:
        return

    supported_terms = [
        term for term in [
            "Stakeholder Management",
            "Client Communication",
            "User Training",
            "Issue Resolution",
            "Relationship Management",
            "Cross-Functional Collaboration",
            "Process Improvement",
            "Dashboard Reporting",
            "Data Analysis",
        ]
        if term in evidence_map
    ]

    templates = {
        "Stakeholder Management": "This work required stakeholder management and clear coordination.",
        "Client Communication": "This work required clear communication and expectation management.",
        "User Training": "This work supported onboarding or training-oriented adoption needs.",
        "Issue Resolution": "This work supported timely issue identification and resolution.",
        "Relationship Management": "This work strengthened ongoing relationship management across partners.",
        "Cross-Functional Collaboration": "This work relied on cross-functional collaboration.",
        "Process Improvement": "This work reflected process improvement and continuous optimization.",
        "Dashboard Reporting": "This work supported recurring reporting and dashboard-style communication.",
        "Data Analysis": "This work relied on structured data analysis and interpretation.",
    }
    rewritten: list[str] = []
    term_index = 0
    for line in experience_lines:
        stripped = line.strip()
        if stripped.startswith("-") and supported_terms:
            term = supported_terms[min(term_index, len(supported_terms) - 1)]
            lowered = stripped.lower()
            if term.lower() not in lowered:
                line = f"{stripped} {templates.get(term, f'This work supported {term.lower()}.')}"
            term_index += 1
        rewritten.append(line)
    sections["experience"] = rewritten


def _replace_or_insert_section(sections: dict[str, list[str]], key: str, new_lines: list[str]) -> None:
    sections[key] = new_lines


def _render_resume(header: list[str], sections: dict[str, list[str]]) -> str:
    output: list[str] = []
    output.extend(_compact_lines(header))
    if output and output[-1] != "":
        output.append("")

    preferred_order = [
        "professional summary",
        "skills",
        "experience",
        "education",
        "certifications",
        "projects",
    ]

    seen = set()
    for key in preferred_order:
        if key not in sections:
            continue
        seen.add(key)
        output.append(key.upper())
        output.extend(_compact_lines(sections[key]))
        output.append("")

    for key, lines in sections.items():
        if key in seen:
            continue
        output.append(key.upper())
        output.extend(_compact_lines(lines))
        output.append("")

    return "\n".join(_compact_lines(output)).strip()


def _build_keyword_explanations(keywords: list[str], analysis: dict, evidence_map: dict[str, dict]) -> list[dict]:
    job_categories = analysis.get("job_keyword_categories", {})
    explanations = []
    for term in keywords:
        category = "Other"
        for key in ["skills", "technologies", "certifications", "responsibilities", "industry_terms"]:
            if term in job_categories.get(key, []):
                category = key.replace("_", " ").title()
                break
        evidence = evidence_map.get(term, {})
        explanations.append(
            {
                "keyword": term,
                "why_added": f"Added because it is relevant to the job's {category.lower()} requirements and supported by the resume.",
                "source_resume_evidence": evidence.get("source_resume_evidence", "No direct evidence found."),
                "exact_resume_line": evidence.get("exact_resume_line", ""),
                "confidence_score": evidence.get("confidence_score", 0),
                "evidence_type": evidence.get("evidence_type", "unsupported"),
                "category": category,
            }
        )
    return explanations


def _compute_trust_score(keywords_added: list[str], evidence_map: dict[str, dict]) -> int:
    if not keywords_added:
        return 100
    supported = sum(1 for term in keywords_added if term in evidence_map)
    return round((supported / len(keywords_added)) * 100)


def _build_breakdown_snapshot(breakdown: dict) -> list[dict]:
    if "competencies" in breakdown:
        return [
            {
                "category": item.get("competency", "Competency"),
                "matched": item.get("matched", []),
                "missing": item.get("job_expectations", []),
                "score": item.get("score", 0),
                "weight": 100,
            }
            for item in breakdown.get("competencies", [])
        ]
    return []


def _build_bridge_the_gap_guidance(analysis: dict, evidence_map: dict[str, dict]) -> list[dict]:
    bridge_items: list[dict] = []
    for item in analysis.get("competency_scores", []):
        if item.get("direct_score", 0) >= 55:
            continue

        supported_terms = [term for term in item.get("matched", []) if term in evidence_map]
        if not supported_terms:
            continue

        lead_terms = supported_terms[:4]
        lead_evidence = evidence_map[lead_terms[0]]
        template = BRIDGE_GUIDANCE_TEMPLATES.get(
            item["competency"],
            "I can position this experience around {evidence_terms} to show relevant overlap with the role.",
        )
        bridge_items.append(
            {
                "competency": item["competency"],
                "resume_evidence": ", ".join(lead_terms),
                "exact_resume_line": lead_evidence.get("exact_resume_line", ""),
                "confidence_score": lead_evidence.get("confidence_score", 0),
                "interview_bridge": template.format(evidence_terms=", ".join(term.lower() for term in lead_terms)),
            }
        )

    return bridge_items[:6]


def build_optimized_resume_package(resume_text: str, job_description_text: str, analysis: dict, generated: dict) -> dict:
    header, sections = _split_resume_sections(resume_text)
    evidence_map = _build_resume_evidence_map(resume_text, analysis)
    original_skills = _extract_original_skills(sections, analysis)
    optimized_summary = _build_optimized_summary(analysis, evidence_map)
    optimized_skills = _build_optimized_skills(original_skills, analysis, evidence_map)

    _replace_or_insert_section(sections, "professional summary", [optimized_summary])
    if optimized_skills:
        _replace_or_insert_section(sections, "skills", [", ".join(optimized_skills)])
    _rewrite_experience_lines(sections, analysis, evidence_map)

    optimized_resume_text = _render_resume(header, sections)
    optimized_analysis = compare_resume_to_job(optimized_resume_text, job_description_text)

    original_ats = int(analysis.get("ats_score", 0))
    raw_optimized_ats = int(optimized_analysis.get("ats_score", 0))

    keywords_before = analysis.get("matching_keywords", [])
    keywords_after = optimized_analysis.get("matching_keywords", [])
    before_set = {kw.lower() for kw in keywords_before}
    candidate_keywords_added = [item for item in keywords_after if item.lower() not in before_set]
    keywords_added = [item for item in candidate_keywords_added if item in evidence_map]
    unsupported_added = [item for item in candidate_keywords_added if item not in evidence_map]

    trust_score = _compute_trust_score(candidate_keywords_added, evidence_map)
    optimized_ats = max(original_ats, raw_optimized_ats - (len(unsupported_added) * 15))
    if original_ats > 0:
        improvement_percentage = round(((optimized_ats - original_ats) / original_ats) * 100)
    else:
        improvement_percentage = 100 if optimized_ats > 0 else 0

    explicit_categories = analysis.get("resume_explicit_keyword_categories", {})
    supported_categories = analysis.get("resume_supported_keyword_categories", {})
    inferred_skills = [
        term
        for term, payload in evidence_map.items()
        if payload["evidence_type"] == "inferred"
    ]

    return {
        "analysis_job_title": analysis.get("job_title", "Optimized Resume"),
        "optimized_resume_text": optimized_resume_text,
        "original_ats_score": original_ats,
        "optimized_ats_score": optimized_ats,
        "ats_improvement_percentage": improvement_percentage,
        "matching_keywords_before": keywords_before,
        "matching_keywords_after": keywords_after,
        "keywords_added": keywords_added,
        "unsupported_added_keywords": unsupported_added,
        "missing_keywords_remaining": optimized_analysis.get("missing_keywords", []),
        "improvements_summary": [
            "Rewrote the professional summary using only resume-backed evidence.",
            "Restricted the skills section to explicit resume skills plus evidence-backed inferred capabilities.",
            "Preserved header details, experience history, employers, titles, and dates from the original resume.",
        ],
        "resume_evidence_map": evidence_map,
        "added_keyword_explanations": _build_keyword_explanations(keywords_added, analysis, evidence_map),
        "bridge_the_gap_guidance": _build_bridge_the_gap_guidance(analysis, evidence_map),
        "trust_score": trust_score,
        "explicit_skills": explicit_categories.get("skills", []) + explicit_categories.get("technologies", []) + explicit_categories.get("certifications", []),
        "inferred_skills": inferred_skills,
        "ats_breakdown_before": _build_breakdown_snapshot(analysis.get("ats_breakdown", {})),
        "ats_breakdown_after": _build_breakdown_snapshot(optimized_analysis.get("ats_breakdown", {})),
    }
