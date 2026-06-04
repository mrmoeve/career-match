import re
from datetime import datetime


GENERIC_BLOCKLIST = {
    "apply",
    "based",
    "account",
    "adoption",
    "committed",
    "dedicated",
    "business",
}

ATS_TERM_LIBRARY = {
    "skills": [
        "financial modeling", "valuation", "forecasting", "budgeting", "fp&a", "financial analysis",
        "variance analysis", "stakeholder management", "stakeholder communication", "customer success",
        "client success", "client relationship management", "cross-functional collaboration",
        "data analysis", "dashboard reporting", "executive reporting", "presentation development",
        "issue resolution", "project management", "project coordination", "business analysis",
        "requirements gathering", "incident management", "reconciliation", "risk management",
        "account management", "product adoption", "user training", "customer onboarding",
        "renewal support", "gross retention", "client engagement", "executive business reviews",
        "upselling", "cross-selling", "customer advocacy", "risk mitigation", "training", "onboarding",
        "relationship management", "client communication", "application support",
    ],
    "technologies": [
        "excel", "sql", "python", "powerpoint", "tableau", "power bi", "salesforce", "gainsight",
        "zendesk", "jira", "confluence", "sap", "erp", "crm", "workday",
    ],
    "certifications": [
        "cfa", "frm", "cpa", "caia", "series 7", "series 63", "series 65", "pmp", "scrum master",
        "aws certified", "azure", "google cloud", "itil", "cbap", "prince2",
    ],
    "responsibilities": [
        "client onboarding", "renewal support", "customer retention", "stakeholder management",
        "cross-functional collaboration", "executive reporting", "kpi reporting", "forecasting",
        "budgeting", "variance analysis", "process improvement", "data analysis", "dashboard reporting",
        "issue resolution", "escalation management", "relationship management", "presentation development",
        "requirements gathering", "incident management", "change management", "product adoption",
        "user training", "risk mitigation", "executive business reviews", "customer advocacy",
        "upselling", "cross-selling", "client engagement", "gross retention", "client communication",
        "training", "onboarding", "application support",
    ],
    "industry_terms": [
        "saas", "financial services", "capital markets", "asset management", "wealth management",
        "investment banking", "customer success", "operations", "trade support", "production support",
        "application support", "portfolio", "treasury", "compliance", "risk", "reconciliation",
        "account management", "renewals",
    ],
}

ATS_SYNONYMS = {
    "skills": [
        (r"\bcustomer relationships?\b", "Client Relationship Management"),
        (r"\baccount managers?\b|\baccount management\b", "Account Management"),
        (r"\bproduct adoption\b", "Product Adoption"),
        (r"\buser training\b|\btraining sessions?\b|\btraining\b|\bonboarding\b", "User Training"),
        (r"\bgross retention\b", "Gross Retention"),
        (r"\bclient engagement\b|\bcustomer engagement\b", "Client Engagement"),
        (r"\bexecutive business reviews?\b", "Executive Business Reviews"),
        (r"\bupselling\b", "Upselling"),
        (r"\bcross-selling\b", "Cross-selling"),
        (r"\brisk mitigation\b|\bmitigate risks?\b", "Risk Mitigation"),
        (r"\binternal stakeholders?\b|\bstakeholders?\b|\bbusiness leaders?\b", "Stakeholder Management"),
        (r"\bcross-functional teams?\b|\bcross-functional collaboration\b|\bpartnered with\b|\bworked with\b", "Cross-Functional Collaboration"),
        (r"\bclient support\b|\bcustomer support\b|\bcommunication\b", "Client Communication"),
        (r"\bissue resolution\b|\bresolve(?:d)? issues?\b", "Issue Resolution"),
        (r"\bapplication support\b", "Application Support"),
        (r"\bbusiness analysis\b|\bbusiness analyst\b", "Business Analysis"),
    ],
    "responsibilities": [
        (r"\bonboarding\b", "Client Onboarding"),
        (r"\brenewals?\b", "Renewal Support"),
        (r"\bcustomer feedback\b", "Client Engagement"),
        (r"\btraining sessions?\b|\buser training\b|\btraining\b", "User Training"),
        (r"\bstakeholders?\b|\bbusiness leaders?\b", "Stakeholder Management"),
        (r"\bcross-functional teams?\b|\bpartnered with\b|\bworked with\b", "Cross-Functional Collaboration"),
        (r"\bexecutive business reviews?\b", "Executive Business Reviews"),
        (r"\bissue resolution\b|\bresolve(?:d)? issues?\b", "Issue Resolution"),
        (r"\bclient communication\b|\bpresenting insights\b|\bcommunication\b", "Client Communication"),
        (r"\bapplication support\b", "Application Support"),
        (r"\bbusiness analysis\b|\bbusiness analyst\b", "Business Analysis"),
    ],
    "industry_terms": [
        (r"\bcustomer success\b", "Customer Success"),
        (r"\baccount management\b|\baccount managers?\b", "Account Management"),
        (r"\brenewals?\b", "Renewals"),
    ],
}

