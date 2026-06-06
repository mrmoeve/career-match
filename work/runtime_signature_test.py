import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.db import ApplicationRecord, init_db, save_application
from services.export_service import (
    build_full_report_docx,
    build_full_report_pdf,
    build_optimized_resume_docx,
    build_optimized_resume_pdf,
)


def main() -> None:
    init_db()

    record = ApplicationRecord(
        company_name="Test",
        job_title="Test",
        original_resume_text="test",
        optimized_resume_text="test",
        original_ats_score=50,
        optimized_ats_score=80,
    )
    save_application(record)

    package = {
        "analysis": {"job_title": "Test", "company_name": "Test", "ats_score": 50},
        "generated": {
            "resume_builder": {
                "analysis_job_title": "Test",
                "optimized_resume_text": "TEST USER\nemail@example.com\n\nPROFESSIONAL SUMMARY\nOptimized summary",
            },
            "cover_letter": "",
            "linkedin_recruiter_message": "",
            "interview_questions_and_answers": [],
            "thank_you_email": "",
        },
        "created_at": "2026-06-03T00:00:00",
    }

    full_docx_bytes = build_full_report_docx(package)
    full_pdf_bytes = build_full_report_pdf(package)
    optimized_docx_bytes = build_optimized_resume_docx(
        package["generated"]["resume_builder"]["optimized_resume_text"]
    )
    optimized_pdf_bytes = build_optimized_resume_pdf(
        package["generated"]["resume_builder"]["optimized_resume_text"]
    )

    print("record_ok", bool(record))
    print("full_docx_ok", len(full_docx_bytes) > 0)
    print("full_pdf_ok", len(full_pdf_bytes) > 0)
    print("optimized_docx_ok", len(optimized_docx_bytes) > 0)
    print("optimized_pdf_ok", len(optimized_pdf_bytes) > 0)


if __name__ == "__main__":
    main()
