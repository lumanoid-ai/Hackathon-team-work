"""
agents/manager.py -- THE MANAGER AGENT. This is your file.

The Manager is the only agent the user talks to. It does three things,
always in this order:

    1. DECOMPOSE  -- turn one vague sentence into 2-4 concrete subtasks
    2. DELEGATE   -- send each subtask to the right specialist, in order
    3. SYNTHESIZE -- combine all the answers into one short brief

IMPORTANT DESIGN CHOICE:
The Manager is a fixed 3-step PIPELINE, not a free-form "AI decides what to
do next" loop. A loop is more impressive on paper but fails unpredictably
and is miserable to debug at 2am. A pipeline does the same thing in the demo
and always works. Build the pipeline.

RULE THE MANAGER MUST NEVER BREAK:
It does not do specialist work itself. It never invents a number and never
writes a job description. If it starts doing that, you have one chatbot
instead of a team, and the whole idea of the product disappears.
"""

import uuid
from llm import ask, ask_json
from events import emit
from registry import get_agent, list_agents


# ------------------------------------------------------------------ prompts

DECOMPOSE_PROMPT = """You are a Chief of Staff at a small company. Break the user's request into subtasks.

Available specialists:
{agent_menu}

Routing rules:
- Anything about dates, times, availability, who is free, meetings, interviews to be booked, birthdays or anniversaries goes to scheduler. Never send these to hr.
- Anything about writing job descriptions, screening or scoring candidates, interview questions, onboarding, or company policy goes to hr.
- Anything requiring a number, a metric, a trend, or an explanation of why something changed goes to data_analyst.

How to split:
- Use the FEWEST subtasks that fully answer the request. Two is usually right. Only use four if the request genuinely has four separate parts.
- If a simple request needs only one specialist, create only one subtask.
- If one specialist needs another's answer to do its job, set depends_on to that subtask's index (0-based). Otherwise use null.
- Order matters: whoever produces the facts goes first, whoever acts on them goes second.
- Each subtask must be one clear instruction a specialist can act on, not a topic.
- Never create a subtask for yourself. You only coordinate.
- Only use agent names from the list above.

Hidden prerequisites:
- Before creating a subtask, ask: does this instruction mention something that must be identified or looked up first? If so, that lookup is its own earlier subtask.
- "the top three candidates", "our best performer", "the shortlist" -> hr must identify them first, then the acting specialist uses that result.
- "why did X change", "what caused Y" -> data_analyst must produce the numbers first, then whoever acts on them comes second.
- Booking anything for specific people requires knowing who those people are. Do not guess names.
- One subtask is correct when the request is fully self-contained. Two or three is correct when a fact must be established before someone can act on it. Prefer fewer, but never drop a step the next specialist genuinely needs.

Return ONLY valid JSON. No markdown, no explanation, no code fences:
{{"subtasks": [
  {{"agent": "data_analyst", "subtask": "...", "depends_on": null}},
  {{"agent": "hr", "subtask": "...", "depends_on": 0}}
]}}"""

SYNTHESIZE_PROMPT = """You are a Chief of Staff writing a brief for a busy founder.

You will be given the original request and what each specialist found.
Combine them into ONE brief.

FORMAT - use markdown headings with ## exactly as shown. Do not use bold text for headings.

## The short answer
Two sentences maximum. Lead with the most important number or fact.

## What we found
3-5 bullets. Start each with the specialist's name and a colon, like "Data Analyst: ..."
Merge findings from the same specialist into one bullet rather than repeating the name.

## What to do next
Up to 3 numbered actions. Each must be something a person can start today.
Put a suggested owner in brackets at the end.
If the Scheduler proposed a booking, the first action should be confirming it.

Hard rules:
- Never invent a number. Only use numbers the specialists actually reported.
- if you are not sure tell the user about it, don't guess.
- If a specialist reported nothing useful, leave them out entirely rather than padding.
- No hedging words: "may", "could", "possibly", "it seems".
- Under 200 words total."""

# ------------------------------------------------------------------ manager