FINANCE_INDUSTRY_TERMS = [
    "bank", "banking", "capital markets", "asset management", "wealth management", "trading",
    "investment", "brokerage", "hedge fund", "private equity", "financial services", "treasury",
    "operations", "reconciliation", "portfolio", "equity research", "credit", "risk", "compliance",
    "customer success", "saas",
]

TITLE_KEYWORDS = {
    "analyst", "associate", "manager", "director", "support", "operations", "product",
    "project", "business analyst", "client success", "customer success", "technology", "engineer",
    "specialist",
}

COMPETENCY_MODEL = {
    "Customer Success": {
        "job_terms": ["Customer Success", "Client Engagement", "Gross Retention", "Renewals", "Customer Onboarding", "Product Adoption"],
        "transfer_terms": ["Stakeholder Management", "Client Communication", "Relationship Management", "Cross-Functional Collaboration", "Issue Resolution", "Application Support", "User Training"],
        "weight": 18,
    },
    "Account Management": {
        "job_terms": ["Account Management", "Client Relationship Management", "Renewal Support", "Upselling", "Cross-selling", "Executive Business Reviews"],
        "transfer_terms": ["Stakeholder Management", "Relationship Management", "Client Communication", "Cross-Functional Collaboration", "Business Analysis", "Stakeholder Communication"],
        "weight": 16,
    },
    "Stakeholder Management": {
        "job_terms": ["Stakeholder Management", "Cross-Functional Collaboration", "Executive Business Reviews"],
        "transfer_terms": ["Stakeholder Communication", "Executive Reporting", "Client Communication", "Business Analysis", "Project Coordination"],
        "weight": 18,
    },
    "Client Communication": {
        "job_terms": ["Client Communication", "Client Relationship Management", "User Training"],
        "transfer_terms": ["Stakeholder Communication", "Executive Reporting", "Presentation Development", "Issue Resolution", "Application Support"],
        "weight": 16,
    },
    "Risk Management": {
        "job_terms": ["Risk Mitigation", "Risk", "Issue Resolution"],
        "transfer_terms": ["Risk Management", "Data Analysis", "Process Improvement", "Reconciliation", "Variance Analysis"],
        "weight": 14,
    },
    "Training & Adoption": {
        "job_terms": ["Product Adoption", "User Training", "Client Onboarding", "Customer Onboarding"],
        "transfer_terms": ["Training", "Dashboard Reporting", "Process Improvement", "Stakeholder Communication", "Presentation Development", "Application Support", "Issue Resolution"],
        "weight": 18,
    },
}

ROLE_FAMILY_RULES = [
    (
        {"Customer Success", "Account Management", "Client Engagement", "Gross Retention", "Renewals", "Product Adoption", "Client Onboarding"},
        "SaaS Customer Success / Account Management",
    ),
    (
        {"Application Support", "Issue Resolution", "Incident Management"},
        "Application Support / Client Service",
    ),
]


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _dedupe_keep_order(items: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = re.sub(r"\s+", " ", item).strip()
        lowered = cleaned.lower()
        if not cleaned or lowered in seen or lowered in GENERIC_BLOCKLIST:
            continue
        seen.add(lowered)
        output.append(cleaned)
    return output


def _title_case_term(term: str) -> str:
    exact_map = {
        "fp&a": "FP&A",
        "sql": "SQL",
        "crm": "CRM",
        "erp": "ERP",
        "sap": "SAP",
        "kpi": "KPI",
        "cfa": "CFA",
        "frm": "FRM",
        "cpa": "CPA",
        "caia": "CAIA",
        "pmp": "PMP",
        "itil": "ITIL",
        "powerpoint": "PowerPoint",
    }
    return " ".join(exact_map.get(word.lower(), word.capitalize()) for word in term.split())


def _contains_term(normalized_text: str, term: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])"
    return bool(re.search(pattern, normalized_text))


def _extract_known_terms(text: str, include_synonyms: bool = True) -> dict[str, list[str]]:
    normalized = _normalize_text(text)
    extracted: dict[str, list[str]] = {}
    for category, terms in ATS_TERM_LIBRARY.items():
        found = [term for term in terms if _contains_term(normalized, term)]
        synonym_hits = []
        if include_synonyms:
            for pattern, label in ATS_SYNONYMS.get(category, []):
                if re.search(pattern, normalized):
                    synonym_hits.append(label)
        extracted[category] = _dedupe_keep_order([_title_case_term(term) for term in found] + synonym_hits)
    return extracted


