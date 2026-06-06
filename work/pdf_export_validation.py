import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.analysis_service import compare_resume_to_job
from services.pdf_export_service import build_pdf_payload, build_tab_pdf
from services.resume_builder_service import build_optimized_resume_package


TAB_NAMES = [
    "Resume Match",
    "Tailored Resume",
    "Resume Builder",
    "Evidence",
    "Career Coach",
    "Cover Letter",
    "Interview Intelligence",
    "LinkedIn Message",
    "Thank You Email",
    "Export",
]


def _build_generated(analysis: dict, builder: dict) -> dict:
    matched = ", ".join((analysis.get("matching_skills", []) or analysis.get("matching_keywords", []))[:4]) or "procurement strategy, vendor negotiation, spend analysis"
    gaps = ", ".join((analysis.get("missing_keywords", []) or [])[:4]) or "ERP, SaaS procurement"
    title = analysis.get("job_title", "Target Role")
    company = analysis.get("company_name", "Target Company")
    coach = {
        "overview": f"This plan helps close the largest gaps for the {title} role at {company}.",
        "missing_skills": analysis.get("missing_keywords", [])[:4],
        "missing_certifications": (analysis.get("job_fit", {}) or {}).get("missing_certifications", [])[:3],
        "missing_technologies": analysis.get("missing_keywords", [])[:4],
        "missing_industry_experience": ["The resume does not show direct SaaS procurement platform ownership."],
        "thirty_day_plan": [{"action": "Reframe procurement wins with role language.", "why_it_matters": "Improves recruiter clarity.", "estimated_job_fit_increase": 3}],
        "ninety_day_plan": [{"action": "Build procurement systems fluency with ERP and intake tooling concepts.", "why_it_matters": "Reduces platform gaps.", "estimated_job_fit_increase": 4}],
        "recommended_certifications": [{"name": "Relevant procurement or sourcing credential", "reason": "Adds credibility.", "estimated_job_fit_increase": 2}],
        "recommended_courses": [{"name": "Strategic sourcing and spend analytics", "reason": "Targets current gaps.", "estimated_job_fit_increase": 2}],
        "resume_improvements": [{"change": "Move vendor negotiation and cost-savings achievements higher.", "reason": "Improves fit visibility.", "estimated_job_fit_increase": 3}],
    }
    interview_dashboard = {
        "overview": f"Interview prep for the {title} role at {company} focused on procurement leadership and savings delivery.",
        "top_25_likely_questions": [
            {
                "question": "How have you driven procurement savings?",
                "confidence_score": 86,
                "answer_summary": "Use documented negotiation, budget, and cost-savings examples from the resume.",
                "star_answer": {
                    "situation": "Multi-site procurement projects needed tighter cost control.",
                    "task": "Protect scope while improving commercial outcomes.",
                    "action": "Negotiated vendors, tracked costs, and improved execution controls.",
                    "result": "Delivered documented savings and stronger vendor coordination.",
                },
            }
        ],
        "technical_questions": [
            {
                "question": "How would you approach spend reporting and dashboards?",
                "confidence_score": 80,
                "answer_summary": "Connect tracking systems, budget ownership, and reporting discipline from the resume.",
                "star_answer": {"situation": "", "task": "", "action": "", "result": ""},
            }
        ],
        "behavioral_questions": [
            {
                "question": "Tell me about a time you partnered across teams.",
                "confidence_score": 84,
                "answer_summary": "Use cross-functional construction and procurement coordination examples.",
                "star_answer": {"situation": "", "task": "", "action": "", "result": ""},
            }
        ],
        "questions_for_interviewer": ["What savings targets matter most in the first 90 days?"],
        "potential_challenges": [
            {
                "challenge": "Direct ERP ownership may be questioned.",
                "why_it_may_come_up": "The job description calls for ERP-linked workflow ownership.",
                "suggested_response": "Acknowledge the gap and connect it to existing tracking-system and process-improvement experience.",
                "confidence_score": 75,
            }
        ],
    }
    return {
        "professional_summary": f"Procurement leader with resume-backed experience in {matched}.",
        "tailored_resume_bullets": builder.get("recruiter_ready_bullets", [])[:5] or ["Reframed real procurement accomplishments using role language."],
        "cover_letter": f"I am interested in the {title} role at {company} because my resume shows evidence-backed experience in {matched}.",
        "linkedin_recruiter_message": f"Hello, I am reaching out regarding the {title} opportunity at {company}. My background includes {matched}.",
        "interview_questions_and_answers": [{"question": "Why this role?", "answer": f"My background in {matched} aligns with the role while I continue closing gaps in {gaps}."}],
        "interview_dashboard": interview_dashboard,
        "career_coach": coach,
        "thank_you_email": f"Thank you for discussing the {title} role with me. I appreciated the conversation and remain very interested.",
        "results_summary_email": f"Subject: Career Match Summary\n\nTop strengths: {matched}\nKey gaps: {gaps}",
        "resume_builder": builder,
    }


