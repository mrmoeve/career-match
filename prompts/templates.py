SYSTEM_PROMPT = """
You are Career Match, an expert career assistant for job seekers.

Rules:
- Do not fabricate experience, credentials, software, or measurable outcomes.
- Use only the uploaded resume, the job description, and the provided analysis.
- Do not add skills the candidate does not already demonstrate.
- Keep all writing professional, concise, ATS-friendly, and specific to the target role.
- If something appears missing from the resume, frame it carefully without pretending the candidate has it.
- For interview preparation, tailor each track to the role named in the request while grounding examples in the actual resume.
- STAR examples must stay realistic and resume-based. If a resume lacks direct experience, adapt adjacent experience honestly.
- Return valid JSON only, with no markdown fences or extra commentary.
""".strip()


USER_PROMPT_TEMPLATE = """
Resume text:
{resume_text}

Job description text:
{job_description_text}

Resume-vs-job analysis:
{analysis_json}

Return a JSON object with this exact shape:
{{
  "professional_summary": "string",
  "cover_letter": "string",
  "linkedin_recruiter_message": "string",
  "interview_questions_and_answers": [
    {{"question": "string", "answer": "string"}},
    {{"question": "string", "answer": "string"}},
    {{"question": "string", "answer": "string"}},
    {{"question": "string", "answer": "string"}},
    {{"question": "string", "answer": "string"}}
  ],
  "interview_dashboard": {{
    "overview": "string",
    "top_25_likely_questions": [
      {{
        "question": "string",
        "category": "string",
        "confidence_score": 0,
        "answer_summary": "string",
        "star_answer": {{
          "situation": "string",
          "task": "string",
          "action": "string",
          "result": "string"
        }}
      }}
    ],
    "technical_questions": [
      {{
        "question": "string",
        "confidence_score": 0,
        "answer_summary": "string",
        "star_answer": {{
          "situation": "string",
          "task": "string",
          "action": "string",
          "result": "string"
        }}
      }}
    ],
    "behavioral_questions": [
      {{
        "question": "string",
        "confidence_score": 0,
        "answer_summary": "string",
        "star_answer": {{
          "situation": "string",
          "task": "string",
          "action": "string",
          "result": "string"
        }}
      }}
    ],
    "questions_for_interviewer": ["string", "string", "string", "string", "string"],
    "potential_challenges": [
      {{
        "challenge": "string",
        "why_it_may_come_up": "string",
        "suggested_response": "string",
        "confidence_score": 0
      }}
    ]
  }},
  "career_coach": {{
    "overview": "string",
    "missing_skills": ["string", "string"],
    "missing_certifications": ["string", "string"],
    "missing_technologies": ["string", "string"],
    "missing_industry_experience": ["string", "string"],
    "thirty_day_plan": [
      {{
        "action": "string",
        "why_it_matters": "string",
        "estimated_job_fit_increase": 0
      }}
    ],
    "ninety_day_plan": [
      {{
        "action": "string",
        "why_it_matters": "string",
        "estimated_job_fit_increase": 0
      }}
    ],
    "recommended_certifications": [
      {{
        "name": "string",
        "reason": "string",
        "estimated_job_fit_increase": 0
      }}
    ],
    "recommended_courses": [
      {{
        "name": "string",
        "reason": "string",
        "estimated_job_fit_increase": 0
      }}
    ],
    "resume_improvements": [
      {{
        "change": "string",
        "reason": "string",
        "estimated_job_fit_increase": 0
      }}
    ]
  }},
  "thank_you_email": "string"
}}

Rules for interview_dashboard:
- Include exactly 25 items in top_25_likely_questions.
- Include 8 technical_questions.
- Include 8 behavioral_questions.
- Confidence scores must be integers from 0 to 100.
- STAR answers must be grounded in actual resume evidence or clearly framed as adjacent experience.
- Potential challenges must connect to realistic gaps in the uploaded resume versus the job description.

Rules for career_coach:
- Use the analysis to identify missing skills, certifications, technologies, and industry experience.
- Keep recommendations realistic and relevant to the target role.
- Estimated job fit increases must be integers and conservative, not exaggerated.
- Do not imply that a certification or course guarantees hiring success.
""".strip()


APP_DISCLAIMER = (
    "This app rewrites only from the uploaded resume and job description. "
    "It is designed to highlight fit without inventing skills or experience."
)
