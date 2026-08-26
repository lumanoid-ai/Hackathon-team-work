"""Manager ko natural-language task dena + policy Q&A."""
from fastapi import APIRouter

from app.agents.manager_agent import run_task
from app.schemas import PolicyQuestion, TaskIn
from app.tools.policy_tools import ask_policy

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/task")
def create_task(body: TaskIn):
    """Misal: 'Backend Engineer ki JD likho aur saari pending applications screen karo'"""
    return run_task(body.instruction, body.workspace_id)


@router.post("/policy")
def policy(body: PolicyQuestion):
    return ask_policy(body.question)
