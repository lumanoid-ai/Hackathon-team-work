"""
registry.py -- the list of specialists the Manager can delegate to.

*** THIS IS THE HANDOVER POINT WITH YOUR TEAMMATES ***

Right now it points at fake stub agents so you can build alone.
When your friends finish, you change the two lines marked SWAP HERE.
Nothing else in your code changes.
"""

from agents.stubs import hr_stub, analyst_stub
from agents.scheduler import scheduler_agent
from agents.researcher import research_agent

# Stubs don't have a .role, so we attach one. Real agents will define
# their own -- delete these two lines when you swap.
hr_stub.role = "hiring, job descriptions, resume screening, interviews, onboarding, company policy"
analyst_stub.role = "numbers, CSVs, metrics, trends, charts, and why a metric changed"


AGENTS = {
    # SWAP HERE (1): when your friend's HR agent is ready
    #   from agents.hr import hr_agent
    #   "hr": hr_agent,
    "hr": hr_stub,

    # SWAP HERE (2): when your friend's Data Analyst agent is ready
    #   from agents.data_analyst import analyst_agent
    #   "data_analyst": analyst_agent,
    "data_analyst": analyst_stub,

    # Yours. Real from day one -- no stub needed.
    "scheduler": scheduler_agent,
    "researcher": research_agent,
}


def get_agent(key: str):
    if key not in AGENTS:
        raise KeyError(f"No agent named '{key}'. Available: {list(AGENTS)}")
    return AGENTS[key]


def list_agents() -> dict:
    return AGENTS


# ---------------------------------------------------------------------------
# THE CONTRACT -- send this to both your friends on day one.
#
# Their agent object must have exactly these three things:
#
#   agent.name   -> str,  e.g. "HR"          (shown in the UI)
#   agent.color  -> str,  e.g. "#10B981"     (agent's colour everywhere)
#   agent.role   -> str,  what it handles    (the Manager reads this to
#                                             decide when to delegate to it)
#
#   agent.run(subtask: str, context: dict, task_id: str) -> str
#
# That's it. They can build their agent however they like internally.
# As long as run() takes those three arguments and returns a string,
# it plugs straight in.
#
# Ask them to emit events using events.emit(task_id, self.name, ...) so
# their work shows up in the live activity feed too.
# ---------------------------------------------------------------------------