class ManagerAgent:

    name = "Manager"
    color = "#7C3AED"

    def handle(self, user_request: str, context: dict | None = None) -> dict:
        """
        The main entry point. Give it a sentence, get back a brief.

        Returns:
            {"task_id": ..., "plan": [...], "results": [...], "brief": "..."}
        """
        task_id = str(uuid.uuid4())[:8]
        context = context or {}

        print(f"\n{'=' * 62}\nTASK {task_id}: {user_request}\n{'=' * 62}")

        emit(task_id, self.name, "thinking", "Reading the request")

        # STEP 1 --------------------------------------------------- decompose
        plan = self.decompose(user_request, task_id)

        # STEP 2 ---------------------------------------------------- delegate
        results = self.execute_plan(plan, context, task_id)

        # STEP 3 -------------------------------------------------- synthesize
        brief = self.synthesize(user_request, results, task_id)

        emit(task_id, self.name, "done", "Brief ready")

        return {"task_id": task_id, "plan": plan,
                "results": results, "brief": brief}

    # ---------------------------------------------------------------- step 1

    def decompose(self, user_request: str, task_id: str) -> list[dict]:
        """Turn one sentence into a list of subtasks."""

        # Build the specialist menu from whoever is actually registered.
        # This means the prompt updates itself when your friends plug in
        # their real agents -- you don't have to edit it.
        agent_menu = "\n".join(
            f"- {key}: {agent.role}" for key, agent in list_agents().items()
        )

        try:
            response = ask_json(
                DECOMPOSE_PROMPT.format(agent_menu=agent_menu),
                f"User request: {user_request}",
            )
            subtasks = response.get("subtasks", [])
        except Exception as e:
            emit(task_id, self.name, "error", f"Planning failed: {e}")
            subtasks = []

        # SAFETY NET: if the AI returned nothing usable, fall back to asking
        # every specialist the original question. An ugly answer beats a
        # crashed demo.
        if not subtasks:
            subtasks = [
                {"agent": key, "subtask": user_request, "depends_on": None}
                for key in list_agents()
            ]
            emit(task_id, self.name, "thinking", "Using fallback plan")

        # Throw away subtasks pointing at agents that don't exist
        subtasks = [s for s in subtasks if s.get("agent") in list_agents()]

        emit(task_id, self.name, "thinking",
             f"Split into {len(subtasks)} subtasks",
             {"plan": subtasks})

        return subtasks

    # ---------------------------------------------------------------- step 2

    def execute_plan(self, plan: list[dict], context: dict,
                     task_id: str) -> list[dict]:
        """
        Run each subtask in dependency order, one at a time.

        WHY ONE AT A TIME: running them in parallel is faster, but it is
        harder to debug AND the delegation tree animation actually looks
        better when nodes light up one by one. Sequential wins here.
        """
        results = []

        for index, step in enumerate(plan):
            agent_key = step["agent"]
            instruction = step["subtask"]

            # If this step depends on an earlier one, paste that answer in
            depends_on = step.get("depends_on")
            if depends_on is not None and depends_on < len(results):
                earlier = results[depends_on]
                instruction = (
                    f"{instruction}\n\n"
                    f"Context from {earlier['agent']}:\n{earlier['result']}"
                )
                emit(task_id, self.name, "thinking",
                     f"Passing {earlier['agent']}'s findings to {agent_key}")

            agent = get_agent(agent_key)

            # This event is what draws an edge in the delegation tree
            emit(task_id, self.name, "delegation",
                 f"Manager -> {agent.name}: {step['subtask'][:70]}",
                 {"to": agent.name, "index": index,
                  "depends_on": depends_on, "color": agent.color})

            try:
                output = agent.run(instruction, context, task_id)
            except Exception as e:
                emit(task_id, agent.name, "error", str(e))
                output = f"[{agent.name} failed: {e}]"

            results.append({"agent": agent.name,
                            "subtask": step["subtask"],
                            "result": output})

        return results

    # ---------------------------------------------------------------- step 3

    def synthesize(self, user_request: str, results: list[dict],
                   task_id: str) -> str:
        """Combine every specialist's answer into one brief."""

        if not results:
            return "No specialists were able to work on this request."

        emit(task_id, self.name, "thinking", "Writing the brief")

        findings = "\n\n".join(
            f"--- {r['agent']} was asked: {r['subtask']}\n"
            f"They reported:\n{r['result']}"
            for r in results
        )

        try:
            brief = ask(
                SYNTHESIZE_PROMPT,
                f"Original request: {user_request}\n\n{findings}",
            )
        except Exception as e:
            emit(task_id, self.name, "error", f"Synthesis failed: {e}")
            # Fallback: just stack the raw findings. Not pretty, but the
            # user still gets their answer.
            brief = "## What we found\n\n" + "\n\n".join(
                f"**{r['agent']}**\n{r['result']}" for r in results
            )

        emit(task_id, self.name, "artifact", "Brief created",
             {"type": "brief", "content": brief})

        return brief
