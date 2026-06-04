import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import streamlit as st
from database.db import ApplicationRecord, init_db, list_applications, save_application
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
from services.text_extractor import extract_text_from_upload


APP_VERSION = "v0.4.0-quality"
APP_NAME = "Career Match"
BUILD_TIMESTAMP = datetime.fromtimestamp(Path(__file__).stat().st_mtime).isoformat(sep=" ", timespec="seconds")


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
            st.session_state["entered_app"] = True
            st.rerun()

    st.markdown("## Privacy Policy")
    st.caption("Your files and generated materials stay within the deployed application environment and local application history database configured for this service.")
    st.markdown("## Terms of Service")
    st.caption("Use Career Match as a decision-support tool. Review all generated materials before submitting them to employers.")
    st.markdown("## Contact")
    st.caption("Contact your deployment administrator or product owner for support, privacy questions, or access requests.")
    st.markdown(
        """
        <div class="footer-links">
          <a href="#privacy-policy">Privacy Policy</a>
          <a href="#terms-of-service">Terms of Service</a>
          <a href="#contact">Contact</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


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
        "entered_app": False,
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
    save_application(record)
    st.session_state["application_saved"] = True


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
    if st.button("Analyze and generate materials", type="primary", disabled=not can_run):
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

    added = ", ".join(builder.get("keywords_added", [])) or "None identified"
    st.write(f"**Keywords added:** {added}")
    if builder.get("unsupported_added_keywords"):
        st.error(
            "Unsupported additions detected and penalized in ATS scoring: "
            + ", ".join(builder.get("unsupported_added_keywords", []))
        )
    remaining = ", ".join(builder.get("missing_keywords_remaining", [])) or "None identified"
    st.write(f"**Remaining gaps:** {remaining}")

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
    applications = list_applications(limit=10)
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


def main() -> None:
    init_db()
    init_state()
    app_status = _detect_local_app_status()
    inject_pwa_support()
    print(
        f"[{APP_NAME}] version={APP_VERSION} build={BUILD_TIMESTAMP} "
        f"pid={os.getpid()} url={app_status.get('url') or 'terminal-reported'}"
    )
    logger.info("App booted. version=%s pid=%s", APP_VERSION, os.getpid())

    try:
        if not st.session_state.get("entered_app"):
            render_landing_page()
        else:
            st.title(APP_NAME)
            st.caption("Match your resume to any job and understand exactly where you stand.")
            render_application_shell()
        render_diagnostics_footer(app_status)
    except Exception:
        logger.exception("Unhandled application error.")
        st.error("Something went wrong while rendering the application. Please refresh and try again.")


if __name__ == "__main__":
    main()
