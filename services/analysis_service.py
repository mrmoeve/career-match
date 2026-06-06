import re
from datetime import datetime

from services.role_profile_service import build_active_role_profile


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
        "strategic sourcing", "procurement analytics", "vendor negotiation", "supplier negotiation",
        "spend analysis", "forecast modeling", "stakeholder partnership", "renewal management",
        "g&a category management", "systems improvement", "process improvement", "automation",
        "procurement", "category management",
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
        "training", "onboarding", "application support", "strategic sourcing", "vendor negotiation",
        "supplier negotiation", "spend analysis", "forecast modeling", "stakeholder partnership",
        "renewal management", "g&a category management", "automation", "procurement analytics",
        "procurement", "category management", "systems improvement",
    ],
    "industry_terms": [
        "saas", "financial services", "capital markets", "asset management", "wealth management",
        "investment banking", "customer success", "operations", "trade support", "production support",
        "application support", "portfolio", "treasury", "compliance", "risk", "reconciliation",
        "account management", "renewals", "procurement", "strategic sourcing", "vendor negotiation",
        "spend analysis", "category management",
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
        (r"\bstrategic sourcing\b|\bsourcing strategy\b", "Strategic Sourcing"),
        (r"\bprocurement analytics\b", "Procurement Analytics"),
        (r"\bvendor negotiation\b|\bsupplier negotiation\b|\bcontract negotiation\b", "Vendor Negotiation"),
        (r"\bspend analysis\b|\bcost analysis\b", "Spend Analysis"),
        (r"\bforecast modeling\b|\bforecast model\b", "Forecast Modeling"),
        (r"\bstakeholder partnership\b", "Stakeholder Partnership"),
        (r"\brenewal management\b|\bcontract renewals?\b", "Renewal Management"),
        (r"\bg&a\b|\bgeneral and administrative\b|\bg&a category management\b", "G&A Category Management"),
        (r"\bautomation\b|\bai\b|\bmachine learning\b", "AI / Automation in Procurement"),
        (r"\bsystems?\b|\bworkflow\b|\bprocess improvement\b", "Systems / Process Improvement"),
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
        (r"\bstrategic sourcing\b|\bsourcing strategy\b", "Strategic Sourcing"),
        (r"\bvendor negotiation\b|\bsupplier negotiation\b|\bcontract negotiation\b", "Vendor Negotiation"),
        (r"\bspend analysis\b|\bcost analysis\b", "Spend Analysis"),
        (r"\bforecast modeling\b|\bforecast model\b", "Forecast Modeling"),
        (r"\brenewal management\b|\bcontract renewals?\b", "Renewal Management"),
        (r"\bautomation\b|\bai\b|\bmachine learning\b", "AI / Automation in Procurement"),
        (r"\bprocurement\b|\bcategory management\b|\bg&a\b", "G&A Category Management"),
    ],
    "industry_terms": [
        (r"\bcustomer success\b", "Customer Success"),
        (r"\baccount management\b|\baccount managers?\b", "Account Management"),
        (r"\brenewals?\b", "Renewals"),
        (r"\bprocurement\b|\bstrategic sourcing\b", "Procurement"),
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


def _evidence_level_from_scores(direct_score: int, transferable_score: int, matched_terms: list[str]) -> str:
    if direct_score >= 75 and matched_terms:
        return "Strong Evidence"
    if direct_score >= 45 and matched_terms:
        return "Moderate Evidence"
    if transferable_score >= 45 and matched_terms:
        return "Transferable Evidence"
    if matched_terms:
        return "Weak Evidence"
    return "Unsupported"


def _confidence_from_evidence_level(level: str) -> int:
    return {
        "Strong Evidence": 92,
        "Moderate Evidence": 78,
        "Transferable Evidence": 64,
        "Weak Evidence": 42,
        "Unsupported": 18,
    }.get(level, 25)


def _impact_level(score: int) -> str:
    if score >= 75:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"


def _summarize_evidence_lines(lines: list[str], matched_terms: list[str] | None = None) -> list[str]:
    seen: set[str] = set()
    summaries: list[str] = []
    for line in lines or []:
        lowered = line.lower()
        summary = ""
        if any(term in lowered for term in ["vendor", "supplier", "negotiat", "contract"]):
            summary = "Vendor or supplier coordination and negotiation"
        elif any(term in lowered for term in ["stakeholder", "leadership", "client-facing", "client facing", "business leaders"]):
            summary = "Stakeholder-facing coordination and partnership"
        elif any(term in lowered for term in ["budget", "forecast", "analysis", "dashboard", "reporting", "metrics", "tracking"]):
            summary = "Data analysis, reporting, or tracking ownership"
        elif any(term in lowered for term in ["training", "onboarding", "support", "issue", "resolve"]):
            summary = "Training, support, or issue-resolution experience"
        elif any(term in lowered for term in ["process", "system", "workflow", "automation"]):
            summary = "Process, systems, or workflow improvement"
        if not summary and matched_terms:
            summary = ", ".join(matched_terms[:3])
        if summary and summary.lower() not in seen:
            summaries.append(summary)
            seen.add(summary.lower())
        if len(summaries) >= 3:
            break
    if not summaries and matched_terms:
        return matched_terms[:3]
    return summaries


def _confidence_label(item: dict) -> str:
    evidence_level = item.get("evidence_level", "Unsupported")
    direct_score = int(item.get("direct_score", 0) or 0)
    transferable_score = int(item.get("transferable_score", 0) or 0)
    if evidence_level in {"Strong Evidence", "Moderate Evidence"} and direct_score >= 45:
        return "High"
    if evidence_level == "Transferable Evidence" or transferable_score >= 45:
        return "Medium"
    return "Low"


def _job_description_sentences(job_description_text: str) -> list[str]:
    raw_parts = re.split(r"[\n\r]+|(?<=[.!?])\s+", job_description_text or "")
    sentences: list[str] = []
    for part in raw_parts:
        cleaned = re.sub(r"\s+", " ", part).strip(" -\t")
        if cleaned and len(cleaned) >= 18:
            sentences.append(cleaned)
    return sentences


def _job_requirement_evidence(job_description_text: str, term: str, fallback_terms: list[str] | None = None) -> dict:
    search_terms = [term] + [item for item in (fallback_terms or []) if item and item.lower() != term.lower()]
    sentences = _job_description_sentences(job_description_text)
    best_sentence = ""
    best_keyword = term
    best_score = 0
    for sentence in sentences:
        lowered = sentence.lower()
        for candidate in search_terms:
            candidate_lower = candidate.lower()
            if candidate_lower and candidate_lower in lowered:
                score = 70
                if re.search(r"\b(required|must have|at least|expertise|demonstrated|own|lead|hands-on)\b", lowered):
                    score += 20
                elif re.search(r"\b(preferred|nice to have|ideal|plus|strong)\b", lowered):
                    score += 10
                if candidate_lower == term.lower():
                    score += 5
                if score > best_score:
                    best_score = min(99, score)
                    best_sentence = sentence
                    best_keyword = candidate
    if not best_sentence and sentences:
        for sentence in sentences:
            lowered = sentence.lower()
            if any(token in lowered for token in term.lower().split() if len(token) > 3):
                best_sentence = sentence
                best_keyword = term
                best_score = 55
                break
    return {
        "job_description_sentence": best_sentence,
        "extracted_keyword": best_keyword,
        "confidence_score": best_score,
    }


def _priority_for_missing_term(
    term: str,
    competency_weight: int,
    job_fit: dict,
    jd_evidence: dict,
) -> str:
    lowered = term.lower()
    required = {str(item).lower() for item in job_fit.get("required_skills", []) + job_fit.get("required_certifications", [])}
    preferred = {str(item).lower() for item in job_fit.get("preferred_skills", [])}
    sentence = (jd_evidence.get("job_description_sentence", "") or "").lower()
    if lowered in required or re.search(r"\b(required|must have|at least|expertise|demonstrated)\b", sentence):
        return "Critical"
    if lowered in preferred or competency_weight >= 14 or re.search(r"\b(preferred|plus|ideal|strong)\b", sentence):
        return "Important"
    return "Nice-to-have"


def _build_missing_keywords_by_priority(
    job_description_text: str,
    competency_scores: list[dict],
    job_fit: dict,
) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {"Critical": [], "Important": [], "Nice-to-have": []}
    seen: set[str] = set()
    for item in competency_scores:
        competency = item.get("competency", "")
        for term in item.get("missing_terms", []) or []:
            key = term.lower()
            if key in seen:
                continue
            jd_evidence = _job_requirement_evidence(job_description_text, term, item.get("job_expectations", []))
            priority = _priority_for_missing_term(term, int(item.get("weight", 0) or 0), job_fit, jd_evidence)
            grouped[priority].append(
                {
                    "term": term,
                    "competency": competency,
                    "priority": priority,
                    "job_description_sentence": jd_evidence.get("job_description_sentence", ""),
                    "extracted_keyword": jd_evidence.get("extracted_keyword", term),
                    "confidence_score": int(jd_evidence.get("confidence_score", 0) or 0),
                }
            )
            seen.add(key)
    for priority in grouped:
        grouped[priority].sort(key=lambda payload: (-payload.get("confidence_score", 0), payload.get("term", "")))
    return grouped


def _build_recruiter_confidence_by_competency(competency_scores: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for item in competency_scores:
        rows.append(
            {
                "competency": item.get("competency", ""),
                "direct_score": item.get("direct_score", 0),
                "transferable_score": item.get("transferable_score", 0),
                "overall_score": item.get("score", 0),
                "evidence": item.get("matched", []),
                "evidence_level": item.get("evidence_level", "Unsupported"),
                "confidence_level": _confidence_label(item),
                "evidence_summary": _summarize_evidence_lines(item.get("resume_evidence_lines", []), item.get("matched", [])),
                "matched_resume_evidence": item.get("resume_evidence_lines", []),
            }
        )
    return rows


def _build_compensation_level_alignment(
    job_title: str,
    job_fit: dict,
    resume_years: int,
    direct_match_score: int,
    transferable_match_score: int,
    title_overlap: list[str],
    industry_overlap: list[str],
) -> dict:
    required_years = int(job_fit.get("years_experience_required", 0) or 0)
    title_score = 18 if title_overlap else 9
    industry_score = 15 if industry_overlap else 8
    experience_score = 25
    if required_years:
        if resume_years >= required_years + 2:
            experience_score = 25
        elif resume_years >= required_years:
            experience_score = 22
        elif resume_years >= max(required_years - 1, 1):
            experience_score = 16
        else:
            experience_score = 8
    alignment_score = round(
        experience_score * 0.35
        + title_score * 0.20
        + industry_score * 0.15
        + direct_match_score * 0.15
        + transferable_match_score * 0.15
    )
    if alignment_score >= 72:
        label = "Strong Alignment"
    elif alignment_score >= 58:
        label = "Moderate Alignment"
    elif alignment_score >= 42:
        label = "Stretch"
    else:
        label = "Overreach"
    reasoning = []
    if required_years:
        reasoning.append(f"Resume suggests about {resume_years} years versus roughly {required_years} years requested.")
    else:
        reasoning.append(f"Resume suggests about {resume_years} years, and the role does not clearly state a years requirement.")
    reasoning.append("Title overlap is " + ("present." if title_overlap else "limited."))
    reasoning.append("Industry overlap is " + ("present." if industry_overlap else "limited."))
    reasoning.append(f"Direct competency match is {direct_match_score}/100 and transferable match is {transferable_match_score}/100.")
    return {
        "label": label,
        "alignment_score": alignment_score,
        "reasoning": reasoning,
        "job_title": job_title,
    }


def _build_typical_applicant_comparison(competency_scores: list[dict]) -> list[dict]:
    comparisons: list[dict] = []
    for item in competency_scores:
        overall = int(item.get("score", 0) or 0)
        direct = int(item.get("direct_score", 0) or 0)
        confidence = _confidence_label(item)
        if confidence == "Low" and overall < 35:
            relative = "Unknown"
        elif overall >= 78 or (direct >= 60 and confidence == "High"):
            relative = "Stronger than typical"
        elif overall >= 55 or confidence in {"High", "Medium"}:
            relative = "Competitive"
        else:
            relative = "Weaker than typical"
        comparisons.append(
            {
                "competency": item.get("competency", ""),
                "relative_strength": relative,
                "confidence_level": confidence,
                "evidence": item.get("matched", []),
            }
        )
    return comparisons


def _build_score_consistency(
    fit_score: int,
    interview_potential: int,
    direct_match_score: int,
    transferable_match_score: int,
    keyword_coverage_score: int,
) -> dict:
    warnings: list[str] = []
    if keyword_coverage_score >= fit_score + 12 and direct_match_score < 60:
        warnings.append("Keyword coverage is strong, but overall fit is limited by missing direct experience.")
    if interview_potential >= fit_score + 15 and direct_match_score < 45:
        warnings.append("Interview potential is being supported mainly by transferable strengths rather than direct title alignment.")
    if direct_match_score < 35 and transferable_match_score >= 65:
        warnings.append("The resume looks more transferable than directly aligned, so recruiter interest will depend on positioning.")
    return {
        "keyword_coverage_score": keyword_coverage_score,
        "warning": " ".join(warnings),
        "is_consistent": not warnings,
        "explanation": "Keyword coverage is not the same as overall job fit.",
    }


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
                "evidence_level": item.get("evidence_level", "Unsupported"),
                "confidence_level": item.get("confidence_level", "Unsupported"),
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
                "evidence_level": item.get("evidence_level", "Unsupported"),
                "why_it_is_missing": (
                    f"The job calls for {', '.join(missing_terms[:3])}, but those phrases do not appear clearly in the uploaded resume."
                ),
                "closest_resume_evidence": nearby_evidence,
            }
        )
    return missing_items


