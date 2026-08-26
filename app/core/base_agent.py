"""Ek hi BaseAgent class — teeno agents sirf config mein farq rakhte hain.

Flow: PLAN (LLM) -> EXECUTE (plain Python) -> SUMMARISE (LLM)
LLM ko 12 baar tool call karne ka faisla nahi dena — wo slow aur mehnga hai.
"""
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.events import emit
from app.core.llm import llm_json, llm_text


@dataclass
class Tool:
    name: str
    fn: Callable
    description: str
    params: dict[str, str] = field(default_factory=dict)

    def schema(self) -> dict:
        return {"name": self.name, "description": self.description, "params": self.params}


PLANNER_PROMPT = """You are {name}, the {role} agent.

Available tools:
{tools}

Manager's instruction:
"{instruction}"

Context available to you (already fetched, do NOT re-fetch):
{context}

Return a JSON array of steps in execution order. Each step:
{{"tool": "tool_name", "args": {{...}}, "why": "one short line"}}

Rules:
- Only use tools from the list. Never invent a tool or an argument.
- Prefer the fewest steps that fully answer the instruction.
- If the instruction needs another specialist, use the tool "handoff".
- If no tool is needed, return [].
"""


class BaseAgent:
    def __init__(self, name: str, role: str, system_prompt: str,
                 tools: list[Tool], color: str):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.tools = {t.name: t for t in tools}
        self.color = color

    # ---------- planning ----------
    def plan(self, instruction: str, context: dict) -> list[dict]:
        tools_desc = "\n".join(
            f"- {t.name}({', '.join(t.params)}): {t.description}" for t in self.tools.values()
        )
        prompt = PLANNER_PROMPT.format(
            name=self.name, role=self.role, tools=tools_desc,
            instruction=instruction, context=json.dumps(context, default=str)[:2000],
        )
        plan = llm_json(prompt, system=self.system_prompt)
        return plan if isinstance(plan, list) else []

    # ---------- execution ----------
    def call_tool(self, task_id: str | None, name: str, args: dict) -> Any:
        tool = self.tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")
        emit(task_id, self.name, "tool_call", f"{name}({', '.join(args)})", {"tool": name, "args": args})
        sig = inspect.signature(tool.fn)
        clean = {k: v for k, v in args.items() if k in sig.parameters}
        return tool.fn(**clean)

    def run(self, instruction: str, context: dict | None = None,
            task_id: str | None = None) -> dict:
        context = context or {}
        emit(task_id, self.name, "thinking", f"Instruction mili: {instruction[:120]}")

        try:
            steps = self.plan(instruction, context)
        except Exception as e:
            emit(task_id, self.name, "error", f"Plan banane mein masla: {e}")
            steps = []

        if steps:
            emit(task_id, self.name, "thinking",
                 " -> ".join(s.get("tool", "?") for s in steps), {"plan": steps})

        results: list[dict] = []
        artifacts: list[str] = []
        for step in steps:
            tool_name, args = step.get("tool"), step.get("args", {}) or {}
            try:
                out = self.call_tool(task_id, tool_name, {**context, **args})
            except Exception as e:
                emit(task_id, self.name, "error", f"{tool_name} fail: {e}")
                results.append({"tool": tool_name, "error": str(e)})
                continue
            if isinstance(out, dict) and out.get("artifact_id"):
                artifacts.append(out["artifact_id"])
                emit(task_id, self.name, "artifact", out.get("title", "Document ready"),
                     {"type": out.get("type"), "id": out["artifact_id"]})
            results.append({"tool": tool_name, "result": out})

        summary = self.summarise(instruction, results)
        emit(task_id, self.name, "done", summary, {"artifacts": artifacts})
        return {"agent": self.name, "summary": summary, "results": results, "artifacts": artifacts}

    # ---------- summary ----------
    def summarise(self, instruction: str, results: list[dict]) -> str:
        if not results:
            return "Koi tool chalane ki zaroorat nahi thi."
        try:
            return llm_text(
                f"Instruction: {instruction}\n\nTool results (JSON):\n"
                f"{json.dumps(results, default=str)[:6000]}\n\n"
                "Report back to the Manager in under 100 words. "
                "State the decision, not the detail. No preamble.",
                system=self.system_prompt, temperature=0.3,
            )
        except Exception:
            return f"{len(results)} steps complete."
