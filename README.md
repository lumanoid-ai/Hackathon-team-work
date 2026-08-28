# Manager Agent — starter

Your piece of the AI Virtual Workforce. Coordinates the HR and Data Analyst
agents and returns one brief to the user.

## Run it in 3 minutes

```bash
pip install -r requirements.txt
cp .env.example .env          # PROVIDER=mock — no API key needed yet
python run_manager.py
```

You should see the Manager plan, delegate to two agents, and print a brief.
**It works offline with no API key.** That is deliberate — get the shape of
the code in your head before you add a real AI.

## Then switch on the real AI

1. Get a free key at <https://aistudio.google.com/apikey> (no card needed)
2. In `.env`: set `PROVIDER=gemini` and paste the key into `GEMINI_API_KEY`
3. `python run_manager.py "Why did our revenue drop in Q3?"`

Also grab a free Groq key at <https://console.groq.com>. Free tiers
rate-limit, and `PROVIDER=groq` is a one-word fix at 2am.

## Then start the API

```bash
uvicorn main:app --reload --port 8000
```

Open <http://localhost:8000/docs> — a clickable test page, free.

## The files

| File | What it does | Touch it? |
|---|---|---|
| `llm.py` | The only file that talks to an AI provider | Rarely |
| `events.py` | Records every agent action for the live UI | Rarely |
| `registry.py` | The list of specialists | **When friends finish** |
| `agents/stubs.py` | Fake HR + Analyst so you're not blocked | Keep as backup |
| `agents/manager.py` | **Your agent.** decompose → delegate → synthesize | **Constantly** |
| `run_manager.py` | Terminal test runner | Use it constantly |
| `main.py` | Web API for the frontend | After the above works |

## Your build order

1. ☐ Run it in mock mode, read `agents/manager.py` top to bottom
2. ☐ Switch to Gemini, confirm `decompose` returns valid JSON reliably
3. ☐ Tune `DECOMPOSE_PROMPT` against 10 test questions you write down first
4. ☐ Tune `SYNTHESIZE_PROMPT` until the brief reads like a human wrote it
5. ☐ Start `main.py`, confirm `/api/task` works in `/docs`
6. ☐ Send the contract (bottom of `registry.py`) to both friends
7. ☐ Swap stubs for real agents, one at a time
8. ☐ Add `handle_cached()` fallback for the demo

## Send this to your two friends today

Their agent needs exactly this shape — nothing more:

```python
class TheirAgent:
    name  = "HR"                      # shown in the UI
    color = "#10B981"                 # their colour everywhere
    role  = "hiring, resumes, ..."    # Manager reads this to route work

    def run(self, subtask: str, context: dict, task_id: str) -> str:
        ...
        return "what they found, as plain text or markdown"
```

Anything else they do inside is their business. Agree on this in hour one
and none of you blocks anyone.

---

## Google Calendar

`tools/calendar.py` is a shared tool. `agents/scheduler.py` is the agent that
owns it. HR imports the same functions when it books an interview.

Works in mock mode out of the box (`CALENDAR_MODE=mock`) — a local JSON file,
no Google account needed. Build against that first.

### Switching on the real calendar

1. <https://console.cloud.google.com> → create a project
2. APIs & Services → Library → enable **Google Calendar API**
3. OAuth consent screen → External → add your own email under **Test users**
4. Credentials → Create credentials → **OAuth client ID** → Desktop app
5. Download the JSON, rename it `credentials.json`, put it next to `main.py`
6. In `.env`: `CALENDAR_MODE=google`
7. `python run_manager.py "what's on my calendar this week"`

First run opens a browser to log in, then saves `token.json`. Never commit
`credentials.json` or `token.json` — both are already in `.gitignore`.
