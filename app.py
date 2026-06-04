import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
from database.db import (
    ApplicationRecord,
    AnalysisFeedback,
    ContactSubmission,
    authenticate_user,
    consume_password_reset_token,
    create_user,
    create_password_reset_token,
    get_dashboard_metrics,
    get_assessment_access,
    get_user_id,
    get_user_profile,
    increment_free_assessment_usage,
    init_db,
    list_applications,
    save_application,
    save_analysis_feedback,
    save_contact_submission,
    save_resume_stub,
    set_subscription_status,
    update_user_profile,
)
from prompts.templates import APP_DISCLAIMER
from services.analysis_service import compare_resume_to_job
from services.export_service import (
    build_full_report_docx,
    build_full_report_pdf,
    build_optimized_resume_docx,
    build_optimized_resume_pdf,
)
from services.job_url_service import JobExtractionError, fetch_job_posting_from_url
from services.openai_service import generate_career_materials, is_demo_mode_api_key
from services.resume_builder_service import build_optimized_resume_package
from services.runtime_service import configure_logging, init_monitoring
from services.subscription_service import get_subscription_blueprint
from services.text_extractor import extract_text_from_upload


APP_VERSION = "v0.4.0-quality"
APP_NAME = "Career Match"
BUILD_TIMESTAMP = datetime.fromtimestamp(Path(__file__).stat().st_mtime).isoformat(sep=" ", timespec="seconds")
VALID_VIEWS = {"home", "auth", "app", "contact", "privacy", "terms", "pro"}
APP_PAGES = ["Dashboard", "Workflow", "Analysis History", "Pro", "Contact", "Privacy Policy", "Terms", "User Profile"]


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