def _build_recruiter_quality_intelligence(
    resume_text: str,
    competency_scores: list[dict],
    match_reasoning: list[dict],
    missing_reasoning: list[dict],
) -> list[dict]:
    match_by_name = {item["competency"]: item for item in match_reasoning}
    missing_by_name = {item["competency"]: item for item in missing_reasoning}
    intelligence: list[dict] = []
    for item in competency_scores:
        competency = item["competency"]
        match_item = match_by_name.get(competency, {})
        missing_item = missing_by_name.get(competency, {})
        evidence_lines = match_item.get("resume_evidence_lines", [])
        matched_terms = item.get("matched", [])[:3]
        if matched_terms:
            repositioning = (
                f"Use job-aligned wording that highlights {', '.join(term.lower() for term in matched_terms)} "
                "while keeping the original scope and evidence intact."
            )
        else:
            repositioning = "Rephrase supported experience using the job's language while staying grounded in the resume."
        intelligence.append(
            {
                "competency": competency,
                "direct_match_score": item.get("direct_score", 0),
                "transferable_match_score": item.get("transferable_score", 0),
                "confidence_level": item.get("confidence_level", "Unsupported"),
                "exact_resume_evidence": evidence_lines,
                "why_this_evidence_matters": match_item.get("why_it_matched", ""),
                "where_resume_falls_short": missing_item.get("why_it_is_missing", ""),
                "repositioning": repositioning,
                "interview_talking_point": (
                    f"In my prior work, I demonstrated {', '.join(item.get('matched', [])[:3]).lower()} "
                    "through hands-on coordination, communication, and execution in complex environments."
                    if item.get("matched")
                    else "I would explain the closest adjacent experience and how it maps into the target role."
                ),
            }
        )
    return intelligence


