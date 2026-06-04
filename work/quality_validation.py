import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bs4 import BeautifulSoup

from services.analysis_service import compare_resume_to_job
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


if __name__ == "__main__":
    main()