def _extract_inferred_responsibilities(text: str) -> list[str]:
    normalized = _normalize_text(text)
    inferred: list[str] = []
    pattern_map = [
        (r"\bpartnered with\b|\bworked with\b|\bcollaborated with\b", "Cross-Functional Collaboration"),
        (r"\bstakeholder|\bsenior stakeholders|\bleadership\b|\bboard-ready\b|\bbusiness leaders?\b", "Stakeholder Management"),
        (r"\breporting|\bdashboard|\bkpi\b", "Dashboard Reporting"),
        (r"\bpresentations?\b|\bpresented\b|\bleadership reviews?\b", "Executive Reporting"),
        (r"\banalysis\b|\banalytical\b|\bvariance\b|\btracking\b", "Data Analysis"),
        (r"\bimprov(ed|ing)\b|\bautomated\b|\breduc(ed|ing)\b", "Process Improvement"),
        (r"\btraining\b|\bonboarding\b", "User Training"),
        (r"\baccount managers?\b|\baccounts?\b", "Account Management"),
        (r"\bissue\b|\bresolution\b", "Issue Resolution"),
        (r"\bcommunicat(ed|ion)\b|\bpresenting insights\b", "Client Communication"),
        (r"\brisk\b|\bcontrols?\b|\breconciliation\b", "Risk Management"),
        (r"\bapplication support\b", "Application Support"),
        (r"\bbusiness analysis\b|\bbusiness analyst\b", "Business Analysis"),
    ]
    for pattern, label in pattern_map:
        if re.search(pattern, normalized):
            inferred.append(label)
    return _dedupe_keep_order(inferred)


def _merge_resume_categories(text: str, include_inferred_responsibilities: bool = False) -> dict[str, list[str]]:
    categories = _extract_known_terms(text, include_synonyms=False)
    if include_inferred_responsibilities:
        inferred = _extract_inferred_responsibilities(text)
        categories["responsibilities"] = _dedupe_keep_order(categories.get("responsibilities", []) + inferred)
        categories["skills"] = _dedupe_keep_order(categories.get("skills", []) + inferred)
    return categories


def _flatten_categories(categories: dict[str, list[str]]) -> list[str]:
    flattened: list[str] = []
    for key in ["skills", "technologies", "certifications", "responsibilities", "industry_terms"]:
        flattened.extend(categories.get(key, []))
    return _dedupe_keep_order(flattened)


def _clean_resume_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line.strip())
        if line:
            lines.append(line)
    return lines


def _find_resume_evidence_lines(resume_text: str, terms: list[str], limit: int = 3) -> list[str]:
    lines = _clean_resume_lines(resume_text)
    matches: list[str] = []
    for line in lines:
        lowered = line.lower()
        if any(term.lower() in lowered for term in terms if term):
            matches.append(line)
        if len(matches) >= limit:
            break
    if matches:
        return matches

    fallback_patterns = [
        ({"Stakeholder Management", "Stakeholder Communication"}, r"\bstakeholder|\bleadership|\bbusiness leaders?\b|\bboard-ready\b"),
        ({"Client Communication", "Relationship Management"}, r"\bcommunicat|\bpresent|\bpartner|\bwork(ed)? with\b"),
        ({"Cross-Functional Collaboration"}, r"\bcross-functional|\bpartnered with\b|\bworked with\b|\bcollaborat"),
        ({"Issue Resolution", "Application Support"}, r"\bissue|\bresolve|\bsupport|\bincident"),
        ({"Data Analysis", "Business Analysis"}, r"\banalysis|\bvariance|\bforecast|\bmetrics|\bdashboard"),
        ({"User Training", "Customer Onboarding", "Training"}, r"\btraining|\bonboarding|\benable"),
    ]
    inferred: list[str] = []
    for term_set, pattern in fallback_patterns:
        if term_set.intersection(set(terms)):
            for line in lines:
                if re.search(pattern, line, re.IGNORECASE):
                    inferred.append(line)
                if len(inferred) >= limit:
                    return inferred
    return inferred


def _build_matching_reasoning(
    resume_text: str,
    job_categories: dict[str, list[str]],
    resume_supported_categories: dict[str, list[str]],
    competency_scores: list[dict],
) -> list[dict]:
    reasoning: list[dict] = []
    for item in competency_scores:
        matched_terms = item.get("matched", [])[:4]
        if not matched_terms:
            continue
        evidence_lines = _find_resume_evidence_lines(resume_text, matched_terms, limit=3)
        reasoning.append(
            {
                "competency": item["competency"],
                "matched_terms": matched_terms,
                "score": item["score"],
                "why_it_matched": (
                    f"The role emphasizes {', '.join(item.get('job_expectations', [])[:3])}, and the resume already shows "
                    f"{', '.join(matched_terms[:3])}."
                ),
                "resume_evidence_lines": evidence_lines,
            }
        )
    return reasoning


def _build_missing_reasoning(
    resume_text: str,
    job_categories: dict[str, list[str]],
    resume_supported_categories: dict[str, list[str]],
    competency_scores: list[dict],
) -> list[dict]:
    supported_terms = set(_flatten_categories(resume_supported_categories))
    missing_items: list[dict] = []
    for item in competency_scores:
        missing_terms = [term for term in item.get("job_expectations", []) if term not in supported_terms][:4]
        if not missing_terms:
            continue
        nearby_evidence = _find_resume_evidence_lines(resume_text, item.get("matched", []), limit=2)
        missing_items.append(
            {
                "competency": item["competency"],
                "missing_terms": missing_terms,
                "why_it_is_missing": (
                    f"The job calls for {', '.join(missing_terms[:3])}, but those phrases do not appear clearly in the uploaded resume."
                ),
                "closest_resume_evidence": nearby_evidence,
            }
        )
    return missing_items