def main() -> None:
    resume_text = Path("work/test_assets/talisa_procurement_resume.txt").read_text()
    job_text = Path("work/test_assets/clay_procurement_job.txt").read_text()
    analysis = compare_resume_to_job(resume_text, job_text)
    analysis["job_title"] = "Procurement"
    analysis["company_name"] = "Clay"
    builder = build_optimized_resume_package(resume_text, job_text, analysis, {"professional_summary": "", "tailored_resume_bullets": []})
    generated = _build_generated(analysis, builder)

    package = {
        "analysis": analysis,
        "generated": generated,
        "resume_text": resume_text,
        "job_text": job_text,
        "resume_filename": "Talisa_Salvador_Resume_2026.pdf",
        "job_url": "https://www.clay.com/jobs?ashby_jid=4be52dd6-244b-4e27-bf4a-757a1094a82a",
        "created_at": "2026-06-05T12:00:00",
        "user_email": "mrmoeve@gmail.com",
        "active_role_profile_name": analysis.get("active_role_profile", {}).get("headline", analysis.get("role_family", "")),
    }

    app_source = Path("app.py").read_text()
    tab_button_checks = {
        tab: f'render_pdf_download_button(\n        "{tab}"' in app_source or f'render_pdf_download_button("{tab}"' in app_source
        for tab in TAB_NAMES
    }

    sample_filenames = []
    non_empty_checks = {}
    role_profile_checks = {}
    contamination_checks = {}
    resume_match_section_checks = {}

    for tab in TAB_NAMES:
        pdf_bytes, file_name, payload = build_tab_pdf(tab, package)
        sample_filenames.append(file_name)
        non_empty_checks[tab] = bool(pdf_bytes.startswith(b"%PDF") and len(pdf_bytes) > 1200)
        role_profile_checks[tab] = package["active_role_profile_name"] in payload.get("text_dump", "")
        lower_dump = payload.get("text_dump", "").lower()
        contamination_checks[tab] = all(
            term not in lower_dump
            for term in ["customer success", "account management", "training & adoption"]
        )
        if tab == "Resume Match":
            text_dump = payload.get("text_dump", "")
            resume_match_section_checks = {
                "why_this_score": "Why This Score?" in text_dump,
                "recruiter_confidence": "Recruiter Confidence" in text_dump,
                "missing_keywords_by_priority": "Missing Keywords by Priority" in text_dump,
                "reasons_to_interview": "Why Recruiters Will Interview" in text_dump,
                "reasons_to_reject": "Why Recruiters May Pass" in text_dump,
                "compensation_level_alignment": "Compensation / Level Alignment" in text_dump,
                "compared_with_typical_applicants": "Compared To Successful Candidates" in text_dump,
                "resume_roi": "Highest ROI Fixes" in text_dump,
                "recruiter_summary": "Recruiter-Style Summary" in text_dump,
                "keyword_coverage_after": "Keyword Coverage After" in text_dump,
            }

    contradiction_free = all(
        (item.get("support_level") != "Weak / Unsupported" or item.get("ats_gain", 0) == 0)
        and (item.get("ats_gain", 0) == 0 or item.get("support_level") in {"Explicit", "Transferable"})
        for item in builder.get("term_validation_report", [])
    )
    unsupported_not_direct = all(
        row.get("evidence_level") != "Unsupported" or row.get("direct_score", 0) == 0
        for row in analysis.get("score_breakdown", [])
    )

    print("tab_pdf_buttons", tab_button_checks)
    print("pdf_non_empty", non_empty_checks)
    print("pdf_role_profile_present", role_profile_checks)
    print("pdf_procurement_contamination_free", contamination_checks)
    print("resume_match_pdf_sections", resume_match_section_checks)
    print("unsupported_terms_not_in_ats_gain", contradiction_free)
    print("unsupported_terms_not_counted_as_direct_evidence", unsupported_not_direct)
    print("sample_pdf_filenames", sample_filenames[:5])

    overall_pass = (
        all(tab_button_checks.values())
        and all(non_empty_checks.values())
        and all(role_profile_checks.values())
        and all(contamination_checks.values())
        and contradiction_free
        and all(resume_match_section_checks.values())
        and unsupported_not_direct
    )
    print("pdf_export_validation_passed", overall_pass)
    if not overall_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
