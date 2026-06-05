import os
import re


RESOURCE_CATALOG = [
    {
        "category": "sql",
        "title": "SQL Foundations for Analysts",
        "provider": "DataCamp",
        "skill": "SQL",
        "description": "Build practical SQL querying skills for reporting, analysis, and business-facing work.",
        "gap_terms": ["sql"],
        "url_env": "AFFILIATE_SQL_URL",
    },
    {
        "category": "excel",
        "title": "Advanced Excel for Business",
        "provider": "Coursera",
        "skill": "Excel",
        "description": "Sharpen advanced spreadsheet modeling, formulas, and reporting workflows.",
        "gap_terms": ["excel", "spreadsheet", "advanced excel"],
        "url_env": "AFFILIATE_EXCEL_URL",
    },
    {
        "category": "salesforce",
        "title": "Salesforce Admin and CRM Fundamentals",
        "provider": "Trailhead",
        "skill": "Salesforce / CRM",
        "description": "Learn Salesforce fundamentals, CRM workflows, and customer lifecycle operations.",
        "gap_terms": ["salesforce", "crm", "hubspot"],
        "url_env": "AFFILIATE_SALESFORCE_URL",
    },
    {
        "category": "customer_success_foundations",
        "title": "Customer Success Foundations",
        "provider": "SuccessCOACHING",
        "skill": "Customer Success",
        "description": "Understand adoption, retention, renewals, and proactive customer success execution.",
        "gap_terms": ["customer success", "product adoption", "renewal", "gross retention", "onboarding"],
        "url_env": "AFFILIATE_CUSTOMER_SUCCESS_URL",
        "role_families": ["SaaS Customer Success / Account Management"],
    },
    {
        "category": "client_relationship_growth",
        "title": "Account Management and Client Relationships",
        "provider": "LinkedIn Learning",
        "skill": "Account Management",
        "description": "Strengthen client relationship management, expansion conversations, and account ownership.",
        "gap_terms": ["account management", "client relationship", "cross-selling", "upselling"],
        "url_env": "AFFILIATE_ACCOUNT_MANAGEMENT_URL",
        "role_families": ["SaaS Customer Success / Account Management"],
    },
    {
        "category": "stakeholder_partnership",
        "title": "Stakeholder Management and Communication",
        "provider": "Coursera",
        "skill": "Stakeholder Management",
        "description": "Improve communication, alignment, and influence across business and technical stakeholders.",
        "gap_terms": ["stakeholder management", "communication", "executive business reviews", "client communication"],
        "url_env": "AFFILIATE_STAKEHOLDER_MANAGEMENT_URL",
        "role_families": ["SaaS Customer Success / Account Management", "Strategic Sourcing / Procurement", "General Professional Role"],
    },
    {
        "category": "strategic_sourcing",
        "title": "Strategic Sourcing Foundations",
        "provider": "Coursera",
        "skill": "Strategic Sourcing",
        "description": "Build sourcing strategy, category planning, and supplier-evaluation fundamentals.",
        "gap_terms": ["strategic sourcing", "sourcing", "category management", "procurement"],
        "url_env": "AFFILIATE_PROJECT_MANAGEMENT_URL",
        "role_families": ["Strategic Sourcing / Procurement"],
    },
    {
        "category": "vendor_negotiation",
        "title": "Vendor Negotiation for Procurement",
        "provider": "LinkedIn Learning",
        "skill": "Vendor Negotiation",
        "description": "Practice negotiation, supplier conversations, and contract-positioning techniques for procurement roles.",
        "gap_terms": ["vendor negotiation", "supplier negotiation", "contract negotiation", "renewal management"],
        "url_env": "AFFILIATE_PROJECT_MANAGEMENT_URL",
        "role_families": ["Strategic Sourcing / Procurement"],
    },
    {
        "category": "procurement_analytics",
        "title": "Procurement Analytics and Spend Insights",
        "provider": "Coursera",
        "skill": "Procurement Analytics",
        "description": "Strengthen spend analysis, forecasting, and procurement decision-support workflows.",
        "gap_terms": ["procurement analytics", "spend analysis", "forecast modeling", "spend", "cost analysis"],
        "url_env": "AFFILIATE_DATA_ANALYTICS_URL",
        "role_families": ["Strategic Sourcing / Procurement"],
    },
    {
        "category": "procurement_automation",
        "title": "AI and Automation for Procurement Teams",
        "provider": "Udemy",
        "skill": "AI / Automation in Procurement",
        "description": "Explore automation, workflow improvement, and AI-assisted procurement operations.",
        "gap_terms": ["automation", "ai", "machine learning", "systems improvement", "process improvement"],
        "url_env": "AFFILIATE_PYTHON_URL",
        "role_families": ["Strategic Sourcing / Procurement"],
    },
    {
        "category": "project_management",
        "title": "Project Management Certification Prep",
        "provider": "PMI / Udemy",
        "skill": "Project Management",
        "description": "Build delivery planning, execution, and project leadership fundamentals.",
        "gap_terms": ["project management", "pmp", "program management"],
        "url_env": "AFFILIATE_PROJECT_MANAGEMENT_URL",
    },
    {
        "category": "data_analytics",
        "title": "Data Analytics and Dashboard Reporting",
        "provider": "Google / Coursera",
        "skill": "Data Analytics",
        "description": "Cover dashboard reporting, Tableau-style analytics, and business data storytelling.",
        "gap_terms": ["tableau", "dashboard reporting", "data analysis", "analytics", "reporting"],
        "url_env": "AFFILIATE_DATA_ANALYTICS_URL",
    },
    {
        "category": "python",
        "title": "Python for Business and Analytics",
        "provider": "DataCamp",
        "skill": "Python",
        "description": "Learn Python workflows that support automation, reporting, and analysis.",
        "gap_terms": ["python"],
        "url_env": "AFFILIATE_PYTHON_URL",
    },
    {
        "category": "interview_prep",
        "title": "Interview Prep for Career Transitions",
        "provider": "Big Interview",
        "skill": "Interview Prep",
        "description": "Practice stronger answers, story structure, and role-specific interview positioning.",
        "gap_terms": ["interview prep", "interview", "behavioral interview", "technical interview"],
        "url_env": "AFFILIATE_INTERVIEW_PREP_URL",
    },
    {
        "category": "resume_ats",
        "title": "Resume and ATS Optimization",
        "provider": "TopResume",
        "skill": "Resume / ATS",
        "description": "Improve ATS alignment and recruiter readability without overstating experience.",
        "gap_terms": ["resume", "ats", "resume optimization", "missing keywords"],
        "url_env": "AFFILIATE_RESUME_ATS_URL",
        "role_families": ["SaaS Customer Success / Account Management", "Strategic Sourcing / Procurement", "General Professional Role"],
    },
]