def _extract_years_of_experience(text: str) -> int:
    matches = re.findall(r"(\d+)\s*\+?\s*years?", text.lower())
    numbers = [int(match) for match in matches]
    return max(numbers) if numbers else 0


def _parse_month(value: str | None, fallback: int) -> int:
    month_lookup = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4,
        "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9,
        "september": 9, "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
    }
    if not value:
        return fallback
    return month_lookup.get(value.lower(), fallback)


def _extract_employment_ranges(resume_text: str) -> list[tuple[datetime, datetime]]:
    current_date = datetime.now()
    ranges: list[tuple[datetime, datetime]] = []
    patterns = [
        re.compile(
            r"(?P<start_month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)?\s*"
            r"(?P<start_year>19\d{2}|20\d{2})\s*(?:-|–|to)\s*"
            r"(?P<end_month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)?\s*"
            r"(?P<end_year>Present|Current|19\d{2}|20\d{2})",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?P<start_year>19\d{2}|20\d{2})\s*(?:-|–|to)\s*(?P<end_year>Present|Current|19\d{2}|20\d{2})",
            re.IGNORECASE,
        ),
    ]

    for line in resume_text.splitlines():
        for pattern in patterns:
            match = pattern.search(line)
            if not match:
                continue
            start_year = int(match.group("start_year"))
            end_year_raw = match.group("end_year")
            start_month = _parse_month(match.groupdict().get("start_month"), 1)
            if end_year_raw.lower() in {"present", "current"}:
                end_year = current_date.year
                end_month = current_date.month
            else:
                end_year = int(end_year_raw)
                end_month = _parse_month(match.groupdict().get("end_month"), 12)
            try:
                start = datetime(start_year, start_month, 1)
                end = datetime(end_year, end_month, 1)
            except ValueError:
                continue
            if end >= start:
                ranges.append((start, end))
            break
    return ranges


def _calculate_total_experience_years(resume_text: str) -> int:
    ranges = sorted(_extract_employment_ranges(resume_text), key=lambda item: item[0])
    if not ranges:
        return _extract_years_of_experience(resume_text)

    merged: list[list[datetime]] = []
    for start, end in ranges:
        if not merged:
            merged.append([start, end])
            continue
        previous_end = merged[-1][1]
        gap_months = (start.year - previous_end.year) * 12 + (start.month - previous_end.month)
        if gap_months <= 1:
            if end > previous_end:
                merged[-1][1] = end
        else:
            merged.append([start, end])

    total_months = 0
    for start, end in merged:
        total_months += (end.year - start.year) * 12 + (end.month - start.month) + 1
    return max(0, round(total_months / 12))


def _extract_required_and_preferred_skills(job_description_text: str, job_skills: set[str]) -> tuple[list[str], list[str]]:
    lowered = job_description_text.lower()
    required = []
    preferred = []
    for skill in sorted(job_skills):
        pattern = re.escape(skill.lower())
        if re.search(rf"(required|must have|strong|need|needs|bring|expertise).{{0,100}}{pattern}|{pattern}.{{0,100}}(required|must have|strong|need|needs)", lowered):
            required.append(skill)
        elif re.search(rf"(preferred|nice to have|plus|ideal).{{0,100}}{pattern}|{pattern}.{{0,100}}(preferred|nice to have|plus)", lowered):
            preferred.append(skill)

    if not required:
        required = sorted(list(job_skills))[: min(6, len(job_skills))]
    remaining = [skill for skill in sorted(job_skills) if skill not in required]
    if not preferred:
        preferred = remaining[: min(4, len(remaining))]
    return required, preferred


def _extract_title_tokens(title: str) -> set[str]:
    normalized = _normalize_text(title)
    return {token for token in TITLE_KEYWORDS if token in normalized}


def _extract_industry_terms(text: str) -> set[str]:
    normalized = _normalize_text(text)
    return {term for term in FINANCE_INDUSTRY_TERMS if term in normalized}


def _extract_titles_and_employers(resume_text: str) -> tuple[set[str], set[str]]:
    titles: set[str] = set()
    employers: set[str] = set()
    for line in resume_text.splitlines():
        cleaned = line.strip()
        if "|" in cleaned and re.search(r"(19|20)\d{2}\s*[-–]\s*(Present|Current|(19|20)\d{2})", cleaned, re.IGNORECASE):
            parts = [part.strip() for part in cleaned.split("|")]
            if len(parts) >= 2:
                titles.add(parts[0].lower())
                employers.add(parts[1].lower())
    return titles, employers


def _extract_quantified_bullets(resume_text: str) -> list[str]:
    bullets = []
    for line in resume_text.splitlines():
        cleaned = line.strip()
        if cleaned.startswith("-") and re.search(r"\d", cleaned):
            bullets.append(cleaned.lstrip("- ").strip())
    return bullets


