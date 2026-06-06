import json
import os
import re
import secrets
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
from database.db import (
    AffiliateClickRecord,
    ApplicationRecord,
    AnalysisFeedback,
    ContactSubmission,
    PageViewRecord,
    PdfDownloadRecord,
    admin_metrics,
    authenticate_user,
    consume_password_reset_token,
    consume_email_verification_token,
    consume_assessment_credit,
    create_user,
    create_email_verification_token,
    create_password_reset_token,
    delete_application,
    delete_saved_resume,
    get_dashboard_metrics,
    get_assessment_access,
    get_database_diagnostics,
    get_saved_resume,
    get_user_id,
    get_user_profile,
    increment_free_assessment_usage,
    init_db,
    list_applications,
    list_contact_messages,
    list_feedback,
    list_saved_resumes,
    mark_saved_resume_used,
    open_beta_enabled,
    rename_saved_resume,
    save_application,
    save_analysis_feedback,
    save_affiliate_click,
    save_contact_submission,
    save_pdf_download,
    save_page_view,
    save_resume_stub,
    set_user_admin,
    update_contact_message_status,
    update_user_profile,
)
from prompts.templates import APP_DISCLAIMER
from services.analysis_service import compare_resume_to_job
from services.affiliate_service import build_learning_recommendations
from services.export_service import (
    build_full_report_docx,
    build_optimized_resume_docx,
    build_optimized_resume_pdf,
)
from services.email_service import build_results_summary_email, email_configured, get_email_diagnostics, send_email_message
from services.job_url_service import JobExtractionError, fetch_job_posting_from_url
from services.pdf_export_service import build_full_ai_review_pdf, build_tab_pdf
from services.billing_service import (
    cancel_subscription,
    create_billing_portal_session,
    create_credit_checkout_session,
    create_pro_checkout_session,
    get_billing_diagnostics,
    payments_configured,
)
from services.openai_service import generate_career_materials, is_demo_mode_api_key
from services.resume_coach_service import QUICK_PROMPTS, generate_resume_coach_response
from services.resume_builder_service import build_optimized_resume_package
from services.role_profile_service import build_active_role_profile, build_role_profile_fingerprint
from services.runtime_service import configure_logging, init_monitoring
from services.subscription_service import get_subscription_blueprint
from services.text_extractor import extract_text_from_upload


APP_VERSION = "v0.4.0-quality"
APP_NAME = "Career Match"
OPEN_BETA_BANNER = "Career Match is currently free during beta. We welcome feedback."
BUILD_TIMESTAMP = datetime.fromtimestamp(Path(__file__).stat().st_mtime).isoformat(sep=" ", timespec="seconds")
SEO_VIEWS = {"ats-checker", "resume-builder", "interview-prep", "cover-letter-generator", "linkedin-message-generator"}
VALID_VIEWS = {"home", "auth", "app", "contact", "privacy", "terms", "pro", "admin", *SEO_VIEWS}
BASE_APP_PAGES = ["Dashboard", "Workflow", "Analysis History", "My Resumes", "Pro", "Subscription", "Contact", "Privacy Policy", "Terms", "User Profile"]
ADMIN_VIEW = "admin"
DEFAULT_ADMIN_EMAILS = {"mrmoeve@gmail.com", "talisa.salvador@gmail.com"}


st.set_page_config(
    page_title=APP_NAME,
    page_icon="F",
    layout="wide",
)


BASE_DIR = Path(__file__).resolve().parent
EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)
LOG_DIR = BASE_DIR / "logs"
logger = configure_logging(LOG_DIR)
init_monitoring()


def _detect_local_app_status() -> dict:
    port = None
    try:
        configured_port = st.get_option("server.port")
        if configured_port:
            port = int(configured_port)
    except Exception:
        port = None

    if port is None:
        env_port = os.getenv("STREAMLIT_SERVER_PORT", "").strip()
        if env_port.isdigit():
            port = int(env_port)

    url = f"http://127.0.0.1:{port}" if port else ""
    warning = ""
    detail = ""

    try:
        result = subprocess.run(
            ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            check=False,
        )
        ports: list[int] = []
        for line in result.stdout.splitlines():
            if "Python" not in line and "streamlit" not in line.lower():
                continue
            match = re.search(r":(\d+)\s+\(LISTEN\)", line)
            if not match:
                continue
            candidate_port = int(match.group(1))
            if 8500 <= candidate_port <= 8999:
                ports.append(candidate_port)
        unique_ports = sorted(set(ports))
        if len(unique_ports) > 1:
            warning = f"Multiple local Streamlit-style ports detected: {', '.join(str(item) for item in unique_ports)}"
        elif not unique_ports:
            detail = "Use the URL printed in the terminal for this running instance."
    except Exception:
        detail = "Use the URL printed in the terminal for this running instance."

    if not url and not detail:
        detail = "Use the URL printed in the terminal for this running instance."

    return {"url": url, "warning": warning, "detail": detail}


def is_debug_visible() -> bool:
    app_env = os.getenv("APP_ENV", "production").strip().lower()
    return app_env == "development" or _user_is_admin()


def render_diagnostics_footer(app_status: dict) -> None:
    if not is_debug_visible():
        return
    db_diag = get_database_diagnostics()
    email_diag = get_email_diagnostics()
    admin_details = _admin_auth_details()
    st.divider()
    with st.expander("Diagnostics"):
        st.write(f"**App Version:** {APP_VERSION}")
        st.write(f"**Build Timestamp:** {BUILD_TIMESTAMP}")
        st.write(f"**Local URL:** {app_status.get('url') or 'Use the URL printed in the terminal for this running instance.'}")
        st.write(f"**Process ID:** {os.getpid()}")
        st.write(f"**Database Engine:** {db_diag.get('engine', 'unknown').title()} ({db_diag.get('target', 'n/a')})")
        st.write(f"**Current User Email:** {admin_details.get('email') or 'anonymous'}")
        st.write(f"**is_admin:** {admin_details.get('is_admin_flag', False)}")
        st.write(f"**Admin Authorized:** {admin_details.get('authorized', False)}")
        st.write(f"**Email Service:** {'Configured' if email_diag.get('configured') else 'Email not configured'}")
        if app_status.get("warning"):
            st.write(f"**Port Check:** {app_status['warning']}")
        elif app_status.get("detail"):
            st.write(f"**Port Check:** {app_status['detail']}")


def inject_pwa_support() -> None:
    st.html(
        """
        <script>
        (function() {
          const parentDoc = window.parent.document;
          const ensureLink = (rel, href) => {
            const existing = [...parentDoc.head.querySelectorAll(`link[rel="${rel}"]`)]
              .find(node => node.getAttribute("href") === href);
            if (existing) return;
            const link = parentDoc.createElement("link");
            link.rel = rel;
            link.href = href;
            parentDoc.head.appendChild(link);
          };
          const ensureMeta = (name, content) => {
            let meta = parentDoc.head.querySelector(`meta[name="${name}"]`);
            if (!meta) {
              meta = parentDoc.createElement("meta");
              meta.name = name;
              parentDoc.head.appendChild(meta);
            }
            meta.content = content;
          };
          ensureLink("manifest", "/manifest.webmanifest");
          ensureLink("apple-touch-icon", "/apple-touch-icon.png");
          ensureMeta("theme-color", "#0f172a");
          ensureMeta("apple-mobile-web-app-capable", "yes");
          ensureMeta("apple-mobile-web-app-status-bar-style", "default");
          if ("serviceWorker" in window.parent.navigator) {
            window.parent.navigator.serviceWorker.register("/sw.js").catch(() => {});
          }
        })();
        </script>
        """,
    )