def render_diagnostics_footer(app_status: dict) -> None:
    st.divider()
    with st.expander("Diagnostics"):
        st.write(f"**App Version:** {APP_VERSION}")
        st.write(f"**Build Timestamp:** {BUILD_TIMESTAMP}")
        st.write(f"**Local URL:** {app_status.get('url') or 'Use the URL printed in the terminal for this running instance.'}")
        st.write(f"**Process ID:** {os.getpid()}")
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
        </style>
        """,
        unsafe_allow_html=True,
    )


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
    return _assessment_access().get("is_pro", False)


def _send_to_pro_page() -> None:
    if st.session_state.get("is_authenticated"):
        st.session_state["app_page"] = "Pro"
        _set_view("app")
    else:
        _set_view("pro")


def render_landing_page() -> None:
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

    st.markdown("## Start")
    cta_col = st.columns([1, 1, 1])[1]
    with cta_col:
        if st.button("Start Free Analysis", type="primary", use_container_width=True):
            if st.session_state.get("is_authenticated"):
                _set_view("app")
            else:
                st.session_state["auth_mode"] = "register"
                _set_view("auth")
            st.rerun()

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
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _application_payload() -> dict:
    return {
        "analysis": st.session_state.get("analysis"),
        "generated": st.session_state.get("generated"),
    }


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


def _optimized_resume_filename(resume_text: str, extension: str) -> str:
    candidate_name = _extract_resume_candidate_name(resume_text)
    safe_name = re.sub(r"[^A-Za-z0-9]+", "_", candidate_name).strip("_") or "Candidate"
    return f"{safe_name}_Resume.{extension}"


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
        resume_file = st.file_uploader(
            "Upload resume",
            type=["pdf", "docx", "txt"],
            help="Supported formats: PDF, DOCX, TXT",
        )
        if resume_file is not None:
            resume_text = extract_text_from_upload(resume_file)
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
                st.success("Job description extracted successfully.")
            except JobExtractionError as exc:
                logger.warning("Job extraction failed for %s: %s", job_url, exc)
                st.session_state["job_text"] = ""
                st.session_state["job_title_preview"] = ""
                st.session_state["company_name_preview"] = ""
                st.session_state["job_location_preview"] = ""
                st.session_state["job_date_posted_preview"] = ""
                st.session_state["job_category_preview"] = ""
                st.session_state["job_extraction_confidence"] = 0
                st.session_state["job_extraction_error"] = str(exc)
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
                    st.success("Manual job details saved. You can continue to analysis.")
                else:
                    st.error("Paste the job description text before using the manual fallback.")

    st.divider()

    can_run = bool(st.session_state["resume_text"].strip() and st.session_state["job_text"].strip())
    access = _assessment_access()
    if st.session_state.get("is_authenticated") and not access.get("can_run_analysis", False):
        st.warning("You’ve used your free Career Match assessment.")
        st.caption("Upgrade to Career Match Pro to continue generating new analyses. Your existing results remain available.")
        if st.button("Upgrade to Career Match Pro", type="primary", use_container_width=True):
            _send_to_pro_page()
            st.rerun()
    if st.button("Analyze and generate materials", type="primary", disabled=not can_run):
        if st.session_state.get("is_authenticated") and not access.get("can_run_analysis", False):
            _send_to_pro_page()
            st.rerun()
        try:
            logger.info("Starting analysis workflow.")
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

            with st.spinner("Generating tailored materials with OpenAI..."):
                generated = generate_career_materials(
                    resume_text=st.session_state["resume_text"],
                    job_description_text=st.session_state["job_text"],
                    analysis=st.session_state["analysis"],
                )
                generated["resume_builder"] = build_optimized_resume_package(
                    resume_text=st.session_state["resume_text"],
                    job_description_text=st.session_state["job_text"],
                    analysis=st.session_state["analysis"],
                    generated=generated,
                )
                st.session_state["optimized_resume_text"] = generated["resume_builder"]["optimized_resume_text"]
                st.session_state["generated"] = generated
                st.session_state["application_saved"] = False

            _save_current_application()
            if st.session_state.get("is_authenticated"):
                increment_free_assessment_usage(st.session_state.get("user_email", ""))
            logger.info("Analysis workflow completed successfully.")
            st.success("Analysis and tailored outputs are ready in the other tabs.")
        except Exception as exc:
            logger.exception("Unable to generate materials.")
            st.error(f"Unable to generate materials: {exc}")


def render_match_tab() -> None:
    st.subheader("Resume match overview")
    analysis = st.session_state.get("analysis")
    if not analysis:
        st.info("Upload a resume and job description in the Upload tab to see the match analysis.")
        return

    job_fit = analysis.get("job_fit", {})

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Overall Fit Score", f"{analysis['overall_fit_score']}/100")
    col2.metric("Experience", f"{analysis.get('years_of_experience', 0)} years")
    col3.metric("Direct Match Score", f"{analysis.get('direct_match_score', 0)}/100")
    col4.metric("Transferable Match Score", f"{analysis.get('transferable_match_score', 0)}/100")
    col5.metric("Interview Potential", f"{analysis.get('overall_interview_potential', 0)}/100")

    st.write(f"**Likely job title:** {analysis['job_title']}")
    st.write(f"**Likely company:** {analysis['company_name']}")
    st.write(f"**Role lens:** {analysis.get('role_family', 'General Professional Role')}")
    if st.session_state.get("job_url"):
        st.write(f"**Job posting URL:** {st.session_state['job_url']}")
    if st.session_state.get("job_location_preview"):
        st.write(f"**Location:** {st.session_state['job_location_preview']}")
    if st.session_state.get("job_date_posted_preview"):
        st.write(f"**Date posted:** {st.session_state['job_date_posted_preview']}")
    if st.session_state.get("job_category_preview"):
        st.write(f"**Category:** {st.session_state['job_category_preview']}")
    st.write(f"**Recommendation:** {job_fit.get('recommendation', 'Not available')}")
    if job_fit:
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

    left, right = st.columns(2)
    with left:
        st.write("**Matching skills**")
        st.write(", ".join(analysis["matching_skills"]) or "None identified")
        st.write("**Recruiter competency scores**")
        for item in analysis.get("competency_scores", []):
            st.write(
                f"- {item['competency']}: Direct {item.get('direct_score', 0)}% | "
                f"Transferable {item.get('transferable_score', 0)}% | "
                f"Overall {item['score']}%"
                + (f" | Evidence: {', '.join(item.get('matched', [])[:3])}" if item.get("matched") else "")
            )
        st.write("**Role-specific strengths**")
        for item in analysis["role_specific_strengths"]:
            st.write(f"- {item}")
    with right:
        st.write("**Missing keywords**")
        st.write(", ".join(analysis["missing_keywords"]) or "None identified")
        st.write("**Competency expectations**")
        for item in analysis.get("competency_scores", []):
            expected = ", ".join(item.get("missing", [])[:4]) or "None"
            st.write(f"- {item['competency']}: {expected}")
        st.write("**Gaps to address**")
        for item in analysis["gaps"]:
            st.write(f"- {item}")

    role_gap = analysis.get("role_gap_analysis", {})
    gap_left, gap_right = st.columns(2)
    with gap_left:
        st.write("**Missing Experience**")
        for item in role_gap.get("missing_experience", []):
            st.write(f"- {item}")
        st.write("**Transferable Experience**")
        for item in role_gap.get("transferable_experience", []):
            st.write(f"- {item}")
    with gap_right:
        st.write("**Resume Repositioning Opportunities**")
        for item in role_gap.get("resume_repositioning", []):
            st.write(f"- {item}")
        st.write("**Direct Match Gaps**")
        for item in role_gap.get("missing_competencies", []):
            st.write(f"- {item}")
        st.write("**Hiring Manager View**")
        for item in analysis.get("hiring_manager_view", []):
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

    render_feedback_section()


def render_tailored_resume_tab() -> None:
    st.subheader("Tailored resume content")
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Your tailored resume content will appear here after analysis.")
        return

    st.write("**Professional summary**")
    st.text_area("Summary", generated["professional_summary"], height=140)
    st.write("**Tailored bullet points**")
    bullet_text = "\n".join(f"- {item}" for item in generated["tailored_resume_bullets"])
    st.text_area("Resume bullets", bullet_text, height=260)


def render_resume_builder_tab() -> None:
    st.subheader("Resume Builder")
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Your optimized full resume will appear here after analysis.")
        return

    builder = generated.get("resume_builder", {})
    if not builder:
        st.warning("Resume Builder output is not available yet. Re-run generation to refresh the output.")
        return

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
    if builder.get("unsupported_added_keywords"):
        st.error(
            "Unsupported additions detected and penalized in ATS scoring: "
            + ", ".join(builder.get("unsupported_added_keywords", []))
        )
    remaining = ", ".join(builder.get("missing_keywords_remaining", [])) or "None identified"
    st.write(f"**Remaining gaps:** {remaining}")
    st.write("**Recruiter-ready bullet rewrites**")
    for bullet in builder.get("recruiter_ready_bullets", []):
        st.write(bullet)

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


def render_cover_letter_tab() -> None:
    st.subheader("Cover letter")
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Your cover letter will appear here after analysis.")
        return
    st.text_area("Cover letter", generated["cover_letter"], height=420)


def render_interview_tab() -> None:
    st.subheader("Interview Intelligence")
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Interview preparation insights will appear here after analysis.")
        return

    dashboard = generated.get("interview_dashboard", {})
    if not dashboard:
        st.warning("Interview intelligence is not available yet. Re-run generation to refresh the output.")
        return

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
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Career coaching insights will appear here after analysis.")
        return

    coach = generated.get("career_coach", {})
    if not coach:
        st.warning("Career coaching recommendations are not available yet. Re-run generation to refresh the output.")
        return

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
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Your LinkedIn outreach message will appear here after analysis.")
        return
    st.text_area("LinkedIn message", generated["linkedin_recruiter_message"], height=220)


def render_thank_you_tab() -> None:
    st.subheader("Thank-you email")
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Your thank-you email will appear here after analysis.")
        return
    st.text_area("Thank-you email", generated["thank_you_email"], height=220)


def render_export_tab() -> None:
    st.subheader("Export")
    analysis = st.session_state.get("analysis")
    generated = st.session_state.get("generated")
    if not analysis or not generated:
        st.info("Generate materials first to enable export.")
        return

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
    pdf_bytes = build_full_report_pdf(package)

    st.download_button(
        "Download DOCX",
        data=docx_bytes,
        file_name="finance_career_copilot_export.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    st.download_button(
        "Download PDF",
        data=pdf_bytes,
        file_name="finance_career_copilot_export.pdf",
        mime="application/pdf",
    )

    st.write("**Saved applications**")
    applications = list_applications(limit=10, user_email=st.session_state.get("user_email", ""))
    if not applications:
        st.caption("No saved applications yet.")
        return

    for item in applications:
        st.write(
            f"- {item['created_at']} | {item['job_title']} at {item['company_name']} | ATS {item['ats_score']}"
        )


def render_evidence_tab() -> None:
    st.subheader("Evidence")
    generated = st.session_state.get("generated")
    if not generated:
        st.info("Evidence details will appear here after analysis.")
        return

    builder = generated.get("resume_builder", {})
    if not builder:
        st.info("Resume evidence details are not available yet.")
        return

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
                )
                if success:
                    _log_in_user(result)
                    st.rerun()
                st.error(result)

    forgot_tab, reset_tab = st.tabs(["Forgot Password", "Reset Password"])
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
                st.success(
                    "Reset token created. In production this would be emailed. For now, use this token in the reset form: "
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
    st.markdown("</div>", unsafe_allow_html=True)

    helper_left, helper_right = st.columns([1, 1])
    with helper_left:
        if st.button("Back to Home", use_container_width=True):
            _set_view("home")
            st.rerun()
    with helper_right:
        st.caption("Use the same email and password next time to continue from the app workflow.")


def render_app_header() -> None:
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
    if view_name == "contact":
        render_contact_page()
    elif view_name == "privacy":
        render_privacy_page()
    elif view_name == "terms":
        render_terms_page()
    elif view_name == "pro":
        render_pro_page()
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
    col4.metric(
        "Free Assessments",
        f"{metrics.get('free_assessments_used', 0)}/{metrics.get('free_assessments_limit', 1)} used",
    )
    col5.metric("Current Plan", str(metrics.get("current_plan", "free")).title())

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
                  <span style="color:#475569;">{item.get('created_at', '')} | Fit {item.get('ats_score', 0)}/100</span>
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

    for item in applications:
        payload = {}
        payload_json = item.get("payload_json", "")
        if payload_json:
            try:
                payload = json.loads(payload_json)
            except json.JSONDecodeError:
                payload = {}
        with st.expander(f"{item['created_at']} | {item['job_title']} at {item['company_name']}"):
            analysis = payload.get("analysis", {})
            generated = payload.get("generated", {})
            recommendation = (analysis.get("job_fit", {}) or {}).get("recommendation", "Not available")
            st.write(f"**Date:** {item.get('created_at', '')}")
            st.write(f"**Company:** {item.get('company_name', '')}")
            st.write(f"**Job Title:** {item.get('job_title', '')}")
            st.write(f"**Fit Score:** {item.get('ats_score', 0)}/100")
            st.write(f"**Recommendation:** {recommendation}")
            if item.get("job_location"):
                st.write(f"**Location:** {item['job_location']}")
            if item.get("job_url"):
                st.write(f"**Job URL:** {item['job_url']}")
            st.write(
                f"**ATS Before / After:** {item.get('original_ats_score', 0)}/100 -> {item.get('optimized_ats_score', 0)}/100"
            )
            if analysis:
                st.write("**Role lens:** " + analysis.get("role_family", "General Professional Role"))
                st.write("**Top strengths:** " + (", ".join(analysis.get("role_specific_strengths", [])[:3]) or "Not available"))
            if st.button("Reopen Analysis", key=f"reopen_{item['id']}"):
                st.session_state["analysis"] = analysis or None
                st.session_state["generated"] = generated or None
                if generated and generated.get("resume_builder"):
                    st.session_state["optimized_resume_text"] = generated["resume_builder"].get("optimized_resume_text", "")
                st.session_state["last_application_id"] = item.get("id", 0)
                st.session_state["app_page"] = "Workflow"
                st.success("Analysis reopened in the workflow.")
                st.rerun()


def render_profile_page() -> None:
    st.subheader("User Profile")
    user_email = st.session_state.get("user_email", "")
    profile = get_user_profile(user_email) or {}
    subscription = get_subscription_blueprint()
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

    st.write("**Subscription**")
    st.write(f"Current plan: {profile.get('subscription_status', 'free').title()}")
    st.write(
        f"Free assessments used: {access.get('used', 0)} / {access.get('limit', 1)} | Remaining: {access.get('remaining', 0)}"
    )
    st.caption("Stripe-ready billing scaffolding is configured so checkout and portal flows can be attached without changing the product workflow.")
    for plan in subscription.get("plans", []):
        with st.expander(plan["name"]):
            for feature in plan.get("features", []):
                st.write(f"- {feature}")
    st.write("**Stripe readiness**")
    st.write(f"- Public key configured: {'Yes' if subscription.get('public_key_configured') else 'No'}")
    st.write(f"- Secret key configured: {'Yes' if subscription.get('secret_key_configured') else 'No'}")
    st.write(f"- Webhook secret configured: {'Yes' if subscription.get('webhook_secret_configured') else 'No'}")
    st.write(f"- Stripe customer id: {profile.get('stripe_customer_id', '') or 'Not set'}")
    st.write(f"- Stripe subscription id: {profile.get('stripe_subscription_id', '') or 'Not set'}")
    st.write("**Implementation next steps**")
    for item in subscription.get("next_steps", []):
        st.write(f"- {item}")


def render_pro_page() -> None:
    st.subheader("Career Match Pro")
    subscription = get_subscription_blueprint()
    access = _assessment_access() if st.session_state.get("is_authenticated") else {
        "used": 0,
        "remaining": 1,
        "limit": 1,
        "subscription_status": "free",
        "is_pro": False,
    }

    if not access.get("is_pro") and access.get("used", 0) >= access.get("limit", 1):
        st.warning("You’ve used your free Career Match assessment.")

    left, right = st.columns(2)
    for col, plan in zip((left, right), subscription.get("plans", [])):
        with col:
            st.markdown(
                f"""
                <div class="page-card">
                  <h3 style="margin-top:0;">{plan['name']}</h3>
                  <p style="font-size:1.15rem; font-weight:700; color:#1d4ed8;">{plan.get('price', '')}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            for feature in plan.get("features", []):
                st.write(f"- {feature}")

    st.write("**Pro benefits**")
    for benefit in [
        "Unlimited Resume Match",
        "Unlimited Resume Builder",
        "Tailored Resume Content",
        "Interview Intelligence",
        "Career Coach",
        "Cover Letters",
        "LinkedIn Messages",
        "Thank You Emails",
        "Analysis History",
    ]:
        st.write(f"- {benefit}")

    if st.button("Upgrade to Career Match Pro", type="primary", use_container_width=True):
        if subscription.get("public_key_configured") and subscription.get("secret_key_configured"):
            st.info("Stripe-ready checkout placeholder: connect the live checkout session URL here.")
        else:
            st.info("Stripe is not configured yet. This placeholder page is ready for checkout wiring.")

    if st.session_state.get("is_authenticated") and not _subscription_is_active():
        if st.button("Demo: Unlock Pro Access", use_container_width=True):
            success, message = set_subscription_status(st.session_state.get("user_email", ""), "pro")
            if success:
                st.success("Pro access enabled for this local environment.")
            else:
                st.error(message)
    if not st.session_state.get("is_authenticated"):
        if st.button("Back to Home", key="pro_home", use_container_width=True):
            _set_view("home")
            st.rerun()