def _build_job_fit_analysis(
    resume_text: str,
    job_description_text: str,
    job_title: str,
    resume_skills: set[str],
    job_skills: set[str],
) -> dict:
    resume_years = _calculate_total_experience_years(resume_text)
    required_years = _extract_years_of_experience(job_description_text)
    resume_certs = set(term.lower() for term in _extract_known_terms(resume_text)["certifications"])
    required_skills, preferred_skills = _extract_required_and_preferred_skills(job_description_text, job_skills)

    required_skill_matches = sorted([skill for skill in required_skills if skill in resume_skills])
    preferred_skill_matches = sorted([skill for skill in preferred_skills if skill in resume_skills])
    missing_required_skills = sorted([skill for skill in required_skills if skill not in resume_skills])
    missing_preferred_skills = sorted([skill for skill in preferred_skills if skill not in resume_skills])

    resume_title_tokens = _extract_title_tokens(resume_text)
    job_title_tokens = _extract_title_tokens(job_title)
    title_overlap = sorted(job_title_tokens.intersection(resume_title_tokens))

    resume_industry = _extract_industry_terms(resume_text)
    job_industry = _extract_industry_terms(job_description_text)
    industry_overlap = sorted(resume_industry.intersection(job_industry))

    required_certs = _extract_known_terms(job_description_text)["certifications"]
    matching_certs = sorted([cert for cert in required_certs if cert.lower() in resume_certs])
    missing_certs = sorted([cert for cert in required_certs if cert.lower() not in resume_certs])

    experience_component = 25
    if required_years:
        if resume_years >= required_years:
            experience_component = 25
        elif resume_years >= max(required_years - 2, 1):
            experience_component = 20
        elif resume_years > 0:
            experience_component = 12
        else:
            experience_component = 4
    title_component = 20 if title_overlap else 10
    industry_component = 15 if industry_overlap else 8
    required_skill_component = round((len(required_skill_matches) / max(len(required_skills), 1)) * 25)
    preferred_skill_component = round((len(preferred_skill_matches) / max(len(preferred_skills), 1)) * 10) if preferred_skills else 6
    certification_component = 5 if (not required_certs or matching_certs) else 0

    fit_score = max(
        0,
        min(
            100,
            experience_component
            + title_component
            + industry_component
            + required_skill_component
            + preferred_skill_component
            + certification_component,
        ),
    )

    if fit_score >= 78 and len(missing_required_skills) <= 1:
        recommendation = "Apply Immediately"
    elif fit_score >= 60:
        recommendation = "Good Stretch Opportunity"
    elif fit_score >= 40:
        recommendation = "Low Probability Match"
    else:
        recommendation = "Not Recommended"

    reasoning = []
    if required_years:
        if resume_years >= required_years:
            reasoning.append(f"Experience level looks aligned: resume history suggests about {resume_years} years versus {required_years} years requested.")
        else:
            reasoning.append(f"Experience gap: resume history suggests about {resume_years} years versus {required_years} years requested.")
    else:
        reasoning.append(f"The job description does not clearly state years of experience, so fit is based on transferable role alignment across about {resume_years} years of resume history.")

    if title_overlap:
        reasoning.append(f"Title match is reasonable because the resume reflects overlapping role language: {', '.join(title_overlap)}.")
    else:
        reasoning.append("Title match is weaker because the resume does not clearly mirror the target title language.")

    if industry_overlap:
        reasoning.append(f"Industry alignment is supported by shared domain terms such as {', '.join(industry_overlap[:4])}.")
    else:
        reasoning.append("Industry match is limited, but the transferable responsibilities may still support a stretch application.")

    reasoning.append(
        f"Required skills matched: {len(required_skill_matches)}/{len(required_skills)}"
        + (f" ({', '.join(required_skill_matches)})." if required_skill_matches else ".")
    )
    if preferred_skills:
        reasoning.append(
            f"Preferred skills matched: {len(preferred_skill_matches)}/{len(preferred_skills)}"
            + (f" ({', '.join(preferred_skill_matches)})." if preferred_skill_matches else ".")
        )
    if required_certs:
        if matching_certs:
            reasoning.append(f"Certification alignment is positive: matched {', '.join(matching_certs)}.")
        else:
            reasoning.append(f"Certification gap: the job mentions {', '.join(required_certs)} and the resume does not show it clearly.")

    return {
        "fit_score": fit_score,
        "recommendation": recommendation,
        "reasoning": reasoning,
        "years_experience_resume": resume_years,
        "years_experience_required": required_years,
        "title_overlap": title_overlap,
        "industry_overlap": industry_overlap,
        "required_skills": required_skills,
        "required_skill_matches": required_skill_matches,
        "missing_required_skills": missing_required_skills,
        "preferred_skills": preferred_skills,
        "preferred_skill_matches": preferred_skill_matches,
        "missing_preferred_skills": missing_preferred_skills,
        "required_certifications": required_certs,
        "matching_certifications": matching_certs,
        "missing_certifications": missing_certs,
    }


