import smtplib
from email.message import EmailMessage


def email_configured() -> bool:
    return all(
        [
            smtp_host(),
            smtp_port(),
            smtp_user(),
            smtp_password(),
            from_email(),
        ]
    )


def smtp_host() -> str:
    import os

    return os.getenv("SMTP_HOST", "").strip()


def smtp_port() -> str:
    import os

    return os.getenv("SMTP_PORT", "").strip()


def smtp_user() -> str:
    import os

    return os.getenv("SMTP_USER", "").strip() or os.getenv("SMTP_USERNAME", "").strip()


def smtp_password() -> str:
    import os

    return os.getenv("SMTP_PASSWORD", "").strip()


def from_email() -> str:
    import os

    return os.getenv("FROM_EMAIL", "").strip()


def get_email_diagnostics() -> dict:
    return {
        "configured": email_configured(),
        "host_loaded": bool(smtp_host()),
        "port_loaded": bool(smtp_port()),
        "user_loaded": bool(smtp_user()),
        "password_loaded": bool(smtp_password()),
        "from_email_loaded": bool(from_email()),
    }


def build_results_summary_email(analysis: dict, generated: dict) -> str:
    job_title = analysis.get("job_title", "Target Role")
    company = analysis.get("company_name", "Target Company")
    fit_score = analysis.get("overall_fit_score", analysis.get("ats_score", 0))
    recommendation = (analysis.get("job_fit", {}) or {}).get("recommendation", "Review recommended")
    strengths = ", ".join(analysis.get("role_specific_strengths", [])[:3]) or "relevant transferable experience"
    gaps = ", ".join(analysis.get("missing_keywords", [])[:4]) or "no major missing keywords identified"
    summary = generated.get("professional_summary", "")

    return (
        f"Subject: Career Match Results Summary - {job_title} at {company}\n\n"
        f"Here is your Career Match summary for {job_title} at {company}.\n\n"
        f"Overall fit score: {fit_score}/100\n"
        f"Recommendation: {recommendation}\n"
        f"Top strengths: {strengths}\n"
        f"Remaining gaps: {gaps}\n\n"
        f"Professional summary preview:\n{summary}\n\n"
        f"You can return to Career Match to review the full resume match, optimized resume, interview prep, and exports."
    )


def send_email_message(to_email: str, subject: str, body: str) -> tuple[bool, str]:
    if not email_configured():
        return False, "Email not configured."

    message = EmailMessage()
    message["From"] = from_email()
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(smtp_host(), int(smtp_port())) as server:
            server.starttls()
            server.login(smtp_user(), smtp_password())
            server.send_message(message)
        return True, "Email sent."
    except Exception as exc:
        return False, str(exc)
