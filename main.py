"""
main.py -- the web API your frontend teammate will call.

Run it:
    uvicorn main:app --reload --port 8000

Then open http://localhost:8000/docs -- FastAPI builds you a clickable
test page for free. Use it to try the API without writing any frontend.

Only build this AFTER run_manager.py works in the terminal. Do not debug
the agent and the web server at the same time.
"""

import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.manager import ManagerAgent
from registry import list_agents
from events import get_events

app = FastAPI(title="AI Virtual Workforce -- Manager API")

# Lets the frontend (running on a different port) call this API.
# Wide open is fine for a hackathon; lock it down if you ever ship.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

manager = ManagerAgent()

# task_id -> the finished result. In-memory is fine for the demo.
TASKS: dict[str, dict] = {}


class TaskRequest(BaseModel):
    request: str


@app.get("/api/agents")
def get_agents():
    """The left rail in the UI is built from this."""
    return [
        {"key": key, "name": a.name, "role": a.role, "color": a.color}
        for key, a in list_agents().items()
    ] + [{"key": "manager", "name": "Manager",
          "role": "coordinates the team", "color": "#7C3AED"}]


@app.post("/api/task")
def create_task(body: TaskRequest):
    """
    Start a task. Returns immediately with a task_id so the UI can begin
    polling for events while the agents are still working.
    """
    task_id_holder = {}

    def work():
        outcome = manager.handle(body.request)
        TASKS[outcome["task_id"]] = outcome
        task_id_holder["id"] = outcome["task_id"]

    # For the hackathon, run it synchronously -- simpler and the whole thing
    # takes under 30 seconds. Swap to a background thread only if you need to.
    work()
    return TASKS[task_id_holder["id"]]


@app.get("/api/task/{task_id}")
def read_task(task_id: str):
    return TASKS.get(task_id, {"error": "not found"})


@app.get("/api/events/{task_id}")
def read_events(task_id: str):
    """
    The frontend polls this every second to animate the delegation tree
    and the activity feed. Polling is not elegant, but it is 10 lines
    instead of 100 and it will not break during your demo.
    """
    return get_events(task_id)


@app.get("/health")
def health():
    return {"ok": True}