def _extract_title(job_description_text: str) -> str:
    first_lines = [line.strip() for line in job_description_text.splitlines() if line.strip()]
    for line in first_lines[:8]:
        lowered = line.lower()
        if (
            "skip to main content" in lowered
            or "apply now" in lowered
            or lowered.endswith(":")
            or lowered in {
                "description",
                "what we’re looking for",
                "what we're looking for",
                "what you'll do",
                "what you’ll do",
                "what you'll bring",
                "what you’ll bring",
                "what we offer",
                "compensation overview",
                "our story",
                "equal employment opportunity statement",
            }
        ):
            continue
        if 2 <= len(line.split()) <= 8:
            return line[:100]

    prose_match = re.search(
        r"\b(?:career as|join us as|hiring a|for a|as a)\s+(?:an?\s+)?([A-Z][A-Za-z0-9&/ .+\-]{3,80}?)\s+at\s+[A-Z]",
        job_description_text,
        re.IGNORECASE,
    )
    if prose_match:
        return prose_match.group(1).strip()[:100]

    title_match = re.search(r"(?:position|role|title)\s*[:\-]\s*(.+)", job_description_text, re.IGNORECASE)
    return title_match.group(1).strip()[:100] if title_match else "Target Finance Role"


def _extract_company(job_description_text: str) -> str:
    first_lines = [line.strip() for line in job_description_text.splitlines() if line.strip()]
    for line in first_lines[:8]:
        lowered = line.lower()
        if (
            lowered.endswith(":")
            or lowered in {
                "description",
                "what we’re looking for",
                "what we're looking for",
                "what you'll do",
                "what you’ll do",
                "what you'll bring",
                "what you’ll bring",
                "what we offer",
                "compensation overview",
                "our story",
                "equal employment opportunity statement",
            }
            or line.startswith("At ")
            or len(line.split()) > 8
        ):
            continue
        if 1 <= len(line.split()) <= 6:
            return line[:100]

    prose_match = re.search(r"\bAt\s+([A-Z][A-Za-z0-9&.\- ]{2,60})[, ]", job_description_text)
    if prose_match:
        return prose_match.group(1).strip()[:100]

    prose_match = re.search(r"\bat\s+([A-Z][A-Za-z0-9&.\- ]{2,60})[, ]", job_description_text)
    if prose_match:
        return prose_match.group(1).strip()[:100]

    company_match = re.search(r"(?:company|organization|firm)\s*[:\-]\s*(.+)", job_description_text, re.IGNORECASE)
    return company_match.group(1).strip()[:100] if company_match else "Target Company"


def _build_competency_scores(
    resume_explicit_categories: dict[str, list[str]],
    resume_supported_categories: dict[str, list[str]],
    job_categories: dict[str, list[str]],
    resume_years: int,
    title_overlap: list[str],
    industry_overlap: list[str],
) -> tuple[list[dict], int, int, int, int]:
    explicit_terms = set(term.lower() for term in _flatten_categories(resume_explicit_categories))
    supported_terms = set(term.lower() for term in _flatten_categories(resume_supported_categories))
    job_terms_flat = set(term.lower() for term in _flatten_categories(job_categories))

    competency_rows: list[dict] = []
    direct_total = 0.0
    transferable_total = 0.0
    weight_total = 0.0

    for name, config in COMPETENCY_MODEL.items():
        job_terms = [term for term in config["job_terms"] if term.lower() in job_terms_flat]
        if not job_terms:
            job_terms = config["job_terms"][:2]

        exact_direct_hits = [term for term in job_terms if term.lower() in explicit_terms]
        adjacent_direct_hits = [term for term in config["transfer_terms"] if term.lower() in explicit_terms]
        transfer_hits = [term for term in config["transfer_terms"] if term.lower() in supported_terms]

        direct_score = round(
            min(
                100,
                ((len(exact_direct_hits) + 0.45 * len(adjacent_direct_hits)) / max(len(job_terms), 1)) * 100,
            )
        )
        transfer_coverage = len(transfer_hits) / max(len(config["transfer_terms"]), 1)
        transferable_score = round(
            min(
                100,
                direct_score * 0.35
                + transfer_coverage * 100 * 0.65
                + (12 if len(transfer_hits) >= 3 else 6 if len(transfer_hits) >= 2 else 0),
            )
        )

        title_bonus = 6 if title_overlap and name in {"Stakeholder Management", "Account Management"} else 0
        industry_bonus = 6 if industry_overlap and name in {"Risk Management", "Account Management"} else 0
        experience_bonus = 8 if resume_years >= 10 else 5 if resume_years >= 5 else 2 if resume_years >= 2 else 0
        overall_score = max(0, min(100, round(direct_score * 0.45 + transferable_score * 0.40 + title_bonus + industry_bonus + experience_bonus)))

        competency_rows.append(
            {
                "competency": name,
                "direct_score": direct_score,
                "transferable_score": transferable_score,
                "score": overall_score,
                "matched": _dedupe_keep_order(exact_direct_hits + adjacent_direct_hits + transfer_hits),
                "job_expectations": job_terms,
            }
        )

        direct_total += direct_score * config["weight"]
        transferable_total += transferable_score * config["weight"]
        weight_total += config["weight"]

    direct_match_score = round(direct_total / weight_total) if weight_total else 0
    transferable_match_score = round(transferable_total / weight_total) if weight_total else 0
    experience_alignment = 90 if resume_years >= 10 else 78 if resume_years >= 5 else 60 if resume_years >= 3 else 40 if resume_years > 0 else 0
    top_competency_average = round(
        sum(sorted((item["score"] for item in competency_rows), reverse=True)[:3]) / min(len(competency_rows), 3)
    ) if competency_rows else 0
    overall_fit_score = max(
        0,
        min(
            100,
            round(
                direct_match_score * 0.28
                + transferable_match_score * 0.44
                + experience_alignment * 0.28
            ),
        ),
    )
    interview_potential_score = max(
        0,
        min(
            100,
            round(
                direct_match_score * 0.14
                + transferable_match_score * 0.40
                + experience_alignment * 0.24
                + top_competency_average * 0.22
            ),
        ),
    )
    return competency_rows, direct_match_score, transferable_match_score, overall_fit_score, interview_potential_score


