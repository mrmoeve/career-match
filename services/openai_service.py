import json
import os
import re
from typing import Any

from openai import OpenAI

from prompts.templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


INVALID_API_KEY_VALUES = {"", "your_api_key_here", "changeme", "replace_me"}


def is_demo_mode_api_key() -> bool:
    cleaned = os.getenv("OPENAI_API_KEY", "").strip()
    return cleaned.lower() in INVALID_API_KEY_VALUES


def _extract_response_text(response: Any) -> str:
    if getattr(response, "output_text", None):
        return response.output_text

    chunks = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text_value = getattr(content, "text", None)
            if text_value:
                chunks.append(text_value)
    return "\n".join(chunks)


def _safe_json_loads(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json", "", 1).strip()
    return json.loads(cleaned)


def _make_star_entry(situation: str, task: str, action: str, result: str) -> dict:
    return {
        "situation": situation,
        "task": task,
        "action": action,
        "result": result,
    }


def _make_question_entry(
    question: str,
    answer_summary: str,
    confidence_score: int,
    situation: str,
    task: str,
    action: str,
    result: str,
    category: str | None = None,
) -> dict:
    payload = {
        "question": question,
        "confidence_score": confidence_score,
        "answer_summary": answer_summary,
        "star_answer": _make_star_entry(situation, task, action, result),
    }
    if category is not None:
        payload["category"] = category
    return payload


def _build_interview_dashboard(analysis: dict, summary_skills: str, gap_note: str, title: str, company: str) -> dict:
    role_label = title if title and title != "Target Finance Role" else "target role"
    technical_topics = analysis.get("job_skills", [])[:8] or ["excel", "sql", "reporting", "analysis"]
    matched_skills = analysis.get("matching_skills", [])[:5]
    strengths = analysis.get("role_specific_strengths", [])[:3]
    strength_line = strengths[0] if strengths else "The resume shows relevant analytical and stakeholder-facing experience."

    overview = (
        f"This interview preparation dashboard is tailored to the {role_label} opportunity at {company}. "
        f"It emphasizes likely questions around {summary_skills}, highlights realistic resume-based STAR stories, "
        f"and prepares the candidate for likely challenges around {gap_note}."
    )

    likely_questions = []
    likely_templates = [
        ("background", f"Walk me through your background and why it fits this {role_label} role.", f"I would connect my experience in {summary_skills} to the priorities in this role and explain the progression visible in my resume."),
        ("motivation", f"Why are you interested in this {role_label} opportunity?", f"I would tie my interest to the mix of finance, problem-solving, and stakeholder work already reflected in my resume."),
        ("skills", "Which of your strengths are most relevant here?", f"I would highlight {summary_skills} and explain how those skills supported measurable business work."),
        ("behavioral", "Tell me about a time you handled a tight deadline.", "I would use a real reporting or planning deadline from my resume and show how I stayed organized under pressure."),
        ("behavioral", "Tell me about a time you worked across teams.", "I would describe coordinating with finance, operations, or leadership stakeholders to move work forward accurately."),
        ("technical", "How have you used Excel or similar tools in your work?", "I would answer with examples already shown in my resume, focusing on reporting, modeling, or analysis tasks."),
        ("technical", "How comfortable are you with SQL or data analysis?", "I would explain the level of SQL usage clearly and avoid overstating depth where the resume does not show it."),
        ("gap", "What is one area where you would need to ramp up?", f"I would answer honestly around any gaps related to {gap_note} and explain how I would close them quickly."),
        ("behavioral", "Tell me about a time you identified a problem and improved the outcome.", "I would use a resume-based example where I improved speed, accuracy, or clarity in a finance workflow."),
        ("stakeholders", "How do you communicate with senior stakeholders?", "I would explain how I keep communication concise, fact-based, and tied to business decisions."),
        ("technical", "How do you approach financial or operational analysis?", "I would describe a structured process: understand the question, validate data, analyze drivers, and communicate the conclusion."),
        ("behavioral", "Describe a time you had incomplete information.", "I would show how I clarified assumptions, aligned stakeholders, and moved the work forward carefully."),
        ("fit", "What makes you a strong fit for this team?", f"I would emphasize matched skills such as {', '.join(matched_skills) if matched_skills else summary_skills} and transferable experience."),
        ("learning", "How do you learn a new system or workflow quickly?", "I would describe learning through documentation, shadowing, hands-on practice, and asking focused questions."),
        ("ownership", "Tell me about a time you took ownership of a deliverable.", "I would use a real example from my resume where I owned reporting, analysis, or stakeholder coordination."),
        ("technical", "How do you ensure accuracy in your work?", "I would explain checks, reconciliation habits, peer review where appropriate, and careful documentation."),
        ("behavioral", "Tell me about a time you managed competing priorities.", "I would describe how I prioritized business impact, deadlines, and stakeholder expectations."),
        ("challenge", "What concern might a hiring manager have about your fit?", f"I would proactively address any direct gap around {gap_note} while reinforcing adjacent experience."),
        ("teamwork", "How do you handle feedback or changing priorities?", "I would explain that I stay flexible, clarify what changed, and adjust execution without losing quality."),
        ("results", "What achievement on your resume best represents your value?", "I would choose the strongest documented outcome from the resume and connect it to this role."),
        ("process", "Tell me about a time you improved a process.", "I would explain the issue, the action I took, and the improvement in efficiency, clarity, or control."),
        ("technical", "How do you work with data, KPIs, or performance metrics?", "I would describe how I use metrics to identify trends, explain results, and support decisions."),
        ("pressure", "How do you handle high-pressure periods?", "I would show calm prioritization, communication, and attention to detail under deadline pressure."),
        ("career", "How does this role fit your career direction?", f"I would connect this {role_label} opportunity to the next logical step based on the experience already on my resume."),
        ("closing", "Why should we hire you over another candidate?", "I would focus on relevant evidence, professionalism, learning agility, and the ability to contribute quickly without overclaiming."),
    ]

    for index, (category, question, answer) in enumerate(likely_templates, start=1):
        likely_questions.append(
            _make_question_entry(
                question=question,
                category=category,
                confidence_score=max(58, min(92, 86 - (index % 6) * 4)),
                answer_summary=answer,
                situation="The resume shows finance-related responsibilities, recurring deliverables, and stakeholder interaction.",
                task=f"The candidate needed to deliver work aligned with {role_label} expectations.",
                action="They organized priorities, used documented tools and processes, communicated clearly, and stayed within the boundaries of actual experience.",
                result=strength_line,
            )
        )

    technical_questions = []
    for index, topic in enumerate(technical_topics[:8], start=1):
        technical_questions.append(
            _make_question_entry(
                question=f"How would you discuss your experience with {topic} in this interview?",
                confidence_score=max(52, min(90, 82 - index * 3)),
                answer_summary=(
                    f"I would describe only the {topic} experience that is clearly supported by the resume, then explain how that background applies to the target role."
                ),
                situation="The job description includes technical or workflow expectations that the interviewer is likely to probe.",
                task=f"The candidate needs to explain their real level of experience with {topic} credibly.",
                action="They should use specific resume evidence, distinguish direct depth from adjacent exposure, and avoid inflated claims.",
                result="The answer remains credible, specific, and aligned with the documented experience.",
            )
        )

    behavioral_questions = [
        _make_question_entry(
            question="Tell me about a time you improved a reporting or analysis process.",
            confidence_score=88,
            answer_summary="Use a real example involving better efficiency, clearer reporting, or stronger accuracy, grounded in the resume.",
            situation="A recurring reporting or planning workflow needed improvement or streamlining.",
            task="The candidate needed to make the output faster, clearer, or more reliable.",
            action="They refined the process, used existing tools more effectively, and coordinated with stakeholders where needed.",
            result="The outcome was better turnaround, higher confidence in the data, or improved decision support.",
        ),
        _make_question_entry(
            question="Describe a time you worked with multiple stakeholders to deliver something important.",
            confidence_score=84,
            answer_summary="Use a resume-backed example showing coordination, expectation management, and clear communication.",
            situation="Different teams or leaders needed input, updates, or aligned execution on a deliverable.",
            task="The candidate needed to keep the work moving while balancing different priorities.",
            action="They clarified requirements, communicated status, and kept the work organized.",
            result="The deliverable moved forward with fewer surprises and stronger alignment.",
        ),
        _make_question_entry(
            question="Tell me about a time you found an error or risk before it became a bigger problem.",
            confidence_score=79,
            answer_summary="Frame a real quality-control example showing attention to detail and professional judgment.",
            situation="There was a risk of inaccurate reporting, incomplete information, or process breakdown.",
            task="The candidate needed to catch the issue and respond before it caused broader impact.",
            action="They reviewed the data carefully, validated assumptions, and raised the issue appropriately.",
            result="The team avoided a larger problem and maintained confidence in the work product.",
        ),
        _make_question_entry(
            question="Describe a time you had to learn something quickly.",
            confidence_score=82,
            answer_summary="Choose a real ramp-up example and show learning agility without overstating expertise.",
            situation="The candidate was asked to support a new tool, process, or workstream.",
            task="They needed to contribute quickly despite not having full familiarity on day one.",
            action="They studied the process, asked focused questions, and learned by doing.",
            result="They became productive quickly while staying accurate and transparent about what they knew.",
        ),
        _make_question_entry(
            question="Tell me about a time you managed competing deadlines.",
            confidence_score=87,
            answer_summary="Use a concrete example where prioritization and communication kept several deliverables on track.",
            situation="Several deadlines landed close together across reporting, planning, or stakeholder requests.",
            task="The candidate had to prioritize effectively while maintaining quality.",
            action="They triaged work by business impact and timing, then communicated tradeoffs early.",
            result="Deadlines were met or risks were managed transparently without unnecessary surprises.",
        ),
        _make_question_entry(
            question="Describe a time you handled ambiguity.",
            confidence_score=74,
            answer_summary="Show structured problem-solving when not all information was available at the start.",
            situation="A request or process lacked complete clarity at the outset.",
            task="The candidate needed to move forward without making unsupported assumptions.",
            action="They clarified the objective, gathered facts, aligned stakeholders, and created a workable path.",
            result="The work progressed with better alignment and reduced confusion.",
        ),
        _make_question_entry(
            question="Tell me about a time you influenced a decision with analysis.",
            confidence_score=76,
            answer_summary="Use a resume-supported example where analysis helped shape planning, reporting, or prioritization.",
            situation="Stakeholders needed insight to make a business or operational decision.",
            task="The candidate needed to translate data into a clear recommendation or takeaway.",
            action="They analyzed the data, explained drivers, and communicated implications clearly.",
            result="Decision-makers had better clarity and were able to act with stronger information.",
        ),
        _make_question_entry(
            question="Describe a time you received feedback and improved.",
            confidence_score=71,
            answer_summary="Answer with maturity, showing responsiveness to feedback and improvement over time.",
            situation="A manager or stakeholder raised feedback on process, communication, or output quality.",
            task="The candidate needed to adapt and improve quickly.",
            action="They listened carefully, changed their approach, and followed through consistently.",
            result="The work improved and stakeholder confidence increased.",
        ),
    ]

    challenges = [
        {
            "challenge": "The interviewer may question whether the resume shows enough direct experience for every part of the role.",
            "why_it_may_come_up": f"The job description emphasizes areas such as {gap_note}, and the resume may show only partial overlap.",
            "suggested_response": (
                f"Acknowledge the gap directly, connect adjacent experience in {summary_skills}, and explain how you have ramped up quickly in past roles."
            ),
            "confidence_score": 79,
        },
        {
            "challenge": "The interviewer may push for deeper technical depth than the resume clearly proves.",
            "why_it_may_come_up": "Some skills in the job description may be listed as required or heavily emphasized.",
            "suggested_response": (
                "Stay precise about your current level, give the strongest real example available, and avoid broad claims that the resume cannot support."
            ),
            "confidence_score": 76,
        },
        {
            "challenge": "The interviewer may ask why you are moving into this exact role now.",
            "why_it_may_come_up": "They may want to test whether the move is logical and motivated by more than title interest.",
            "suggested_response": (
                f"Frame the role as a natural next step because it builds on existing experience in {summary_skills} while expanding responsibility in a focused direction."
            ),
            "confidence_score": 83,
        },
        {
            "challenge": "The interviewer may test whether you can operate credibly in their finance-specific environment.",
            "why_it_may_come_up": "Industry context and terminology can matter even when the core skills transfer well.",
            "suggested_response": (
                "Use any relevant finance-domain examples from the resume, then show curiosity, preparation, and a structured approach to learning firm-specific context."
            ),
            "confidence_score": 72,
        },
    ]

    return {
        "overview": overview,
        "top_25_likely_questions": likely_questions,
        "technical_questions": technical_questions,
        "behavioral_questions": behavioral_questions,
        "questions_for_interviewer": [
            f"What would strong performance look like in the first 90 days for this {role_label} role?",
            "Which projects, workflows, or business priorities would this person support most heavily right away?",
            "What are the biggest challenges the team is facing right now?",
            "How does the team measure success for this position over the first year?",
            "What distinguishes someone who performs well in this team from someone who is only average?",
        ],
        "potential_challenges": challenges,
    }


def _estimate_increase(base: int, multiplier: int = 1) -> int:
    return max(1, min(12, base * multiplier))


def _parse_resume_experience(resume_text: str) -> list[dict]:
    entries: list[dict] = []
    current: dict | None = None
    for raw_line in resume_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "|" in line and re.search(r"(19|20)\d{2}\s*[-–]\s*(Present|Current|(19|20)\d{2})", line, re.IGNORECASE):
            parts = [part.strip() for part in line.split("|")]
            if len(parts) >= 3:
                current = {
                    "title": parts[0],
                    "company": parts[1],
                    "dates": parts[2],
                    "bullets": [],
                }
                entries.append(current)
                continue
        if current and line.startswith("-"):
            current["bullets"].append(line.lstrip("- ").strip())
    return entries


def _extract_resume_highlights(resume_text: str) -> dict:
    entries = _parse_resume_experience(resume_text)
    companies = [entry["company"] for entry in entries[:3]]
    titles = [entry["title"] for entry in entries[:3]]
    bullets = []
    for entry in entries:
        for bullet in entry.get("bullets", [])[:2]:
            bullets.append({"company": entry["company"], "title": entry["title"], "bullet": bullet})
    return {
        "entries": entries,
        "companies": companies,
        "titles": titles,
        "bullets": bullets[:6],
    }


def _build_career_coach(analysis: dict, title: str, company: str) -> dict:
    job_fit = analysis.get("job_fit", {})
    missing_skills = analysis.get("job_fit", {}).get("missing_required_skills", [])[:4]
    missing_certifications = analysis.get("job_fit", {}).get("missing_certifications", [])[:3]
    missing_technologies = analysis.get("missing_keywords", [])[:4]
    industry_overlap = analysis.get("job_fit", {}).get("industry_overlap", [])
    missing_industry_experience = []
    if not industry_overlap:
        missing_industry_experience.append(
            f"The resume does not strongly show the same finance-sector context as the {title} opportunity at {company}."
        )
    if analysis.get("job_fit", {}).get("title_overlap") == []:
        missing_industry_experience.append(
            "The resume may need clearer positioning toward this specific functional path or business context."
        )

    if not missing_skills:
        missing_skills = analysis.get("missing_keywords", [])[:3]
    if not missing_technologies:
        missing_technologies = analysis.get("job_skills", [])[2:5]

    thirty_day_plan = [
        {
            "action": f"Rewrite the resume summary and core bullets to emphasize {', '.join(analysis.get('matching_skills', [])[:3]) or 'the most relevant finance skills'}.",
            "why_it_matters": "Stronger role alignment can improve how quickly recruiters and hiring managers see the fit.",
            "estimated_job_fit_increase": _estimate_increase(3),
        },
        {
            "action": f"Create talking points and mini-project evidence around missing areas such as {', '.join(missing_skills[:2]) or 'target-role requirements'}.",
            "why_it_matters": "This helps close perception gaps even before new formal experience is added.",
            "estimated_job_fit_increase": _estimate_increase(4),
        },
        {
            "action": f"Study the role's key technologies and workflows, especially {', '.join(missing_technologies[:2]) or 'the main tools in the job description'}.",
            "why_it_matters": "A basic working vocabulary can make interview answers more credible and specific.",
            "estimated_job_fit_increase": _estimate_increase(2),
        },
    ]

    ninety_day_plan = [
        {
            "action": "Complete one targeted learning path and build a small portfolio artifact, case study, or documented walkthrough tied to the target role.",
            "why_it_matters": "Demonstrated effort and applied learning help bridge gaps more effectively than passive study alone.",
            "estimated_job_fit_increase": _estimate_increase(5),
        },
        {
            "action": "Strengthen domain exposure through networking, informational interviews, and finance-specific reading tied to the target industry segment.",
            "why_it_matters": "This improves industry fluency and helps the candidate sound more credible in interviews.",
            "estimated_job_fit_increase": _estimate_increase(3),
        },
        {
            "action": "Refresh the resume again after new learning so the strongest proof points are visible near the top.",
            "why_it_matters": "Updated positioning helps convert effort into a clearer perceived match.",
            "estimated_job_fit_increase": _estimate_increase(2),
        },
    ]

    recommended_certifications = []
    if missing_certifications:
        for cert in missing_certifications[:3]:
            recommended_certifications.append(
                {
                    "name": cert.upper(),
                    "reason": f"The job description appears to value {cert}, and earning or progressing toward it could reduce a visible gap.",
                    "estimated_job_fit_increase": _estimate_increase(4),
                }
            )
    else:
        recommended_certifications.extend(
            [
                {
                    "name": "CFA or role-relevant finance credential",
                    "reason": "Useful when targeting deeper finance-domain credibility, especially if the role is industry-specific.",
                    "estimated_job_fit_increase": _estimate_increase(2),
                },
                {
                    "name": "PMP, Scrum, or operational credential where relevant",
                    "reason": "Helpful for project, product, or operations-oriented tracks when the resume needs stronger role signaling.",
                    "estimated_job_fit_increase": _estimate_increase(2),
                },
            ]
        )

    recommended_courses = [
        {
            "name": f"Role-aligned course on {missing_technologies[0] if missing_technologies else 'finance analytics'}",
            "reason": "Targets a visible knowledge gap from the job description and improves interview readiness.",
            "estimated_job_fit_increase": _estimate_increase(2),
        },
        {
            "name": "Business communication or stakeholder management course",
            "reason": "Useful when the role requires presenting insights, cross-functional coordination, or influencing decisions.",
            "estimated_job_fit_increase": _estimate_increase(1),
        },
        {
            "name": "Industry-specific primer for the target finance segment",
            "reason": "Helps close any industry-context gap and improves the quality of interview examples and questions.",
            "estimated_job_fit_increase": _estimate_increase(2),
        },
    ]

    resume_improvements = [
        {
            "change": "Move the most relevant keywords and tools from the job description into resume bullets where they are honestly supported.",
            "reason": "This can improve both ATS alignment and perceived relevance without inventing experience.",
            "estimated_job_fit_increase": _estimate_increase(3),
        },
        {
            "change": "Add clearer business outcomes, scope, and stakeholder context to the strongest experience bullets.",
            "reason": "More specific impact statements make the resume feel closer to the target role.",
            "estimated_job_fit_increase": _estimate_increase(2),
        },
        {
            "change": "Create a targeted summary section that matches the role's language and domain emphasis.",
            "reason": "A sharper summary improves first-impression fit before the reader gets into details.",
            "estimated_job_fit_increase": _estimate_increase(2),
        },
    ]

    return {
        "overview": (
            f"This Career Coach plan is designed to raise the candidate's fit for the {title} role at {company} "
            "by closing the most visible gaps first and improving how current experience is positioned."
        ),
        "missing_skills": missing_skills,
        "missing_certifications": missing_certifications,
        "missing_technologies": missing_technologies,
        "missing_industry_experience": missing_industry_experience or ["Industry alignment is not a major weakness, but deeper domain examples could still strengthen the profile."],
        "thirty_day_plan": thirty_day_plan,
        "ninety_day_plan": ninety_day_plan,
        "recommended_certifications": recommended_certifications,
        "recommended_courses": recommended_courses,
        "resume_improvements": resume_improvements,
    }


def _build_demo_materials(analysis: dict, resume_text: str, job_description_text: str) -> dict:
    matching_skills = analysis.get("matching_skills", [])[:4]
    missing_keywords = analysis.get("missing_keywords", [])[:4]
    strengths = analysis.get("role_specific_strengths", [])[:3]
    title = analysis.get("job_title", "Target Finance Role")
    company = analysis.get("company_name", "Target Company")
    highlights = _extract_resume_highlights(resume_text)
    companies = highlights.get("companies", [])
    bullets_data = highlights.get("bullets", [])

    summary_skills = ", ".join(matching_skills) if matching_skills else "stakeholder communication, reporting, and analysis"
    gap_note = ", ".join(missing_keywords) if missing_keywords else "the role's preferred tools and terminology"
    role_language = [
        "stakeholder management",
        "client support",
        "onboarding",
        "training",
        "issue resolution",
        "relationship management",
        "cross-functional collaboration",
    ]
    supported_role_language = [item for item in role_language if item.title() in analysis.get("matching_keywords", []) or item.title() in analysis.get("resume_supported_keyword_categories", {}).get("skills", []) or item.title() in analysis.get("resume_supported_keyword_categories", {}).get("responsibilities", [])]
    bullets = []
    for item in bullets_data[:4]:
        language = supported_role_language[min(len(bullets), len(supported_role_language) - 1)] if supported_role_language else "stakeholder-facing execution"
        bullet_text = item["bullet"].rstrip(".")
        bullets.append(
            f"At {item['company']}, {bullet_text[0].lower() + bullet_text[1:] if len(bullet_text) > 1 else bullet_text}, demonstrating {language}."
        )
    bullets.append(f"Tailored prior accomplishments toward {title} priorities such as {summary_skills}.")

    strength_lines = " ".join(strengths) if strengths else "The resume already shows relevant finance experience."
    employer_line = ", ".join(companies) if companies else "prior employers"
    accomplishment_line = bullets_data[0]["bullet"].rstrip(".") if bullets_data else "supported analytical and stakeholder-facing deliverables"
    cover_letter = (
        f"Dear Hiring Team,\n\n"
        f"I am excited to apply for the {title} role at {company}. My background across {employer_line} includes work in "
        f"{summary_skills}, and I see strong overlap with the role's emphasis on customer-facing partnership, communication, and execution.\n\n"
        f"In my prior experience, I have delivered work such as {accomplishment_line}. That experience required clear communication, "
        f"stakeholder coordination, and reliable follow-through. {strength_lines}\n\n"
        f"I would welcome the opportunity to bring that same client-focused, cross-functional approach to {company}.\n\n"
        f"Thank you for your consideration.\n\nSincerely,\nCandidate"
    )
    linkedin_message = (
        f"Hello, I’m reaching out regarding the {title} opportunity at {company}. "
        f"My background includes {summary_skills}, and I’ve supported stakeholder-facing work across {employer_line} "
        f"that seems relevant to the role. I’d be glad to share more context if helpful."
    )
    thank_you_email = (
        f"Subject: Thank You\n\nThank you for taking the time to discuss the {title} role with me. "
        f"I enjoyed learning more about the team and the opportunity at {company}. "
        f"Our conversation reinforced my interest in the role, especially where my experience in {summary_skills} can contribute. "
        f"Please let me know if I can provide anything further."
    )
    interview_items = [
        {
            "question": "How does your background match this role?",
            "answer": f"My resume shows experience in {summary_skills}, along with budgeting, forecasting, and reporting work that maps directly to the core requirements.",
        },
        {
            "question": "What is one strength you would bring to this team?",
            "answer": strengths[0] if strengths else "I bring a practical finance toolkit and the ability to communicate findings clearly to stakeholders.",
        },
        {
            "question": "Where might you need to ramp up?",
            "answer": f"I would be transparent that I may need to deepen exposure to {gap_note}, and I would address that through focused onboarding and practice.",
        },
        {
            "question": "How do you approach executive reporting?",
            "answer": "I focus on clarity, concise takeaways, and linking the numbers to business decisions while keeping supporting detail ready for follow-up questions.",
        },
        {
            "question": "Why are you interested in this opportunity?",
            "answer": f"I’m interested because the {title} role combines planning, analysis, and cross-functional partnership in a way that fits the experience already demonstrated in my resume.",
        },
    ]
    interview_dashboard = _build_interview_dashboard(analysis, summary_skills, gap_note, title, company)
    career_coach = _build_career_coach(analysis, title, company)

    return {
        "professional_summary": (
            f"Professional with experience in {summary_skills}. Background includes stakeholder-facing analysis, "
            f"cross-functional coordination, reporting, and client-support style communication relevant to the {title} opportunity."
        ),
        "tailored_resume_bullets": bullets,
        "cover_letter": cover_letter,
        "linkedin_recruiter_message": linkedin_message,
        "interview_questions_and_answers": interview_items,
        "interview_dashboard": interview_dashboard,
        "career_coach": career_coach,
        "thank_you_email": thank_you_email,
    }


def generate_career_materials(resume_text: str, job_description_text: str, analysis: dict) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if is_demo_mode_api_key():
        return _build_demo_materials(analysis, resume_text, job_description_text)

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    user_prompt = USER_PROMPT_TEMPLATE.format(
        resume_text=resume_text[:15000],
        job_description_text=job_description_text[:15000],
        analysis_json=json.dumps(analysis, ensure_ascii=True, indent=2),
    )

    try:
        response = client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=user_prompt,
            temperature=0.5,
        )
        parsed = _safe_json_loads(_extract_response_text(response))
    except Exception:
        return _build_demo_materials(analysis, resume_text, job_description_text)

    parsed.setdefault("professional_summary", "")
    parsed.setdefault("tailored_resume_bullets", [])
    parsed.setdefault("cover_letter", "")
    parsed.setdefault("linkedin_recruiter_message", "")
    parsed.setdefault("interview_questions_and_answers", [])
    parsed.setdefault("interview_dashboard", {})
    parsed.setdefault("career_coach", {})
    parsed.setdefault("thank_you_email", "")

    if not parsed["interview_dashboard"]:
        parsed["interview_dashboard"] = _build_interview_dashboard(
            analysis,
            ", ".join(analysis.get("matching_skills", [])[:4]) or "finance analysis and stakeholder communication",
            ", ".join(analysis.get("missing_keywords", [])[:4]) or "role-specific tools and terminology",
            analysis.get("job_title", "Target Finance Role"),
            analysis.get("company_name", "Target Company"),
        )
    if not parsed["career_coach"]:
        parsed["career_coach"] = _build_career_coach(
            analysis,
            analysis.get("job_title", "Target Finance Role"),
            analysis.get("company_name", "Target Company"),
        )
    return parsed