def _normalize_phrase(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _role_family(analysis: dict) -> str:
    profile = analysis.get("active_role_profile", {}) or {}
    return str(profile.get("family", analysis.get("role_family", "General Professional Role")))


def _gap_pool(analysis: dict) -> list[str]:
    role_gap = analysis.get("role_gap_analysis", {}) or {}
    job_fit = analysis.get("job_fit", {}) or {}
    competency_scores = analysis.get("competency_scores", []) or []
    values: list[str] = []
    for item in analysis.get("missing_keywords", []):
        values.append(str(item))
    for item in analysis.get("gaps", []):
        values.append(str(item))
    for item in role_gap.get("missing_competencies", []):
        values.append(str(item))
    for item in role_gap.get("missing_experience", []):
        values.append(str(item))
    for item in job_fit.get("missing_required_skills", []):
        values.append(str(item))
    for item in job_fit.get("missing_preferred_skills", []):
        values.append(str(item))
    for competency in competency_scores:
        if competency.get("score", 0) < 55:
            values.append(str(competency.get("competency", "")))
            values.extend(str(item) for item in competency.get("missing", []))
    return [item.strip() for item in values if str(item).strip()]


def _allowed_resource(resource: dict, analysis: dict, normalized_gap_pool: list[str]) -> bool:
    role_family = _role_family(analysis)
    allowed_families = resource.get("role_families") or []
    if allowed_families and role_family not in allowed_families:
        explicit_terms = {_normalize_phrase(item) for item in analysis.get("missing_keywords", []) + analysis.get("job_skills", [])}
        if not any(_normalize_phrase(term) in explicit_terms for term in resource.get("gap_terms", [])):
            return False

    if resource.get("category") in {"customer_success_foundations", "client_relationship_growth"}:
        if role_family != "SaaS Customer Success / Account Management":
            explicit_terms = {_normalize_phrase(item) for item in analysis.get("missing_keywords", [])}
            required_terms = {_normalize_phrase(term) for term in ["customer success", "account management", "client relationship management"]}
            if explicit_terms.isdisjoint(required_terms):
                return False

    if resource.get("category") == "stakeholder_partnership" and role_family == "Strategic Sourcing / Procurement":
        procurement_terms = {"stakeholder partnership", "procurement", "strategic sourcing", "vendor negotiation"}
        if all(term not in normalized_gap_pool for term in procurement_terms):
            return False

    return True


def _term_matches_pool(term: str, normalized_gap_pool: list[str]) -> bool:
    normalized_term = _normalize_phrase(term)
    if not normalized_term:
        return False
    for item in normalized_gap_pool:
        if item == normalized_term:
            return True
        if re.search(rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])", item):
            return True
    return False


def build_learning_recommendations(analysis: dict) -> list[dict]:
    gap_pool = _gap_pool(analysis)
    normalized_gap_pool = [_normalize_phrase(item) for item in gap_pool if _normalize_phrase(item)]
    recommendations: list[dict] = []
    seen: set[str] = set()

    for resource in RESOURCE_CATALOG:
        if not _allowed_resource(resource, analysis, normalized_gap_pool):
            continue
        matched_terms = [term for term in resource["gap_terms"] if _term_matches_pool(term, normalized_gap_pool)]
        if not matched_terms:
            continue
        category = resource["category"]
        if category in seen:
            continue
        seen.add(category)
        affiliate_url = os.getenv(resource["url_env"], "").strip()
        recommendations.append(
            {
                "category": category,
                "title": resource["title"],
                "provider": resource["provider"],
                "skill_addressed": resource["skill"],
                "description": resource["description"],
                "why_recommended": f"Recommended because your assessment shows a gap or weaker alignment around {', '.join(matched_terms[:2])}.",
                "affiliate_url": affiliate_url,
                "button_label": "View Resource" if affiliate_url else "Resource coming soon",
                "available": bool(affiliate_url),
            }
        )
        if len(recommendations) >= 5:
            break

    if not recommendations:
        ats_url = os.getenv("AFFILIATE_RESUME_ATS_URL", "").strip()
        recommendations.append(
            {
                "category": "resume_ats",
                "title": "Resume and ATS Optimization",
                "provider": "TopResume",
                "skill_addressed": "Resume / ATS",
                "description": "Improve ATS alignment and recruiter readability using clearer role-specific language.",
                "why_recommended": "Recommended because polishing positioning and ATS language is the most reliable next step from this assessment.",
                "affiliate_url": ats_url,
                "button_label": "View Resource" if ats_url else "Resource coming soon",
                "available": bool(ats_url),
            }
        )

    return recommendations[:5]