def inject_theme_overrides() -> None:
    st.markdown(
        """
        <style>
        div[data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at top right, rgba(59, 130, 246, 0.10), transparent 28%),
                linear-gradient(180deg, #f8fbff 0%, #f6f9fc 100%);
        }
        div[data-testid="stHorizontalBlock"] div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #dbeafe;
            border-radius: 18px;
            padding: 0.75rem 1rem;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
        }
        div.stButton > button,
        div.stDownloadButton > button {
            border-radius: 999px;
            border: 1px solid #2563eb;
            background: linear-gradient(135deg, #2563eb 0%, #38bdf8 100%);
            color: #ffffff;
            font-weight: 600;
            box-shadow: 0 10px 28px rgba(37, 99, 235, 0.18);
        }
        div.stButton > button[kind="secondary"],
        div.stDownloadButton > button[kind="secondary"] {
            background: #ffffff;
            color: #1d4ed8;
        }
        div[data-baseweb="tab-list"] {
            gap: 0.3rem;
        }
        button[data-baseweb="tab"] {
            border-radius: 999px;
            border: 1px solid #dbeafe;
            background: #eff6ff;
            color: #1e3a8a;
            padding: 0.45rem 0.95rem;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, #1d4ed8 0%, #38bdf8 100%);
            color: #ffffff;
            border-color: #1d4ed8;
        }
        div[data-testid="stVerticalBlock"] div[data-testid="stExpander"] {
            border: 1px solid #dbeafe;
            border-radius: 16px;
            background: #ffffff;
        }
        .app-header-card {
            background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 68%, #38bdf8 100%);
            border-radius: 20px;
            padding: 0.9rem 1.1rem;
            color: #f8fafc;
            margin-bottom: 0.5rem;
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.18);
        }
        .app-header-card h1 {
            margin: 0;
            color: #ffffff;
            font-size: 1.5rem;
        }
        .app-header-card p {
            margin: 0.2rem 0 0 0;
            color: rgba(248, 250, 252, 0.92);
            font-size: 0.95rem;
        }
        .auth-shell {
            padding: 1.5rem 0 0.5rem 0;
        }
        .auth-hero {
            background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 58%, #38bdf8 100%);
            border-radius: 28px;
            padding: 2.4rem;
            color: #f8fafc;
            box-shadow: 0 24px 70px rgba(15, 23, 42, 0.2);
            margin-bottom: 1.2rem;
        }
        .auth-panel {
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid #dbeafe;
            border-radius: 24px;
            padding: 1rem;
            box-shadow: 0 18px 36px rgba(15, 23, 42, 0.08);
        }
        .page-card {
            background: #ffffff;
            border: 1px solid #dbeafe;
            border-radius: 20px;
            padding: 1rem 1.1rem;
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
            margin-bottom: 1rem;
        }
        .summary-hero {
            background: linear-gradient(135deg, #eff6ff 0%, #ffffff 55%, #f0f9ff 100%);
            border: 1px solid #bfdbfe;
            border-radius: 24px;
            padding: 1.2rem;
            box-shadow: 0 18px 38px rgba(15, 23, 42, 0.08);
            margin-bottom: 1rem;
        }
        .summary-eyebrow {
            color: #2563eb;
            font-size: 0.82rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .summary-score {
            font-size: 2.4rem;
            line-height: 1;
            font-weight: 800;
            color: #0f172a;
            margin: 0.35rem 0 0.25rem 0;
        }
        .summary-copy {
            color: #334155;
            margin: 0.15rem 0 0 0;
            line-height: 1.55;
        }
        .signal-chip {
            display: inline-block;
            padding: 0.36rem 0.72rem;
            border-radius: 999px;
            font-size: 0.88rem;
            font-weight: 700;
            margin: 0.2rem 0.4rem 0.2rem 0;
        }
        .signal-good {
            background: #dcfce7;
            color: #166534;
            border: 1px solid #86efac;
        }
        .signal-warn {
            background: #fef3c7;
            color: #92400e;
            border: 1px solid #fcd34d;
        }
        .signal-bad {
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fca5a5;
        }
        .mini-card {
            background: #ffffff;
            border: 1px solid #dbeafe;
            border-radius: 18px;
            padding: 0.95rem 1rem;
            box-shadow: 0 10px 26px rgba(15, 23, 42, 0.05);
            height: 100%;
        }
        .mini-card h4 {
            margin: 0 0 0.55rem 0;
            color: #0f172a;
            font-size: 1rem;
        }
        .mini-card ul {
            margin: 0;
            padding-left: 1.15rem;
            color: #334155;
        }
        .mini-card li {
            margin-bottom: 0.38rem;
        }
        .summary-label {
            color: #475569;
            font-size: 0.88rem;
            font-weight: 600;
            margin-bottom: 0.2rem;
        }
        .summary-value {
            color: #0f172a;
            font-size: 1.2rem;
            font-weight: 800;
            margin-bottom: 0.45rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _recommendation_signal(recommendation: str) -> str:
    value = (recommendation or "").strip().lower()
    if "apply immediately" in value:
        return "good"
    if "stretch" in value:
        return "warn"
    if "low probability" in value or "not recommended" in value:
        return "bad"
    return "warn"


def _score_signal(score: int) -> str:
    if score >= 75:
        return "good"
    if score >= 50:
        return "warn"
    return "bad"


def _signal_chip(label: str, tone: str) -> str:
    tone_class = {"good": "signal-good", "warn": "signal-warn", "bad": "signal-bad"}.get(tone, "signal-warn")
    return f'<span class="signal-chip {tone_class}">{label}</span>'


def _top_gaps(analysis: dict) -> list[str]:
    job_fit = analysis.get("job_fit", {}) or {}
    role_gap = analysis.get("role_gap_analysis", {}) or {}
    candidates = (
        job_fit.get("missing_required_skills", [])
        + role_gap.get("missing_competencies", [])
        + analysis.get("missing_keywords", [])
        + analysis.get("gaps", [])
    )
    seen: set[str] = set()
    results: list[str] = []
    for item in candidates:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append(text)
        if len(results) == 3:
            break
    return results or ["No material gaps were identified from the current resume and job description."]


def _top_strengths(analysis: dict) -> list[str]:
    candidates = analysis.get("role_specific_strengths", []) + analysis.get("hiring_manager_view", [])
    seen: set[str] = set()
    results: list[str] = []
    for item in candidates:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append(text)
        if len(results) == 3:
            break
    return results or ["The resume shows credible transferable strengths that can be positioned more clearly for this role."]


def _recommended_next_actions(analysis: dict) -> list[str]:
    job_fit = analysis.get("job_fit", {}) or {}
    role_gap = analysis.get("role_gap_analysis", {}) or {}
    missing_required = job_fit.get("missing_required_skills", [])[:2]
    reposition = role_gap.get("resume_repositioning", [])[:1]
    actions: list[str] = []
    if missing_required:
        actions.append(f"Address the most visible gap first: {', '.join(missing_required)}.")
    if reposition:
        actions.append(reposition[0])
    if analysis.get("match_reasoning"):
        actions.append("Lead interviews with the strongest evidence-backed examples from your resume.")
    if analysis.get("overall_interview_potential", 0) >= 60:
        actions.append("Apply if the role is attractive, but position your transferable experience early.")
    return actions[:3] or ["Use the Resume Builder to sharpen role language before applying."]


def _ats_improvement_opportunities(analysis: dict) -> list[str]:
    missing = analysis.get("missing_keywords", [])[:3]
    role_gap = analysis.get("role_gap_analysis", {}) or {}
    suggestions = []
    for item in missing:
        suggestions.append(f"Add resume-backed language for {item} where your experience already supports it.")
    for item in role_gap.get("resume_repositioning", []):
        if item not in suggestions:
            suggestions.append(item)
        if len(suggestions) >= 3:
            break
    return suggestions[:3] or ["The biggest ATS gains will come from clearer role-specific wording, not more keywords."]


def _current_learning_recommendations() -> list[dict]:
    analysis = st.session_state.get("analysis") or {}
    if not analysis or not st.session_state.get("last_application_id"):
        return []
    return build_learning_recommendations(analysis)


def _record_affiliate_click(recommendation: dict) -> None:
    url = (recommendation.get("affiliate_url") or "").strip()
    if not url:
        return
    save_affiliate_click(
        AffiliateClickRecord(
            user_email=st.session_state.get("user_email", ""),
            assessment_id=int(st.session_state.get("last_application_id", 0) or 0),
            recommendation_name=recommendation.get("title", ""),
            recommendation_category=recommendation.get("category", ""),
            provider=recommendation.get("provider", ""),
            affiliate_url=url,
            clicked_at=datetime.now().isoformat(timespec="seconds"),
        )
    )
    logger.info(
        "Affiliate resource clicked. current_user_email=%s assessment_id=%s recommendation=%s category=%s provider=%s",
        st.session_state.get("user_email", "") or "anonymous",
        st.session_state.get("last_application_id", 0),
        recommendation.get("title", ""),
        recommendation.get("category", ""),
        recommendation.get("provider", ""),
    )


def render_learning_resources_section(key_prefix: str = "match") -> None:
    recommendations = _current_learning_recommendations()
    if not recommendations:
        logger.info(
            "Affiliate recommendations render skipped. affiliate_cards_rendered=%s recommendation_count=%s recommendation_categories=%s section=%s",
            False,
            0,
            [],
            key_prefix,
        )
        return
    logger.info(
        "Affiliate recommendations rendered. affiliate_cards_rendered=%s recommendation_count=%s recommendation_categories=%s section=%s",
        True,
        len(recommendations),
        [item.get("category", "") for item in recommendations],
        key_prefix,
    )
    st.write("**Recommended Learning Resources**")
    st.caption("Some resources may use affiliate links. Recommendations are based on your assessment gaps.")
    for index, recommendation in enumerate(recommendations, start=1):
        st.markdown(
            f"""
            <div class="mini-card">
                <h4>{recommendation.get('title', '')}</h4>
                <p class="summary-copy"><strong>Provider:</strong> {recommendation.get('provider', '')}</p>
                <p class="summary-copy"><strong>Skill addressed:</strong> {recommendation.get('skill_addressed', '')}</p>
                <p class="summary-copy">{recommendation.get('description', '')}</p>
                <p class="summary-copy"><strong>Why recommended:</strong> {recommendation.get('why_recommended', '')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        button_key = f"{key_prefix}_affiliate_resource_{recommendation.get('category', '')}_{index}"
        if recommendation.get("available"):
            if st.button(recommendation.get("button_label", "View Resource"), key=button_key):
                _record_affiliate_click(recommendation)
                safe_url = json.dumps(recommendation.get("affiliate_url", ""))
                st.html(f"<script>window.parent.open({safe_url}, '_blank');</script>")
                st.success("Opening resource in a new tab.")
        else:
            st.button(recommendation.get("button_label", "Resource coming soon"), key=button_key, disabled=True)


def _recruiter_likelihood_label(analysis: dict) -> tuple[str, int]:
    direct_score = int(analysis.get("direct_match_score", 0) or 0)
    transferable_score = int(analysis.get("transferable_match_score", 0) or 0)
    interview_score = int(analysis.get("overall_interview_potential", 0) or 0)
    estimated = round(direct_score * 0.25 + transferable_score * 0.35 + interview_score * 0.40)
    if estimated >= 75:
        label = "High"
    elif estimated >= 55:
        label = "Moderate"
    else:
        label = "Low"
    return label, estimated


def _render_bullet_html(items: list[str]) -> str:
    if not items:
        items = ["None identified."]
    bullet_items = "".join(f"<li>{item}</li>" for item in items[:3])
    return f"<ul>{bullet_items}</ul>"


def _normalize_view(value: str) -> str:
    return value if value in VALID_VIEWS else "home"


def _current_view() -> str:
    view_value = st.query_params.get("view", st.session_state.get("current_view", "home"))
    if isinstance(view_value, list):
        view_value = view_value[0] if view_value else "home"
    return _normalize_view(str(view_value))


def _set_view(view: str) -> None:
    normalized = _normalize_view(view)
    st.session_state["current_view"] = normalized
    if normalized == "home":
        try:
            st.query_params.clear()
        except Exception:
            st.query_params["view"] = normalized
    else:
        st.query_params["view"] = normalized


def _log_in_user(email: str) -> None:
    st.session_state["is_authenticated"] = True
    st.session_state["user_email"] = (email or "").strip().lower()
    st.session_state["app_page"] = "Workflow"
    _set_view("app")


def _log_out_user() -> None:
    st.session_state["is_authenticated"] = False
    st.session_state["user_email"] = ""
    st.session_state["app_page"] = "Workflow"
    st.session_state["auth_notice"] = "You have been logged out."
    _set_view("home")


def _assessment_access() -> dict:
    return get_assessment_access(st.session_state.get("user_email", ""))


def _subscription_is_active() -> bool:
    if open_beta_enabled():
        return True
    return _assessment_access().get("is_pro", False)


def _admin_emails() -> set[str]:
    raw = os.getenv("ADMIN_EMAILS", "")
    emails = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return emails | DEFAULT_ADMIN_EMAILS


def _user_is_admin() -> bool:
    email = st.session_state.get("user_email", "").strip().lower()
    if not email:
        return False
    if email in _admin_emails():
        return True
    profile = get_user_profile(email) or {}
    return bool(profile.get("is_admin", 0))


def _admin_auth_details() -> dict:
    email = st.session_state.get("user_email", "").strip().lower()
    profile = get_user_profile(email) or {} if email else {}
    flag_value = bool(profile.get("is_admin", 0))
    allowlisted = email in _admin_emails() if email else False
    authorized = bool(email) and (allowlisted or flag_value)
    return {
        "email": email,
        "is_admin_flag": flag_value,
        "allowlisted": allowlisted,
        "authorized": authorized,
    }


def _app_pages() -> list[str]:
    pages = list(BASE_APP_PAGES)
    if _user_is_admin() and "Admin" not in pages:
        pages.append("Admin")
    return pages


def _bootstrap_admin_access() -> None:
    for email in _admin_emails():
        if not email:
            continue
        profile = get_user_profile(email)
        if profile and not profile.get("is_admin", 0):
            logger.info("Promoting bootstrap admin user. email=%s", email)
            set_user_admin(email, True)


def _email_delivery_configured() -> bool:
    return email_configured()


def _rate_limit_allows_analysis() -> bool:
    if open_beta_enabled():
        return True
    timestamps = st.session_state.get("analysis_rate_timestamps", [])
    now = datetime.now()
    fresh = [item for item in timestamps if (now - item).total_seconds() < 60]
    st.session_state["analysis_rate_timestamps"] = fresh
    if len(fresh) >= 5:
        return False
    fresh.append(now)
    st.session_state["analysis_rate_timestamps"] = fresh
    return True


def _admin_test_mode_enabled() -> bool:
    return bool(_user_is_admin() and st.session_state.get("admin_test_mode", True))


def _ensure_admin_test_mode_for_admin() -> bool:
    if _user_is_admin():
        st.session_state["admin_test_mode"] = True
        return True
    return False


def _record_successful_assessment() -> None:
    if not st.session_state.get("is_authenticated"):
        return
    if _admin_test_mode_enabled():
        return
    if open_beta_enabled():
        return
    access = _assessment_access()
    email = st.session_state.get("user_email", "")
    if access.get("is_pro"):
        return
    if access.get("credits", 0) > 0:
        consume_assessment_credit(email)
        return
    increment_free_assessment_usage(email)


def _current_payment_type_used() -> str:
    if _admin_test_mode_enabled():
        return "admin_test"
    if open_beta_enabled():
        return "beta"
    access = _assessment_access()
    if access.get("is_pro"):
        return "pro"
    if access.get("credits", 0) > 0:
        return "credit"
    return "free"


def _payment_type_label(value: str) -> str:
    mapping = {
        "beta": "Open Beta",
        "free": "Free",
        "credit": "Credit",
        "pro": "Pro",
        "admin_test": "Admin Test",
    }
    return mapping.get((value or "").strip().lower(), (value or "free").replace("_", " ").title())


def _send_to_pro_page() -> None:
    if st.session_state.get("is_authenticated"):
        st.session_state["app_page"] = "Pro"
        _set_view("app")
    else:
        _set_view("pro")


def _checkout_status_notice() -> None:
    status = st.query_params.get("checkout", "")
    if isinstance(status, list):
        status = status[0] if status else ""
    if status == "success":
        st.success("Stripe checkout completed. Your plan status will update as soon as the payment confirmation is received.")
    elif status == "canceled":
        st.info("Stripe checkout was canceled. You can return any time to upgrade.")


def _start_checkout(product_type: str) -> None:
    if not st.session_state.get("is_authenticated"):
        st.session_state["auth_notice"] = "Create an account or sign in before starting checkout."
        st.session_state["auth_mode"] = "login"
        _set_view("auth")
        st.rerun()

    user_id = get_user_id(st.session_state.get("user_email", ""))
    if product_type == "pro":
        checkout = create_pro_checkout_session(user_id)
        state_key = "pro_checkout_url"
    else:
        checkout = create_credit_checkout_session(user_id)
        state_key = "credit_checkout_url"

    diagnostics = get_billing_diagnostics()
    st.session_state["last_checkout_exception"] = diagnostics.get("last_checkout_exception", "")

    if checkout.get("ok") and checkout.get("checkout_url"):
        st.session_state[state_key] = checkout["checkout_url"]
        st.success(checkout.get("message", "Stripe Checkout is ready."))
    else:
        st.session_state[state_key] = ""
        st.error(checkout.get("message", "Unable to start checkout."))


def _open_billing_portal() -> None:
    result = create_billing_portal_session(st.session_state.get("user_email", ""))
    if result.get("ok") and result.get("portal_url"):
        st.session_state["billing_portal_url"] = result["portal_url"]
        st.success(result.get("message", "Billing portal ready."))
    else:
        st.error(result.get("message", "Unable to open the billing portal."))


def _can_run_analysis() -> tuple[bool, str]:
    if not st.session_state.get("is_authenticated"):
        return False, "Sign in to start an analysis."
    if open_beta_enabled():
        return True, ""
    if _admin_test_mode_enabled():
        return True, ""
    access = _assessment_access()
    if access.get("is_pro"):
        return True, ""
    if access.get("credits", 0) > 0:
        return True, ""
    if access.get("remaining", 0) > 0:
        return True, ""
    return False, "paywall"


def render_beta_banner() -> None:
    if open_beta_enabled():
        st.info(OPEN_BETA_BANNER)


def render_waitlist_section(source: str = "general") -> None:
    st.write("**Join Waitlist**")
    st.caption("Join the waitlist to hear about future premium features, early access, and private beta experiments.")
    default_profile = get_user_profile(st.session_state.get("user_email", "")) or {}
    with st.form(f"waitlist_form_{source}", clear_on_submit=True):
        waitlist_name = st.text_input("Name", value=default_profile.get("full_name", ""), key=f"waitlist_name_{source}")
        waitlist_email = st.text_input("Email", value=st.session_state.get("user_email", ""), key=f"waitlist_email_{source}")
        interests = st.text_area(
            "What premium features would you want most?",
            height=100,
            key=f"waitlist_interest_{source}",
            placeholder="Examples: team seats, recruiter reviews, branded exports, deeper analytics.",
        )
        submitted = st.form_submit_button("Join Waitlist", use_container_width=True)
    if submitted:
        submission = ContactSubmission(
            created_at=datetime.now().isoformat(timespec="seconds"),
            user_id=get_user_id((waitlist_email or "").strip().lower()) if (waitlist_email or "").strip() else 0,
            user_email=(waitlist_email or "").strip().lower(),
            name=waitlist_name.strip(),
            message_type="Waitlist",
            message=(interests.strip() or "Interested in future premium features."),
            status="new",
        )
        save_contact_submission(submission)
        st.success("You’re on the waitlist. Thanks for helping shape Career Match.")


def render_landing_page() -> None:
    render_beta_banner()
    st.markdown(
        """
        <style>
        .landing-shell {
            padding: 2rem 0 1rem 0;
        }
        .hero-card {
            background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 58%, #38bdf8 100%);
            border-radius: 28px;
            padding: 3rem;
            color: #f8fafc;
            box-shadow: 0 30px 80px rgba(15, 23, 42, 0.24);
            overflow: hidden;
            position: relative;
        }
        .hero-card::after {
            content: "";
            position: absolute;
            inset: auto -4rem -5rem auto;
            width: 220px;
            height: 220px;
            border-radius: 999px;
            background: rgba(255,255,255,0.14);
            filter: blur(1px);
        }
        .eyebrow {
            display: inline-block;
            padding: 0.45rem 0.8rem;
            background: rgba(255,255,255,0.14);
            border: 1px solid rgba(255,255,255,0.18);
            border-radius: 999px;
            font-size: 0.9rem;
            letter-spacing: 0.02em;
            margin-bottom: 1rem;
        }
        .hero-title {
            font-size: clamp(2rem, 5vw, 3.8rem);
            line-height: 1.05;
            font-weight: 700;
            margin: 0 0 1rem 0;
        }
        .hero-copy {
            max-width: 52rem;
            font-size: 1.1rem;
            line-height: 1.7;
            color: rgba(248, 250, 252, 0.92);
            margin-bottom: 1.5rem;
        }
        .section-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1rem;
            margin-top: 1.5rem;
        }
        .section-card {
            background: #ffffff;
            border: 1px solid #dbe4f0;
            border-radius: 22px;
            padding: 1.25rem;
            box-shadow: 0 14px 35px rgba(15, 23, 42, 0.08);
            height: 100%;
        }
        .section-card h3 {
            margin-top: 0;
            margin-bottom: 0.5rem;
            color: #0f172a;
            font-size: 1.05rem;
        }
        .section-card p, .section-card li {
            color: #334155;
            line-height: 1.6;
        }
        .section-title {
            font-size: 1.55rem;
            font-weight: 700;
            margin: 2.5rem 0 0.8rem 0;
            color: #0f172a;
        }
        .trust-list, .footer-links {
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-top: 1rem;
        }
        .pill {
            padding: 0.65rem 0.9rem;
            border-radius: 999px;
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            color: #1e3a8a;
            font-size: 0.95rem;
        }
        .footer-links a {
            color: #1d4ed8;
            text-decoration: none;
            font-weight: 600;
        }
        </style>
        <div class="landing-shell">
          <div class="hero-card">
            <div class="eyebrow">Career Match</div>
            <h1 class="hero-title">Career Match</h1>
            <p class="hero-copy">Match your resume to any job and understand exactly where you stand.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## How It Works")
    how_cols = st.columns(3)
    how_steps = [
        ("Step 1: Upload Resume", "Upload your resume in PDF, DOCX, or TXT format."),
        ("Step 2: Add Job Posting URL", "Paste a job URL or use the manual fallback when a job board blocks extraction."),
        ("Step 3: Generate Resume Match, Interview Prep, and Career Insights", "Review fit analysis, resume rewriting, interview preparation, and evidence-backed recommendations."),
    ]
    for column, (title, body) in zip(how_cols, how_steps):
        with column:
            st.markdown(f"<div class='section-card'><h3>{title}</h3><p>{body}</p></div>", unsafe_allow_html=True)

    st.markdown("## Features")
    st.markdown(
        """
        <div class="section-grid">
          <div class="section-card"><h3>Resume Match Analysis</h3><p>Measure direct fit, transferable fit, and interview potential from your current resume.</p></div>
          <div class="section-card"><h3>ATS Optimization</h3><p>Improve keyword alignment while keeping every recommendation grounded in resume evidence.</p></div>
          <div class="section-card"><h3>Resume Builder</h3><p>Generate a full optimized resume without inventing employers, dates, or unsupported tools.</p></div>
          <div class="section-card"><h3>Interview Intelligence</h3><p>Prepare with likely questions, STAR answers, technical prompts, and challenge handling.</p></div>
          <div class="section-card"><h3>Career Coach</h3><p>Get role-gap analysis, improvement plans, and guidance on how to bridge missing competencies.</p></div>
          <div class="section-card"><h3>Cover Letter Generator</h3><p>Create targeted outreach materials based on your actual employers and accomplishments.</p></div>
          <div class="section-card"><h3>LinkedIn Outreach Messages</h3><p>Draft concise recruiter introductions aligned to the target opportunity.</p></div>
          <div class="section-card"><h3>Thank You Emails</h3><p>Generate polished post-interview follow-up messages in seconds.</p></div>
          <div class="section-card"><h3>Evidence-Based Recommendations</h3><p>See why each change was suggested and what resume evidence supports it.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## Why Users Trust It")
    st.markdown(
        """
        <div class="trust-list">
          <span class="pill">Resume-backed recommendations</span>
          <span class="pill">Evidence validation</span>
          <span class="pill">Trust Score</span>
          <span class="pill">Transferable skills analysis</span>
          <span class="pill">Recruiter-style fit scoring</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## Open Beta")
    pricing_cols = st.columns(3)
    pricing_cards = [
        ("Resume Analyses", "Free", ["Unlimited analyses during beta"]),
        ("PDF Exports", "Free", ["Unlimited downloads during beta"]),
        ("Job Evaluations", "Free", ["Unlimited job URL and manual fallback evaluations"]),
    ]
    for column, (title, price, bullets) in zip(pricing_cols, pricing_cards):
        with column:
            st.markdown(
                f"<div class='section-card'><h3>{title}</h3><p><strong>{price}</strong></p><p>{'<br/>'.join(bullets)}</p></div>",
                unsafe_allow_html=True,
            )

    st.markdown("## FAQ")
    faq_items = {
        "How does Career Match work?": "Upload your resume, add a job posting, and Career Match compares the two before generating tailored materials.",
        "Does Career Match rewrite my resume?": "Yes, but only using evidence already present in your uploaded resume.",
        "Is Career Match free right now?": "Yes. Career Match is currently free during beta, including analyses, exports, and job evaluations.",
        "Will premium features exist later?": "Yes. We’re collecting waitlist interest and feedback now so future premium features solve the right problems.",
        "Is my resume stored?": "Career Match may store resume text, history, feedback, and generated outputs to support your account workflow.",
        "Can I delete my data?": "You can submit a deletion request through the Contact page.",
    }
    for question, answer in faq_items.items():
        with st.expander(question):
            st.write(answer)

    st.markdown("## Start")
    cta_col, waitlist_cta_col = st.columns(2)
    with cta_col:
        if st.button("Start Free Analysis", type="primary", use_container_width=True):
            if st.session_state.get("is_authenticated"):
                _set_view("app")
            else:
                st.session_state["auth_mode"] = "register"
                _set_view("auth")
            st.rerun()
    with waitlist_cta_col:
        st.caption("Want future premium features?")
        if st.button("Join Future Features Waitlist", use_container_width=True):
            _set_view("pro")
            st.rerun()

    render_waitlist_section("landing")

    st.markdown("## Privacy Policy")
    st.caption("Your files and generated materials stay within the deployed application environment and local application history database configured for this service.")
    st.markdown("## Terms of Service")
    st.caption("Use Career Match as a decision-support tool. Review all generated materials before submitting them to employers.")
    st.markdown("## Contact")
    st.caption("Contact your deployment administrator or product owner for support, privacy questions, or access requests.")
    footer_cols = st.columns(4)
    with footer_cols[0]:
        if st.button("Privacy Policy", key="landing_privacy", use_container_width=True):
            _set_view("privacy")
            st.rerun()
    with footer_cols[1]:
        if st.button("Terms of Service", key="landing_terms", use_container_width=True):
            _set_view("terms")
            st.rerun()
    with footer_cols[2]:
        if st.button("Contact", key="landing_contact", use_container_width=True):
            _set_view("contact")
            st.rerun()
    with footer_cols[3]:
        if st.button("Career Match Pro", key="landing_pro", use_container_width=True):
            _set_view("pro")
            st.rerun()

    st.markdown("## Explore More")
    seo_cols = st.columns(5)
    seo_pages = [
        ("ATS Checker", "ats-checker"),
        ("Resume Builder", "resume-builder"),
        ("Interview Prep", "interview-prep"),
        ("Cover Letter Generator", "cover-letter-generator"),
        ("LinkedIn Message Generator", "linkedin-message-generator"),
    ]
    for column, (label, view_name) in zip(seo_cols, seo_pages):
        with column:
            if st.button(label, key=f"seo_{view_name}", use_container_width=True):
                _set_view(view_name)
                st.rerun()


def render_seo_page(view_name: str) -> None:
    page_content = {
        "ats-checker": (
            "ATS Resume Checker",
            "See how well your resume matches a target job before you apply.",
            "Upload your resume, add a job posting, and Career Match shows ATS alignment, direct fit, transferable fit, and remaining gaps.",
        ),
        "resume-builder": (
            "AI Resume Builder",
            "Turn your uploaded resume into a clearer, stronger job-targeted version.",
            "Career Match rewrites your summary and bullets using only resume-backed evidence, then shows ATS before vs after and remaining gaps.",
        ),
        "interview-prep": (
            "Interview Prep Generator",
            "Prepare faster with recruiter-style interview intelligence.",
            "Get likely questions, STAR answers, challenge handling, and role-specific talking points tied to your actual resume.",
        ),
        "cover-letter-generator": (
            "Cover Letter Generator",
            "Generate a role-targeted cover letter from your actual background.",
            "Career Match references your real employers, accomplishments, and transferable strengths instead of generic filler.",
        ),
        "linkedin-message-generator": (
            "LinkedIn Message Generator",
            "Create concise recruiter outreach messages tailored to a target job.",
            "Use your resume and the job posting to generate professional LinkedIn outreach that stays aligned to your real experience.",
        ),
    }
    title, subtitle, body = page_content.get(
        view_name,
        ("Career Match", "Match your resume to any job and understand exactly where you stand.", ""),
    )
    st.markdown(
        f"""
        <div class="landing-shell">
          <div class="hero-card">
            <div class="eyebrow">Career Match</div>
            <h1 class="hero-title">{title}</h1>
            <p class="hero-copy">{subtitle}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write(body)
    st.write("Career Match helps you understand direct fit, transferable fit, interview potential, and the strongest evidence already in your resume.")
    st.write("Pricing")
    st.write("- Free: 1 assessment")
    st.write("- One-Time: $4.99 per additional assessment")
    st.write("- Pro: $19/month unlimited")
    if st.button("Start Free Analysis", key=f"cta_{view_name}", type="primary", use_container_width=True):
        if st.session_state.get("is_authenticated"):
            _set_view("app")
        else:
            st.session_state["auth_mode"] = "register"
            _set_view("auth")
        st.rerun()


def init_state() -> None:
    defaults = {
        "resume_text": "",
        "job_text": "",
        "resume_filename": "",
        "job_filename": "",
        "job_url": "",
        "job_title_preview": "",
        "company_name_preview": "",
        "job_location_preview": "",
        "job_date_posted_preview": "",
        "job_category_preview": "",
        "job_extraction_confidence": 0,
        "job_extraction_error": "",
        "manual_job_text": "",
        "manual_title": "",
        "manual_company": "",
        "manual_location": "",
        "optimized_resume_text": "",
        "analysis": None,
        "generated": None,
        "application_saved": False,
        "demo_mode": is_demo_mode_api_key(),
        "current_view": "home",
        "auth_mode": "login",
        "auth_notice": "",
        "is_authenticated": False,
        "user_email": "",
        "app_page": "Workflow",
        "last_application_id": 0,
        "feedback_submitted_for_analysis": False,
        "last_saved_resume_signature": "",
        "analysis_rate_timestamps": [],
        "pro_checkout_url": "",
        "credit_checkout_url": "",
        "billing_portal_url": "",
        "last_checkout_exception": "",
        "session_id": "",
        "page_view_tracker": {},
        "admin_test_mode": True,
        "resume_coach_messages": [],
        "resume_coach_prompt_input": "",
        "resume_coach_logged_opened": False,
        "active_role_fingerprint": "",
        "active_role_profile": {},
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    if not st.session_state.get("session_id"):
        st.session_state["session_id"] = secrets.token_urlsafe(12)


def _application_payload() -> dict:
    return {
        "analysis": st.session_state.get("analysis"),
        "generated": st.session_state.get("generated"),
    }


def _reset_analysis_outputs(reason: str) -> None:
    logger.info("Resetting cached analysis outputs. reason=%s", reason)
    st.session_state["analysis"] = None
    st.session_state["generated"] = None
    st.session_state["optimized_resume_text"] = ""
    st.session_state["application_saved"] = False
    st.session_state["last_application_id"] = 0
    st.session_state["feedback_submitted_for_analysis"] = False
    st.session_state["resume_coach_messages"] = []
    st.session_state["resume_coach_prompt_input"] = ""
    st.session_state["resume_coach_logged_opened"] = False


def _sync_active_role_profile() -> None:
    job_title = st.session_state.get("job_title_preview", "") or st.session_state.get("manual_title", "")
    job_text = st.session_state.get("job_text", "") or st.session_state.get("manual_job_text", "")
    if not job_text.strip():
        st.session_state["active_role_profile"] = {}
        st.session_state["active_role_fingerprint"] = ""
        return
    role_profile = build_active_role_profile(job_title, job_text)
    fingerprint = build_role_profile_fingerprint(job_title or role_profile.get("display_name", ""), job_text)
    previous = st.session_state.get("active_role_fingerprint", "")
    if previous and previous != fingerprint:
        _reset_analysis_outputs("role_profile_changed")
    st.session_state["active_role_profile"] = role_profile
    st.session_state["active_role_fingerprint"] = fingerprint


def _save_current_application() -> None:
    analysis = st.session_state.get("analysis") or {}
    generated = st.session_state.get("generated") or {}
    if not analysis or not generated:
        return

    record = ApplicationRecord(
        user_email=st.session_state.get("user_email", ""),
        created_at=datetime.now().isoformat(timespec="seconds"),
        original_resume_text=st.session_state.get("resume_text", ""),
        optimized_resume_text=generated.get("resume_builder", {}).get("optimized_resume_text", ""),
        original_ats_score=int(analysis.get("ats_score", 0)),
        optimized_ats_score=int(generated.get("resume_builder", {}).get("optimized_ats_score", 0)),
        company_name=analysis.get("company_name", "Unknown"),
        job_title=analysis.get("job_title", "Target Role"),
        job_url=st.session_state.get("job_url", ""),
        job_location=st.session_state.get("job_location_preview", ""),
        job_date_posted=st.session_state.get("job_date_posted_preview", ""),
        job_category=st.session_state.get("job_category_preview", ""),
        resume_text=st.session_state.get("resume_text", ""),
        job_description_text=st.session_state.get("job_text", ""),
        ats_score=int(analysis.get("ats_score", 0)),
        payment_type_used=_current_payment_type_used(),
        is_admin_test=1 if _admin_test_mode_enabled() else 0,
        payload_json=json.dumps(_application_payload(), ensure_ascii=True),
    )
    application_id = save_application(record)
    st.session_state["last_application_id"] = application_id
    st.session_state["application_saved"] = True
    st.session_state["feedback_submitted_for_analysis"] = False


def _extract_resume_candidate_name(resume_text: str) -> str:
    for line in (resume_text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if "@" in stripped or "|" in stripped:
            continue
        return stripped
    return "Candidate"


def _exact_keyword_matches(analysis: dict) -> list[str]:
    exact_matches = analysis.get("matching_keywords", []) or analysis.get("matching_skills", []) or []
    deduped: list[str] = []
    seen: set[str] = set()
    for item in exact_matches:
        cleaned = str(item).strip()
        lowered = cleaned.lower()
        if cleaned and lowered not in seen:
            deduped.append(cleaned)
            seen.add(lowered)
    return deduped


def _semantic_skill_matches(analysis: dict) -> list[dict]:
    semantic_matches: list[dict] = []
    for item in analysis.get("competency_scores", []) or []:
        confidence = int(item.get("score", 0) or 0)
        direct_score = int(item.get("direct_score", 0) or 0)
        transferable_score = int(item.get("transferable_score", 0) or 0)
        matched_terms = item.get("matched", []) or []
        if confidence <= 0 and not matched_terms:
            continue
        if confidence < 25 and not matched_terms:
            continue
        semantic_matches.append(
            {
                "skill": item.get("competency", "Competency"),
                "confidence": confidence,
                "direct_score": direct_score,
                "transferable_score": transferable_score,
                "matched_terms": matched_terms,
            }
        )
    semantic_matches.sort(key=lambda payload: (-payload["confidence"], payload["skill"]))
    return semantic_matches


def _render_term_detail_block(title: str, details: list[dict]) -> None:
    st.write(f"**{title}**")
    if not details:
        st.write("None identified")
        return
    for item in details:
        st.write(f"- {item.get('term', '')}")
        st.write(f"  Source resume evidence: {item.get('source_resume_evidence', 'No evidence found.')}")
        exact_line = item.get("exact_resume_line", "")
        if exact_line:
            st.write(f"  Exact resume line: {exact_line}")
        st.write(f"  Support level: {item.get('support_level', 'Unknown')}")


def _render_role_match_snapshot(analysis: dict, heading: str = "Recruiter Summary Card") -> None:
    if not analysis:
        return
    recruiter_summary = analysis.get("recruiter_style_summary", {}) or {}
    score_consistency = analysis.get("score_consistency", {}) or {}
    level_alignment = analysis.get("compensation_level_alignment", {}) or {}
    st.write(f"**{heading}**")
    snapshot_left, snapshot_mid, snapshot_right, snapshot_far_right = st.columns(4, gap="large")
    with snapshot_left:
        st.markdown(
            f"""
            <div class="mini-card">
                <h4>Best Case Recruiter Read</h4>
                <p>{recruiter_summary.get('best_case_recruiter_read', 'Not available')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with snapshot_mid:
        st.markdown(
            f"""
            <div class="mini-card">
                <h4>Worst Case Recruiter Read</h4>
                <p>{recruiter_summary.get('worst_case_recruiter_read', 'Not available')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with snapshot_right:
        st.markdown(
            f"""
            <div class="mini-card">
                <h4>Most Important Fix</h4>
                <p>{recruiter_summary.get('most_important_fix_before_applying', 'Not available')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with snapshot_far_right:
        st.markdown(
            f"""
            <div class="mini-card">
                <h4>Level Alignment</h4>
                <p>{level_alignment.get('label', 'Moderate Alignment')}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    if score_consistency.get("warning"):
        st.warning(score_consistency.get("warning", ""))
        if score_consistency.get("explanation"):
            st.write(f"Reason: {score_consistency.get('explanation', '')}")


def _hydrate_saved_analysis(item: dict, saved_analysis: dict | None) -> dict:
    analysis = dict(saved_analysis or {})
    resume_text = (
        item.get("original_resume_text")
        or item.get("resume_text")
        or st.session_state.get("resume_text", "")
    )
    job_text = item.get("job_description_text") or st.session_state.get("job_text", "")

    if resume_text and job_text:
        try:
            analysis = compare_resume_to_job(resume_text, job_text)
            logger.info(
                "Historical analysis backfilled with current compare pipeline. application_id=%s resume_text_exists=%s job_text_exists=%s",
                item.get("id", 0),
                bool(resume_text),
                bool(job_text),
            )
        except Exception:
            logger.exception(
                "Unable to rehydrate saved analysis from stored resume/job text. Falling back to saved payload. application_id=%s",
                item.get("id", 0),
            )
            analysis = dict(saved_analysis or {})
    else:
        logger.info(
            "Historical analysis backfill skipped due to missing source text. application_id=%s resume_text_exists=%s job_text_exists=%s",
            item.get("id", 0),
            bool(resume_text),
            bool(job_text),
        )

    if item.get("job_title"):
        analysis["job_title"] = item.get("job_title", analysis.get("job_title", "Target Role"))
    if item.get("company_name"):
        analysis["company_name"] = item.get("company_name", analysis.get("company_name", "Unknown"))
    return analysis


def _generated_role_fingerprint(generated: dict) -> str:
    return (
        generated.get("role_profile_fingerprint", "")
        or generated.get("resume_builder", {}).get("role_profile_fingerprint", "")
    )


def _generated_matches_analysis(analysis: dict, generated: dict) -> bool:
    analysis_fingerprint = analysis.get("role_profile_fingerprint", "")
    generated_fingerprint = _generated_role_fingerprint(generated)
    return bool(analysis_fingerprint and generated_fingerprint and analysis_fingerprint == generated_fingerprint)


def _rebuild_generated_outputs(resume_text: str, job_text: str, analysis: dict) -> dict:
    generated = generate_career_materials(
        resume_text=resume_text,
        job_description_text=job_text,
        analysis=analysis,
    )
    generated["resume_builder"] = build_optimized_resume_package(
        resume_text=resume_text,
        job_description_text=job_text,
        analysis=analysis,
        generated=generated,
    )
    generated["results_summary_email"] = build_results_summary_email(
        analysis=analysis,
        generated=generated,
    )
    generated["role_profile_fingerprint"] = analysis.get("role_profile_fingerprint", "")
    generated["resume_builder"]["role_profile_fingerprint"] = analysis.get("role_profile_fingerprint", "")
    return generated


def _render_resume_coach(builder: dict) -> None:
    analysis = st.session_state.get("analysis") or {}
    resume_text = st.session_state.get("resume_text", "") or builder.get("original_resume_text", "") or builder.get("optimized_resume_text", "")
    job_text = (
        st.session_state.get("job_text", "")
        or st.session_state.get("manual_job_text", "")
        or builder.get("job_description_text", "")
    )
    render_reason = ""
    if not analysis:
        render_reason = "missing_analysis"
    elif not builder:
        render_reason = "missing_resume_builder"
    elif not resume_text:
        render_reason = "missing_resume_text"
    if render_reason:
        logger.info(
            "resume_coach_rendered=%s reason=%s analysis_present=%s builder_present=%s resume_text_present=%s job_text_present=%s analysis_id=%s",
            False,
            render_reason,
            bool(analysis),
            bool(builder),
            bool(resume_text),
            bool(job_text),
            st.session_state.get("last_application_id", 0),
        )
        return
    logger.info(
        "resume_coach_rendered=%s reason=%s analysis_present=%s builder_present=%s resume_text_present=%s job_text_present=%s analysis_id=%s",
        True,
        "ready",
        bool(analysis),
        bool(builder),
        bool(resume_text),
        bool(job_text),
        st.session_state.get("last_application_id", 0),
    )

    st.write("**AI Resume Coach**")
    st.caption(
        "Ask how to improve your resume using only evidence from your uploaded resume and the job description."
    )

    if not st.session_state.get("resume_coach_logged_opened"):
        logger.info(
            "resume_coach_chat_opened user_email=%s analysis_id=%s",
            st.session_state.get("user_email", "") or "anonymous",
            st.session_state.get("last_application_id", 0),
        )
        st.session_state["resume_coach_logged_opened"] = True

    prompt_cols = st.columns(len(QUICK_PROMPTS))
    for index, quick_prompt in enumerate(QUICK_PROMPTS):
        with prompt_cols[index]:
            if st.button(quick_prompt, key=f"resume_coach_quick_{index}", use_container_width=True):
                st.session_state["resume_coach_prompt_input"] = quick_prompt

    messages = st.session_state.setdefault("resume_coach_messages", [])
    for message in messages:
        with st.chat_message(message.get("role", "assistant")):
            st.markdown(message.get("content", ""))

    user_prompt = st.chat_input(
        "Ask the AI Resume Coach",
        key="resume_coach_chat_input",
    )
    if not user_prompt and st.session_state.get("resume_coach_prompt_input"):
        user_prompt = st.session_state.get("resume_coach_prompt_input", "")
        st.session_state["resume_coach_prompt_input"] = ""

    if not user_prompt:
        return

    logger.info(
        "resume_coach_prompt_submitted user_email=%s analysis_id=%s prompt=%s",
        st.session_state.get("user_email", "") or "anonymous",
        st.session_state.get("last_application_id", 0),
        user_prompt[:200],
    )

    messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        with st.spinner("Coaching your resume..."):
            response = generate_resume_coach_response(
                user_prompt=user_prompt,
                resume_text=resume_text,
                job_description_text=job_text,
                analysis=analysis,
                builder=builder,
            )
            st.markdown(response)

    logger.info(
        "resume_coach_response_generated user_email=%s analysis_id=%s response_length=%s",
        st.session_state.get("user_email", "") or "anonymous",
        st.session_state.get("last_application_id", 0),
        len(response),
    )
    messages.append({"role": "assistant", "content": response})


def _resume_coach_diagnostics(builder: dict) -> dict:
    analysis = st.session_state.get("analysis") or {}
    resume_text = st.session_state.get("resume_text", "") or builder.get("original_resume_text", "") or builder.get("optimized_resume_text", "")
    job_text = (
        st.session_state.get("job_text", "")
        or st.session_state.get("manual_job_text", "")
        or builder.get("job_description_text", "")
    )
    optimized_resume_text = builder.get("optimized_resume_text", "") or st.session_state.get("optimized_resume_text", "")
    analysis_exists = bool(analysis)
    resume_builder_exists = bool(builder)
    resume_text_exists = bool(resume_text)
    job_text_exists = bool(job_text)
    optimized_resume_exists = bool(optimized_resume_text)
    missing_keywords_count = len(analysis.get("missing_keywords", []) or [])
    targeted_gap_fix_count = len(builder.get("targeted_gap_fixes", []) or [])

    skip_reason = ""
    if not analysis_exists:
        skip_reason = "missing_analysis"
    elif not resume_builder_exists:
        skip_reason = "missing_resume_builder"
    elif not resume_text_exists:
        skip_reason = "missing_resume_text"

    return {
        "resume_coach_rendered": skip_reason == "",
        "resume_coach_skip_reason": skip_reason or "ready",
        "analysis_exists": analysis_exists,
        "resume_builder_exists": resume_builder_exists,
        "resume_text_exists": resume_text_exists,
        "job_text_exists": job_text_exists,
        "optimized_resume_exists": optimized_resume_exists,
        "missing_keywords_count": missing_keywords_count,
        "targeted_gap_fix_count": targeted_gap_fix_count,
    }


def _track_page_view(view_name: str, app_page: str = "") -> None:
    now = datetime.now()
    tracker = st.session_state.get("page_view_tracker", {})
    tracker_key = f"{view_name}|{app_page or '-'}"
    last_seen = tracker.get(tracker_key)
    if isinstance(last_seen, str):
        try:
            last_seen = datetime.fromisoformat(last_seen)
        except ValueError:
            last_seen = None
    if last_seen and (now - last_seen).total_seconds() < 120:
        return

    user_email = st.session_state.get("user_email", "")
    save_page_view(
        PageViewRecord(
            created_at=now.isoformat(timespec="seconds"),
            user_id=get_user_id(user_email) if user_email else 0,
            user_email=user_email,
            session_id=st.session_state.get("session_id", ""),
            view_name=view_name,
            app_page=app_page,
        )
    )
    tracker[tracker_key] = now.isoformat(timespec="seconds")
    st.session_state["page_view_tracker"] = tracker


def _contact_message_bucket(message_type: str) -> str:
    value = (message_type or "").strip().lower()
    if any(term in value for term in ["sales", "partnership", "billing"]):
        return "Sales"
    if any(term in value for term in ["feature", "feedback"]):
        return "Feedback"
    return "Support"


def _optimized_resume_filename(resume_text: str, extension: str) -> str:
    candidate_name = _extract_resume_candidate_name(resume_text)
    safe_name = re.sub(r"[^A-Za-z0-9]+", "_", candidate_name).strip("_") or "Candidate"
    return f"{safe_name}_Resume.{extension}"


def _pdf_export_package(analysis: dict, resume_text: str, job_text: str, generated_outputs: dict) -> dict:
    analysis = analysis or {}
    return {
        "analysis": analysis,
        "generated": generated_outputs or {},
        "resume_text": resume_text or "",
        "job_text": job_text or "",
        "resume_filename": st.session_state.get("resume_filename", ""),
        "job_filename": st.session_state.get("job_filename", ""),
        "job_url": st.session_state.get("job_url", ""),
        "job_location": st.session_state.get("job_location_preview", ""),
        "job_date_posted": st.session_state.get("job_date_posted_preview", ""),
        "job_category": st.session_state.get("job_category_preview", ""),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "user_email": st.session_state.get("user_email", ""),
        "active_role_profile_name": (
            analysis.get("active_role_profile", {}).get("headline")
            or st.session_state.get("active_role_profile", {}).get("headline", "")
            or analysis.get("role_family", "")
        ),
    }


def render_pdf_download_button(tab_name, analysis, resume_text, job_text, generated_outputs):
    analysis = analysis or {}
    has_results = bool(
        analysis
        or generated_outputs
        or resume_text.strip()
        or job_text.strip()
    )
    if not has_results:
        st.warning("PDF export is unavailable because this tab does not have any generated results yet.")
        logger.info("pdf_button_skipped tab=%s reason=no_results", tab_name)
        return

    st.write("**PDF Export**")
    package = _pdf_export_package(analysis, resume_text, job_text, generated_outputs)
    try:
        if tab_name == "Export":
            pdf_bytes, file_name, _payload = build_full_ai_review_pdf(package)
            label = "Download Full AI Review PDF"
        else:
            pdf_bytes, file_name, _payload = build_tab_pdf(tab_name, package)
            label = "Download PDF"
        if not pdf_bytes:
            raise ValueError("PDF generation returned empty content.")
        download_clicked = st.download_button(
            label=label,
            data=pdf_bytes,
            file_name=file_name,
            mime="application/pdf",
            key=f"pdf_download_{tab_name.lower().replace(' ', '_')}",
        )
        logger.info("pdf_button_rendered tab=%s file_name=%s bytes=%s", tab_name, file_name, len(pdf_bytes))
        if download_clicked:
            save_pdf_download(
                PdfDownloadRecord(
                    created_at=datetime.now().isoformat(timespec="seconds"),
                    user_id=get_user_id(st.session_state.get("user_email", "")),
                    user_email=st.session_state.get("user_email", ""),
                    application_id=int(st.session_state.get("last_application_id", 0) or 0),
                    tab_name=tab_name,
                    file_name=file_name,
                )
            )
            logger.info(
                "pdf_download_recorded current_user_email=%s application_id=%s tab=%s file_name=%s",
                st.session_state.get("user_email", "") or "anonymous",
                int(st.session_state.get("last_application_id", 0) or 0),
                tab_name,
                file_name,
            )
    except Exception as exc:
        logger.exception("PDF export unavailable for tab=%s", tab_name)
        st.warning(f"PDF export is temporarily unavailable for this tab: {exc}")


def render_upload_tab() -> None:
    st.subheader("Upload source materials")
    st.caption(APP_DISCLAIMER)

    st.session_state["demo_mode"] = is_demo_mode_api_key()
    if st.session_state.get("demo_mode"):
        st.warning(
            "Demo Mode: Add a valid OpenAI API key to generate real AI outputs."
        )

    left, right = st.columns(2)
    with left:
        if st.session_state.get("is_authenticated"):
            saved_resumes = list_saved_resumes(st.session_state.get("user_email", ""))
            if saved_resumes:
                resume_options = {f"{item['resume_name']} ({item['original_filename']})": item["resume_id"] for item in saved_resumes}
                selected_saved_resume = st.selectbox(
                    "Or select a saved resume",
                    ["Choose a saved resume"] + list(resume_options.keys()),
                )
                if selected_saved_resume != "Choose a saved resume" and st.button("Use Saved Resume", use_container_width=True):
                    saved_resume = get_saved_resume(
                        st.session_state.get("user_email", ""),
                        resume_options[selected_saved_resume],
                    )
                    if saved_resume:
                        _reset_analysis_outputs("saved_resume_selected")
                        st.session_state["resume_text"] = saved_resume.get("extracted_text", "")
                        st.session_state["resume_filename"] = saved_resume.get("original_filename", "")
                        mark_saved_resume_used(
                            st.session_state.get("user_email", ""),
                            saved_resume.get("resume_id", 0),
                        )
                        st.success(f"Loaded saved resume: {saved_resume.get('resume_name', 'Resume')}")
        resume_file = st.file_uploader(
            "Upload resume",
            type=["pdf", "docx", "txt"],
            help="Supported formats: PDF, DOCX, TXT",
        )
        if resume_file is not None:
            resume_text = extract_text_from_upload(resume_file)
            if resume_text != st.session_state.get("resume_text", ""):
                _reset_analysis_outputs("resume_uploaded")
            st.session_state["resume_text"] = resume_text
            st.session_state["resume_filename"] = resume_file.name
            st.success(f"Resume loaded from {resume_file.name}")
            st.text_area("Extracted resume text", resume_text, height=260)
            resume_signature = f"{resume_file.name}:{hash(resume_text)}"
            if (
                st.session_state.get("is_authenticated")
                and resume_text.strip()
                and st.session_state.get("last_saved_resume_signature") != resume_signature
            ):
                save_resume_stub(
                    user_email=st.session_state.get("user_email", ""),
                    resume_name=_extract_resume_candidate_name(resume_text),
                    original_filename=resume_file.name,
                    extracted_text=resume_text,
                    created_at=datetime.now().isoformat(timespec="seconds"),
                )
                st.session_state["last_saved_resume_signature"] = resume_signature

    with right:
        job_url = st.text_input(
            "Job posting URL",
            value=st.session_state.get("job_url", ""),
            placeholder="https://www.linkedin.com/jobs/view/...",
            help="Supported sources include LinkedIn, Indeed, Greenhouse, Lever, Workday, and company career pages.",
        )
        st.session_state["job_url"] = job_url

        if st.button("Fetch Job Description"):
            try:
                logger.info("Fetching job description from %s", job_url)
                extracted = fetch_job_posting_from_url(job_url)
                st.session_state["job_text"] = extracted.description_text
                st.session_state["job_title_preview"] = extracted.title
                st.session_state["company_name_preview"] = extracted.company_name
                st.session_state["job_location_preview"] = extracted.location
                st.session_state["job_date_posted_preview"] = extracted.date_posted
                st.session_state["job_category_preview"] = extracted.category
                st.session_state["job_extraction_confidence"] = extracted.extraction_confidence
                st.session_state["job_filename"] = extracted.url
                st.session_state["job_extraction_error"] = ""
                st.session_state["manual_title"] = extracted.title
                st.session_state["manual_company"] = extracted.company_name
                st.session_state["manual_location"] = extracted.location
                _sync_active_role_profile()
                st.success("Job description extracted successfully.")
            except JobExtractionError as exc:
                logger.warning("Job extraction failed for %s: %s", job_url, exc)
                _reset_analysis_outputs("job_extraction_failed")
                st.session_state["job_text"] = ""
                st.session_state["job_title_preview"] = ""
                st.session_state["company_name_preview"] = ""
                st.session_state["job_location_preview"] = ""
                st.session_state["job_date_posted_preview"] = ""
                st.session_state["job_category_preview"] = ""
                st.session_state["job_extraction_confidence"] = 0
                st.session_state["job_extraction_error"] = str(exc)
                st.session_state["active_role_profile"] = {}
                st.session_state["active_role_fingerprint"] = ""
                st.error(str(exc))

        if st.session_state.get("job_title_preview"):
            st.write(f"**Extracted title:** {st.session_state['job_title_preview']}")
        if st.session_state.get("company_name_preview"):
            st.write(f"**Extracted company:** {st.session_state['company_name_preview']}")
        if st.session_state.get("job_location_preview"):
            st.write(f"**Location:** {st.session_state['job_location_preview']}")
        if st.session_state.get("job_date_posted_preview"):
            st.write(f"**Date posted:** {st.session_state['job_date_posted_preview']}")
        if st.session_state.get("job_category_preview"):
            st.write(f"**Category:** {st.session_state['job_category_preview']}")
        if st.session_state.get("job_extraction_confidence"):
            st.write(f"**Extraction confidence:** {st.session_state['job_extraction_confidence']}/100")
        if st.session_state.get("job_text"):
            st.write("**Job description preview**")
            st.text_area(
                "Cleaned job description",
                st.session_state["job_text"],
                height=280,
                disabled=False,
            )

        low_confidence = 0 < st.session_state.get("job_extraction_confidence", 0) < 60
        if low_confidence:
            with st.expander("Review extracted fields"):
                manual_title = st.text_input(
                    "Confirm or correct job title",
                    value=st.session_state.get("manual_title", st.session_state.get("job_title_preview", "")),
                )
                manual_company = st.text_input(
                    "Confirm or correct company name",
                    value=st.session_state.get("manual_company", st.session_state.get("company_name_preview", "")),
                )
                manual_location = st.text_input(
                    "Confirm or correct location",
                    value=st.session_state.get("manual_location", st.session_state.get("job_location_preview", "")),
                )
                st.session_state["manual_title"] = manual_title
                st.session_state["manual_company"] = manual_company
                st.session_state["manual_location"] = manual_location
                if st.button("Apply Field Corrections"):
                    st.session_state["job_title_preview"] = manual_title.strip() or st.session_state.get("job_title_preview", "")
                    st.session_state["company_name_preview"] = manual_company.strip() or st.session_state.get("company_name_preview", "")
                    st.session_state["job_location_preview"] = manual_location.strip() or st.session_state.get("job_location_preview", "")
                    _sync_active_role_profile()
                    st.success("Field corrections applied.")

        fallback_expanded = bool(st.session_state.get("job_extraction_error"))
        with st.expander("Manual fallback", expanded=fallback_expanded):
            st.caption("Some job boards block automated extraction. Paste the job details below to continue.")
            manual_company = st.text_input(
                "Company",
                value=st.session_state.get("manual_company", st.session_state.get("company_name_preview", "")),
            )
            manual_title = st.text_input(
                "Job Title",
                value=st.session_state.get("manual_title", st.session_state.get("job_title_preview", "")),
            )
            manual_location = st.text_input(
                "Location",
                value=st.session_state.get("manual_location", st.session_state.get("job_location_preview", "")),
            )
            manual_job_text = st.text_area(
                "Job Description",
                value=st.session_state.get("manual_job_text", ""),
                height=240,
                help="Paste the visible job description from the job page when automated extraction is blocked or incomplete.",
            )

            st.session_state["manual_company"] = manual_company
            st.session_state["manual_title"] = manual_title
            st.session_state["manual_location"] = manual_location
            st.session_state["manual_job_text"] = manual_job_text

            if st.button("Use Manual Job Description"):
                if manual_job_text.strip():
                    st.session_state["job_text"] = manual_job_text.strip()
                    st.session_state["job_title_preview"] = manual_title.strip()
                    st.session_state["company_name_preview"] = manual_company.strip()
                    st.session_state["job_location_preview"] = manual_location.strip()
                    st.session_state["job_extraction_error"] = ""
                    _sync_active_role_profile()
                    st.success("Manual job details saved. You can continue to analysis.")
                else:
                    st.error("Paste the job description text before using the manual fallback.")

    st.divider()

    can_run = bool(st.session_state["resume_text"].strip() and st.session_state["job_text"].strip())
    admin_active = _ensure_admin_test_mode_for_admin()
    analysis_allowed, block_reason = _can_run_analysis()
    if admin_active:
        st.info("Admin test mode active. This run will not consume credits or require payment.")
        admin_test_value = st.toggle(
            "Run as admin test",
            value=True,
            help="Admin-only support mode. Runs are saved as admin tests and do not consume user billing access.",
            disabled=True,
        )
        st.session_state["admin_test_mode"] = bool(admin_test_value)
    if open_beta_enabled():
        st.caption("Open beta access is enabled. Analyses, exports, and job evaluations are currently unlimited.")
    elif st.session_state.get("is_authenticated") and block_reason == "paywall" and not admin_active:
        st.warning("You’ve used your free Career Match assessment.")
        st.caption("Upgrade to Career Match Pro or buy one more assessment to continue. Your previous results remain available.")
        if st.button("View Upgrade Options", type="primary", use_container_width=True):
            _send_to_pro_page()
            st.rerun()
    if st.button("Analyze and generate materials", type="primary", disabled=not can_run):
        if not analysis_allowed:
            _send_to_pro_page()
            st.rerun()
        if not _rate_limit_allows_analysis():
            st.error("Please wait a moment before starting another analysis.")
            return
        try:
            logger.info(
                "Starting analysis workflow. current_user_email=%s is_admin=%s admin_test_mode=%s paywall_bypassed=%s payment_type_used=%s",
                st.session_state.get("user_email", ""),
                _user_is_admin(),
                _admin_test_mode_enabled(),
                admin_active,
                _current_payment_type_used(),
            )
            with st.spinner("Comparing resume to the job description..."):
                analysis = compare_resume_to_job(
                    st.session_state["resume_text"],
                    st.session_state["job_text"],
                )
                if st.session_state.get("job_title_preview"):
                    analysis["job_title"] = st.session_state["job_title_preview"]
                if st.session_state.get("company_name_preview"):
                    analysis["company_name"] = st.session_state["company_name_preview"]
                st.session_state["analysis"] = analysis
                st.session_state["active_role_profile"] = analysis.get("active_role_profile", {})
                st.session_state["active_role_fingerprint"] = analysis.get("role_profile_fingerprint", "")

            with st.spinner("Generating tailored materials with OpenAI..."):
                generated = _rebuild_generated_outputs(
                    st.session_state["resume_text"],
                    st.session_state["job_text"],
                    st.session_state["analysis"],
                )
                st.session_state["optimized_resume_text"] = generated["resume_builder"]["optimized_resume_text"]
                st.session_state["generated"] = generated
                st.session_state["application_saved"] = False
                st.session_state["resume_coach_messages"] = []
                st.session_state["resume_coach_prompt_input"] = ""
                st.session_state["resume_coach_logged_opened"] = False

            _save_current_application()
            _record_successful_assessment()
            logger.info(
                "Analysis workflow completed successfully. current_user_email=%s is_admin=%s admin_test_mode=%s paywall_bypassed=%s payment_type_used=%s",
                st.session_state.get("user_email", ""),
                _user_is_admin(),
                _admin_test_mode_enabled(),
                admin_active,
                _current_payment_type_used(),
            )
            st.success("Analysis and tailored outputs are ready in the other tabs.")
        except Exception as exc:
            logger.exception("Unable to generate materials.")
            st.error(f"Unable to generate materials: {exc}")


def render_match_tab() -> None:
    st.subheader("Resume match overview")
    analysis = st.session_state.get("analysis")
    generated = st.session_state.get("generated") or {}
    if not analysis:
        st.info("Upload a resume and job description in the Upload tab to see the match analysis.")
        return
    render_pdf_download_button(
        "Resume Match",
        analysis,
        st.session_state.get("resume_text", ""),
        st.session_state.get("job_text", ""),
        generated,
    )

    job_fit = analysis.get("job_fit", {})
    fit_score = int(analysis.get("overall_fit_score", 0) or 0)
    direct_score = int(analysis.get("direct_match_score", 0) or 0)
    transferable_score = int(analysis.get("transferable_match_score", 0) or 0)
    interview_score = int(analysis.get("overall_interview_potential", 0) or 0)
    recruiter_label, recruiter_score = _recruiter_likelihood_label(analysis)
    recommendation = job_fit.get("recommendation", "Not available")
    why_items = (job_fit.get("reasoning", []) or analysis.get("hiring_manager_view", []))[:3]
    top_strengths = _top_strengths(analysis)
    top_gaps = _top_gaps(analysis)
    next_actions = _recommended_next_actions(analysis)
    ats_opportunities = _ats_improvement_opportunities(analysis)
    score_breakdown = analysis.get("score_breakdown", [])
    reasons_to_interview = analysis.get("reasons_to_interview", [])
    reasons_to_reject = analysis.get("reasons_to_reject", [])
    resume_roi_fixes = analysis.get("resume_roi_fixes", [])
    recruiter_summary = analysis.get("recruiter_style_summary", {})
    missing_keywords_by_priority = analysis.get("missing_keywords_by_priority", {})
    recruiter_confidence_rows = analysis.get("recruiter_confidence_by_competency", [])
    level_alignment = analysis.get("compensation_level_alignment", {})
    typical_comparison = analysis.get("compared_with_typical_applicants", [])
    score_consistency = analysis.get("score_consistency", {})
    builder = generated.get("resume_builder", {}) or {}
    keyword_coverage_before = int(analysis.get("keyword_coverage_score", 0) or 0)
    keyword_coverage_after = int(builder.get("optimized_ats_score", keyword_coverage_before) or keyword_coverage_before)
    keyword_coverage_label = analysis.get("keyword_coverage_label", "Keyword Coverage Before")
    coverage_explanation = score_consistency.get("explanation", "Keyword coverage is not the same as overall job fit.")
    coverage_warning = score_consistency.get("warning", "")
    if keyword_coverage_after >= fit_score + 12 and direct_score < 60:
        coverage_warning = "Keyword coverage is strong, but overall fit is limited by missing direct experience."
    score_explanation = analysis.get("score_explanation", [])
    recruiter_benchmarking = analysis.get("recruiter_benchmarking", [])
    roi_projection = analysis.get("roi_projection", {})

    hero_left, hero_right = st.columns([1.35, 1], gap="large")
    with hero_left:
        st.markdown(
            f"""
            <div class="summary-hero">
                <div class="summary-eyebrow">Executive Summary</div>
                <div class="summary-score">{fit_score}/100</div>
                <div>{_signal_chip(recommendation, _recommendation_signal(recommendation))}</div>
                <p class="summary-copy"><strong>Why:</strong> {" ".join(why_items) if why_items else "The recommendation is based on direct matches, transferable experience, and the strongest evidence found in the resume."}</p>
                <p class="summary-copy"><strong>What to do next:</strong> {" ".join(next_actions[:2]) if next_actions else "Use the strongest evidence-backed examples in the Resume Builder before applying."}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hero_right:
        st.markdown(
            f"""
            <div class="mini-card">
                <div class="summary-label">Interview Probability</div>
                <div class="summary-value">{interview_score}/100</div>
                <div class="summary-label">Recruiter Likelihood</div>
                <div class="summary-value">{recruiter_label} ({recruiter_score}/100)</div>
                <div class="summary-label">Overall Recommendation</div>
                <div class="summary-copy">{recommendation}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("Fit Score", f"{fit_score}/100")
    metric2.metric("Direct Match", f"{direct_score}/100")
    metric3.metric("Transferable Match", f"{transferable_score}/100")
    metric4.metric("Experience", f"{analysis.get('years_of_experience', 0)} years")

    coverage_left, coverage_right = st.columns(2, gap="large")
    with coverage_left:
        st.markdown(
            f"""
            <div class="mini-card">
                <h4>{keyword_coverage_label}</h4>
                <div class="summary-value">{keyword_coverage_before}/100</div>
                <p class="summary-copy">{coverage_explanation}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with coverage_right:
        st.markdown(
            f"""
            <div class="mini-card">
                <h4>Keyword Coverage After</h4>
                <div class="summary-value">{keyword_coverage_after}/100</div>
                <p class="summary-copy">{coverage_explanation}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    if coverage_warning:
        st.warning(coverage_warning)

    _render_role_match_snapshot(analysis, "Recruiter Summary Card")

    recruiter_left, recruiter_right = st.columns(2, gap="large")
    with recruiter_left:
        st.write("**Why Recruiters Will Interview**")
        if reasons_to_interview:
            for item in reasons_to_interview[:5]:
                with st.expander(f"{item.get('reason_title', 'Reason')} | {item.get('strength_level', 'Transferable')}"):
                    st.write(item.get("reason_bullet", ""))
                    st.write(f"**Confidence level:** {item.get('strength_level', 'Transferable')}")
                    st.write("**Relevant job requirement:** " + (item.get("relevant_job_requirement", "") or "Not specified"))
                    evidence_lines = item.get("supporting_resume_evidence", [])
                    if evidence_lines:
                        st.write("**Supporting resume evidence:**")
                        for line in evidence_lines:
                            st.write(f"- {line}")
        else:
            st.write("No strong interview reasons were identified.")
    with recruiter_right:
        st.write("**Why Recruiters May Pass**")
        if reasons_to_reject:
            for item in reasons_to_reject[:5]:
                with st.expander(f"{item.get('gap_name', 'Gap')} | {item.get('impact_level', 'Medium')} impact"):
                    st.write(item.get("risk_bullet", ""))
                    st.write(f"**Why it matters:** {item.get('why_it_matters', '')}")
                    st.write("**Missing job requirement:** " + (item.get("missing_job_requirement", "") or "Not specified"))
                    st.write("**Fixability:** " + (item.get("fixability", "") or "Unknown"))
        else:
            st.write("No major reject risks were identified.")

    st.write("**Highest Impact Fixes**")
    st.write(f"Current Score: {roi_projection.get('current_score', fit_score)}")
    st.write(f"Potential Score: {roi_projection.get('potential_score', fit_score)}")
    for item in roi_projection.get("top_fixes", [])[:5]:
        st.write(
            f"- {item.get('gap_or_keyword', '')} .......... +{item.get('estimated_score_impact', 0)} | "
            f"{item.get('expected_impact', 'Medium')} impact"
        )

    detail_left, detail_right = st.columns([1.2, 1], gap="large")
    with detail_left:
        st.markdown(
            f"""
            <div class="mini-card">
                <h4>Top 3 strengths</h4>
                {_render_bullet_html(top_strengths)}
            </div>
            """,
            unsafe_allow_html=True,
        )
    with detail_right:
        st.markdown(
            f"""
            <div class="mini-card">
                <h4>Top 3 gaps</h4>
                {_render_bullet_html(top_gaps)}
            </div>
            """,
            unsafe_allow_html=True,
        )

    action_left, action_right = st.columns(2, gap="large")
    with action_left:
        st.markdown(
            f"""
            <div class="mini-card">
                <h4>Recommended next actions</h4>
                {_render_bullet_html(next_actions)}
            </div>
            """,
            unsafe_allow_html=True,
        )
    with action_right:
        st.markdown(
            f"""
            <div class="mini-card">
                <h4>ATS improvement opportunities</h4>
                {_render_bullet_html(ats_opportunities)}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("**Why This Score?**")
    explanation_left, explanation_right = st.columns([1.2, 1], gap="large")
    with explanation_left:
        if score_explanation:
            for item in score_explanation:
                st.write(
                    f"- {item.get('category', '')}: {item.get('weight', 0)}% weight | "
                    f"raw {item.get('raw_score', 0)}/100 | contribution {item.get('contribution', 0)}"
                )
        else:
            st.write("Score explanation is not available.")
    with explanation_right:
        st.write("**Highest ROI Fixes**")
        for item in roi_projection.get("top_fixes", []):
            st.write(
                f"- {item.get('gap_or_keyword', '')} .......... +{item.get('estimated_score_impact', 0)} | "
                f"{item.get('expected_impact', 'Medium')} impact"
            )

    st.write("**Competency Score Breakdown**")
    if score_breakdown:
        for item in score_breakdown:
            with st.expander(
                f"{item.get('competency', 'Competency')} | Contribution {item.get('contribution', 0)}/100 | {item.get('confidence_level', 'Unsupported')}"
            ):
                st.write(f"**Weight:** {item.get('weight', 0)}")
                st.write(f"**Raw score:** {item.get('raw_score', 0)}/100")
                st.write(f"**Contribution to final score:** {item.get('contribution', 0)}/100")
                st.write(f"**Evidence level:** {item.get('evidence_level', 'Unsupported')}")
                st.write(f"**Confidence level:** {item.get('confidence_level', 'Unsupported')}")
                st.write("**Matched terms:** " + (", ".join(item.get("matched_terms", [])) or "None"))
                st.write("**Missing requirement:** " + (item.get("missing_requirement", "") or "None"))
                evidence_lines = item.get("matched_resume_evidence", [])
                if evidence_lines:
                    st.write("**Matched resume evidence:**")
                    for line in evidence_lines:
                        st.write(f"- {line}")
    else:
        st.write("Score breakdown is not available for this analysis yet.")

    st.write("**Highest ROI Fixes**")
    if resume_roi_fixes:
        for item in resume_roi_fixes:
            support_label = "Supported" if item.get("safely_supported") else "Not safely supported"
            with st.expander(
                f"{item.get('gap_or_keyword', 'Gap')} | {item.get('expected_impact', 'Medium')} impact | +{item.get('estimated_score_impact', 0)} potential points"
            ):
                st.write(f"**Evidence level:** {item.get('evidence_level', 'Unsupported')}")
                st.write(f"**Why it matters:** {item.get('why_it_matters', '')}")
                st.write(f"**Recommended action:** {item.get('recommended_action', '')}")
                st.write(f"**Safe to use:** {support_label}")
                evidence_lines = item.get("supporting_resume_evidence", [])
                if evidence_lines:
                    st.write("**Supporting resume evidence:**")
                    for line in evidence_lines:
                        st.write(f"- {line}")
    else:
        st.write("No high-impact fixes were identified.")

    st.write("**Recruiter Confidence**")
    if recruiter_confidence_rows:
        for item in recruiter_confidence_rows:
            with st.expander(f"{item.get('competency', 'Competency')} | {item.get('confidence_level', 'Low')} confidence"):
                st.write(f"**Direct Score:** {item.get('direct_score', 0)}/100")
                st.write(f"**Transferable Score:** {item.get('transferable_score', 0)}/100")
                st.write(f"**Overall Score:** {item.get('overall_score', 0)}/100")
                st.write(f"**Evidence Level:** {item.get('evidence_level', 'Unsupported')}")
                evidence_summary = item.get("evidence_summary", [])
                st.write("**Evidence Summary:**")
                for line in evidence_summary:
                    st.write(f"- {line}")
                with st.expander("View Full Evidence"):
                    st.write("**Evidence:** " + (", ".join(item.get("evidence", [])) or "None"))
                    for line in item.get("matched_resume_evidence", []):
                        st.write(f"- {line}")
    else:
        st.write("No recruiter confidence data is available.")

    priority_left, priority_right = st.columns(2, gap="large")
    with priority_left:
        st.write("**Missing Keywords by Priority**")
        for priority in ["Critical", "Important", "Nice-to-have"]:
            items = missing_keywords_by_priority.get(priority, [])
            st.write(f"**{priority}**")
            if not items:
                st.write("None identified")
                continue
            for item in items:
                with st.expander(item.get("term", "")):
                    st.write(f"**Competency:** {item.get('competency', '')}")
                    st.write(f"**JD keyword:** {item.get('extracted_keyword', '')}")
                    st.write(f"**Confidence:** {item.get('confidence_score', 0)}")
                    st.write(item.get("job_description_sentence", "") or "No direct job-description sentence captured.")
    with priority_right:
        st.write("**Compensation / Level Alignment**")
        st.markdown(
            f"""
            <div class="mini-card">
                <h4>{level_alignment.get('label', 'Moderate Alignment')}</h4>
                <div class="summary-value">{level_alignment.get('alignment_score', 0)}/100</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for item in level_alignment.get("reasoning", []):
            st.write(f"- {item}")

        st.write("**Compared To Successful Candidates**")
        if recruiter_benchmarking:
            for item in recruiter_benchmarking:
                icon = "✓" if item.get("status") == "Above" else "⚠" if item.get("status") == "Below" else "•"
                st.write(
                    f"{icon} {item.get('competency', '')} | You: {item.get('you_score', 0)} | "
                    f"Target: {item.get('target_score', 0)} | {item.get('status', 'Competitive')}"
                )
        elif typical_comparison:
            for item in typical_comparison:
                evidence = ", ".join(item.get("evidence", [])[:3]) or "No clear evidence"
                st.write(f"- {item.get('competency', '')}: {item.get('relative_strength', 'Unknown')} | {item.get('confidence_level', 'Low')} confidence | Evidence: {evidence}")
        else:
            st.write("No comparison data is available.")

    st.caption(
        f"{analysis['job_title']} at {analysis['company_name']} | "
        f"{analysis.get('role_family', 'General Professional Role')}"
        + (f" | {st.session_state['job_location_preview']}" if st.session_state.get("job_location_preview") else "")
    )
    if st.session_state.get("job_url"):
        st.write(f"**Job posting URL:** {st.session_state['job_url']}")
    if st.session_state.get("job_date_posted_preview"):
        st.write(f"**Date posted:** {st.session_state['job_date_posted_preview']}")
    if st.session_state.get("job_category_preview"):
        st.write(f"**Category:** {st.session_state['job_category_preview']}")

    exact_keyword_matches = _exact_keyword_matches(analysis)
    semantic_skill_matches = _semantic_skill_matches(analysis)

    with st.expander("Detailed fit reasoning", expanded=False):
        st.write(f"**Likely job title:** {analysis['job_title']}")
        st.write(f"**Likely company:** {analysis['company_name']}")
        st.write(f"**Role lens:** {analysis.get('role_family', 'General Professional Role')}")
        st.write(f"**Recommendation:** {recommendation}")
    if job_fit:
        with st.expander("Experience, title, and skills breakdown", expanded=False):
            st.write("**Job fit reasoning**")
            for item in job_fit.get("reasoning", []):
                st.write(f"- {item}")

            fit_left, fit_right = st.columns(2)
            with fit_left:
                st.write("**Experience and title**")
                years_required = job_fit.get("years_experience_required", 0)
                years_resume = job_fit.get("years_experience_resume", 0)
                if years_required:
                    st.write(f"- Years of experience: resume ~{years_resume}, job asks for ~{years_required}")
                else:
                    st.write(f"- Years of experience: resume ~{years_resume}, job requirement not clearly stated")
                st.write(
                    "- Title match: "
                    + (", ".join(job_fit.get("title_overlap", [])) if job_fit.get("title_overlap") else "limited overlap")
                )
                st.write(
                    "- Industry match: "
                    + (", ".join(job_fit.get("industry_overlap", [])) if job_fit.get("industry_overlap") else "limited overlap")
                )
            with fit_right:
                st.write("**Skills and certifications**")
                st.write(
                    "- Required skills matched: "
                    f"{len(job_fit.get('required_skill_matches', []))}/{len(job_fit.get('required_skills', []))}"
                )
                if job_fit.get("preferred_skills"):
                    st.write(
                        "- Preferred skills matched: "
                        f"{len(job_fit.get('preferred_skill_matches', []))}/{len(job_fit.get('preferred_skills', []))}"
                    )
                certs = job_fit.get("required_certifications", [])
                if certs:
                    st.write(
                        "- Certifications: "
                        + (
                            f"matched {', '.join(job_fit.get('matching_certifications', []))}"
                            if job_fit.get("matching_certifications")
                            else f"missing {', '.join(job_fit.get('missing_certifications', []))}"
                        )
                    )
                else:
                    st.write("- Certifications: none clearly required in the job description")

    with st.expander("Keyword and evidence detail", expanded=False):
        left, right = st.columns(2)
        with left:
            st.write("**Exact Keyword Matches**")
            st.write(", ".join(exact_keyword_matches) or "None identified")
            st.write("**Semantic Matches**")
            if semantic_skill_matches:
                for item in semantic_skill_matches:
                    details = (
                        f" | Direct {item['direct_score']}% | Transferable {item['transferable_score']}%"
                        + (f" | Evidence: {', '.join(item.get('matched_terms', [])[:3])}" if item.get("matched_terms") else "")
                    )
                    st.write(f"- {item['skill']} ({item['confidence']}%){details}")
            else:
                st.write("None identified")
        with right:
            st.write("**Role-specific strengths**")
            for item in analysis["role_specific_strengths"]:
                st.write(f"- {item}")
            st.write("**Gaps to address**")
            for item in analysis["gaps"]:
                st.write(f"- {item}")

        reasoning_left, reasoning_right = st.columns(2)
        with reasoning_left:
            st.write("**Why skills matched**")
            for item in analysis.get("match_reasoning", []):
                with st.expander(f"{item.get('competency', 'Competency')} | Score {item.get('score', 0)}/100"):
                    st.write(item.get("why_it_matched", ""))
                    st.write("**Matched terms:** " + (", ".join(item.get("matched_terms", [])) or "None"))
                    st.write("**Exact resume bullets / lines:**")
                    for line in item.get("resume_evidence_lines", []):
                        st.write(f"- {line}")
        with reasoning_right:
            st.write("**Why skills are still missing**")
            for item in analysis.get("missing_reasoning", []):
                with st.expander(item.get("competency", "Competency")):
                    st.write(item.get("why_it_is_missing", ""))
                    st.write("**Missing terms:** " + (", ".join(item.get("missing_terms", [])) or "None"))
                    closest = item.get("closest_resume_evidence", [])
                    if closest:
                        st.write("**Closest resume evidence:**")
                        for line in closest:
                            st.write(f"- {line}")

    render_learning_resources_section("match")
    render_feedback_section()


def render_tailored_resume_tab() -> None:
    st.subheader("Tailored resume content")
    analysis = st.session_state.get("analysis", {}) or {}
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Your tailored resume content will appear here after analysis.")
        return
    render_pdf_download_button(
        "Tailored Resume",
        analysis,
        st.session_state.get("resume_text", ""),
        st.session_state.get("job_text", ""),
        generated,
    )
    _render_role_match_snapshot(analysis, "Recruiter Summary Card")

    st.write("**Professional summary**")
    st.text_area("Summary", generated["professional_summary"], height=140)
    st.write("**Tailored bullet points**")
    bullet_text = "\n".join(f"- {item}" for item in generated["tailored_resume_bullets"])
    st.text_area("Resume bullets", bullet_text, height=260)


def render_resume_builder_tab() -> None:
    st.subheader("Resume Builder")
    analysis = st.session_state.get("analysis", {}) or {}
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Your optimized full resume will appear here after analysis.")
        return

    builder = generated.get("resume_builder", {})
    if not builder:
        st.warning("Resume Builder output is not available yet. Re-run generation to refresh the output.")
        return
    render_pdf_download_button(
        "Resume Builder",
        analysis,
        st.session_state.get("resume_text", ""),
        st.session_state.get("job_text", ""),
        generated,
    )
    _render_role_match_snapshot(analysis, "Recruiter Summary Card")

    st.warning(
        "Review before submitting. This tool rewrites only from your uploaded resume and does not verify employer requirements."
    )

    st.write("**Summary of improvements**")
    for item in builder.get("improvements_summary", []):
        st.write(f"- {item}")

    trust_col, explicit_col, inferred_col = st.columns(3)
    trust_col.metric("Trust Score", f"{builder.get('trust_score', 0)}%")
    explicit_col.metric("Explicit Skills", len(builder.get("explicit_skills", [])))
    inferred_col.metric("Inferred Skills", len(builder.get("inferred_skills", [])))

    st.write("**Explicit skills**")
    st.write(", ".join(builder.get("explicit_skills", [])) or "None identified")
    st.write("**Inferred skills**")
    st.write(", ".join(builder.get("inferred_skills", [])) or "None identified")

    left, right = st.columns(2)
    with left:
        st.write("**Original Resume**")
        st.metric("ATS Before", f"{builder.get('original_ats_score', 0)}/100")
        before_keywords = ", ".join(builder.get("matching_keywords_before", [])) or "None identified"
        st.write(f"Matching keywords before: {before_keywords}")
    with right:
        st.write("**Optimized Resume**")
        st.metric("ATS After", f"{builder.get('optimized_ats_score', 0)}/100")
        st.metric("ATS Improvement", f"{builder.get('ats_improvement_percentage', 0)}%")
        after_keywords = ", ".join(builder.get("matching_keywords_after", [])) or "None identified"
        st.write(f"Matching keywords after: {after_keywords}")
    st.caption(builder.get("ats_change_explanation", ""))

    added = ", ".join(builder.get("keywords_added", [])) or "None identified"
    st.write(f"**Keywords added:** {added}")
    _render_term_detail_block("Terms Already Present", builder.get("terms_already_present_details", []))
    _render_term_detail_block("Terms Repositioned", builder.get("terms_repositioned_details", []))
    _render_term_detail_block("Terms Newly Added From Resume Evidence", builder.get("terms_newly_added_details", []))
    _render_term_detail_block("Transferable Terms Used Carefully", builder.get("transferable_terms_used_carefully_details", []))
    not_added = ", ".join(builder.get("targeted_keywords_rejected", [])) or "None identified"
    st.write(f"**Keywords not added:** {not_added}")
    _render_term_detail_block("Terms Not Added Due To Insufficient Evidence", builder.get("terms_not_added_details", []))
    st.write("**ATS Gain Contribution**")
    gain_contribution = builder.get("category_improvements", [])
    if gain_contribution:
        for item in gain_contribution:
            after_terms = ", ".join(item.get("matched_terms_after", [])[:4]) or "None"
            st.write(f"- {item.get('category', 'Category')}: +{item.get('delta', 0)} | Matched after: {after_terms}")
    else:
        st.write("None identified")
    if builder.get("unsupported_added_keywords"):
        st.error(
            "Unsupported additions detected and penalized in ATS scoring: "
            + ", ".join(builder.get("unsupported_added_keywords", []))
        )
    remaining = ", ".join(builder.get("missing_keywords_remaining", [])) or "None identified"
    st.write(f"**Remaining gaps:** {remaining}")
    remaining_gap_details = builder.get("remaining_gap_details", [])
    if remaining_gap_details:
        st.write("**Gap evidence from the job description**")
        for item in remaining_gap_details:
            with st.expander(f"{item.get('term', 'Gap')} | Confidence {item.get('confidence_score', 0)}%"):
                st.write(f"**Extracted keyword:** {item.get('extracted_keyword', '') or 'None'}")
                st.write(f"**Job description sentence:** {item.get('job_description_sentence', '') or 'None'}")
                st.write(f"**Resume support level:** {item.get('support_level', 'Weak / Unsupported')}")
                if item.get("source_resume_evidence"):
                    st.write(f"**Resume evidence:** {item.get('source_resume_evidence', '')}")
                if item.get("exact_resume_line"):
                    st.write(f"**Exact resume line:** {item.get('exact_resume_line', '')}")
    st.write("**ATS validation report**")
    validation_rows = builder.get("term_validation_report", [])
    if validation_rows:
        for row in validation_rows:
            status = "Pass" if row.get("is_valid") else "Fail"
            st.write(
                f"- {row.get('term', 'Term')}: support {row.get('support_level', 'Unknown')} | "
                f"ATS gain {row.get('ats_gain', 0)} | remaining gap {row.get('remaining_gap_flag', False)} | {status}"
            )
    else:
        st.write("None identified")
    st.write("**Targeted Gap Fixes**")
    for item in builder.get("targeted_gap_fixes", []):
        with st.expander(item.get("gap_name", "Gap")):
            st.write(f"**Supported by resume evidence:** {'Yes' if item.get('supported_by_resume_evidence') else 'No'}")
            evidence_used = item.get("resume_evidence_used", [])
            st.write("**Evidence used**")
            if evidence_used:
                for evidence in evidence_used:
                    st.write(f"- {evidence}")
            else:
                st.write("- No resume-backed evidence found.")
            st.write("**Rewritten bullets targeting gaps**")
            if item.get("rewritten_bullet_suggestions"):
                for suggestion in item.get("rewritten_bullet_suggestions", []):
                    st.write(f"- {suggestion}")
            else:
                st.write("- No ATS-safe rewrite was added.")
            st.write(f"**Keyword added:** {'Yes' if item.get('keyword_added') else 'No'}")
            st.write(f"**Keyword repositioned:** {'Yes' if item.get('keyword_repositioned') else 'No'}")
            if item.get("not_added_reason"):
                st.caption(item.get("not_added_reason", ""))
    coach_diagnostics = _resume_coach_diagnostics(builder)
    logger.info(
        "resume_coach_rendered=%s resume_coach_skip_reason=%s analysis_exists=%s resume_builder_exists=%s resume_text_exists=%s job_text_exists=%s optimized_resume_exists=%s missing_keywords_count=%s targeted_gap_fix_count=%s analysis_id=%s",
        coach_diagnostics["resume_coach_rendered"],
        coach_diagnostics["resume_coach_skip_reason"],
        coach_diagnostics["analysis_exists"],
        coach_diagnostics["resume_builder_exists"],
        coach_diagnostics["resume_text_exists"],
        coach_diagnostics["job_text_exists"],
        coach_diagnostics["optimized_resume_exists"],
        coach_diagnostics["missing_keywords_count"],
        coach_diagnostics["targeted_gap_fix_count"],
        st.session_state.get("last_application_id", 0),
    )
    st.write("**AI Resume Coach Diagnostics**")
    diagnostics_left, diagnostics_right = st.columns(2)
    with diagnostics_left:
        st.write(f"- resume_coach_rendered: {coach_diagnostics['resume_coach_rendered']}")
        st.write(f"- resume_coach_skip_reason: {coach_diagnostics['resume_coach_skip_reason']}")
        st.write(f"- analysis_exists: {coach_diagnostics['analysis_exists']}")
        st.write(f"- resume_builder_exists: {coach_diagnostics['resume_builder_exists']}")
        st.write(f"- resume_text_exists: {coach_diagnostics['resume_text_exists']}")
    with diagnostics_right:
        st.write(f"- job_text_exists: {coach_diagnostics['job_text_exists']}")
        st.write(f"- optimized_resume_exists: {coach_diagnostics['optimized_resume_exists']}")
        st.write(f"- missing_keywords_count: {coach_diagnostics['missing_keywords_count']}")
        st.write(f"- targeted_gap_fix_count: {coach_diagnostics['targeted_gap_fix_count']}")
    _render_resume_coach(builder)
    st.write("**Recruiter-ready bullet rewrites**")
    for bullet in builder.get("recruiter_ready_bullets", []):
        st.write(bullet)
    original_bullets_col, improved_bullets_col = st.columns(2)
    with original_bullets_col:
        st.write("**Original bullets**")
        for item in builder.get("rewritten_bullet_details", []):
            st.write(f"- {item.get('original_bullet', '')}")
    with improved_bullets_col:
        st.write("**Rewritten bullets**")
        for item in builder.get("rewritten_bullet_details", []):
            st.write(f"- {item.get('improved_bullet', '')}")
    st.write("**Original vs improved bullets**")
    for index, item in enumerate(builder.get("rewritten_bullet_details", []), start=1):
        with st.expander(f"Bullet {index}"):
            st.write(f"**Original bullet:** {item.get('original_bullet', '')}")
            st.write(f"**Improved bullet:** {item.get('improved_bullet', '')}")
            st.write(f"**Why it improved:** {item.get('why_it_improved', '')}")
            st.write(f"**Evidence used:** {item.get('evidence_used', '')}")
            st.write(f"**Recruiter explanation:** {item.get('recruiter_explanation', '')}")

    breakdown_left, breakdown_right = st.columns(2)
    with breakdown_left:
        st.write("**ATS Category Breakdown Before**")
        for item in builder.get("ats_breakdown_before", []):
            st.write(
                f"- {item['category']}: {item['score']}/{item['weight']} | "
                f"Matched: {', '.join(item.get('matched', [])) or 'None'} | "
                f"Missing: {', '.join(item.get('missing', [])[:5]) or 'None'}"
            )
    with breakdown_right:
        st.write("**ATS Category Breakdown After**")
        for item in builder.get("ats_breakdown_after", []):
            st.write(
                f"- {item['category']}: {item['score']}/{item['weight']} | "
                f"Matched: {', '.join(item.get('matched', [])) or 'None'} | "
                f"Missing: {', '.join(item.get('missing', [])[:5]) or 'None'}"
            )

    before_col, after_col = st.columns(2)
    with before_col:
        st.write("**Original Resume**")
        st.text_area(
            "Original resume preview",
            st.session_state.get("resume_text", ""),
            height=520,
        )
    with after_col:
        st.write("**Optimized Resume**")
        st.text_area(
            "Optimized resume preview",
            builder.get("optimized_resume_text", ""),
            height=520,
        )

    docx_bytes = build_optimized_resume_docx(builder.get("optimized_resume_text", ""))
    pdf_bytes = build_optimized_resume_pdf(builder.get("optimized_resume_text", ""))
    st.download_button(
        "Download Optimized Resume DOCX",
        data=docx_bytes,
        file_name=_optimized_resume_filename(builder.get("optimized_resume_text", ""), "docx"),
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    st.download_button(
        "Download Optimized Resume PDF",
        data=pdf_bytes,
        file_name=_optimized_resume_filename(builder.get("optimized_resume_text", ""), "pdf"),
        mime="application/pdf",
    )
    render_learning_resources_section("resume_builder")


def render_cover_letter_tab() -> None:
    st.subheader("Cover letter")
    analysis = st.session_state.get("analysis", {}) or {}
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Your cover letter will appear here after analysis.")
        return
    render_pdf_download_button(
        "Cover Letter",
        analysis,
        st.session_state.get("resume_text", ""),
        st.session_state.get("job_text", ""),
        generated,
    )
    _render_role_match_snapshot(analysis, "Recruiter Summary Card")
    st.text_area("Cover letter", generated["cover_letter"], height=420)


def render_interview_tab() -> None:
    st.subheader("Interview Intelligence")
    analysis = st.session_state.get("analysis", {}) or {}
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Interview preparation insights will appear here after analysis.")
        return

    dashboard = generated.get("interview_dashboard", {})
    if not dashboard:
        st.warning("Interview intelligence is not available yet. Re-run generation to refresh the output.")
        return
    render_pdf_download_button(
        "Interview Intelligence",
        analysis,
        st.session_state.get("resume_text", ""),
        st.session_state.get("job_text", ""),
        generated,
    )
    _render_role_match_snapshot(analysis, "Recruiter Summary Card")

    top_questions = dashboard.get("top_25_likely_questions", [])
    technical_questions = dashboard.get("technical_questions", [])
    behavioral_questions = dashboard.get("behavioral_questions", [])
    challenges = dashboard.get("potential_challenges", [])

    avg_confidence = 0
    scored_items = top_questions + technical_questions + behavioral_questions
    if scored_items:
        avg_confidence = round(sum(item.get("confidence_score", 0) for item in scored_items) / len(scored_items))

    st.caption(dashboard.get("overview", ""))

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("Likely Questions", len(top_questions))
    metric2.metric("Technical", len(technical_questions))
    metric3.metric("Behavioral", len(behavioral_questions))
    metric4.metric("Avg Confidence", f"{avg_confidence}/100")

    section_tabs = st.tabs(
        [
            "Top 25 Questions",
            "Technical",
            "Behavioral",
            "Ask Them",
            "Challenges",
        ]
    )

    def render_question_list(items: list[dict], prefix: str) -> None:
        for index, item in enumerate(items, start=1):
            label = f"{prefix} {index}: {item['question']}"
            with st.expander(label):
                if item.get("category"):
                    st.write(f"**Category:** {item['category'].title()}")
                st.write(f"**Confidence Score:** {item.get('confidence_score', 0)}/100")
                st.write("**Suggested Answer**")
                st.write(item.get("answer_summary", ""))
                star = item.get("star_answer", {})
                st.write("**STAR Structure**")
                st.write(f"Situation: {star.get('situation', '')}")
                st.write(f"Task: {star.get('task', '')}")
                st.write(f"Action: {star.get('action', '')}")
                st.write(f"Result: {star.get('result', '')}")

    with section_tabs[0]:
        render_question_list(top_questions, "Likely Question")

    with section_tabs[1]:
        render_question_list(technical_questions, "Technical Question")

    with section_tabs[2]:
        render_question_list(behavioral_questions, "Behavioral Question")

    with section_tabs[3]:
        st.write("**Questions the candidate should ask the interviewer**")
        for item in dashboard.get("questions_for_interviewer", []):
            st.write(f"- {item}")

    with section_tabs[4]:
        st.write("**Potential weaknesses or gaps the interviewer may challenge**")
        for index, item in enumerate(challenges, start=1):
            with st.expander(f"Challenge {index}: {item['challenge']}"):
                st.write(f"**Why this may come up:** {item.get('why_it_may_come_up', '')}")
                st.write(f"**Suggested response:** {item.get('suggested_response', '')}")
                st.write(f"**Confidence Score:** {item.get('confidence_score', 0)}/100")


def render_career_coach_tab() -> None:
    st.subheader("Career Coach")
    analysis = st.session_state.get("analysis", {}) or {}
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Career coaching insights will appear here after analysis.")
        return

    coach = generated.get("career_coach", {})
    if not coach:
        st.warning("Career coaching recommendations are not available yet. Re-run generation to refresh the output.")
        return
    render_pdf_download_button(
        "Career Coach",
        analysis,
        st.session_state.get("resume_text", ""),
        st.session_state.get("job_text", ""),
        generated,
    )
    _render_role_match_snapshot(analysis, "Recruiter Summary Card")

    st.caption(coach.get("overview", ""))

    left, right = st.columns(2)
    with left:
        st.write("**Missing skills**")
        for item in coach.get("missing_skills", []):
            st.write(f"- {item}")
        st.write("**Missing technologies**")
        for item in coach.get("missing_technologies", []):
            st.write(f"- {item}")
    with right:
        st.write("**Missing certifications**")
        for item in coach.get("missing_certifications", []):
            st.write(f"- {item}")
        st.write("**Missing industry experience**")
        for item in coach.get("missing_industry_experience", []):
            st.write(f"- {item}")

    plan_tabs = st.tabs(
        [
            "30-Day Plan",
            "90-Day Plan",
            "Certifications",
            "Courses",
            "Resume Improvements",
        ]
    )

    def render_improvement_list(items: list[dict], action_key: str) -> None:
        for index, item in enumerate(items, start=1):
            title = item.get(action_key, f"Item {index}")
            with st.expander(f"{index}. {title}"):
                if item.get("why_it_matters"):
                    st.write(f"**Why it matters:** {item['why_it_matters']}")
                if item.get("reason"):
                    st.write(f"**Reason:** {item['reason']}")
                st.write(f"**Estimated Job Fit Score increase:** +{item.get('estimated_job_fit_increase', 0)}")

    with plan_tabs[0]:
        render_improvement_list(coach.get("thirty_day_plan", []), "action")
    with plan_tabs[1]:
        render_improvement_list(coach.get("ninety_day_plan", []), "action")
    with plan_tabs[2]:
        render_improvement_list(coach.get("recommended_certifications", []), "name")
    with plan_tabs[3]:
        render_improvement_list(coach.get("recommended_courses", []), "name")
    with plan_tabs[4]:
        render_improvement_list(coach.get("resume_improvements", []), "change")


def render_linkedin_tab() -> None:
    st.subheader("LinkedIn recruiter message")
    analysis = st.session_state.get("analysis", {}) or {}
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Your LinkedIn outreach message will appear here after analysis.")
        return
    render_pdf_download_button(
        "LinkedIn Message",
        analysis,
        st.session_state.get("resume_text", ""),
        st.session_state.get("job_text", ""),
        generated,
    )
    _render_role_match_snapshot(analysis, "Recruiter Summary Card")
    st.text_area("LinkedIn message", generated["linkedin_recruiter_message"], height=220)


def render_thank_you_tab() -> None:
    st.subheader("Thank-you email")
    analysis = st.session_state.get("analysis", {}) or {}
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Your thank-you email will appear here after analysis.")
        return
    render_pdf_download_button(
        "Thank You Email",
        analysis,
        st.session_state.get("resume_text", ""),
        st.session_state.get("job_text", ""),
        generated,
    )
    _render_role_match_snapshot(analysis, "Recruiter Summary Card")
    st.text_area("Thank-you email", generated["thank_you_email"], height=220)


def render_export_tab() -> None:
    st.subheader("Export")
    analysis = st.session_state.get("analysis")
    generated = st.session_state.get("generated")
    if not analysis or not generated:
        st.info("Generate materials first to enable export.")
        return
    render_pdf_download_button(
        "Export",
        analysis,
        st.session_state.get("resume_text", ""),
        st.session_state.get("job_text", ""),
        generated,
    )
    _render_role_match_snapshot(analysis, "Recruiter Summary Card")

    package = {
        "analysis": analysis,
        "generated": generated,
        "resume_filename": st.session_state.get("resume_filename", ""),
        "job_filename": st.session_state.get("job_filename", ""),
        "job_url": st.session_state.get("job_url", ""),
        "job_location": st.session_state.get("job_location_preview", ""),
        "job_date_posted": st.session_state.get("job_date_posted_preview", ""),
        "job_category": st.session_state.get("job_category_preview", ""),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    docx_bytes = build_full_report_docx(package)
    st.download_button(
        "Download DOCX",
        data=docx_bytes,
        file_name="career_match_export.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    st.write("**Results summary email**")
    results_summary_email = generated.get("results_summary_email", "")
    st.text_area("Analysis summary email template", results_summary_email, height=220)
    if not email_configured():
        st.caption("Email not configured. Add SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, and FROM_EMAIL to enable sending later.")
    else:
        if st.button("Email Summary to My Account", use_container_width=True):
            subject_line = "Career Match Results Summary"
            body_lines = results_summary_email.splitlines()
            if body_lines and body_lines[0].lower().startswith("subject:"):
                subject_line = body_lines[0].split(":", 1)[1].strip() or subject_line
                body_content = "\n".join(body_lines[2:]) if len(body_lines) > 2 else results_summary_email
            else:
                body_content = results_summary_email
            success, message = send_email_message(st.session_state.get("user_email", ""), subject_line, body_content)
            if success:
                st.success(message)
            else:
                st.error(message)

    st.write("**Saved applications**")
    applications = list_applications(limit=10, user_email=st.session_state.get("user_email", ""))
    if not applications:
        st.caption("No saved applications yet.")
        return

    for item in applications:
        st.write(
            f"- {item['created_at']} | {item['job_title']} at {item['company_name']} | ATS {item['ats_score']} | {_payment_type_label(item.get('payment_type_used', 'free'))}"
        )


def render_evidence_tab() -> None:
    st.subheader("Evidence")
    analysis = st.session_state.get("analysis", {}) or {}
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Evidence details will appear here after analysis.")
        return

    builder = generated.get("resume_builder", {})
    if not builder:
        st.info("Resume evidence details are not available yet.")
        return
    render_pdf_download_button(
        "Evidence",
        analysis,
        st.session_state.get("resume_text", ""),
        st.session_state.get("job_text", ""),
        generated,
    )
    _render_role_match_snapshot(analysis, "Recruiter Summary Card")

    st.metric("Trust Score", f"{builder.get('trust_score', 0)}%")
    st.write("**Added keywords**")
    st.write(", ".join(builder.get("keywords_added", [])) or "None identified")

    bridge_guidance = builder.get("bridge_the_gap_guidance", [])
    if bridge_guidance:
        st.write("**Bridge the Gap Guidance**")
        for item in bridge_guidance:
            with st.expander(item.get("competency", "Competency")):
                st.write(f"**Resume evidence:** {item.get('resume_evidence', '')}")
                st.write(f"**Exact resume line:** {item.get('exact_resume_line', '')}")
                st.write(f"**Interview bridge:** {item.get('interview_bridge', '')}")
                st.write(f"**Confidence Score:** {item.get('confidence_score', 0)}%")

    explanations = builder.get("added_keyword_explanations", [])
    if not explanations:
        st.caption("No evidence-backed keyword additions were needed.")
        return

    for item in explanations:
        with st.expander(f"{item['keyword']} ({item.get('category', 'Other')})"):
            st.write(f"**Why it was added:** {item.get('why_added', '')}")
            st.write(f"**Source Resume Evidence:** {item.get('source_resume_evidence', '')}")
            st.write(f"**Exact Resume Line:** {item.get('exact_resume_line', '')}")
            st.write(f"**Confidence Score:** {item.get('confidence_score', 0)}%")
            st.write(f"**Evidence Type:** {item.get('evidence_type', '').title()}")


def render_auth_page() -> None:
    st.markdown(
        """
        <div class="auth-shell">
          <div class="auth-hero">
            <div class="eyebrow">Career Match</div>
            <h1 class="hero-title" style="margin-bottom:0.75rem;">Start your analysis</h1>
            <p class="hero-copy" style="margin-bottom:0;">Create an account or sign in to unlock resume matching, interview prep, and evidence-backed guidance.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    notice = st.session_state.get("auth_notice", "")
    if notice:
        st.info(notice)
        st.session_state["auth_notice"] = ""

    st.markdown(
        "<div class='auth-panel'>",
        unsafe_allow_html=True,
    )
    login_tab, register_tab = st.tabs(["Log In", "Register"])

    with login_tab:
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log In", use_container_width=True)
        if submitted:
            success, result = authenticate_user(email, password)
            if success:
                _log_in_user(result)
                st.rerun()
            st.error(result)

    with register_tab:
        with st.form("register_form", clear_on_submit=False):
            full_name = st.text_input("Full Name", key="register_full_name")
            email = st.text_input("Email", key="register_email")
            password = st.text_input("Password", type="password", key="register_password")
            confirm_password = st.text_input("Confirm Password", type="password", key="register_confirm_password")
            submitted = st.form_submit_button("Create Account", use_container_width=True)
        if submitted:
            if password != confirm_password:
                st.error("Passwords must match before we can create your account.")
            else:
                success, result = create_user(
                    created_at=datetime.now().isoformat(timespec="seconds"),
                    email=email,
                    password=password,
                    full_name=full_name,
                    is_admin=(email or "").strip().lower() in _admin_emails(),
                )
                if success:
                    _log_in_user(result)
                    st.rerun()
                st.error(result)

    forgot_tab, reset_tab, verify_tab = st.tabs(["Forgot Password", "Reset Password", "Verify Email"])
    with forgot_tab:
        with st.form("forgot_password_form", clear_on_submit=False):
            email = st.text_input("Account Email", key="forgot_email")
            submitted = st.form_submit_button("Request Reset Token", use_container_width=True)
        if submitted:
            success, result = create_password_reset_token(
                email=email,
                expires_at=(datetime.now() + timedelta(minutes=30)).isoformat(timespec="seconds"),
            )
            if success:
                if _email_delivery_configured():
                    st.success("Reset request received. Check your email for the password reset link.")
                else:
                    st.info("Email delivery is not configured yet.")
                    st.success(
                        "Reset token created. For local development, use this token in the reset form: "
                        f"`{result}`"
                    )
            else:
                st.error(result)
    with reset_tab:
        with st.form("reset_password_form", clear_on_submit=False):
            token = st.text_input("Reset Token", key="reset_token")
            new_password = st.text_input("New Password", type="password", key="reset_password")
            confirm_password = st.text_input("Confirm New Password", type="password", key="reset_confirm_password")
            submitted = st.form_submit_button("Reset Password", use_container_width=True)
        if submitted:
            if new_password != confirm_password:
                st.error("Passwords must match before the password can be reset.")
            else:
                success, result = consume_password_reset_token(
                    token=token,
                    new_password=new_password,
                    current_time=datetime.now().isoformat(timespec="seconds"),
                )
                if success:
                    st.success(result)
                else:
                    st.error(result)
    with verify_tab:
        with st.form("verify_email_request_form", clear_on_submit=False):
            email = st.text_input("Verification Email", key="verify_email")
            request_submitted = st.form_submit_button("Request Verification Token", use_container_width=True)
        if request_submitted:
            success, result = create_email_verification_token(
                email=email,
                expires_at=(datetime.now() + timedelta(hours=2)).isoformat(timespec="seconds"),
            )
            if success:
                if _email_delivery_configured():
                    st.success("Verification email requested. Check your inbox for the verification link.")
                else:
                    st.info("Email delivery is not configured yet.")
                    st.success(f"Verification token for local development: `{result}`")
            else:
                st.error(result)
        with st.form("verify_email_token_form", clear_on_submit=False):
            token = st.text_input("Verification Token", key="verify_email_token")
            verify_submitted = st.form_submit_button("Verify Email", use_container_width=True)
        if verify_submitted:
            success, result = consume_email_verification_token(
                token=token,
                current_time=datetime.now().isoformat(timespec="seconds"),
            )
            if success:
                st.success(result)
            else:
                st.error(result)
    st.markdown("</div>", unsafe_allow_html=True)

    helper_left, helper_right = st.columns([1, 1])
    with helper_left:
        if st.button("Back to Home", use_container_width=True):
            _set_view("home")
            st.rerun()
    with helper_right:
        st.caption("Use the same email and password next time to continue from the app workflow.")


def render_app_header() -> None:
    render_beta_banner()
    header_left, header_middle, header_right = st.columns([6, 2, 2])
    with header_left:
        st.markdown(
            f"""
            <div class="app-header-card">
              <h1>{APP_NAME}</h1>
              <p>Match your resume to any job and understand exactly where you stand.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with header_middle:
        st.write("")
        st.write("")
        if st.button("Home", use_container_width=True):
            _set_view("home")
            st.rerun()
    with header_right:
        st.write("")
        st.write("")
        if st.button("Log Out", use_container_width=True):
            _log_out_user()
            st.rerun()

    user_email = st.session_state.get("user_email", "")
    if user_email:
        st.caption(f"Signed in as {user_email}")


def render_public_page(view_name: str) -> None:
    _track_page_view(view_name, "")
    if view_name == "contact":
        render_contact_page()
    elif view_name == "privacy":
        render_privacy_page()
    elif view_name == "terms":
        render_terms_page()
    elif view_name == "pro":
        render_pro_page()
    elif view_name == "admin":
        render_admin_page()
    elif view_name in SEO_VIEWS:
        render_seo_page(view_name)
    else:
        render_landing_page()


def render_dashboard_page() -> None:
    st.subheader("Dashboard")
    metrics = get_dashboard_metrics(st.session_state.get("user_email", ""))
    recent = metrics.get("recent_analyses", [])

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Jobs Analyzed", metrics.get("jobs_analyzed", 0))
    col2.metric("Average Fit Score", f"{metrics.get('average_fit_score', 0)}/100")
    col3.metric("Best Fit Score", f"{metrics.get('best_fit_score', 0)}/100")
    col4.metric("PDF Downloads", metrics.get("pdf_downloads", 0))
    col5.metric("Current Access", str(metrics.get("current_plan", "Open Beta")))
    extra1, extra2, extra3, extra4 = st.columns(4)
    extra1.metric("Analyses Per User", metrics.get("analyses_per_user", 0))
    extra2.metric("Repeat Users", metrics.get("repeat_users", 0))
    extra3.metric("Feedback Submissions", metrics.get("feedback_submissions", 0))
    extra4.metric("Subscription Status", "Not required")

    st.success("Open beta access is active. Analyses, exports, and job evaluations are currently free.")

    st.write("**Recent analyses**")
    if not recent:
        st.caption("Your recent analyses will appear here after you run the first job match.")
        return

    for item in recent:
        with st.container():
            st.markdown(
                f"""
                <div class="page-card">
                  <strong>{item.get('job_title', 'Role')}</strong> at {item.get('company_name', 'Company')}<br/>
                  <span style="color:#475569;">{item.get('created_at', '')} | {item.get('job_location', 'Location not provided')} | Fit {item.get('ats_score', 0)}/100 | {_payment_type_label(item.get('payment_type_used', 'free'))}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_history_page() -> None:
    st.subheader("Analysis History")
    applications = list_applications(limit=50, user_email=st.session_state.get("user_email", ""))
    if not applications:
        st.info("Saved analyses will appear here after you run your first job match.")
        return

    filter_left, filter_right, filter_score, filter_rec = st.columns(4)
    company_filter = filter_left.text_input("Company Filter")
    title_filter = filter_right.text_input("Job Title Filter")
    min_score = filter_score.slider("Minimum Fit Score", 0, 100, 0)
    recommendation_filter = filter_rec.selectbox("Recommendation", ["All", "Apply Immediately", "Good Stretch Opportunity", "Low Probability Match", "Not Recommended"])

    search_term = st.text_input("Search by company, role, or keyword")

    summary_rows = []
    for item in applications:
        payload = {}
        payload_json = item.get("payload_json", "")
        if payload_json:
            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError:
                payload = {}
        saved_analysis = payload.get("analysis", {})
        analysis = _hydrate_saved_analysis(item, saved_analysis)
        generated = payload.get("generated", {})
        display_analysis = analysis or {}
        recommendation = (analysis.get("job_fit", {}) or {}).get("recommendation", "Not available")
        haystack = " ".join([
            str(item.get("company_name", "")),
            str(item.get("job_title", "")),
            str(item.get("job_location", "")),
            " ".join(analysis.get("matching_keywords", [])) if analysis else "",
        ]).lower()
        if company_filter and company_filter.lower() not in str(item.get("company_name", "")).lower():
            continue
        if title_filter and title_filter.lower() not in str(item.get("job_title", "")).lower():
            continue
        if int(item.get("ats_score", 0)) < min_score:
            continue
        if recommendation_filter != "All" and recommendation != recommendation_filter:
            continue
        if search_term and search_term.lower() not in haystack:
            continue
        summary_rows.append(
            {
                "Date": item.get("created_at", ""),
                "Company": item.get("company_name", ""),
                "Job Title": item.get("job_title", ""),
                "Location": item.get("job_location", ""),
                "Fit Score": item.get("ats_score", 0),
                "Recommendation": recommendation,
                "Payment Type": _payment_type_label(item.get("payment_type_used", "free")),
            }
        )

    if summary_rows:
        st.dataframe(summary_rows, use_container_width=True, hide_index=True)

    for item in applications:
        payload = {}
        payload_json = item.get("payload_json", "")
        if payload_json:
            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError:
                payload = {}
        analysis = payload.get("analysis", {})
        generated = payload.get("generated", {})
        recommendation = (analysis.get("job_fit", {}) or {}).get("recommendation", "Not available")
        haystack = " ".join([
            str(item.get("company_name", "")),
            str(item.get("job_title", "")),
            str(item.get("job_location", "")),
            " ".join(analysis.get("matching_keywords", [])) if analysis else "",
        ]).lower()
        if company_filter and company_filter.lower() not in str(item.get("company_name", "")).lower():
            continue
        if title_filter and title_filter.lower() not in str(item.get("job_title", "")).lower():
            continue
        if int(item.get("ats_score", 0)) < min_score:
            continue
        if recommendation_filter != "All" and recommendation != recommendation_filter:
            continue
        if search_term and search_term.lower() not in haystack:
            continue
        with st.expander(f"{item['created_at']} | {item['job_title']} at {item['company_name']}"):
            st.write(f"**Date:** {item.get('created_at', '')}")
            st.write(f"**Company:** {item.get('company_name', '')}")
            st.write(f"**Job Title:** {item.get('job_title', '')}")
            st.write(f"**Location:** {item.get('job_location', '')}")
            st.write(f"**Fit Score:** {item.get('ats_score', 0)}/100")
            st.write(f"**Payment Type Used:** {_payment_type_label(item.get('payment_type_used', 'free'))}")
            st.write(f"**Direct Match Score:** {analysis.get('direct_match_score', 0) if analysis else 0}/100")
            st.write(f"**Transferable Match Score:** {analysis.get('transferable_match_score', 0) if analysis else 0}/100")
            st.write(f"**Recommendation:** {recommendation}")
            if item.get("job_location"):
                pass
            if item.get("job_url"):
                st.write(f"**Job URL:** {item['job_url']}")
            st.write(
                f"**ATS Before / After:** {item.get('original_ats_score', 0)}/100 -> {item.get('optimized_ats_score', 0)}/100"
            )
            if display_analysis:
                exact_matches = _exact_keyword_matches(display_analysis)
                semantic_matches = _semantic_skill_matches(display_analysis)
                st.write("**Role lens:** " + display_analysis.get("role_family", "General Professional Role"))
                st.write("**Top strengths:** " + (", ".join(display_analysis.get("role_specific_strengths", [])[:3]) or "Not available"))
                st.write("**Exact Keyword Matches:** " + (", ".join(exact_matches) or "None identified"))
                if semantic_matches:
                    semantic_summary = ", ".join(
                        f"{match['skill']} ({match['confidence']}%)" for match in semantic_matches[:5]
                    )
                    st.write("**Semantic Matches:** " + semantic_summary)
                elif not exact_matches:
                    st.write("**Semantic Matches:** None identified")
                else:
                    st.write("**Semantic Matches:** None identified")
            if st.button("Reopen Analysis", key=f"reopen_{item['id']}"):
                st.session_state["analysis"] = display_analysis or None
                rebuilt_generated = generated or {}
                st.session_state["resume_text"] = (
                    item.get("original_resume_text")
                    or item.get("resume_text")
                    or st.session_state.get("resume_text", "")
                )
                st.session_state["job_text"] = (
                    item.get("job_description_text")
                    or st.session_state.get("job_text", "")
                )
                if st.session_state["analysis"] and st.session_state["resume_text"] and st.session_state["job_text"]:
                    if not _generated_matches_analysis(st.session_state["analysis"], rebuilt_generated):
                        rebuilt_generated = _rebuild_generated_outputs(
                            st.session_state["resume_text"],
                            st.session_state["job_text"],
                            st.session_state["analysis"],
                        )
                st.session_state["generated"] = rebuilt_generated or None
                if rebuilt_generated and rebuilt_generated.get("resume_builder"):
                    st.session_state["optimized_resume_text"] = rebuilt_generated["resume_builder"].get("optimized_resume_text", "")
                st.session_state["resume_coach_logged_opened"] = False
                st.session_state["active_role_profile"] = st.session_state["analysis"].get("active_role_profile", {})
                st.session_state["active_role_fingerprint"] = st.session_state["analysis"].get("role_profile_fingerprint", "")
                st.session_state["last_application_id"] = item.get("id", 0)
                st.session_state["app_page"] = "Workflow"
                st.success("Analysis reopened in the workflow.")
                st.rerun()
            if st.button("Duplicate Analysis", key=f"duplicate_{item['id']}"):
                st.session_state["analysis"] = display_analysis or None
                rebuilt_generated = generated or {}
                st.session_state["resume_text"] = (
                    item.get("original_resume_text")
                    or item.get("resume_text")
                    or st.session_state.get("resume_text", "")
                )
                st.session_state["job_text"] = (
                    item.get("job_description_text")
                    or st.session_state.get("job_text", "")
                )
                if st.session_state["analysis"] and st.session_state["resume_text"] and st.session_state["job_text"]:
                    if not _generated_matches_analysis(st.session_state["analysis"], rebuilt_generated):
                        rebuilt_generated = _rebuild_generated_outputs(
                            st.session_state["resume_text"],
                            st.session_state["job_text"],
                            st.session_state["analysis"],
                        )
                st.session_state["generated"] = rebuilt_generated or None
                st.session_state["resume_coach_logged_opened"] = False
                st.session_state["active_role_profile"] = st.session_state["analysis"].get("active_role_profile", {})
                st.session_state["active_role_fingerprint"] = st.session_state["analysis"].get("role_profile_fingerprint", "")
                st.session_state["app_page"] = "Workflow"
                st.success("Analysis duplicated into the workflow for editing.")
                st.rerun()
            if st.button("Delete Analysis", key=f"delete_{item['id']}"):
                success, message = delete_application(st.session_state.get("user_email", ""), item["id"])
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)


def render_saved_resumes_page() -> None:
    st.subheader("My Resumes")
    resumes = list_saved_resumes(st.session_state.get("user_email", ""))
    if not resumes:
        st.info("Saved resumes will appear here after you upload a resume in the workflow.")
        return
    for item in resumes:
        with st.expander(f"{item.get('resume_name', 'Resume')} | {item.get('original_filename', '')}"):
            st.write(f"**Resume name:** {item.get('resume_name', '')}")
            st.write(f"**File name:** {item.get('original_filename', '')}")
            st.write(f"**Created:** {item.get('created_at', '')}")
            st.write(f"**Last used:** {item.get('last_used_at', '')}")
            if st.button("Use Resume", key=f"use_resume_{item['resume_id']}"):
                saved_resume = get_saved_resume(st.session_state.get("user_email", ""), item["resume_id"])
                if saved_resume:
                    st.session_state["resume_text"] = saved_resume.get("extracted_text", "")
                    st.session_state["resume_filename"] = saved_resume.get("original_filename", "")
                    st.session_state["app_page"] = "Workflow"
                    mark_saved_resume_used(st.session_state.get("user_email", ""), item["resume_id"])
                    st.success("Saved resume loaded into the workflow.")
                    st.rerun()
            new_name = st.text_input("Rename resume", value=item.get("resume_name", ""), key=f"rename_resume_text_{item['resume_id']}")
            if st.button("Rename", key=f"rename_resume_{item['resume_id']}"):
                success, message = rename_saved_resume(st.session_state.get("user_email", ""), item["resume_id"], new_name)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            if st.button("Delete", key=f"delete_resume_{item['resume_id']}"):
                success, message = delete_saved_resume(st.session_state.get("user_email", ""), item["resume_id"])
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)


def render_profile_page() -> None:
    st.subheader("User Profile")
    user_email = st.session_state.get("user_email", "")
    profile = get_user_profile(user_email) or {}
    access = _assessment_access()

    with st.form("profile_form", clear_on_submit=False):
        full_name = st.text_input("Full Name", value=profile.get("full_name", ""))
        email_display = st.text_input("Email", value=user_email, disabled=True)
        submitted = st.form_submit_button("Save Profile")
    if submitted:
        success, message = update_user_profile(user_email, full_name)
        if success:
            st.success(message)
        else:
            st.error(message)

    st.write("**Access**")
    st.write(f"Current plan: {access.get('current_plan_label', 'Open Beta')}")
    st.write("Analysis access: Unlimited during beta")
    st.write("PDF exports: Unlimited during beta")
    st.write(f"Total analyses: {get_dashboard_metrics(user_email).get('jobs_analyzed', 0)}")
    st.write("Subscription status: Not required during beta")
    st.write(f"Email verified: {'Yes' if profile.get('email_verified') else 'No'}")
    st.caption("Career Match is in open beta. Premium features are not required to use the core workflow right now.")
    render_waitlist_section("profile")
    st.caption("Change password is available from the auth screen. Delete account requests can be submitted through Contact.")


def render_subscription_page() -> None:
    st.subheader("Subscription")
    st.success("Open beta mode is active. No subscription is required to use Career Match right now.")
    st.write("- Unlimited resume analyses")
    st.write("- Unlimited PDF exports")
    st.write("- Unlimited job description evaluations")
    render_waitlist_section("subscription")


def render_pro_page() -> None:
    st.subheader("Career Match Pro")
    st.success("Career Match is currently free during beta. We welcome feedback.")
    st.write("Future premium capabilities may include team collaboration, advanced analytics, recruiter review workflows, and branded exports.")
    render_waitlist_section("pro")

    if st.button("Return to Dashboard", use_container_width=True):
        if st.session_state.get("is_authenticated"):
            st.session_state["app_page"] = "Dashboard"
            _set_view("app")
        else:
            _set_view("home")
        st.rerun()
    if not st.session_state.get("is_authenticated"):
        if st.button("Back to Home", key="pro_home", use_container_width=True):
            _set_view("home")
            st.rerun()

    with st.expander("Beta diagnostics"):
        st.write(f"**Open beta enabled:** {'Yes' if open_beta_enabled() else 'No'}")
        st.write(f"**Authenticated user:** {st.session_state.get('user_email', '') or 'Not signed in'}")


def render_contact_page() -> None:
    st.subheader("Contact")
    default_profile = get_user_profile(st.session_state.get("user_email", "")) or {}
    with st.form("contact_form", clear_on_submit=True):
        name = st.text_input("Name", value=default_profile.get("full_name", ""))
        email = st.text_input("Email", value=st.session_state.get("user_email", ""))
        message_type = st.selectbox(
            "Message type",
            ["Support", "Billing", "Bug Report", "Feature Request", "Partnership", "Privacy Request"],
        )
        message = st.text_area("Message", height=180)
        submitted = st.form_submit_button("Submit", use_container_width=True)
    if submitted:
        submission = ContactSubmission(
            created_at=datetime.now().isoformat(timespec="seconds"),
            user_id=get_user_id((email or "").strip().lower()) if (email or "").strip() else 0,
            user_email=(email or "").strip().lower(),
            name=name.strip(),
            message_type=message_type,
            message=message.strip(),
            status="new",
        )
        save_contact_submission(submission)
        st.success("Thanks for reaching out. Your message has been saved and is ready for follow-up.")
    if not st.session_state.get("is_authenticated"):
        if st.button("Back to Home", key="contact_home", use_container_width=True):
            _set_view("home")
            st.rerun()


def render_privacy_page() -> None:
    st.subheader("Privacy Policy")
    st.write("Career Match may store account email, resume uploads, job description URLs, manual pasted job descriptions, generated AI outputs, analysis history, contact messages, and feedback submissions so the service can function and preserve user history.")
    st.write("Resume uploads and job descriptions are processed to generate fit analysis, resume rewrites, interview preparation, and related outputs.")
    st.write("Account records include email addresses and securely hashed passwords. Plaintext passwords are not stored.")
    st.write("Generated outputs and saved analyses may be retained in the application database to support dashboard metrics, history, reopened analyses, and saved resume features.")
    st.write("If billing is enabled in the future, payment data would be handled through Stripe. During beta, Career Match stores only the metadata needed for account workflow, history, and analytics.")
    st.write("Career Match does not sell user resumes. Users may request account or data deletion through the contact channel. Contact email placeholder: support@careermatch.example")
    st.write("Retention periods may vary by plan, support need, and deployment environment.")
    if not st.session_state.get("is_authenticated"):
        if st.button("Back to Home", key="privacy_home", use_container_width=True):
            _set_view("home")
            st.rerun()


def render_terms_page() -> None:
    st.subheader("Terms of Service")
    st.write("Career Match is a decision-support tool that provides AI-generated resume analysis and writing assistance. All content should be reviewed by the user before submission to any employer.")
    st.write("The service does not guarantee interviews, job offers, or employment outcomes.")
    st.write("Career Match does not provide legal, financial, employment, or career guarantees.")
    st.write("Users are responsible for confirming that generated materials are accurate, truthful, and appropriate for the target role.")
    st.write("Future premium plans may be introduced after beta. Any future billing terms would be communicated clearly before charges apply.")
    st.write("Accounts may be limited or terminated for abuse, misuse, or service protection reasons.")
    st.write("Service availability may vary based on hosting, third-party APIs, maintenance windows, and platform outages.")
    if not st.session_state.get("is_authenticated"):
        if st.button("Back to Home", key="terms_home", use_container_width=True):
            _set_view("home")
            st.rerun()


def render_feedback_section() -> None:
    analysis = st.session_state.get("analysis")
    if not analysis or not st.session_state.get("last_application_id"):
        return
    st.divider()
    st.write("**Was this analysis helpful?**")
    if st.session_state.get("feedback_submitted_for_analysis"):
        st.success("Thanks for your feedback.")
        return

    with st.form("analysis_feedback_form", clear_on_submit=True):
        helpful_label = st.radio("Helpful", ["Helpful", "Not Helpful"], horizontal=True)
        comment = st.text_area("Optional comment", height=120)
        submitted = st.form_submit_button("Submit Feedback")
    if submitted:
        feedback = AnalysisFeedback(
            created_at=datetime.now().isoformat(timespec="seconds"),
            user_email=st.session_state.get("user_email", ""),
            user_id=get_user_id(st.session_state.get("user_email", "")),
            application_id=int(st.session_state.get("last_application_id", 0)),
            rating=helpful_label,
            comment=comment.strip(),
        )
        save_analysis_feedback(feedback)
        st.session_state["feedback_submitted_for_analysis"] = True
        st.success("Thanks for your feedback.")


def render_admin_page() -> None:
    st.subheader("Admin")
    admin_details = _admin_auth_details()
    st.write(f"**Admin User:** {'true' if admin_details['authorized'] else 'false'}")
    st.caption(
        f"Current user email: {admin_details['email'] or 'anonymous'} | "
        f"is_admin: {str(admin_details['is_admin_flag']).lower()} | "
        f"authorized: {str(admin_details['authorized']).lower()}"
    )
    logger.info(
        "Admin authorization check. current_user_email=%s is_admin=%s allowlisted=%s authorized=%s",
        admin_details["email"] or "anonymous",
        admin_details["is_admin_flag"],
        admin_details["allowlisted"],
        admin_details["authorized"],
    )
    if not admin_details["authorized"]:
        st.error("You do not have access to this page.")
        return
    metrics = admin_metrics()
    overview_tab, messages_tab = st.tabs(["Overview", "Messages"])

    with overview_tab:
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Total Users", metrics.get("total_users", 0))
        col2.metric("Active Users (30d)", metrics.get("active_users", 0))
        col3.metric("Free Users", metrics.get("free_users", 0))
        col4.metric("Paid Users", metrics.get("paid_users", 0))
        col5.metric("Conversion Rate", f"{metrics.get('conversion_rate', 0)}%")
        col6.metric("Assessments Completed", metrics.get("completed_assessments", 0))

        stat1, stat2, stat3, stat4, stat5, stat6 = st.columns(6)
        stat1.metric("Registrations", metrics.get("registrations", 0))
        stat2.metric("Total Analyses", metrics.get("total_analyses", 0))
        stat3.metric("Analyses / User", metrics.get("analyses_per_user", 0))
        stat4.metric("Repeat Users", metrics.get("repeat_users", 0))
        stat5.metric("PDF Downloads", metrics.get("pdf_downloads", 0))
        stat6.metric("Unread Messages", metrics.get("open_contact_messages", 0))

        affiliate1, affiliate2, affiliate3, affiliate4, affiliate5 = st.columns(5)
        affiliate1.metric("Affiliate Clicks", metrics.get("total_affiliate_clicks", 0))
        affiliate2.metric("Affiliate Clicks (7d)", metrics.get("affiliate_clicks_7d", 0))
        affiliate3.metric("Affiliate Clicks (30d)", metrics.get("affiliate_clicks_30d", 0))
        affiliate4.metric("Top Recommendation", metrics.get("top_clicked_recommendation", "") or "None yet")
        affiliate5.metric("Feedback Submissions", metrics.get("feedback_submissions", 0))

        aux1, aux2 = st.columns(2)
        with aux1:
            st.write("**Business snapshot**")
            st.write(f"- Total users: {metrics.get('total_users', 0)}")
            st.write(f"- Active users in the last 30 days: {metrics.get('active_users', 0)}")
            st.write(f"- Total analyses: {metrics.get('total_analyses', 0)}")
            st.write(f"- Average analyses per user: {metrics.get('analyses_per_user', 0)}")
        with aux2:
            st.write("**Engagement snapshot**")
            st.write(f"- Contact messages: {metrics.get('total_contact_messages', 0)}")
            st.write(f"- Unread / open messages: {metrics.get('open_contact_messages', 0)}")
            st.write(f"- Feedback items: {metrics.get('total_feedback_items', 0)}")
            st.write(f"- PDF downloads: {metrics.get('pdf_downloads', 0)}")

        st.write("**Most-used tabs**")
        for item in metrics.get("most_used_tabs", []):
            st.write(f"- {item.get('app_page', '')}: {item.get('view_count', 0)}")

        st.write("**Most common missing skills**")
        for skill, count in metrics.get("most_common_missing_skills", []):
            st.write(f"- {skill}: {count}")

        st.write("**Recent feedback**")
        for item in metrics.get("recent_feedback", []):
            st.write(f"- {item.get('created_at', '')} | {item.get('rating', '')} | Analysis {item.get('application_id', 0)}")

        st.write("**Recent affiliate clicks**")
        affiliate_rows = [
            {
                "Date/Time": item.get("clicked_at", ""),
                "User Email": item.get("user_email", ""),
                "Recommendation": item.get("recommendation_name", ""),
                "Category": item.get("recommendation_category", ""),
                "Provider": item.get("provider", ""),
            }
            for item in metrics.get("recent_affiliate_clicks", [])
        ]
        st.dataframe(affiliate_rows, use_container_width=True, hide_index=True)

    with messages_tab:
        st.write("**Contact Messages**")
        all_messages = list_contact_messages(limit=500)
        search_term = st.text_input("Search messages", placeholder="Search by name, email, or message text")
        filter_left, filter_mid, filter_right = st.columns(3)
        status_filter = filter_left.selectbox("Status", ["All", "Open", "Closed"])
        type_filter = filter_mid.selectbox("Message Type", ["All", "Support", "Feedback", "Sales"])
        filter_right.metric("Total Messages", len(all_messages))

        filtered_messages = []
        for item in all_messages:
            normalized_status = ((item.get("status", "") or "new").strip().lower())
            display_status = "Open" if normalized_status in {"new", "open"} else "Closed"
            bucket = _contact_message_bucket(item.get("message_type", ""))
            haystack = " ".join(
                [
                    str(item.get("name", "")),
                    str(item.get("email", "")),
                    str(item.get("message_type", "")),
                    str(item.get("message", "")),
                ]
            ).lower()
            if search_term and search_term.lower() not in haystack:
                continue
            if status_filter != "All" and display_status != status_filter:
                continue
            if type_filter != "All" and bucket != type_filter:
                continue
            filtered_messages.append(
                {
                    **item,
                    "display_status": display_status,
                    "bucket": bucket,
                }
            )

        summary_rows = [
            {
                "Date": item.get("created_at", ""),
                "Name": item.get("name", ""),
                "Email": item.get("email", ""),
                "Message Type": item.get("bucket", ""),
                "Message": item.get("message", ""),
                "Status": item.get("display_status", ""),
            }
            for item in filtered_messages
        ]
        st.dataframe(summary_rows, use_container_width=True, hide_index=True)

        for item in filtered_messages:
            title = f"{item.get('created_at', '')} | {item.get('name', '') or item.get('email', '')} | {item.get('bucket', '')}"
            with st.expander(title):
                st.write(f"**Date:** {item.get('created_at', '')}")
                st.write(f"**Name:** {item.get('name', '')}")
                st.write(f"**Email:** {item.get('email', '')}")
                st.write(f"**Message Type:** {item.get('bucket', '')}")
                st.write(f"**Original Type:** {item.get('message_type', '')}")
                st.write(f"**Status:** {item.get('display_status', '')}")
                st.write("**Message:**")
                st.write(item.get("message", ""))

                current_status = item.get("display_status", "Open")
                next_status = "Closed" if current_status == "Open" else "Open"
                if st.button(f"Mark {next_status}", key=f"message_status_{item.get('message_id', 0)}"):
                    success, message = update_contact_message_status(
                        int(item.get("message_id", 0)),
                        next_status.lower(),
                    )
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)


def render_application_shell() -> None:
    active_role_profile = (st.session_state.get("analysis") or {}).get("active_role_profile") or st.session_state.get("active_role_profile", {})
    if active_role_profile:
        st.caption(f"Active Role Profile: {active_role_profile.get('headline', active_role_profile.get('family', 'General Professional Role'))}")
    tabs = st.tabs(
        [
            "Upload",
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
    )

    with tabs[0]:
        render_upload_tab()
    with tabs[1]:
        render_match_tab()
    with tabs[2]:
        render_tailored_resume_tab()
    with tabs[3]:
        render_resume_builder_tab()
    with tabs[4]:
        render_evidence_tab()
    with tabs[5]:
        render_career_coach_tab()
    with tabs[6]:
        render_cover_letter_tab()
    with tabs[7]:
        render_interview_tab()
    with tabs[8]:
        render_linkedin_tab()
    with tabs[9]:
        render_thank_you_tab()
    with tabs[10]:
        render_export_tab()


def render_authenticated_app() -> None:
    render_app_header()
    pages = _app_pages()
    selected_page = st.radio(
        "Navigation",
        pages,
        horizontal=True,
        index=pages.index(st.session_state.get("app_page", "Workflow")) if st.session_state.get("app_page", "Workflow") in pages else 1,
        label_visibility="collapsed",
    )
    st.session_state["app_page"] = selected_page
    _track_page_view("app", selected_page)

    if selected_page == "Dashboard":
        render_dashboard_page()
    elif selected_page == "Analysis History":
        render_history_page()
    elif selected_page == "My Resumes":
        render_saved_resumes_page()
    elif selected_page == "Pro":
        render_pro_page()
    elif selected_page == "Subscription":
        render_subscription_page()
    elif selected_page == "Contact":
        render_contact_page()
    elif selected_page == "Privacy Policy":
        render_privacy_page()
    elif selected_page == "Terms":
        render_terms_page()
    elif selected_page == "User Profile":
        render_profile_page()
    elif selected_page == "Admin":
        render_admin_page()
    else:
        render_application_shell()


def main() -> None:
    init_db()
    init_state()
    _bootstrap_admin_access()
    app_status = _detect_local_app_status()
    inject_pwa_support()
    inject_theme_overrides()
    print(
        f"[{APP_NAME}] version={APP_VERSION} build={BUILD_TIMESTAMP} "
        f"pid={os.getpid()} url={app_status.get('url') or 'terminal-reported'}"
    )
    logger.info("App booted. version=%s pid=%s", APP_VERSION, os.getpid())

    try:
        requested_view = _current_view()
        if requested_view in {"app", "admin"} and not st.session_state.get("is_authenticated"):
            st.session_state["auth_notice"] = "Create an account or sign in to continue."
            requested_view = "auth"
            _set_view("auth")
        else:
            st.session_state["current_view"] = requested_view

        admin_details = _admin_auth_details()
        logger.info(
            "Startup auth state. current_user_email=%s is_admin=%s allowlisted=%s authorized=%s view=%s",
            admin_details["email"] or "anonymous",
            admin_details["is_admin_flag"],
            admin_details["allowlisted"],
            admin_details["authorized"],
            requested_view,
        )

        if requested_view in {"home", "contact", "privacy", "terms", "pro"}:
            render_public_page(requested_view)
        elif requested_view == "admin":
            _track_page_view("admin", "Admin")
            render_admin_page()
        elif requested_view == "auth":
            _track_page_view("auth", "")
            render_auth_page()
        else:
            render_authenticated_app()
        render_diagnostics_footer(app_status)
    except Exception:
        logger.exception("Unhandled application error.")
        st.error("Something went wrong while rendering the application. Please refresh and try again.")


if __name__ == "__main__":
    main()
