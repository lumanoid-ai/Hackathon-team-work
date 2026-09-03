"""Test the whole pipeline with a stubbed LLM (no API key needed)."""
import json
from analyst import llm

CALLS = []
def fake_complete(system, user, max_tokens=2000):
    CALLS.append(system[:40])
    if "You write DuckDB SQL" in system:
        if "WHAT WENT WRONG" in user:
            return """SELECT department, stage, count(*) AS candidates
FROM hiring_funnel GROUP BY department, stage ORDER BY department, candidates DESC"""
        # first attempt deliberately uses a wrong value -> zero rows -> retry
        return "SELECT * FROM hiring_funnel WHERE stage = 'offer'"
    if "You choose how to chart" in system:
        return json.dumps({"type":"grouped_bar","x":"stage","y":"candidates",
                           "series":"department","title":"Funnel by department"})
    return "Engineering has 67 candidates stuck at Phone Screen and only 2 hires."

llm.complete = fake_complete
import analyst.sql_writer as sw, analyst.charts as ch, analyst.narrator as nr
sw.complete = ch.complete = nr.complete = fake_complete

from analyst.agent import DataAnalystAgent
from analyst.events import print_listener

agent = DataAnalystAgent("./workspace", listener=print_listener)
r = agent.ask("Why are we behind on Q3 hiring?")
print("\nSQL:", r.sql[:80])
print("rows:", r.row_count, "| chart:", r.chart["type"], "| failed:", r.failed)
print("narrative:", r.narrative)
