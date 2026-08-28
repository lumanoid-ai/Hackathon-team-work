"""
agents/stubs.py -- FAKE HR and Data Analyst agents.

*** THIS IS THE MOST IMPORTANT FILE FOR YOU RIGHT NOW ***

Your Manager needs HR and Data Analyst to exist before it can delegate to
them. But your friends are still building those. If you wait for them, you
lose two days.

So: these fakes return believable canned results. Your Manager can be fully
built and tested against them today. When your friends finish, you change
ONE LINE in registry.py and the real agents take over.

Do not delete this file even after that -- switching back to stubs is your
safety net if a real agent breaks 10 minutes before the demo.
"""

import time
from events import emit


class StubAgent:
    """Pretends to be a real agent. Same interface, fake brain."""

    def __init__(self, name: str, color: str, canned_result: str):
        self.name = name
        self.color = color
        self.canned_result = canned_result

    def run(self, subtask: str, context: dict, task_id: str) -> str:
        emit(task_id, self.name, "thinking", f"Working on: {subtask[:60]}")
        time.sleep(1.2)          # fake "thinking" time so the UI can animate
        emit(task_id, self.name, "done", "Finished")
        return self.canned_result


hr_stub = StubAgent(
    name="HR",
    color="#10B981",
    canned_result=(
        "Reviewed the screening process. The rubric changed on 1 July: a new "
        "'must have 5+ years' filter was added, which auto-rejected 34 "
        "candidates who previously would have advanced.\n"
        "Recommendation: lower the filter to 3+ years and re-review the 34 "
        "rejected candidates. Drafted a revised screening rubric."
    ),
)

analyst_stub = StubAgent(
    name="Data Analyst",
    color="#3B82F6",
    canned_result=(
        "Screening-to-interview conversion fell from 62% (Apr-Jun) to 21% in "
        "July -- a 41 point drop. Applications held steady at ~85/month, so "
        "this is a screening bottleneck, not a top-of-funnel problem.\n"
        "Offers made in Q3: 4 vs a target of 12."
    ),
)
