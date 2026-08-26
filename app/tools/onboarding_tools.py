"""H5 — onboarding checklist."""
from app.core.llm import llm_json
from app.tools.artifacts import save_artifact

PROMPT = """Build an onboarding checklist for a {role} starting on {start_date}.

Return ONLY JSON:
{{"before_day_1":[{{"task":"","owner":""}}],
  "day_1":[...], "week_1":[...], "month_1":[...]}}

Owner is a real function: "IT", "Hiring Manager", "HR", "Buddy".
Tasks must be concrete and specific to this role, not generic filler.
"""


def build_onboarding_checklist(role: str, start_date: str, task_id: str | None = None) -> dict:
    data = llm_json(PROMPT.format(role=role, start_date=start_date))
    for bucket in data:
        data[bucket] = [{**item, "done": False} for item in data[bucket]]

    md = "\n\n".join(
        f"## {b.replace('_', ' ').title()}\n" +
        "\n".join(f"- [ ] {i['task']}  _( {i.get('owner','HR')} )_" for i in items)
        for b, items in data.items()
    )
    art_id = save_artifact("HR", "checklist", f"Onboarding — {role}", md, task_id,
                           meta={"checklist": data, "start_date": start_date})
    return {"artifact_id": art_id, "type": "checklist",
            "title": f"Onboarding — {role}", "checklist": data, "content": md}