def _infer_role_family(job_categories: dict[str, list[str]]) -> str:
    job_terms = set(_flatten_categories(job_categories))
    for triggers, label in ROLE_FAMILY_RULES:
        if job_terms.intersection(triggers):
            return label
    if "SaaS" in job_terms or "Customer Success" in job_terms:
        return "SaaS Customer Success / Account Management"
    if "Financial Services" in job_terms:
        return "Financial Services"
    return "General Professional Role"


def _build_role_gap_analysis(
    job_categories: dict[str, list[str]],
    resume_explicit_categories: dict[str, list[str]],
    resume_supported_categories: dict[str, list[str]],
    competency_scores: list[dict],
) -> dict:
    explicit_terms = set(_flatten_categories(resume_explicit_categories))
    supported_terms = set(_flatten_categories(resume_supported_categories))
    job_terms = _flatten_categories(job_categories)

    missing_experience = [term for term in job_terms if term not in supported_terms][:8]
    transferable_experience = [term for term in supported_terms if term in _flatten_categories(job_categories)][:8]
    missing_competencies = [item["competency"] for item in competency_scores if item["direct_score"] < 45][:6]
    reposition_resume = []
    mapping_suggestions = [
        ("Stakeholder Management", "Reposition stakeholder coordination as customer-success-relevant relationship management."),
        ("Client Communication", "Highlight communication work as client-facing support and expectation management."),
        ("Application Support", "Frame application or operational support work as issue resolution and adoption support."),
        ("Business Analysis", "Position analytical problem-solving as proactive customer problem resolution."),
        ("Cross-Functional Collaboration", "Emphasize partnership across teams as a customer-success style coordination strength."),
    ]
    for term, suggestion in mapping_suggestions:
        if term in supported_terms:
            reposition_resume.append(suggestion)

    return {
        "missing_experience": missing_experience,
        "transferable_experience": transferable_experience,
        "missing_competencies": missing_competencies,
        "resume_repositioning": _dedupe_keep_order(reposition_resume)[:5],
    }


def _build_hiring_manager_view(
    resume_text: str,
    resume_years: int,
    competency_scores: list[dict],
    direct_match_score: int,
    transferable_match_score: int,
    overall_fit_score: int,
) -> list[str]:
    _, employers = _extract_titles_and_employers(resume_text)
    quantified = _extract_quantified_bullets(resume_text)
    reasons = []

    if resume_years >= 5:
        reasons.append(f"The candidate brings about {resume_years} years of professional experience, which can offset limited exact-title alignment.")
    if employers:
        reasons.append(f"The resume shows experience at established employers such as {', '.join(sorted(employers)[:3])}.")
    if transferable_match_score >= 70:
        reasons.append(f"Transferable match is strong at {transferable_match_score}%, suggesting the candidate could ramp into the role even without a direct customer-success title.")
    strong_competencies = [item["competency"] for item in competency_scores if item["score"] >= 70]
    if strong_competencies:
        reasons.append(f"Interview potential is supported by strong competencies in {', '.join(strong_competencies[:3])}.")
    if quantified:
        reasons.append("The resume includes measurable accomplishments, which gives a hiring manager concrete evidence of impact and execution.")
    if direct_match_score < 50 and overall_fit_score >= 65:
        reasons.append("Even with lighter direct match, the candidate may still merit an interview because the transferable profile is materially stronger than the title history alone suggests.")

    return reasons[:5]


