import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bs4 import BeautifulSoup

from services.analysis_service import compare_resume_to_job
from services.affiliate_service import build_learning_recommendations
from services.job_url_service import (
    _extract_category,
    _extract_company,
    _extract_date_posted,
    _extract_description,
    _extract_json_ld_objects,
    _extract_location,
    _extract_title,
    _pick_job_posting_object,
)
from services.resume_builder_service import build_optimized_resume_package


MELTWATER_HTML = """
<html>
  <head>
    <title>Customer Success Manager II - Meltwater Careers</title>
    <meta property="og:title" content="Customer Success Manager II - Meltwater" />
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Customer Success Manager II",
        "datePosted": "2026-06-03",
        "description": "<div><p>Drive customer retention, executive reporting, dashboard reporting, data analysis, and cross-functional collaboration.</p><p>Use Salesforce, CRM workflows, Excel, and PowerPoint.</p></div>",
        "hiringOrganization": {"@type": "Organization", "name": "Meltwater"},
        "jobLocation": {
          "@type": "Place",
          "address": {
            "@type": "PostalAddress",
            "addressLocality": "New York",
            "addressRegion": "NY",
            "addressCountry": "United States"
          }
        },
        "occupationalCategory": "Sales"
      }
    </script>
  </head>
  <body>
    <nav>Skip to main content Search Jobs Saved Jobs Back to Search Results Apply Now Save Job Share to LinkedIn Share to Facebook Share to Twitter</nav>
    <main>
      <h1>Skip to main content Customer Success Manager II</h1>
      <div class="company">Meltwater</div>
      <div class="location">New York, NY, United States</div>
      <article>
        <p>Customer Success Manager II</p>
        <p>Meltwater is hiring a customer success leader with stakeholder management, client relationship management, cross-functional collaboration, dashboard reporting, executive reporting, and data analysis experience.</p>
        <p>Preferred technologies include Excel, PowerPoint, Salesforce, and CRM workflows in a SaaS environment.</p>
      </article>
    </main>
  </body>
</html>
"""

MELTWATER_JOB_TEXT = """Customer Success Manager II
Meltwater
New York, NY, United States
Sales

Meltwater is hiring a Customer Success Manager II to support customer success in a SaaS environment.
Responsibilities include stakeholder management, client relationship management, cross-functional collaboration,
dashboard reporting, executive reporting, data analysis, issue resolution, and process improvement.
Preferred technologies include Excel, PowerPoint, Salesforce, and CRM workflows.
"""

PROCUREMENT_JOB_TEXT = """Senior Procurement Analyst
Datadog
New York, NY, United States

Datadog is hiring a Senior Procurement Analyst to support strategic sourcing, procurement analytics,
vendor negotiation, spend analysis, renewal management, forecast modeling, stakeholder partnership,
AI and automation in procurement, G&A category management, and systems/process improvement.
The role partners across finance, legal, procurement, and business teams to improve sourcing decisions and operating leverage.
"""

CYERA_JOB_TEXT = """Procurement Specialist
Cyera
New York, NY, United States

Cyera is hiring a Procurement Specialist to own indirect procurement across software, SaaS, marketing, and professional services.
The role covers the full procurement lifecycle, vendor management, renewals, cross-functional partnership, supplier sourcing,
cost improvement, risk and compliance management, spend analytics, automation, and AI tools.
Required qualifications include procurement experience, strong analytical skills, vendor negotiation, procurement and ERP platforms,
excellent communication, and the ability to influence senior stakeholders.
"""