def render_contact_page() -> None:
    st.subheader("Contact")
    default_profile = get_user_profile(st.session_state.get("user_email", "")) or {}
    with st.form("contact_form", clear_on_submit=True):
        name = st.text_input("Name", value=default_profile.get("full_name", ""))
        email = st.text_input("Email", value=st.session_state.get("user_email", ""))
        message_type = st.selectbox(
            "Message type",
            ["General Question", "Bug Report", "Feature Request", "Billing Question"],
        )
        message = st.text_area("Message", height=180)
        submitted = st.form_submit_button("Submit", use_container_width=True)
    if submitted:
        submission = ContactSubmission(
            created_at=datetime.now().isoformat(timespec="seconds"),
            user_email=(email or "").strip().lower(),
            name=name.strip(),
            message_type=message_type,
            message=message.strip(),
        )
        save_contact_submission(submission)
        st.success("Thanks for reaching out. Your message has been saved and is ready for follow-up.")
    if not st.session_state.get("is_authenticated"):
        if st.button("Back to Home", key="contact_home", use_container_width=True):
            _set_view("home")
            st.rerun()


def render_privacy_page() -> None:
    st.subheader("Privacy Policy")
    st.write("Career Match may store uploaded resumes, pasted or extracted job descriptions, account email/password data, generated outputs, feedback, and support submissions so the service can function and preserve user history.")
    st.write("Resume uploads and job descriptions are processed to generate fit analysis, resume rewrites, interview preparation, and related outputs.")
    st.write("Account records include email addresses and securely hashed passwords. Plaintext passwords are not stored.")
    st.write("Generated outputs and saved analyses may be retained in the application database to support dashboard metrics, history, and reopened analyses.")
    st.write("Users may request account or data deletion through the contact channel. Contact email placeholder: support@careermatch.example")
    st.write("Retention periods may vary by plan, support need, and deployment environment.")
    if not st.session_state.get("is_authenticated"):
        if st.button("Back to Home", key="privacy_home", use_container_width=True):
            _set_view("home")
            st.rerun()