def compare_resume_to_job(resume_text: str, job_description_text: str) -> dict:
    resume_explicit_categories = _merge_resume_categories(resume_text, include_inferred_responsibilities=False)
    resume_supported_categories = _merge_resume_categories(resume_text, include_inferred_responsibilities=True)
    job_categories = _extract_known_terms(job_description_text, include_synonyms=True)

    job_title = _extract_title(job_description_text)
    company_name = _extract_company(job_description_text)
    resume_years = _calculate_total_experience_years(resume_text)
    title_overlap = sorted(_extract_title_tokens(job_title).intersection(_extract_title_tokens(resume_text)))
    industry_overlap = sorted(_extract_industry_terms(resume_text).intersection(_extract_industry_terms(job_description_text)))

    competency_scores, direct_match_score, transferable_match_score, overall_fit_score, interview_potential_score = _build_competency_scores(
        resume_explicit_categories,
        resume_supported_categories,
        job_categories,
        resume_years,
        title_overlap,
        industry_overlap,
    )
    role_family = _infer_role_family(job_categories)
    if role_family == "SaaS Customer Success / Account Management":
        transfer_relevance_terms = {
            "Stakeholder Management",
            "Stakeholder Communication",
            "Client Communication",
            "Cross-Functional Collaboration",
            "Application Support",
            "Business Analysis",
            "Issue Resolution",
            "User Training",
            "Relationship Management",
            "Process Improvement",
        }
        transfer_overlap = len(set(_flatten_categories(resume_supported_categories)).intersection(transfer_relevance_terms))
        transfer_bonus = min(10, transfer_overlap * 2)
        transferable_match_score = min(100, transferable_match_score + transfer_bonus)
        overall_fit_score = min(100, overall_fit_score + round(transfer_bonus * 0.6))
        interview_potential_score = min(100, interview_potential_score + round(transfer_bonus * 0.8))

    matching_keywords = _flatten_categories(
        {key: [term for term in job_categories.get(key, []) if term in resume_supported_categories.get(key, [])] for key in job_categories}
    )
    missing_keywords = _flatten_categories(
        {key: [term for term in job_categories.get(key, []) if term not in resume_supported_categories.get(key, [])] for key in job_categories}
    )[:12]

    matching_skills = _dedupe_keep_order(
        [term for term in _flatten_categories(resume_supported_categories) if term in _flatten_categories(job_categories)]
    )

    gaps = []
    for item in competency_scores:
        if item["score"] < 55:
            gaps.append(
                f"{item['competency']} is lighter than the role expects; the job emphasizes {', '.join(item['job_expectations'][:3])}."
            )

    strengths = []
    for item in competency_scores:
        if item["score"] >= 65 and item["matched"]:
            strengths.append(
                f"Transferable strength in {item['competency']} supported by {', '.join(item['matched'][:3])}."
            )
    if not strengths:
        strengths.append("The resume shows transferable analytical, stakeholder-facing, and communication strengths that can be positioned more clearly for the role.")

    job_skill_set = set(term.lower() for term in job_categories["skills"] + job_categories["technologies"])
    resume_skill_set = set(term.lower() for term in resume_supported_categories["skills"] + resume_supported_categories["technologies"])
    job_fit = _build_job_fit_analysis(
        resume_text=resume_text,
        job_description_text=job_description_text,
        job_title=job_title,
        resume_skills=resume_skill_set,
        job_skills=job_skill_set,
    )

    role_gap_analysis = _build_role_gap_analysis(
        job_categories=job_categories,
        resume_explicit_categories=resume_explicit_categories,
        resume_supported_categories=resume_supported_categories,
        competency_scores=competency_scores,
    )
    match_reasoning = _build_matching_reasoning(
        resume_text=resume_text,
        job_categories=job_categories,
        resume_supported_categories=resume_supported_categories,
        competency_scores=competency_scores,
    )
    missing_reasoning = _build_missing_reasoning(
        resume_text=resume_text,
        job_categories=job_categories,
        resume_supported_categories=resume_supported_categories,
        competency_scores=competency_scores,
    )
    hiring_manager_view = _build_hiring_manager_view(
        resume_text=resume_text,
        resume_years=resume_years,
        competency_scores=competency_scores,
        direct_match_score=direct_match_score,
        transferable_match_score=transferable_match_score,
        overall_fit_score=overall_fit_score,
    )

    return {
        "job_title": job_title,
        "company_name": company_name,
        "ats_score": overall_fit_score,
        "direct_match_score": direct_match_score,
        "transferable_match_score": transferable_match_score,
        "overall_fit_score": overall_fit_score,
        "overall_interview_potential": interview_potential_score,
        "role_family": role_family,
        "job_fit": job_fit,
        "matching_skills": matching_skills[:15],
        "missing_keywords": missing_keywords,
        "gaps": gaps,
        "role_specific_strengths": strengths,
        "resume_skills": _dedupe_keep_order(resume_explicit_categories["skills"] + resume_explicit_categories["technologies"]),
        "job_skills": _dedupe_keep_order(job_categories["skills"] + job_categories["technologies"]),
        "matching_keywords": matching_keywords[:15],
        "resume_explicit_keyword_categories": resume_explicit_categories,
        "resume_keyword_categories": resume_explicit_categories,
        "resume_supported_keyword_categories": resume_supported_categories,
        "job_keyword_categories": job_categories,
        "ats_breakdown": {"competencies": competency_scores},
        "competency_scores": competency_scores,
        "match_reasoning": match_reasoning,
        "missing_reasoning": missing_reasoning,
        "years_of_experience": resume_years,
        "role_gap_analysis": role_gap_analysis,
        "hiring_manager_view": hiring_manager_view,
    }