def main() -> None:
    resume_text = Path("work/test_assets/sample_resume.txt").read_text()

    soup = BeautifulSoup(MELTWATER_HTML, "html.parser")
    objects = _extract_json_ld_objects(soup)
    job_posting = _pick_job_posting_object(objects)
    title, _ = _extract_title(soup, job_posting)
    company, _ = _extract_company(soup, job_posting, "https://jobs.meltwater.com/example")
    location, _ = _extract_location(soup, job_posting)
    date_posted, _ = _extract_date_posted(soup, job_posting)
    category, _ = _extract_category(soup, job_posting)
    description, _ = _extract_description(soup, job_posting)

    analysis = compare_resume_to_job(resume_text, MELTWATER_JOB_TEXT)
    generated = {"professional_summary": "", "tailored_resume_bullets": []}
    builder = build_optimized_resume_package(resume_text, MELTWATER_JOB_TEXT, analysis, generated)

    optimized_lines = builder["optimized_resume_text"].splitlines()
    skills_section_line = ""
    for index, line in enumerate(optimized_lines):
        if line.strip().upper() == "SKILLS" and index + 1 < len(optimized_lines):
            skills_section_line = optimized_lines[index + 1].strip()
            break

    print("title", title)
    print("company", company)
    print("location", location)
    print("date_posted", date_posted)
    print("category", category)
    print("nav_title_removed", "Skip to main content" not in title and "Skip to main content" not in description)
    print("role_family", analysis.get("role_family"))
    print("matching_keywords", analysis["matching_keywords"])
    print("has_bad_keywords", any(word.lower() in {"apply", "based", "account", "adoption", "committed", "dedicated", "business"} for word in analysis["matching_keywords"]))
    print("skills_line", skills_section_line)
    print("skills_contains_experience_text", "Harbor Peak Retail" in skills_section_line)
    print("direct_match_score", analysis["direct_match_score"])
    print("transferable_match_score", analysis["transferable_match_score"])
    print("overall_fit_score", analysis["overall_fit_score"])
    print("interview_potential_score", analysis["overall_interview_potential"])
    print("ats_before", analysis["ats_score"])
    print("ats_after", builder["optimized_ats_score"])
    print("keywords_added", builder["keywords_added"])
    print("bridge_guidance", builder.get("bridge_the_gap_guidance", []))

    procurement_analysis = compare_resume_to_job(resume_text, PROCUREMENT_JOB_TEXT)
    procurement_competencies = [item["competency"] for item in procurement_analysis.get("competency_scores", [])]
    procurement_recommendations = build_learning_recommendations(procurement_analysis)
    procurement_categories = [item.get("category", "") for item in procurement_recommendations]
    print("procurement_role_family", procurement_analysis.get("role_family"))
    print("procurement_active_role_profile", procurement_analysis.get("active_role_profile", {}).get("headline", ""))
    print("procurement_has_customer_success_labels", any(item in {"Customer Success", "Account Management", "Training & Adoption"} for item in procurement_competencies))
    print("procurement_expected_competencies_present", all(item in procurement_competencies for item in [
        "Strategic Sourcing",
        "Procurement Analytics",
        "Vendor Negotiation",
        "Spend Analysis",
        "Renewal Management",
        "Forecast Modeling",
        "Stakeholder Partnership",
        "AI / Automation in Procurement",
        "G&A Category Management",
        "Systems / Process Improvement",
    ]))
    print("procurement_affiliate_categories", procurement_categories)
    print("procurement_customer_success_labels_count", sum(1 for item in procurement_competencies if item == "Customer Success"))
    print("procurement_account_management_labels_count", sum(1 for item in procurement_competencies if item == "Account Management"))
    print("procurement_training_adoption_labels_count", sum(1 for item in procurement_competencies if item == "Training & Adoption"))
    print("procurement_customer_success_recommendations", sum(1 for item in procurement_categories if item == "customer_success_foundations"))
    print("procurement_account_management_recommendations", sum(1 for item in procurement_categories if item == "client_relationship_growth"))
    print("procurement_cross_role_contamination_passed", not any(item in {"customer_success_foundations", "client_relationship_growth"} for item in procurement_categories))

    talisa_resume = Path("work/test_assets/talisa_procurement_resume.txt").read_text()
    cyera_analysis = compare_resume_to_job(talisa_resume, CYERA_JOB_TEXT)
    cyera_builder = build_optimized_resume_package(talisa_resume, CYERA_JOB_TEXT, cyera_analysis, {"professional_summary": "", "tailored_resume_bullets": []})
    print("cyera_ats_before", cyera_analysis.get("ats_score"))
    print("cyera_ats_after", cyera_builder.get("optimized_ats_score"))
    print("cyera_keywords_added", cyera_builder.get("keywords_added"))
    print("cyera_terms_already_present", cyera_builder.get("terms_already_present"))
    print("cyera_terms_safely_added", cyera_builder.get("terms_safely_added"))
    print("cyera_terms_repositioned", cyera_builder.get("terms_repositioned"))
    print("cyera_terms_newly_added", cyera_builder.get("terms_newly_added_from_resume_evidence"))
    print("cyera_terms_not_added", cyera_builder.get("terms_not_added_due_to_insufficient_evidence"))
    print("cyera_unsupported_added", cyera_builder.get("unsupported_added_keywords"))
    print("cyera_category_improvements", [item.get("category") for item in cyera_builder.get("category_improvements", [])])
    original_resume_lower = talisa_resume.lower()
    print(
        "cyera_newly_added_not_in_original_resume",
        all(term.lower() not in original_resume_lower for term in cyera_builder.get("terms_newly_added_from_resume_evidence", [])),
    )
    print(
        "cyera_consistency_test_passed",
        not cyera_builder.get("category_improvements")
        or cyera_builder.get("optimized_ats_score", 0) > cyera_builder.get("original_ats_score", 0)
        or "unsupported additions" in cyera_builder.get("ats_change_explanation", "").lower(),
    )

    pulte_job_text = Path("work/test_assets/pultegroup_procurement_agent_job.txt").read_text()
    pulte_analysis = compare_resume_to_job(talisa_resume, pulte_job_text)
    pulte_builder = build_optimized_resume_package(talisa_resume, pulte_job_text, pulte_analysis, {"professional_summary": "", "tailored_resume_bullets": []})
    print("pulte_ats_before", pulte_analysis.get("ats_score"))
    print("pulte_ats_after", pulte_builder.get("optimized_ats_score"))
    print("pulte_ats_improvement", pulte_builder.get("ats_improvement_percentage"))
    print("pulte_terms_already_present", pulte_builder.get("terms_already_present"))
    print("pulte_terms_repositioned", pulte_builder.get("terms_repositioned"))
    print("pulte_terms_newly_added", pulte_builder.get("terms_newly_added_from_resume_evidence"))
    print("pulte_transferable_terms", pulte_builder.get("transferable_terms_used_carefully"))
    print("pulte_terms_not_added", pulte_builder.get("terms_not_added_due_to_insufficient_evidence"))
    print("pulte_unsupported_terms", pulte_builder.get("unsupported_added_keywords"))
    print("pulte_category_improvements", [f"{item.get('category')}:+{item.get('delta')}" for item in pulte_builder.get("category_improvements", [])])
    print("pulte_onboarding_not_safely_added", "Onboarding" not in pulte_builder.get("terms_newly_added_from_resume_evidence", []) + pulte_builder.get("transferable_terms_used_carefully", []))
    print("pulte_client_onboarding_not_safely_added", "Client Onboarding" not in pulte_builder.get("terms_newly_added_from_resume_evidence", []) + pulte_builder.get("transferable_terms_used_carefully", []))
    print("pulte_category_management_transferable", "Category Management" in pulte_builder.get("transferable_terms_used_carefully", []) or "G&A Category Management" in pulte_builder.get("transferable_terms_used_carefully", []))
    visible_detail_terms = {
        item.get("term", "")
        for item in pulte_builder.get("terms_newly_added_details", []) + pulte_builder.get("transferable_terms_used_carefully_details", [])
        if item.get("source_resume_evidence") and item.get("support_level")
    }
    safe_terms = set(pulte_builder.get("terms_newly_added_from_resume_evidence", []) + pulte_builder.get("transferable_terms_used_carefully", []))
    print("pulte_safe_terms_have_visible_evidence", safe_terms.issubset(visible_detail_terms))


if __name__ == "__main__":
    main()
