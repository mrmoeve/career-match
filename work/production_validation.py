from pathlib import Path
import sys
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from streamlit.testing.v1 import AppTest

from app import SEO_VIEWS
from database.db import (
    count_contact_messages_for_user,
    count_feedback_for_user,
    count_saved_resumes_for_user,
    get_dashboard_metrics,
    get_user_profile,
    test_database_connection,
)
from services.analysis_service import compare_resume_to_job
from services.billing_service import handle_webhook_event
from services.export_service import build_optimized_resume_docx, build_optimized_resume_pdf
from services.resume_builder_service import build_optimized_resume_package


def main() -> None:
    resume_path = Path("work/test_assets/sample_resume.txt")
    job_path = Path("work/test_assets/meltwater_real_job_description.txt")
    resume_text = resume_path.read_text()
    job_text = job_path.read_text()
    db_ok, db_engine = test_database_connection()
    print("database_connection_ok", db_ok)
    print("database_engine", db_engine)

    at = AppTest.from_file("app.py")
    at.run()

    print("landing_page_visible", "Match your resume to any job and understand exactly where you stand." in "".join(str(item.value) for item in at.markdown))
    print("app_name_present", "Career Match" in "".join(str(item.value) for item in at.markdown))
    print("diagnostics_present", any(item.label == "Diagnostics" for item in at.expander))

    start_button = next(button for button in at.button if button.label == "Start Free Analysis")
    start_button.click()
    at.run()

    print("auth_view_visible", any(tab.label == "Log In" for tab in at.tabs) and any(tab.label == "Register" for tab in at.tabs))

    email = f"career-match-{uuid4().hex[:8]}@example.com"
    inputs_by_key = {item.key: item for item in at.text_input}
    inputs_by_key["register_email"].set_value(email)
    inputs_by_key["register_password"].set_value("CareerMatch123")
    inputs_by_key["register_confirm_password"].set_value("CareerMatch123")
    next(button for button in at.button if button.label == "Create Account").click()
    at.run()

    print("registered_user", at.session_state["user_email"])
    print("is_authenticated", at.session_state["is_authenticated"])
    print("nav_pages_present", [item.value for item in at.radio if item.label == "Navigation"])
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
    print("saved_application", at.session_state["application_saved"])
    print("exception_count", len(at.exception))
    feedback_radios = [item for item in at.radio if item.label == "Helpful"]
    if feedback_radios:
        feedback_radios[0].set_value("Helpful")
        at.text_area[-1].set_value("Strong recruiter-quality framing.")
        next(button for button in at.button if button.label == "Submit Feedback").click()
        at.run()
    print("free_usage_after_first", get_dashboard_metrics(email)["free_assessments_used"])
    print("free_remaining_after_first", get_dashboard_metrics(email)["free_assessments_remaining"])

    next(button for button in at.button if button.label == "Analyze and generate materials").click()
    at.run(timeout=60)
    print("second_assessment_routes_to_pro", at.session_state["app_page"] == "Pro")

    credit_result = handle_webhook_event(
        "checkout.session.completed",
        {
            "user_email": email,
            "stripe_session_id": "test_credit_session",
            "stripe_payment_intent": "test_credit_intent",
            "amount": 499,
            "currency": "usd",
            "product_type": "one_time_assessment",
            "status": "completed",
        },
    )
    print("credit_webhook_ok", credit_result.get("ok"))
    at.session_state["app_page"] = "Workflow"
    at.run()
    next(button for button in at.button if button.label == "Analyze and generate materials").click()
    at.run(timeout=60)
    print("credit_user_bypasses_paywall_once", at.session_state["app_page"] == "Workflow")
    print("credits_after_consumption", get_dashboard_metrics(email)["assessment_credits"])

    pro_result = handle_webhook_event(
        "checkout.session.completed",
        {
            "user_email": email,
            "stripe_session_id": "test_pro_session",
            "stripe_payment_intent": "test_pro_intent",
            "stripe_customer_id": "cus_test_123",
            "stripe_subscription_id": "sub_test_123",
            "amount": 1900,
            "currency": "usd",
            "product_type": "pro_monthly",
            "status": "completed",
            "subscription_start": "2026-06-04T12:00:00",
            "subscription_end": "2026-07-04T12:00:00",
        },
    )
    print("pro_webhook_ok", pro_result.get("ok"))
    at.session_state["app_page"] = "Workflow"
    at.run()
    next(button for button in at.button if button.label == "Analyze and generate materials").click()
    at.run(timeout=60)
    print("pro_user_bypasses_paywall", at.session_state["app_page"] == "Workflow")
    print("dashboard_jobs_analyzed", get_dashboard_metrics(email)["jobs_analyzed"])

    next(item for item in at.radio if item.label == "Navigation").set_value("Subscription")
    at.run()
    print("subscription_page_present", at.session_state["app_page"] == "Subscription")
    profile = get_user_profile(email) or {}
    print("stripe_customer_saved", bool(profile.get("stripe_customer_id")))
    print("stripe_subscription_saved", bool(profile.get("stripe_subscription_id")))
    print("subscription_status_active", profile.get("subscription_status") == "active")
    print("subscription_end_saved", bool(profile.get("subscription_end")))

    at.session_state["app_page"] = "Contact"
    at.run()
    next(item for item in at.text_input if item.label == "Name").set_value("Jordan Tester")
    next(item for item in at.text_input if item.label == "Email").set_value(email)
    at.selectbox[0].set_value("Feature Request")
    at.text_area[-1].set_value("Please keep improving the recruiter-quality analysis.")
    next(button for button in at.button if button.label == "Submit").click()
    at.run()

    saved_contact_count = count_contact_messages_for_user(email)
    saved_feedback_count = count_feedback_for_user(email)
    saved_resume_count = count_saved_resumes_for_user(email)
    print("contact_saved", saved_contact_count >= 1)
    print("feedback_saved", saved_feedback_count >= 1)
    print("saved_resume_count", saved_resume_count)

    next(button for button in at.button if button.label == "Home").click()
    at.run()
    print("home_button_returns_landing", "Match your resume to any job and understand exactly where you stand." in "".join(str(item.value) for item in at.markdown))

    at.session_state["app_page"] = "Workflow"
    at.session_state["current_view"] = "app"
    at.run()
    print("authenticated_user_can_reenter_app", any(tab.label == "Upload" for tab in at.tabs))

    next(button for button in at.button if button.label == "Log Out").click()
    at.run()
    print("logout_returns_home", at.session_state["is_authenticated"] is False and "Match your resume to any job and understand exactly where you stand." in "".join(str(item.value) for item in at.markdown))

    at.session_state["current_view"] = "app"
    at.run()
    print("logged_out_app_access_blocked", any(tab.label == "Log In" for tab in at.tabs))

    seo_checks = {
        "ats-checker": "ATS Resume Checker",
        "resume-builder": "AI Resume Builder",
        "interview-prep": "Interview Prep Generator",
        "cover-letter-generator": "Cover Letter Generator",
        "linkedin-message-generator": "LinkedIn Message Generator",
    }
    caddy_config = Path("deploy/Caddyfile").read_text()
    for view_name in seo_checks:
        print(f"{view_name}_registered", view_name in SEO_VIEWS)
        print(f"{view_name}_caddy_redirect", f"/{view_name}" in caddy_config)

    analysis = compare_resume_to_job(resume_text, job_text)
    builder = build_optimized_resume_package(resume_text, job_text, analysis, {"professional_summary": "", "tailored_resume_bullets": []})
    docx_bytes = build_optimized_resume_docx(builder["optimized_resume_text"])
    pdf_bytes = build_optimized_resume_pdf(builder["optimized_resume_text"])

    print("docx_bytes", len(docx_bytes))
    print("pdf_bytes", len(pdf_bytes))


if __name__ == "__main__":
    main()