def _build_score_breakdown(competency_scores: list[dict], overall_fit_score: int) -> list[dict]:
    rows: list[dict] = []
    total_weight = sum(item.get("weight", 0) for item in competency_scores) or 1
    for item in competency_scores:
        contribution = round((item.get("score", 0) * item.get("weight", 0)) / total_weight, 1)
        rows.append(
            {
                "competency": item.get("competency", ""),
                "weight": item.get("weight", 0),
                "raw_score": item.get("score", 0),
                "direct_score": item.get("direct_score", 0),
                "transferable_score": item.get("transferable_score", 0),
                "contribution": contribution,
                "evidence_level": item.get("evidence_level", "Unsupported"),
                "confidence_level": item.get("confidence_level", "Unsupported"),
                "confidence_score": item.get("confidence_score", 0),
                "matched_resume_evidence": item.get("resume_evidence_lines", []),
                "matched_terms": item.get("matched", []),
                "missing_requirement": ", ".join(item.get("job_expectations", [])[:3]),
            }
        )
    return rows


def _build_reasons_to_interview(competency_scores: list[dict]) -> list[dict]:
    reasons: list[dict] = []
    sorted_items = sorted(
        [item for item in competency_scores if item.get("matched")],
        key=lambda item: (item.get("score", 0), item.get("direct_score", 0), item.get("transferable_score", 0)),
        reverse=True,
    )
    for item in sorted_items[:5]:
        if item.get("direct_score", 0) >= 60:
            strength_level = "Strong"
        elif item.get("direct_score", 0) >= 35:
            strength_level = "Moderate"
        else:
            strength_level = "Transferable"
        reasons.append(
            {
                "reason_title": item.get("competency", ""),
                "reason_bullet": (
                    f"{item.get('competency', '')} is supported by resume-backed evidence such as "
                    f"{'; '.join((item.get('resume_evidence_lines', []) or [])[:1]) or ', '.join(item.get('matched', [])[:3])}."
                ),
                "supporting_resume_evidence": item.get("resume_evidence_lines", []),
                "relevant_job_requirement": ", ".join(item.get("job_expectations", [])[:3]),
                "strength_level": strength_level,
            }
        )
    return reasons


