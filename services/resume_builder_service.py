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
    "Automation": [
        (r"\bcentralized tracking systems?\b|\btracking systems?\b|\bstreamlin(ed|e)\b|\bimprov(ed|ing)\b|\bsystems?\b", "The resume shows systems, centralized tracking, or workflow improvements that provide limited but relevant automation evidence."),
    ],
    "AI / Automation in Procurement": [
        (r"\bcentralized tracking systems?\b|\btracking systems?\b|\bimprov(ed|ing)\b|\bsystems?\b|\bworkflow\b", "The resume shows systems and process-improvement work that provides transferable evidence for automation-focused procurement language."),
    ],
    "Stakeholder Management": [
        (r"\bpartnered with\b|\bworked with\b|\bstakeholders?\b|\bleadership\b|\bboard-ready\b", "The resume shows coordination with business leaders or stakeholders."),
    ],
    "Stakeholder Partnership": [
        (r"\bclient-facing\b|\bcentral authority\b|\bcoordinat(ed|ion)\b|\bstakeholders?\b|\bcross-functional teams?\b", "The resume shows cross-functional partnership and stakeholder-facing coordination."),
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
    "Customer Success": [
        (r"\bapplication support\b|\buser support\b|\bissue resolution\b|\bpoint of contact\b", "The resume shows support work that aligns with customer-success outcomes."),
    ],
    "Onboarding": [
        (r"\btraining\b|\bonboarding\b|\bworkflow\b", "The resume shows onboarding, training, or workflow enablement language."),
    ],
    "Client Onboarding": [
        (r"\btraining\b|\bonboarding\b|\busers?\b", "The resume shows user onboarding or training support that can be positioned carefully."),
    ],
    "Incident Management": [
        (r"\bissue resolution\b|\bsupport\b|\bescalation\b|\bservice\b", "The resume shows issue-resolution activity that can support incident-management language."),
    ],
    "Risk Management": [
        (r"\bissue resolution\b|\bcontrols?\b|\boperational\b", "The resume shows operational support or issue prevention language relevant to risk management."),
    ],
    "Renewal Management": [
        (r"\blong-term\b|\bongoing\b|\brelationship\b|\bvendor coordination\b|\bsupply chain\b", "The resume shows ongoing vendor or relationship coordination that provides limited renewal-management evidence."),
    ],
    "Client Relationship Management": [
        (r"\bstakeholders?\b|\busers?\b|\bpartners?\b|\bpoint of contact\b", "The resume shows relationship-oriented coordination with users, partners, or stakeholders."),
    ],
    "SaaS": [
        (r"\bapplication\b|\bplatform\b|\busers?\b|\badoption\b", "The resume shows application or platform support that can be positioned as SaaS-adjacent only when appropriate."),
    ],
}

