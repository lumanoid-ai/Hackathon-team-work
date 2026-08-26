from app.agents.data_agent import data_agent
from app.agents.hr_agent import hr_agent

AGENTS = {"HR": hr_agent, "Data": data_agent}


def get_agent(name: str):
    key = (name or "").strip().title()
    if key not in AGENTS:
        raise ValueError(f"Agent nahi mila: {name}. Available: {list(AGENTS)}")
    return AGENTS[key]
