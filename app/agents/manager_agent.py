"""Agent 1 — Manager. User se sirf yeh baat karta hai; kaam delegate karta hai."""
from app.core.base_agent import BaseAgent, Tool
from app.core.events import emit
from app.core.llm import llm_text
from app.database import db_session
from app.models import Task

MANAGER_SYSTEM_PROMPT = """You are the Manager of an AI workforce with two specialists:
- HR: job descriptions, resume screening, scoring, interviews, onboarding, policy
- Data: hiring metrics, funnels, score distributions

You never do specialist work yourself. You split the user's request into
delegations, then combine the specialists' summaries into one answer for the user.
Be concrete. Under 150 words."""


def delegate(agent: str, instruction: str, task_id: str | None = None, **ctx) -> dict:
    from app.agents.registry import get_agent
    emit(task_id, "Manager", "handoff", f"{agent} ko de raha hoon: {instruction[:100]}",
         {"to": agent})
    return get_agent(agent).run(instruction, context=ctx, task_id=task_id)


manager_agent = BaseAgent(
    name="Manager",
    role="Delegation and synthesis",
    system_prompt=MANAGER_SYSTEM_PROMPT,
    tools=[Tool("delegate", delegate,
                "Give a specialist agent ('HR' or 'Data') a self-contained instruction",
                {"agent": "'HR'|'Data'", "instruction": "str"})],
    color="#8B5CF6",   # purple
)


def run_task(instruction: str, workspace_id: str | None = None) -> dict:
    """Entry point: user -> Manager -> specialists -> user."""
    db = db_session()
    try:
        task = Task(instruction=instruction, workspace_id=workspace_id)
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id
    finally:
        db.close()

    result = manager_agent.run(instruction, context={"workspace_id": workspace_id},
                               task_id=task_id)

    final = llm_text(
        f"User asked: {instruction}\n\nSpecialist summaries:\n"
        f"{[r.get('result', {}).get('summary') for r in result['results']]}\n\n"
        "Write the final answer for the user.",
        system=MANAGER_SYSTEM_PROMPT, temperature=0.4,
    ) if result["results"] else result["summary"]

    db = db_session()
    try:
        t = db.get(Task, task_id)
        t.status = "done"
        t.result = {"answer": final, "artifacts": result["artifacts"]}
        db.commit()
    finally:
        db.close()

    emit(task_id, "Manager", "done", final[:200])
    return {"task_id": task_id, "answer": final, "artifacts": result["artifacts"]}