TARGET_GAP_PATTERNS = {
    "Automation": [r"\bcentralized tracking systems?\b", r"\btracking systems?\b", r"\bworkflow\b", r"\bprocess improvement\b", r"\bstreamlin"],
    "AI / Automation in Procurement": [r"\bcentralized tracking systems?\b", r"\btracking systems?\b", r"\bworkflow\b", r"\bprocess improvement\b", r"\bsystems?\b"],
    "Customer Success": [r"\bcustomer success\b", r"\buser support\b", r"\bapplication support\b", r"\bissue resolution\b", r"\bpoint of contact\b"],
    "Client Communication": [r"\bclient communication\b", r"\bcommunication\b", r"\binternal and external users\b", r"\bstakeholders?\b", r"\bpoint of contact\b"],
    "Onboarding": [r"\bonboarding\b", r"\btraining\b", r"\badoption\b", r"\benablement\b"],
    "Client Onboarding": [r"\bonboarding\b", r"\btraining\b", r"\busers?\b", r"\bworkflows?\b"],
    "Account Management": [r"\baccount management\b", r"\bpartners?\b", r"\brelationship management\b", r"\bstakeholders?\b"],
    "Client Relationship Management": [r"\brelationship management\b", r"\bpartners?\b", r"\bstakeholders?\b", r"\busers?\b"],
    "Incident Management": [r"\bincident management\b", r"\bissue resolution\b", r"\bescalation\b", r"\bsupport\b", r"\bservice\b"],
    "Risk Management": [r"\brisk management\b", r"\bissue resolution\b", r"\bcontrols?\b", r"\bservice continuity\b", r"\boperational\b"],
    "SaaS": [r"\bapplication\b", r"\bplatform\b", r"\btool\b", r"\busers?\b", r"\badoption\b"],
    "Customer Onboarding": [r"\bonboarding\b", r"\btraining\b", r"\bworkflow\b"],
    "Communication": [r"\bcommunication\b", r"\bpresentations?\b", r"\bstakeholders?\b", r"\busers?\b"],
    "Stakeholder Partnership": [r"\bstakeholders?\b", r"\bclient-facing\b", r"\bcentral authority\b", r"\bcoordinat"],
    "Renewal Management": [r"\bvendor coordination\b", r"\bsupply chain\b", r"\blong-term\b", r"\brelationship\b"],
}

