import hashlib
import re


PROCUREMENT_PROFILE = {
    "name": "senior_procurement_analyst",
    "display_name": "Senior Procurement Analyst",
    "family": "Strategic Sourcing / Procurement",
    "headline": "Senior Procurement Analyst | Strategic Sourcing / Procurement",
    "keywords": [
        "procurement",
        "strategic sourcing",
        "sourcing",
        "vendor negotiation",
        "supplier negotiation",
        "spend analysis",
        "renewal management",
        "forecast modeling",
        "category management",
        "g&a",
        "purchase",
        "contract negotiation",
        "procurement analytics",
        "supplier",
        "datadog",
    ],
    "competencies": [
        {
            "label": "Strategic Sourcing",
            "job_terms": ["Strategic Sourcing", "Category Management", "Procurement"],
            "transfer_terms": ["Stakeholder Management", "Vendor Management", "Contract Negotiation", "Business Analysis", "Process Improvement"],
            "weight": 16,
        },
        {
            "label": "Procurement Analytics",
            "job_terms": ["Procurement Analytics", "Spend Analysis", "Procurement", "Data Analysis"],
            "transfer_terms": ["Data Analysis", "Forecasting", "Variance Analysis", "Dashboard Reporting", "Business Analysis"],
            "weight": 14,
        },
        {
            "label": "Vendor Negotiation",
            "job_terms": ["Vendor Negotiation", "Supplier Negotiation", "Contract Negotiation"],
            "transfer_terms": ["Stakeholder Communication", "Relationship Management", "Account Management", "Project Coordination"],
            "weight": 14,
        },
        {
            "label": "Spend Analysis",
            "job_terms": ["Spend Analysis", "Budgeting", "Cost Analysis"],
            "transfer_terms": ["Financial Analysis", "Variance Analysis", "Forecasting", "Data Analysis", "Reconciliation"],
            "weight": 12,
        },
        {
            "label": "Renewal Management",
            "job_terms": ["Renewal Management", "Renewals", "Contract Management"],
            "transfer_terms": ["Relationship Management", "Issue Resolution", "Account Management", "Stakeholder Management"],
            "weight": 12,
        },
        {
            "label": "Forecast Modeling",
            "job_terms": ["Forecast Modeling", "Forecasting", "Budgeting"],
            "transfer_terms": ["Financial Modeling", "Financial Analysis", "Variance Analysis", "Excel", "Data Analysis"],
            "weight": 12,
        },
        {
            "label": "Stakeholder Partnership",
            "job_terms": ["Stakeholder Partnership", "Stakeholder Management", "Cross-Functional Collaboration"],
            "transfer_terms": ["Stakeholder Communication", "Executive Reporting", "Client Communication", "Project Coordination", "Business Analysis"],
            "weight": 14,
        },
        {
            "label": "AI / Automation in Procurement",
            "job_terms": ["AI", "Automation", "Procurement Automation", "Process Improvement"],
            "transfer_terms": ["Python", "Process Improvement", "Systems Optimization", "Automation", "Data Analysis"],
            "weight": 8,
        },
        {
            "label": "G&A Category Management",
            "job_terms": ["G&A", "Category Management", "Procurement"],
            "transfer_terms": ["Budgeting", "Stakeholder Management", "Project Management", "Business Analysis"],
            "weight": 6,
        },
        {
            "label": "Systems / Process Improvement",
            "job_terms": ["Systems", "Process Improvement", "Automation", "Workflow"],
            "transfer_terms": ["Process Improvement", "Application Support", "Business Analysis", "Project Coordination"],
            "weight": 12,
        },
    ],
}