def render_terms_page() -> None:
    st.subheader("Terms of Service")
    st.write("Career Match provides AI-generated resume analysis and writing assistance. All content should be reviewed by the user before submission to any employer.")
    st.write("The service does not guarantee interviews, job offers, or employment outcomes.")
    st.write("Career Match does not provide legal, financial, or employment advice.")
    st.write("Users are responsible for confirming that generated materials are accurate, truthful, and appropriate for the target role.")
    st.write("Service availability may vary based on hosting, third-party APIs, and maintenance windows.")
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
            helpful=1 if helpful_label == "Helpful" else 0,
            comment=comment.strip(),
        )
        save_analysis_feedback(feedback)
        st.session_state["feedback_submitted_for_analysis"] = True
        st.success("Thanks for your feedback.")


def render_application_shell() -> None:
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
    selected_page = st.radio(
        "Navigation",
        APP_PAGES,
        horizontal=True,
        index=APP_PAGES.index(st.session_state.get("app_page", "Workflow")) if st.session_state.get("app_page", "Workflow") in APP_PAGES else 1,
        label_visibility="collapsed",
    )
    st.session_state["app_page"] = selected_page

    if selected_page == "Dashboard":
        render_dashboard_page()
    elif selected_page == "Analysis History":
        render_history_page()
    elif selected_page == "Pro":
        render_pro_page()
    elif selected_page == "Contact":
        render_contact_page()
    elif selected_page == "Privacy Policy":
        render_privacy_page()
    elif selected_page == "Terms":
        render_terms_page()
    elif selected_page == "User Profile":
        render_profile_page()
    else:
        render_application_shell()


def main() -> None:
    init_db()
    init_state()
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
        if requested_view == "app" and not st.session_state.get("is_authenticated"):
            st.session_state["auth_notice"] = "Create an account or sign in to continue to the app."
            requested_view = "auth"
            _set_view("auth")
        else:
            st.session_state["current_view"] = requested_view

        if requested_view in {"home", "contact", "privacy", "terms", "pro"}:
            render_public_page(requested_view)
        elif requested_view == "auth":
            render_auth_page()
        else:
            render_authenticated_app()
        render_diagnostics_footer(app_status)
    except Exception:
        logger.exception("Unhandled application error.")
        st.error("Something went wrong while rendering the application. Please refresh and try again.")


if __name__ == "__main__":
    main()
