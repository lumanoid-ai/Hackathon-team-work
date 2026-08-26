"""Agent 2 — HR. Spec ke mutabiq: same BaseAgent, alag config."""
from app.core.base_agent import BaseAgent, Tool
from app.services.application_service import make_offer, screen_application, screen_pending
from app.services.job_service import import_external_jobs
from app.tools.interview_tools import generate_screening_questions, schedule_interview
from app.tools.jd_tools import write_jd
from app.tools.onboarding_tools import build_onboarding_checklist
from app.tools.policy_tools import ask_policy
from app.tools.resume_tools import parse_resumes, score_candidates

HR_SYSTEM_PROMPT = """You are the HR specialist in an AI workforce. The Manager delegates to you.
You handle: job descriptions, resume screening, candidate scoring,
interview questions, interview scheduling, onboarding, and company policy questions.

Rules:
1. Never invent a candidate's experience. If the resume doesn't say it,
   it isn't there — list it as a gap instead.
2. Be honest in scoring. Spread scores across the full range.
3. Never mention age, gender, nationality, marital status, religion or photos
   in any assessment. Skills and experience only.
4. When you produce a document, save it as an artifact and return its ID.
5. Report back to the Manager in under 100 words. The documents carry
   the detail; your summary carries the decision.
"""


def _handoff(agent: str, question: str, task_id: str | None = None) -> dict:
    """HR -> Data Analyst wala handoff. Yahi wo lamha hai jab team lagti hai, menu nahi."""
    from app.agents.registry import get_agent
    from app.core.events import emit
    emit(task_id, "HR", "handoff", f"{agent} se pooch raha hoon: {question}",
         {"to": agent, "question": question})
    return get_agent(agent).run(question, task_id=task_id)


HR_TOOLS = [
    Tool("write_jd", write_jd,
         "Write a full formatted job description for a role",
         {"role": "str", "seniority": "str", "must_have_skills": "list[str]",
          "location": "str", "company_context": "str", "job_id": "str"}),
    Tool("parse_resumes", parse_resumes,
         "Extract structured JSON from a list of resume files (loops internally)",
         {"file_paths": "list[str]"}),
    Tool("score_candidates", score_candidates,
         "Score parsed candidates against a JD and return a ranked list",
         {"candidates": "list[dict]", "jd": "str"}),
    Tool("screen_application", screen_application,
         "Parse + score ONE application, decide shortlist/hold/reject, send the email",
         {"application_id": "str"}),
    Tool("screen_pending", screen_pending,
         "Screen every application currently in 'received' status",
         {"limit": "int"}),
    Tool("generate_screening_questions", generate_screening_questions,
         "5 role-specific interview questions with red flags",
         {"jd": "str", "job_id": "str"}),
    Tool("schedule_interview", schedule_interview,
         "Book the next free slot, email the candidate an invite with .ics",
         {"application_id": "str"}),
    Tool("build_onboarding_checklist", build_onboarding_checklist,
         "Day-1 / week-1 / month-1 onboarding tasks",
         {"role": "str", "start_date": "str"}),
    Tool("make_offer", make_offer,
         "Send offer + onboarding emails and mark the candidate hired",
         {"application_id": "str", "start_date": "str"}),
    Tool("ask_policy", ask_policy,
         "Answer a question from the uploaded company handbook, with the quoted section",
         {"question": "str"}),
    Tool("import_external_jobs", import_external_jobs,
         "Fetch jobs from free public job boards and import them",
         {"workspace_id": "str", "query": "str", "limit": "int"}),
    Tool("handoff", _handoff,
         "Ask another agent (Data) a question and use their answer",
         {"agent": "str", "question": "str"}),
]

hr_agent = BaseAgent(
    name="HR",
    role="Hiring, screening, onboarding, policy",
    system_prompt=HR_SYSTEM_PROMPT,
    tools=HR_TOOLS,
    color="#10B981",   # green
)
