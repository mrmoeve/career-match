import os


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
        "category": "customer_success",
        "title": "Customer Success Foundations",
        "provider": "SuccessCOACHING",
        "skill": "Customer Success",
        "description": "Understand adoption, retention, renewals, and proactive customer success execution.",
        "gap_terms": ["customer success", "product adoption", "renewal", "gross retention", "onboarding"],
        "url_env": "AFFILIATE_CUSTOMER_SUCCESS_URL",
    },
    {
        "category": "account_management",
        "title": "Account Management and Client Relationships",
        "provider": "LinkedIn Learning",
        "skill": "Account Management",
        "description": "Strengthen client relationship management, expansion conversations, and account ownership.",
        "gap_terms": ["account management", "client relationship", "cross-selling", "upselling"],
        "url_env": "AFFILIATE_ACCOUNT_MANAGEMENT_URL",
    },
    {
        "category": "stakeholder_management",
        "title": "Stakeholder Management and Communication",
        "provider": "Coursera",
        "skill": "Stakeholder Management",
        "description": "Improve communication, alignment, and influence across business and technical stakeholders.",
        "gap_terms": ["stakeholder management", "communication", "executive business reviews", "client communication"],
        "url_env": "AFFILIATE_STAKEHOLDER_MANAGEMENT_URL",
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
    },
]


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


def build_learning_recommendations(analysis: dict) -> list[dict]:
    gap_pool = _gap_pool(analysis)
    normalized_pool = " | ".join(item.lower() for item in gap_pool)
    recommendations: list[dict] = []
    seen: set[str] = set()

    for resource in RESOURCE_CATALOG:
        matched_terms = [term for term in resource["gap_terms"] if term.lower() in normalized_pool]
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