def _build_reasons_to_reject(competency_scores: list[dict]) -> list[dict]:
    risks: list[dict] = []
    sorted_items = sorted(
        competency_scores,
        key=lambda item: (100 - item.get("score", 0), 100 - item.get("direct_score", 0), item.get("weight", 0)),
        reverse=True,
    )
    for item in sorted_items[:6]:
        missing_terms = item.get("missing_terms", []) or item.get("job_expectations", [])
        if not missing_terms:
            continue
        fixable = item.get("evidence_level") in {"Moderate Evidence", "Transferable Evidence", "Weak Evidence"}
        risks.append(
            {
                "gap_name": item.get("competency", ""),
                "risk_bullet": f"{item.get('competency', '')} is not yet clearly evidenced at the level the job appears to expect.",
                "why_it_matters": f"This competency affects the recruiter read because the role emphasizes {', '.join(missing_terms[:3])}.",
                "missing_job_requirement": ", ".join(missing_terms[:3]),
                "fixability": "Resume wording can help" if fixable else "Truly missing experience",
                "impact_level": _impact_level(item.get("weight", 0) * max(1, 100 - item.get("score", 0)) // 100),
            }
        )
    return risks


def _build_resume_roi_fixes(competency_scores: list[dict]) -> list[dict]:
    fixes: list[dict] = []
    for item in sorted(competency_scores, key=lambda row: (row.get("weight", 0), 100 - row.get("score", 0)), reverse=True):
        missing_terms = item.get("missing_terms", []) or item.get("job_expectations", [])
        if not missing_terms:
            continue
        lead_gap = missing_terms[0]
        evidence_level = item.get("evidence_level", "Unsupported")
        if evidence_level in {"Strong Evidence", "Moderate Evidence"}:
            safely_supported = True
            action = "Move higher and quantify."
        elif evidence_level == "Transferable Evidence":
            safely_supported = True
            action = "Reframe carefully using adjacent resume evidence."
        else:
            safely_supported = False
            action = "Do not claim unless true."
        estimated_impact = max(2, round(item.get("weight", 0) * (100 - item.get("score", 0)) / 100))
        fixes.append(
            {
                "gap_or_keyword": lead_gap,
                "estimated_score_impact": estimated_impact,
                "expected_impact": _impact_level(estimated_impact * 10),
                "safely_supported": safely_supported,
                "recommended_action": action,
                "why_it_matters": f"The role explicitly leans on {lead_gap.lower()} within {item.get('competency', '').lower()}.",
                "supporting_resume_evidence": item.get("resume_evidence_lines", []),
                "evidence_level": evidence_level,
            }
        )
    deduped: list[dict] = []
    seen: set[str] = set()
    for item in fixes:
        key = item["gap_or_keyword"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:8]


def _build_recruiter_style_summary(
    reasons_to_interview: list[dict],
    reasons_to_reject: list[dict],
    roi_fixes: list[dict],
) -> dict:
    best_case = (
        f"The candidate shows the clearest upside in {reasons_to_interview[0]['reason_title'].lower()}."
        if reasons_to_interview else
        "The candidate has some transferable upside but needs clearer evidence positioning."
    )
    worst_case = (
        f"A recruiter may pause on {reasons_to_reject[0]['gap_name'].lower()} because the job explicitly requires {reasons_to_reject[0]['missing_job_requirement'].lower()}."
        if reasons_to_reject else
        "There are no major reject signals beyond normal competitive filtering."
    )
    most_important_fix = (
        f"{roi_fixes[0]['gap_or_keyword']}: {roi_fixes[0]['recommended_action']}"
        if roi_fixes else
        "No single high-impact fix identified."
    )
    return {
        "best_case_recruiter_read": best_case,
        "worst_case_recruiter_read": worst_case,
        "most_important_fix_before_applying": most_important_fix,
    }


def _build_score_explanation(
    resume_years: int,
    job_fit: dict,
    keyword_coverage_score: int,
    competency_scores: list[dict],
    industry_overlap: list[str],
) -> list[dict]:
    required_years = int(job_fit.get("years_experience_required", 0) or 0)
    experience_score = 75 if resume_years else 0
    if required_years:
        if resume_years >= required_years:
            experience_score = 88
        elif resume_years >= max(required_years - 1, 1):
            experience_score = 68
        else:
            experience_score = 42
    skills_score = keyword_coverage_score
    industry_score = 82 if industry_overlap else 45
    competencies_score = round(sum(item.get("score", 0) for item in competency_scores) / max(len(competency_scores), 1)) if competency_scores else 0
    evidence_strength_score = round(sum(item.get("confidence_score", 0) for item in competency_scores) / max(len(competency_scores), 1)) if competency_scores else 0
    config = [
        ("Experience", 25, experience_score),
        ("Skills", 30, skills_score),
        ("Industry", 15, industry_score),
        ("Competencies", 20, competencies_score),
        ("Evidence Strength", 10, evidence_strength_score),
    ]
    rows: list[dict] = []
    for label, weight, raw_score in config:
        rows.append(
            {
                "category": label,
                "weight": weight,
                "raw_score": raw_score,
                "contribution": round(raw_score * weight / 100, 1),
            }
        )
    return rows


def _benchmark_target_for_competency(item: dict) -> int:
    weight = int(item.get("weight", 0) or 0)
    if weight >= 18:
        return 82
    if weight >= 16:
        return 78
    if weight >= 14:
        return 74
    if weight >= 12:
        return 68
    return 62


def _build_recruiter_benchmarking(competency_scores: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for item in competency_scores:
        target = _benchmark_target_for_competency(item)
        score = int(item.get("score", 0) or 0)
        if score >= target + 8:
            status = "Above"
        elif score >= target - 8:
            status = "Competitive"
        else:
            status = "Below"
        rows.append(
            {
                "competency": item.get("competency", ""),
                "you_score": score,
                "target_score": target,
                "status": status,
            }
        )
    return rows


def _build_roi_projection(fit_score: int, roi_fixes: list[dict]) -> dict:
    top_fixes = roi_fixes[:3]
    projected_gain = sum(int(item.get("estimated_score_impact", 0) or 0) for item in top_fixes)
    return {
        "current_score": fit_score,
        "potential_score": min(100, fit_score + projected_gain),
        "top_fixes": top_fixes,
    }


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
    active_role_profile: dict,
) -> tuple[list[dict], int, int, int, int]:
    explicit_terms = set(term.lower() for term in _flatten_categories(resume_explicit_categories))
    supported_terms = set(term.lower() for term in _flatten_categories(resume_supported_categories))
    job_terms_flat = set(term.lower() for term in _flatten_categories(job_categories))

    competency_rows: list[dict] = []
    direct_total = 0.0
    transferable_total = 0.0
    weight_total = 0.0

    for config in active_role_profile.get("competencies", []):
        name = config["label"]
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

        title_bonus = 6 if title_overlap and any(token in name.lower() for token in {"stakeholder", "account", "procurement", "sourcing"}) else 0
        industry_bonus = 6 if industry_overlap and any(token in name.lower() for token in {"risk", "account", "procurement", "spend"}) else 0
        experience_bonus = 8 if resume_years >= 10 else 5 if resume_years >= 5 else 2 if resume_years >= 2 else 0
        overall_score = max(0, min(100, round(direct_score * 0.45 + transferable_score * 0.40 + title_bonus + industry_bonus + experience_bonus)))
        evidence_level = _evidence_level_from_scores(
            direct_score,
            transferable_score,
            _dedupe_keep_order(exact_direct_hits + adjacent_direct_hits + transfer_hits),
        )
        confidence_score = _confidence_from_evidence_level(evidence_level)
        confidence_level = _confidence_label(
            {
                "evidence_level": evidence_level,
                "direct_score": direct_score,
                "transferable_score": transferable_score,
            }
        )

        competency_rows.append(
            {
                "competency": name,
                "weight": config["weight"],
                "direct_score": direct_score,
                "transferable_score": transferable_score,
                "score": overall_score,
                "matched": _dedupe_keep_order(exact_direct_hits + adjacent_direct_hits + transfer_hits),
                "job_expectations": job_terms,
                "missing_terms": [term for term in job_terms if term.lower() not in supported_terms],
                "evidence_level": evidence_level,
                "confidence_level": confidence_level,
                "confidence_score": confidence_score,
                "resume_evidence_lines": [],
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


def _build_role_gap_analysis(
    job_categories: dict[str, list[str]],
    resume_explicit_categories: dict[str, list[str]],
    resume_supported_categories: dict[str, list[str]],
    competency_scores: list[dict],
    active_role_profile: dict,
) -> dict:
    explicit_terms = set(_flatten_categories(resume_explicit_categories))
    supported_terms = set(_flatten_categories(resume_supported_categories))
    job_terms = _flatten_categories(job_categories)

    missing_experience = [term for term in job_terms if term not in supported_terms][:8]
    transferable_experience = [term for term in supported_terms if term in _flatten_categories(job_categories)][:8]
    missing_competencies = [item["competency"] for item in competency_scores if item["direct_score"] < 45][:6]
    reposition_resume = []
    mapping_suggestions = [
        ("Stakeholder Management", "Move stakeholder-facing examples higher and connect them to the role's partnership requirements."),
        ("Stakeholder Partnership", "Move stakeholder-facing examples higher and connect them to the role's partnership requirements."),
        ("Client Communication", "Rewrite communication bullets so they reflect the audience, decisions, and outcomes more clearly."),
        ("Application Support", "Frame operational or systems support as process reliability and issue-resolution strength."),
        ("Business Analysis", "Position analytical problem-solving as evidence of structured decision support."),
        ("Cross-Functional Collaboration", "Emphasize how cross-functional work helped move business priorities forward."),
        ("Strategic Sourcing", "Highlight sourcing, negotiation, or vendor-facing work using procurement language where evidence supports it."),
        ("Procurement Analytics", "Make cost, spend, or analytical decision-support work more visible near the top of the resume."),
    ]
    for term, suggestion in mapping_suggestions:
        if term in supported_terms:
            reposition_resume.append(suggestion)

    return {
        "missing_experience": missing_experience,
        "transferable_experience": transferable_experience,
        "missing_competencies": missing_competencies,
        "resume_repositioning": _dedupe_keep_order(reposition_resume)[:5],
        "active_role_profile_name": active_role_profile.get("headline", active_role_profile.get("family", "General Professional Role")),
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
        reasons.append(f"Transferable match is strong at {transferable_match_score}%, suggesting the candidate could ramp into the role even without a direct title match.")
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
    active_role_profile = build_active_role_profile(job_title, job_description_text)
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
        active_role_profile,
    )
    role_family = active_role_profile.get("family", "General Professional Role")
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
    unique_job_keywords = _dedupe_keep_order(_flatten_categories(job_categories))
    keyword_coverage_score = round((len({item.lower() for item in matching_keywords}) / max(len(unique_job_keywords), 1)) * 100)

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
        active_role_profile=active_role_profile,
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
    match_reasoning_by_name = {item["competency"]: item for item in match_reasoning}
    missing_reasoning_by_name = {item["competency"]: item for item in missing_reasoning}
    enriched_competency_scores: list[dict] = []
    for item in competency_scores:
        competency = item.get("competency", "")
        enriched_item = dict(item)
        enriched_item["resume_evidence_lines"] = match_reasoning_by_name.get(competency, {}).get("resume_evidence_lines", [])
        enriched_item["missing_terms"] = missing_reasoning_by_name.get(competency, {}).get("missing_terms", item.get("missing_terms", []))
        enriched_competency_scores.append(enriched_item)
    competency_scores = enriched_competency_scores

    score_breakdown = _build_score_breakdown(competency_scores, overall_fit_score)
    reasons_to_interview = _build_reasons_to_interview(competency_scores)
    reasons_to_reject = _build_reasons_to_reject(competency_scores)
    resume_roi_fixes = _build_resume_roi_fixes(competency_scores)
    missing_keywords_by_priority = _build_missing_keywords_by_priority(
        job_description_text=job_description_text,
        competency_scores=competency_scores,
        job_fit=job_fit,
    )
    recruiter_confidence_by_competency = _build_recruiter_confidence_by_competency(competency_scores)
    compensation_level_alignment = _build_compensation_level_alignment(
        job_title=job_title,
        job_fit=job_fit,
        resume_years=resume_years,
        direct_match_score=direct_match_score,
        transferable_match_score=transferable_match_score,
        title_overlap=title_overlap,
        industry_overlap=industry_overlap,
    )
    compared_with_typical_applicants = _build_typical_applicant_comparison(competency_scores)
    recruiter_benchmarking = _build_recruiter_benchmarking(competency_scores)
    score_explanation = _build_score_explanation(
        resume_years=resume_years,
        job_fit=job_fit,
        keyword_coverage_score=keyword_coverage_score,
        competency_scores=competency_scores,
        industry_overlap=industry_overlap,
    )
    roi_projection = _build_roi_projection(overall_fit_score, resume_roi_fixes)
    score_consistency = _build_score_consistency(
        fit_score=overall_fit_score,
        interview_potential=interview_potential_score,
        direct_match_score=direct_match_score,
        transferable_match_score=transferable_match_score,
        keyword_coverage_score=keyword_coverage_score,
    )
    recruiter_style_summary = _build_recruiter_style_summary(
        reasons_to_interview,
        reasons_to_reject,
        resume_roi_fixes,
    )
    recruiter_quality_intelligence = _build_recruiter_quality_intelligence(
        resume_text=resume_text,
        competency_scores=competency_scores,
        match_reasoning=match_reasoning,
        missing_reasoning=missing_reasoning,
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
        "active_role_profile": active_role_profile,
        "role_profile_fingerprint": active_role_profile.get("fingerprint", ""),
        "job_fit": job_fit,
        "matching_skills": matching_skills[:15],
        "missing_keywords": missing_keywords,
        "gaps": gaps,
        "role_specific_strengths": strengths,
        "keyword_coverage_score": keyword_coverage_score,
        "keyword_coverage_label": "Keyword Coverage Before",
        "resume_skills": _dedupe_keep_order(resume_explicit_categories["skills"] + resume_explicit_categories["technologies"]),
        "job_skills": _dedupe_keep_order(job_categories["skills"] + job_categories["technologies"]),
        "matching_keywords": matching_keywords[:15],
        "resume_explicit_keyword_categories": resume_explicit_categories,
        "resume_keyword_categories": resume_explicit_categories,
        "resume_supported_keyword_categories": resume_supported_categories,
        "job_keyword_categories": job_categories,
        "ats_breakdown": {"competencies": competency_scores},
        "competency_scores": competency_scores,
        "score_breakdown": score_breakdown,
        "match_reasoning": match_reasoning,
        "missing_reasoning": missing_reasoning,
        "reasons_to_interview": reasons_to_interview,
        "reasons_to_reject": reasons_to_reject,
        "resume_roi_fixes": resume_roi_fixes,
        "missing_keywords_by_priority": missing_keywords_by_priority,
        "recruiter_confidence_by_competency": recruiter_confidence_by_competency,
        "compensation_level_alignment": compensation_level_alignment,
        "compared_with_typical_applicants": compared_with_typical_applicants,
        "recruiter_benchmarking": recruiter_benchmarking,
        "score_explanation": score_explanation,
        "roi_projection": roi_projection,
        "score_consistency": score_consistency,
        "recruiter_style_summary": recruiter_style_summary,
        "recruiter_quality_intelligence": recruiter_quality_intelligence,
        "years_of_experience": resume_years,
        "role_gap_analysis": role_gap_analysis,
        "hiring_manager_view": hiring_manager_view,
    }
