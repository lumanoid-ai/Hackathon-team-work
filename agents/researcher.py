"""
agents/researcher.py -- the Research agent.

Handles anything the company's own data cannot answer, by searching the web
and coming back with an answer PLUS real links the user can open.

It covers all of these:
  - "what is X", "how do I do Y"          -> explanation + sources
  - "what are the options for Z"          -> suggestions + links
  - "flights from Karachi to Toronto"     -> where to look + booking site links
  - "average salary for a backend dev"    -> figures + where they came from
  - "best tools for X", "X vs Y"          -> comparison + links

IT NEVER TAKES AN ACTION. It does not book, buy, send, or change anything.
It finds information and hands the user the links. That is the whole job.

THE MOST IMPORTANT RULE IN THIS FILE:
Links are taken from the search results in Python. The AI never writes a URL.
Language models invent real-looking links constantly -- a link that 404s in
front of a judge is worse than no link at all. So the AI writes the words,
and Python attaches the sources.
"""

from datetime import datetime

from llm import ask, ask_json
from events import emit
from tools import websearch


QUERY_PROMPT = """Turn the user's request into ONE good web search query.

Rules:
- Keywords, not a sentence. 3-8 words.
- Keep names, places, numbers and dates. Drop filler words.
- For travel, use the pattern: flights <origin> to <destination> <month year>
- For prices or salaries, add the year: {year}
- If a place is mentioned without a country and it is ambiguous, leave it as written.

Return ONLY valid JSON, no markdown:
{"query": "...", "kind": "travel" | "price" | "howto" | "general"}"""


ANSWER_PROMPT = """You are a research assistant. You will be given a question and real
web search results.

Answer the question using ONLY what the search results say.

Hard rules:
1. Never write a URL or a link. Links are added separately. If you mention a
   website, use its name only.
2. Never invent a price, a statistic, a date, or a company name. If the
   results do not contain it, say the results do not cover it.
3. If sources disagree, say they disagree instead of picking one.
4. You are informing, not doing. Never say you have booked, ordered,
   scheduled or arranged anything.
5. Under 160 words.

Format:
**Answer:** 2-4 sentences, or 3-5 bullets if the question has several parts.
**Worth knowing:** one line -- a caveat, a cheaper option, or what to check next.

For travel questions specifically: give the typical route, rough price range
if the results mention one, and what affects the price. Then stop. The links
below will take them to the booking sites."""


class ResearchAgent:

    name = "Researcher"
    color = "#D4537E"
    role = ("anything requiring information from outside the company: general "
            "questions, how-to explanations, definitions, product and tool "
            "suggestions, comparisons, market rates and salaries, prices, "
            "regulations, travel and flight options, and current events. "
            "Returns information and links only -- it never books, buys or "
            "changes anything")

    def run(self, subtask: str, context: dict, task_id: str) -> str:
        emit(task_id, self.name, "thinking", f"Looking this up: {subtask[:55]}")

        query, kind = self._build_query(subtask)
        emit(task_id, self.name, "tool_call", f"web search: {query}")

        results = websearch.search(query, max_results=6)

        if not results or not results[0].get("url"):
            emit(task_id, self.name, "error", "Search returned nothing usable")
            return ("Web search is unavailable right now, so I cannot give you "
                    "sourced information on this. Check the connection and "
                    "SEARCH_MODE in .env.")

        emit(task_id, self.name, "thinking", f"Read {len(results)} sources")

        # ---- the AI writes the words -------------------------------------
        findings = "\n\n".join(
            f"[{r['title']}]\n{r['snippet']}" for r in results
        )

        try:
            answer = ask(ANSWER_PROMPT,
                         f"Question: {subtask}\n\nSearch results:\n{findings}")
        except Exception as e:
            emit(task_id, self.name, "error", str(e))
            answer = "**Answer:** Could not summarise the sources, but here they are."

        # ---- Python attaches the links -----------------------------------
        links = self._link_block(results, kind)

        emit(task_id, self.name, "artifact", "Research with sources",
             {"type": "research", "query": query,
              "sources": [{"title": r["title"], "url": r["url"]}
                          for r in results if r.get("url")]})

        emit(task_id, self.name, "done", f"{len(results)} sources")
        return f"{answer}\n\n{links}"

    # ------------------------------------------------------------------

    def _build_query(self, subtask: str) -> tuple[str, str]:
        """Ask the AI for a good search query. Fall back to keyword stripping."""
        year = datetime.now().year
        try:
            out = ask_json(QUERY_PROMPT.replace("{year}", str(year)),
                           f"Request: {subtask}")
            query = out.get("query", "").strip()
            if query:
                return query, out.get("kind", "general")
        except Exception:
            pass

        drop = {"find", "out", "research", "look", "up", "what", "is", "the",
                "our", "we", "a", "an", "for", "about", "and", "to", "of",
                "please", "can", "you", "should", "how", "much", "are", "i"}
        words = [w for w in subtask.replace(",", " ").split()
                 if w.lower().strip(".?") not in drop]
        return " ".join(words[:8]), "general"

    def _link_block(self, results: list[dict], kind: str) -> str:
        """
        Build the links section from the actual search results.

        Every URL here came back from the search engine. None were written
        by the AI, so none of them can be made up.
        """
        lines = ["**Where to look:**"]
        seen = set()

        for r in results:
            url = r.get("url", "")
            if not url:
                continue
            domain = url.split("/")[2].replace("www.", "") if "://" in url else url
            if domain in seen:
                continue
            seen.add(domain)
            title = r["title"][:70]
            lines.append(f"- [{title}]({url}) -- {domain}")
            if len(seen) >= 4:
                break

        if kind == "travel":
            lines.append("")
            lines.append("These are search results only. Compare on the sites "
                         "above and book directly with the airline or agent.")

        return "\n".join(lines)


research_agent = ResearchAgent()
