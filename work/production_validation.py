from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from streamlit.testing.v1 import AppTest

from services.analysis_service import compare_resume_to_job
from services.export_service import build_optimized_resume_docx, build_optimized_resume_pdf
from services.resume_builder_service import build_optimized_resume_package


def main() -> None:
    resume_path = Path("work/test_assets/sample_resume.txt")
    job_path = Path("work/test_assets/meltwater_real_job_description.txt")
    resume_text = resume_path.read_text()
    job_text = job_path.read_text()

    at = AppTest.from_file("app.py")
    at.run()

    print("landing_page_visible", "Match your resume to any job and understand exactly where you stand." in "".join(str(item.value) for item in at.markdown))
    print("app_name_present", "Career Match" in "".join(str(item.value) for item in at.markdown))
    print("diagnostics_present", any(item.label == "Diagnostics" for item in at.expander))

    start_button = next(button for button in at.button if button.label == "Start Free Analysis")
    start_button.click()
    at.run()

    print("entered_app", at.session_state["entered_app"])
    print("has_upload_tab", any(tab.label == "Upload" for tab in at.tabs))

    at.file_uploader[0].set_value((resume_path.name, resume_path.read_bytes(), "text/plain"))
    at.run()

    fields = {item.label: item for item in at.text_input}
    fields["Company"].set_value("Meltwater")
    fields["Job Title"].set_value("Customer Success Manager II")
    fields["Location"].set_value("New York, NY, United States")
    at.text_area[1].set_value(job_text)
    next(button for button in at.button if button.label == "Use Manual Job Description").click()
    at.run()

    next(button for button in at.button if button.label == "Analyze and generate materials").click()
    at.run(timeout=60)

    print("analysis_company", at.session_state["analysis"]["company_name"])
    print("analysis_title", at.session_state["analysis"]["job_title"])
    print("role_family", at.session_state["analysis"]["role_family"])
    print("trust_score", at.session_state["generated"]["resume_builder"]["trust_score"])
    print("exception_count", len(at.exception))

    analysis = compare_resume_to_job(resume_text, job_text)
    builder = build_optimized_resume_package(resume_text, job_text, analysis, {"professional_summary": "", "tailored_resume_bullets": []})
    docx_bytes = build_optimized_resume_docx(builder["optimized_resume_text"])
    pdf_bytes = build_optimized_resume_pdf(builder["optimized_resume_text"])

    print("docx_bytes", len(docx_bytes))
    print("pdf_bytes", len(pdf_bytes))


if __name__ == "__main__":
    main()