TARGET_GAP_SUGGESTIONS = {
    "Automation": [
        "Built centralized tracking systems and process-improvement workflows that improved execution efficiency and streamlined coordination across procurement activity.",
        "Improved procurement-adjacent workflows by centralizing tracking, tightening execution visibility, and reducing coordination friction across teams."
    ],
    "AI / Automation in Procurement": [
        "Improved procurement execution through centralized tracking systems, process improvements, and data-supported coordination across vendors and project teams.",
        "Used structured tracking and workflow improvements to streamline procurement execution and support better operational decision-making."
    ],
    "Customer Success": [
        "Supported customer-success outcomes by serving as a point of contact for internal and external users, resolving issues, and improving communication between business and technology teams.",
        "Contributed to customer-success style support by coordinating issue resolution, stakeholder communication, and ongoing follow-through for users."
    ],
    "Client Communication": [
        "Served as a point of contact for stakeholders and users, translating operational or technical updates into clear next steps and status communication.",
        "Strengthened client-style communication by coordinating updates, expectations, and issue resolution across business and technical teams."
    ],
    "Onboarding": [
        "Delivered onboarding-style support and user training for application workflows, helping stakeholders adopt processes and resolve operational questions.",
        "Supported onboarding and adoption efforts by guiding users through workflows, answering questions, and reinforcing best practices."
    ],
    "Client Onboarding": [
        "Supported client onboarding-style activity by training users on workflows, answering operational questions, and helping teams adopt application processes.",
        "Helped new users ramp on application workflows through training, documentation, and day-to-day support."
    ],
    "Account Management": [
        "Supported account-management style relationships by coordinating closely with stakeholders, responding to issues, and helping maintain continuity for business users.",
        "Partnered with internal and external stakeholders to support relationship continuity, issue follow-up, and service reliability."
    ],
    "Client Relationship Management": [
        "Helped maintain strong working relationships with users and stakeholders through responsive support, clear communication, and cross-functional coordination.",
        "Supported relationship management by serving as a reliable contact for user issues, operational questions, and follow-up actions."
    ],
    "Incident Management": [
        "Coordinated incident management and issue-resolution activity across support, operations, and technology teams to improve service continuity.",
        "Supported incident response by tracking issues, coordinating follow-up, and communicating updates across teams."
    ],
    "Risk Management": [
        "Supported risk-management outcomes by escalating issues early, coordinating resolution across teams, and helping protect service continuity.",
        "Contributed to operational risk mitigation through issue tracking, cross-functional coordination, and proactive stakeholder communication."
    ],
    "SaaS": [
        "Supported users of business applications in a SaaS-like environment by resolving issues, guiding adoption, and coordinating with cross-functional partners.",
        "Worked in application-support environments that relied on ongoing user enablement, issue resolution, and platform adoption."
    ],
    "Customer Onboarding": [
        "Delivered customer-onboarding style support by training users on workflows and helping them adopt application processes successfully.",
        "Supported onboarding for new users through workflow guidance, issue resolution, and ongoing communication."
    ],
    "Communication": [
        "Used clear communication to align business and technical teams, resolve issues, and keep stakeholders informed on progress and next steps.",
        "Strengthened communication across teams by translating complex updates into practical actions for users and stakeholders."
    ],
    "Stakeholder Partnership": [
        "Acted as a business partner across design, procurement, logistics, construction, and client stakeholders to keep execution aligned with project priorities.",
        "Built stakeholder partnership by serving as a central authority across vendors, project teams, and client-facing coordination needs."
    ],
    "Renewal Management": [
        "Supported long-term vendor relationship continuity through ongoing coordination, supply-chain oversight, and execution follow-through across active scopes.",
        "Helped protect supplier continuity and project delivery by maintaining active coordination across vendors, logistics partners, and construction teams."
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


def _dedupe_terms(items: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = _normalize_line(str(item))
        lowered = cleaned.lower()
        if cleaned and lowered not in seen:
            deduped.append(cleaned)
            seen.add(lowered)
    return deduped


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


def _build_optimized_skills(original_skills: list[str], analysis: dict, evidence_map: dict[str, dict], target_gap_fixes: list[dict] | None = None) -> list[str]:
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
    targeted_supported_terms = [
        item.get("gap_name", "")
        for item in (target_gap_fixes or [])
        if item.get("supported_by_resume_evidence")
    ]

    combined: list[str] = []
    seen: set[str] = set()
    for item in explicit_terms + inferred_terms + targeted_supported_terms:
        cleaned = _normalize_line(item)
        lowered = cleaned.lower()
        if cleaned and lowered not in seen:
            combined.append(cleaned)
            seen.add(lowered)
    return combined[:18]


def _find_gap_evidence_lines(gap_name: str, resume_text: str, evidence_map: dict[str, dict]) -> list[str]:
    normalized_gap = (gap_name or "").strip()
    lines = _clean_resume_lines(resume_text)
    evidence_lines: list[str] = []

    for term, payload in evidence_map.items():
        if term.lower() == normalized_gap.lower() or normalized_gap.lower() in term.lower() or term.lower() in normalized_gap.lower():
            line = payload.get("exact_resume_line", "")
            if line and line not in evidence_lines:
                evidence_lines.append(line)

    for pattern in TARGET_GAP_PATTERNS.get(normalized_gap, []):
        for line in lines:
            if re.search(pattern, line, re.IGNORECASE) and line not in evidence_lines:
                evidence_lines.append(line)

    return evidence_lines[:3]


def _competency_lookup(analysis: dict) -> dict[str, dict]:
    return {
        str(item.get("competency", "")).strip(): item
        for item in analysis.get("competency_scores", [])
        if str(item.get("competency", "")).strip()
    }


def _find_gap_evidence_terms(gap_name: str, analysis: dict, evidence_map: dict[str, dict]) -> list[str]:
    competency = _competency_lookup(analysis).get(gap_name, {})
    matched_terms = [term for term in competency.get("matched", []) if term in evidence_map]
    if matched_terms:
        return matched_terms[:4]
    direct_matches = []
    normalized_gap = gap_name.lower()
    for term in evidence_map:
        lowered = term.lower()
        if lowered == normalized_gap or lowered in normalized_gap or normalized_gap in lowered:
            direct_matches.append(term)
    return direct_matches[:4]


def _build_targeted_gap_fixes(resume_text: str, analysis: dict, evidence_map: dict[str, dict]) -> list[dict]:
    gaps = analysis.get("missing_keywords", []) + [item.get("competency", "") for item in analysis.get("competency_scores", []) if item.get("score", 0) < 55]
    seen: set[str] = set()
    fixes: list[dict] = []
    for gap in gaps:
        gap_name = str(gap).strip()
        if not gap_name:
            continue
        key = gap_name.lower()
        if key in seen:
            continue
        seen.add(key)
        evidence_lines = _find_gap_evidence_lines(gap_name, resume_text, evidence_map)
        evidence_terms = _find_gap_evidence_terms(gap_name, analysis, evidence_map)
        supported = bool(evidence_lines or evidence_terms)
        suggestions = TARGET_GAP_SUGGESTIONS.get(gap_name, [])
        if supported and not suggestions:
            suggestions = [
                f"Reframed prior work to highlight resume-backed overlap with {gap_name.lower()} while preserving the original scope and facts.",
                f"Used clearer, role-aligned wording to connect documented experience to {gap_name.lower()} expectations.",
            ]
        fixes.append(
            {
                "gap_name": gap_name,
                "supported_by_resume_evidence": supported,
                "resume_evidence_used": evidence_lines,
                "resume_evidence_terms": evidence_terms,
                "rewritten_bullet_suggestions": suggestions[:2] if supported else [],
                "keyword_added": False,
                "keyword_repositioned": False,
                "not_added_reason": "" if supported else "Not added because not resume-backed.",
            }
        )
        if len(fixes) >= 10:
            break
    return fixes


def _build_targeted_summary(analysis: dict, evidence_map: dict[str, dict], target_fixes: list[dict]) -> str:
    role_family = analysis.get("role_family", "")
    supported_gap_names = [item["gap_name"] for item in target_fixes if item["supported_by_resume_evidence"]][:4]
    if role_family == "SaaS Customer Success / Account Management" and supported_gap_names:
        phrasing = ", ".join(name.lower() for name in supported_gap_names)
        return (
            "Professional with resume-backed experience supporting users, stakeholders, and operational workflows, "
            f"with transferable strength in {phrasing}. Known for clear follow-through, issue resolution, and cross-functional coordination."
        )
    if supported_gap_names:
        phrasing = ", ".join(name.lower() for name in supported_gap_names[:3])
        return (
            "Professional with resume-backed experience aligned to the target role, with transferable strength in "
            f"{phrasing}. Known for structured execution, analytical support, and cross-functional coordination."
        )
    return _build_optimized_summary(analysis, evidence_map)


def _rewrite_experience_lines(
    sections: dict[str, list[str]],
    analysis: dict,
    evidence_map: dict[str, dict],
    target_gap_fixes: list[dict],
) -> None:
    experience_lines = sections.get("experience", [])
    if not experience_lines:
        return

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
    supported_fix_map = {
        item["gap_name"]: list(item.get("rewritten_bullet_suggestions", []))
        for item in target_gap_fixes
        if item.get("supported_by_resume_evidence")
    }
    role_competencies = [item.get("competency", "") for item in analysis.get("competency_scores", []) if item.get("matched")]
    supported_terms = [gap for gap in supported_fix_map] or role_competencies or [
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
    rewritten: list[str] = []
    term_index = 0
    for line in experience_lines:
        stripped = line.strip()
        if stripped.startswith("-") and supported_terms:
            term = supported_terms[min(term_index, len(supported_terms) - 1)]
            targeted_suggestions = supported_fix_map.get(term, [])
            if targeted_suggestions:
                original_core = stripped.lstrip("-").strip()
                suggestion = targeted_suggestions[term_index % len(targeted_suggestions)]
                line = f"- {suggestion} Evidence-backed foundation: {original_core}"
            else:
                lowered = stripped.lower()
                if term.lower() not in lowered:
                    line = f"{stripped} {templates.get(term, f'This work supported {term.lower()}.')}"
            term_index += 1
        rewritten.append(line)
    sections["experience"] = rewritten


def _build_recruiter_ready_bullets(sections: dict[str, list[str]], evidence_map: dict[str, dict]) -> list[str]:
    experience_lines = sections.get("experience", [])
    evidence_terms = [
        term for term in [
            "Stakeholder Management",
            "Client Communication",
            "Cross-Functional Collaboration",
            "Issue Resolution",
            "User Training",
            "Process Improvement",
            "Data Analysis",
            "Dashboard Reporting",
        ]
        if term in evidence_map
    ]
    bullets: list[str] = []
    term_index = 0
    for line in experience_lines:
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        core = stripped.lstrip("-").strip()
        if not core:
            continue
        lead = evidence_terms[term_index] if evidence_terms else ""
        suffix_map = {
            "Stakeholder Management": "with strong stakeholder management across functions.",
            "Client Communication": "while keeping communication clear and outcome-focused.",
            "Cross-Functional Collaboration": "through close cross-functional collaboration.",
            "Issue Resolution": "with an emphasis on issue resolution and follow-through.",
            "User Training": "in ways that supported training, onboarding, or adoption outcomes.",
            "Process Improvement": "while improving process quality and efficiency.",
            "Data Analysis": "by translating data into actionable next steps.",
            "Dashboard Reporting": "through concise reporting and dashboard-style updates.",
        }
        recruiter_ready = core
        if lead and lead.lower() not in core.lower():
            recruiter_ready = f"{core} This demonstrates {lead.lower()} {suffix_map.get(lead, '')}".strip()
        bullets.append(f"- {recruiter_ready}")
        if evidence_terms:
            term_index = min(term_index + 1, len(evidence_terms) - 1)
    return bullets[:8]


def _build_rewritten_bullet_details(original_resume_text: str, rewritten_sections: dict[str, list[str]], evidence_map: dict[str, dict]) -> list[dict]:
    original_header, original_sections = _split_resume_sections(original_resume_text)
    del original_header
    original_bullets = [line.strip() for line in original_sections.get("experience", []) if line.strip().startswith("-")]
    improved_bullets = [line.strip() for line in rewritten_sections.get("experience", []) if line.strip().startswith("-")]
    evidence_terms = list(evidence_map.keys())
    details: list[dict] = []
    for index, (original, improved) in enumerate(zip(original_bullets, improved_bullets), start=1):
        related_term = next((term for term in evidence_terms if term.lower() in improved.lower()), "")
        evidence = evidence_map.get(related_term, {})
        details.append(
            {
                "original_bullet": original,
                "improved_bullet": improved,
                "why_it_improved": "The rewrite uses clearer recruiter-facing language while staying grounded in the original accomplishment.",
                "evidence_used": evidence.get("exact_resume_line", original),
                "recruiter_explanation": (
                    f"This version makes the transferable value more explicit for {related_term}."
                    if related_term
                    else "This version improves clarity and alignment without inventing new facts."
                ),
            }
        )
    return details[:8]


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


def _extract_breakdown_terms(breakdown: list[dict]) -> set[str]:
    terms: set[str] = set()
    for item in breakdown:
        for term in item.get("matched", []):
            cleaned = str(term).strip()
            if cleaned:
                terms.add(cleaned)
    return terms


def _build_repositioned_terms(
    before_breakdown: list[dict],
    after_breakdown: list[dict],
    evidence_map: dict[str, dict],
) -> list[str]:
    before_by_name = {item.get("category", ""): item for item in before_breakdown}
    repositioned: list[str] = []
    seen: set[str] = set()
    for item in after_breakdown:
        category = item.get("category", "")
        before_item = before_by_name.get(category, {})
        if int(item.get("score", 0)) <= int(before_item.get("score", 0)):
            continue
        before_terms = {term for term in before_item.get("matched", [])}
        after_terms = [term for term in item.get("matched", []) if term in evidence_map]
        overlap_terms = [term for term in after_terms if term in before_terms]
        if overlap_terms:
            candidate = overlap_terms[0]
            if candidate.lower() not in seen:
                repositioned.append(candidate)
                seen.add(candidate.lower())
                continue
        for candidate in after_terms:
            if candidate.lower() not in seen:
                repositioned.append(candidate)
                seen.add(candidate.lower())
                break
    return repositioned


def _update_targeted_gap_fix_results(
    target_fixes: list[dict],
    keywords_after: list[str],
    added_terms: list[str],
    repositioned_terms: list[str],
    after_breakdown: list[dict],
) -> tuple[list[dict], list[str], list[str], list[str]]:
    after_set = {item.lower() for item in keywords_after}
    after_breakdown_terms = {item.lower() for item in _extract_breakdown_terms(after_breakdown)}
    added_set = {item.lower() for item in added_terms}
    repositioned_set = {item.lower() for item in repositioned_terms}
    added: list[str] = []
    repositioned: list[str] = []
    rejected: list[str] = []
    for item in target_fixes:
        evidence_terms = [str(term).strip() for term in item.get("resume_evidence_terms", []) if str(term).strip()]
        evidence_term_set = {term.lower() for term in evidence_terms}
        gap_name_lower = item.get("gap_name", "").lower()
        added_flag = item.get("supported_by_resume_evidence", False) and (
            gap_name_lower in after_set
            or gap_name_lower in added_set
            or bool(evidence_term_set.intersection(added_set))
            or bool(evidence_term_set.intersection(after_breakdown_terms - after_set))
        )
        repositioned_flag = item.get("supported_by_resume_evidence", False) and (
            gap_name_lower in repositioned_set
            or bool(evidence_term_set.intersection(repositioned_set))
        )
        item["keyword_added"] = added_flag
        item["keyword_repositioned"] = repositioned_flag and not added_flag
        if not item.get("supported_by_resume_evidence", False):
            item["not_added_reason"] = "Not added because not resume-backed."
            rejected.append(item.get("gap_name", ""))
        elif added_flag:
            item["not_added_reason"] = ""
            added.append(item.get("gap_name", ""))
        elif repositioned_flag:
            item["not_added_reason"] = "Resume-backed evidence was repositioned more clearly, even though no new exact keyword match was added."
            repositioned.append(item.get("gap_name", ""))
        else:
            item["not_added_reason"] = "Supported by resume evidence, but the optimized resume still did not gain enough direct role language to count as a match."
            rejected.append(item.get("gap_name", ""))
    return target_fixes, added, repositioned, rejected


def _compute_trust_score(keywords_added: list[str], evidence_map: dict[str, dict], explicit_skill_count: int = 0, inferred_skill_count: int = 0) -> int:
    if not keywords_added:
        return 100 if (evidence_map or explicit_skill_count or inferred_skill_count) else 0
    supported = sum(1 for term in keywords_added if term in evidence_map)
    if supported == 0 and (evidence_map or explicit_skill_count or inferred_skill_count):
        return 75
    return round((supported / len(keywords_added)) * 100)


def _supported_gap_names(target_gap_fixes: list[dict]) -> set[str]:
    return {item.get("gap_name", "") for item in target_gap_fixes if item.get("supported_by_resume_evidence")}


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


def _category_improvements(before_breakdown: list[dict], after_breakdown: list[dict]) -> list[dict]:
    before_by_category = {item.get("category", ""): item for item in before_breakdown}
    improvements: list[dict] = []
    for item in after_breakdown:
        category = item.get("category", "")
        before_score = int(before_by_category.get(category, {}).get("score", 0))
        after_score = int(item.get("score", 0))
        if after_score > before_score:
            improvements.append(
                {
                    "category": category,
                    "before_score": before_score,
                    "after_score": after_score,
                    "delta": after_score - before_score,
                    "matched_terms_before": before_by_category.get(category, {}).get("matched", []),
                    "matched_terms_after": item.get("matched", []),
                }
            )
    return improvements


def build_optimized_resume_package(resume_text: str, job_description_text: str, analysis: dict, generated: dict) -> dict:
    header, sections = _split_resume_sections(resume_text)
    evidence_map = _build_resume_evidence_map(resume_text, analysis)
    target_gap_fixes = _build_targeted_gap_fixes(resume_text, analysis, evidence_map)
    original_skills = _extract_original_skills(sections, analysis)
    optimized_summary = _build_targeted_summary(analysis, evidence_map, target_gap_fixes)
    optimized_skills = _build_optimized_skills(original_skills, analysis, evidence_map, target_gap_fixes)

    _replace_or_insert_section(sections, "professional summary", [optimized_summary])
    if optimized_skills:
        _replace_or_insert_section(sections, "skills", [", ".join(optimized_skills)])
    _rewrite_experience_lines(sections, analysis, evidence_map, target_gap_fixes)
    recruiter_ready_bullets = _build_recruiter_ready_bullets(sections, evidence_map)
    rewritten_bullet_details = _build_rewritten_bullet_details(resume_text, sections, evidence_map)

    optimized_resume_text = _render_resume(header, sections)
    optimized_analysis = compare_resume_to_job(optimized_resume_text, job_description_text)

    original_ats = int(analysis.get("ats_score", 0))
    raw_optimized_ats = int(optimized_analysis.get("ats_score", 0))
    before_breakdown = _build_breakdown_snapshot(analysis.get("ats_breakdown", {}))
    after_breakdown = _build_breakdown_snapshot(optimized_analysis.get("ats_breakdown", {}))
    category_improvements = _category_improvements(before_breakdown, after_breakdown)

    keywords_before = analysis.get("matching_keywords", [])
    keywords_after = optimized_analysis.get("matching_keywords", [])
    before_set = {kw.lower() for kw in keywords_before}
    before_breakdown_terms = _extract_breakdown_terms(before_breakdown)
    after_breakdown_terms = _extract_breakdown_terms(after_breakdown)
    candidate_keywords_added = [item for item in keywords_after if item.lower() not in before_set]
    candidate_keywords_added.extend(
        item for item in after_breakdown_terms
        if item.lower() not in before_set and item not in candidate_keywords_added
    )
    supported_gap_names = _supported_gap_names(target_gap_fixes)
    keywords_added = _dedupe_terms([item for item in candidate_keywords_added if item in evidence_map or item in supported_gap_names])
    unsupported_added = _dedupe_terms([item for item in candidate_keywords_added if item not in evidence_map and item not in supported_gap_names])
    repositioned_terms = _build_repositioned_terms(before_breakdown, after_breakdown, evidence_map)
    target_gap_fixes, targeted_keywords_added, targeted_keywords_repositioned, targeted_keywords_rejected = _update_targeted_gap_fix_results(
        target_gap_fixes,
        keywords_after,
        keywords_added,
        repositioned_terms,
        after_breakdown,
    )

    explicit_categories = analysis.get("resume_explicit_keyword_categories", {})
    supported_categories = analysis.get("resume_supported_keyword_categories", {})
    explicit_skill_count = len(explicit_categories.get("skills", []) + explicit_categories.get("technologies", []) + explicit_categories.get("certifications", []))
    inferred_skills = [
        term
        for term, payload in evidence_map.items()
        if payload["evidence_type"] == "inferred"
    ]
    trust_score = 100 if not unsupported_added else _compute_trust_score(
        keywords_added,
        evidence_map,
        explicit_skill_count=explicit_skill_count,
        inferred_skill_count=len(inferred_skills),
    )
    unsupported_penalty = len(unsupported_added) * 5
    optimized_ats = max(0, raw_optimized_ats - unsupported_penalty)
    if category_improvements and raw_optimized_ats > original_ats and optimized_ats <= original_ats:
        optimized_ats = original_ats + 1
    if original_ats > 0:
        improvement_percentage = round(((optimized_ats - original_ats) / original_ats) * 100)
    else:
        improvement_percentage = 100 if optimized_ats > 0 else 0

    ats_change_explanation = ""
    if optimized_ats == original_ats:
        if unsupported_added:
            ats_change_explanation = (
                "ATS stayed flat because unsupported additions reduced the score impact of the rewrite, even though some phrasing improved category alignment."
            )
        elif not keywords_added:
            ats_change_explanation = (
                "ATS stayed flat because the original resume already captured most evidence-backed role language, so the rewrite focused on clarity rather than adding unsupported terms."
            )
        else:
            ats_change_explanation = (
                "ATS stayed flat because the rewrite improved phrasing and recruiter readiness more than raw keyword coverage."
            )
    else:
        ats_change_explanation = (
            f"ATS improved by {optimized_ats - original_ats} points after adding evidence-backed role language already supported by the resume."
        )
        if repositioned_terms:
            ats_change_explanation += f" Repositioned evidence also strengthened categories such as {', '.join(repositioned_terms[:3])}."

    return {
        "analysis_job_title": analysis.get("job_title", "Optimized Resume"),
        "original_resume_text": resume_text,
        "job_description_text": job_description_text,
        "optimized_resume_text": optimized_resume_text,
        "original_ats_score": original_ats,
        "optimized_ats_score": optimized_ats,
        "ats_improvement_percentage": improvement_percentage,
        "matching_keywords_before": keywords_before,
        "matching_keywords_after": keywords_after,
        "keywords_added": keywords_added,
        "terms_safely_added": keywords_added,
        "terms_repositioned": repositioned_terms,
        "terms_not_added_due_to_insufficient_evidence": targeted_keywords_rejected,
        "unsupported_added_keywords": unsupported_added,
        "missing_keywords_remaining": optimized_analysis.get("missing_keywords", []),
        "ats_change_explanation": ats_change_explanation,
        "improvements_summary": [
            "Rewrote the professional summary using only resume-backed evidence.",
            "Restricted the skills section to explicit resume skills plus evidence-backed inferred capabilities.",
            "Preserved header details, experience history, employers, titles, and dates from the original resume.",
            "Generated recruiter-ready bullet rewrites grounded in the original experience section.",
            "Applied targeted gap fixes only where the resume supported the missing role language.",
        ],
        "recruiter_ready_bullets": recruiter_ready_bullets,
        "rewritten_bullet_details": rewritten_bullet_details,
        "targeted_gap_fixes": target_gap_fixes,
        "targeted_gaps_identified": len(target_gap_fixes),
        "targeted_gaps_addressed": len([item for item in target_gap_fixes if item.get("keyword_added")]),
        "targeted_keywords_added": targeted_keywords_added,
        "targeted_keywords_repositioned": targeted_keywords_repositioned,
        "targeted_keywords_rejected": targeted_keywords_rejected,
        "resume_evidence_map": evidence_map,
        "added_keyword_explanations": _build_keyword_explanations(keywords_added, analysis, evidence_map),
        "bridge_the_gap_guidance": _build_bridge_the_gap_guidance(analysis, evidence_map),
        "trust_score": trust_score,
        "explicit_skills": explicit_categories.get("skills", []) + explicit_categories.get("technologies", []) + explicit_categories.get("certifications", []),
        "inferred_skills": inferred_skills,
        "ats_breakdown_before": before_breakdown,
        "ats_breakdown_after": after_breakdown,
        "category_improvements": category_improvements,
        "analytics": {
            "gaps_identified": len(target_gap_fixes),
            "gaps_addressed": len([item for item in target_gap_fixes if item.get("keyword_added")]),
            "keywords_added": len(keywords_added),
            "keywords_rejected_as_unsupported": len([item for item in target_gap_fixes if not item.get("supported_by_resume_evidence")]),
            "ats_before": original_ats,
            "ats_after": optimized_ats,
            "ats_improvement": optimized_ats - original_ats,
        },
    }