CUSTOMER_SUCCESS_PROFILE = {
    "name": "saas_customer_success",
    "display_name": "Customer Success Manager",
    "family": "SaaS Customer Success / Account Management",
    "headline": "Customer Success Manager | SaaS Customer Success / Account Management",
    "keywords": [
        "customer success",
        "product adoption",
        "gross retention",
        "renewals",
        "account management",
        "client success",
        "onboarding",
        "customer onboarding",
        "saas",
    ],
    "competencies": [
        {
            "label": "Customer Success",
            "job_terms": ["Customer Success", "Client Engagement", "Gross Retention", "Renewals", "Customer Onboarding", "Product Adoption"],
            "transfer_terms": ["Stakeholder Management", "Client Communication", "Relationship Management", "Cross-Functional Collaboration", "Issue Resolution", "Application Support", "User Training"],
            "weight": 18,
        },
        {
            "label": "Account Management",
            "job_terms": ["Account Management", "Client Relationship Management", "Renewal Support", "Upselling", "Cross-selling", "Executive Business Reviews"],
            "transfer_terms": ["Stakeholder Management", "Relationship Management", "Client Communication", "Cross-Functional Collaboration", "Business Analysis", "Stakeholder Communication"],
            "weight": 16,
        },
        {
            "label": "Stakeholder Management",
            "job_terms": ["Stakeholder Management", "Cross-Functional Collaboration", "Executive Business Reviews"],
            "transfer_terms": ["Stakeholder Communication", "Executive Reporting", "Client Communication", "Business Analysis", "Project Coordination"],
            "weight": 18,
        },
        {
            "label": "Client Communication",
            "job_terms": ["Client Communication", "Client Relationship Management", "User Training"],
            "transfer_terms": ["Stakeholder Communication", "Executive Reporting", "Presentation Development", "Issue Resolution", "Application Support"],
            "weight": 16,
        },
        {
            "label": "Risk Management",
            "job_terms": ["Risk Mitigation", "Risk", "Issue Resolution"],
            "transfer_terms": ["Risk Management", "Data Analysis", "Process Improvement", "Reconciliation", "Variance Analysis"],
            "weight": 14,
        },
        {
            "label": "Training & Adoption",
            "job_terms": ["Product Adoption", "User Training", "Client Onboarding", "Customer Onboarding"],
            "transfer_terms": ["Training", "Dashboard Reporting", "Process Improvement", "Stakeholder Communication", "Presentation Development", "Application Support", "Issue Resolution"],
            "weight": 18,
        },
    ],
}

GENERAL_PROFILE = {
    "name": "general_professional",
    "display_name": "Professional Role",
    "family": "General Professional Role",
    "headline": "Professional Role | General Professional Role",
    "keywords": [],
    "competencies": [
        {
            "label": "Analytical Problem Solving",
            "job_terms": ["Data Analysis", "Business Analysis", "Financial Analysis"],
            "transfer_terms": ["Data Analysis", "Business Analysis", "Forecasting", "Variance Analysis", "Process Improvement"],
            "weight": 20,
        },
        {
            "label": "Stakeholder Partnership",
            "job_terms": ["Stakeholder Management", "Cross-Functional Collaboration", "Communication"],
            "transfer_terms": ["Stakeholder Communication", "Executive Reporting", "Project Coordination", "Relationship Management"],
            "weight": 20,
        },
        {
            "label": "Execution & Delivery",
            "job_terms": ["Project Management", "Process Improvement", "Operations"],
            "transfer_terms": ["Project Coordination", "Process Improvement", "Issue Resolution", "Application Support"],
            "weight": 20,
        },
        {
            "label": "Reporting & Insights",
            "job_terms": ["Reporting", "Dashboard Reporting", "Forecasting"],
            "transfer_terms": ["Executive Reporting", "Presentation Development", "Data Analysis", "Excel"],
            "weight": 20,
        },
        {
            "label": "Systems & Tools",
            "job_terms": ["Systems", "Automation", "Technology"],
            "transfer_terms": ["Application Support", "Python", "SQL", "Process Improvement"],
            "weight": 20,
        },
    ],
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def build_role_profile_fingerprint(job_title: str, job_description_text: str) -> str:
    payload = f"{(job_title or '').strip().lower()}|{_normalize(job_description_text)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_active_role_profile(job_title: str, job_description_text: str) -> dict:
    normalized_title = _normalize(job_title)
    normalized_text = _normalize(job_description_text)
    haystack = f"{normalized_title} {normalized_text}"

    procurement_hits = sum(1 for term in PROCUREMENT_PROFILE["keywords"] if term in haystack)
    customer_success_hits = sum(1 for term in CUSTOMER_SUCCESS_PROFILE["keywords"] if term in haystack)

    if procurement_hits >= max(2, customer_success_hits + 1):
        profile = PROCUREMENT_PROFILE.copy()
    elif customer_success_hits >= 2:
        profile = CUSTOMER_SUCCESS_PROFILE.copy()
    else:
        profile = GENERAL_PROFILE.copy()

    role_title = (job_title or "").strip() or profile["display_name"]
    profile["job_title"] = role_title
    profile["fingerprint"] = build_role_profile_fingerprint(role_title, job_description_text)
    profile["headline"] = f"{role_title} | {profile['family']}"
    return profile
