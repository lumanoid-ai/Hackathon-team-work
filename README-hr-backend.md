# Autonomous HR Agent — Backend

Multi-agent AI workforce ka HR agent. **Backend only** — koi frontend nahi.
Har cheez REST API + background scheduler ke through chalti hai.

- Python **3.11** (recommended). 3.12 bhi theek. **3.13 abhi avoid karein** (chromadb wheels).
- **Koi transformers / torch nahi.** Embeddings Google `text-embedding-004` se, vector store **ChromaDB**.

---

## 1. Setup

```bash
# Python 3.11 check
python3.11 --version

python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env               # phir .env mein keys bharein
```

`.env` mein kam se kam yeh 2 cheezein:
- `GEMINI_API_KEY` → https://aistudio.google.com/apikey (free)
- `SMTP_USER` + `SMTP_PASSWORD` → Gmail → 2FA on → App Password (free, 16 chars)
  - SMTP khali chhod dein to emails console pe print honge (dev mode) — demo ke liye kaafi.

## 2. Chalana

```bash
uvicorn app.main:app --reload --port 8000
# docs:  http://localhost:8000/docs
```

Server start hote hi: DB tables ban jate hain + scheduler chal parta hai
(screening har 2 min, job-sync har 6 ghante, reminders har 30 min).

## 3. Demo data (pehli dafa)

```bash
python -m scripts.seed_demo        # workspace + job + JD + 30 interview slots
python -m scripts.seed_resumes     # 12 uneven fake resumes (3 strong/5 mid/4 weak)
python -m scripts.demo_pipeline <JOB_ID>   # poora apply→screen→email→interview flow
```

## 4. Aam commands (curl)

```bash
ADMIN="X-Admin-Key: change-me-admin-key"

# --- ADMIN: job banao (JD agent khud likhega) ---
curl -X POST localhost:8000/api/admin/jobs -H "$ADMIN" -H "Content-Type: application/json" -d '{
  "workspace_id":"<WS_ID>", "title":"Backend Engineer", "seniority":"mid",
  "location":"Remote (PK)", "must_have":["Python","PostgreSQL","Docker"],
  "nice_to_have":["AWS"], "generate_jd":true}'

# --- ADMIN: interview slot do ---
curl -X POST localhost:8000/api/admin/slots -H "$ADMIN" -H "Content-Type: application/json" -d '{
  "interviewer_email":"manager@acme.com",
  "start_at":"2026-09-02T10:00:00","end_at":"2026-09-02T10:45:00"}'

# --- ADMIN: free job boards se jobs import ---
curl -X POST localhost:8000/api/admin/jobs/import -H "$ADMIN" -H "Content-Type: application/json" -d '{
  "workspace_id":"<WS_ID>","query":"python developer","limit":20}'

# --- PUBLIC: jobs dekho ---
curl "localhost:8000/api/jobs?q=engineer"
curl "localhost:8000/api/jobs/search-live?q=data%20analyst&limit=10"

# --- CANDIDATE: apply karo (yahin se emails shuru) ---
curl -X POST localhost:8000/api/jobs/<JOB_ID>/apply \
  -F "name=Sara K" -F "email=sara@example.com" \
  -F "resume=@./data/resumes/01_strong_Sara_K.pdf"

# --- CANDIDATE: apni status dekho ---
curl localhost:8000/api/applications/<APP_ID>

# --- ADMIN: ranked candidate list ---
curl localhost:8000/api/admin/jobs/<JOB_ID>/candidates -H "$ADMIN"

# --- ADMIN: interview ka result + offer ---
curl -X POST localhost:8000/api/admin/interviews/result -H "$ADMIN" -H "Content-Type: application/json" \
  -d '{"application_id":"<APP_ID>","passed":true}'
curl -X POST localhost:8000/api/admin/offer -H "$ADMIN" -H "Content-Type: application/json" \
  -d '{"application_id":"<APP_ID>","start_date":"2026-09-15"}'

# --- AGENT: natural language task (Manager delegate karega) ---
curl -X POST localhost:8000/api/agent/task -H "Content-Type: application/json" -d '{
  "instruction":"Saari pending applications screen karo aur mujhe top 3 batao",
  "workspace_id":"<WS_ID>"}'

# --- AGENT: handbook Q&A ---
curl -X POST localhost:8000/api/admin/handbook -H "$ADMIN" -F "file=@handbook.pdf"
curl -X POST localhost:8000/api/agent/policy -H "Content-Type: application/json" \
  -d '{"question":"Maternity leave kitni hai?"}'

# --- Live activity feed ---
curl -N localhost:8000/api/events/stream
curl localhost:8000/api/admin/emails -H "$ADMIN"     # kaun se emails gaye
```

## 5. File map

```
app/
  config.py              saari settings
  database.py            engine + session
  models.py              11 tables ka poora schema
  schemas.py             request/response models
  core/
    llm.py               Gemini wrapper (llm_text, llm_json)
    events.py            event bus (DB + SSE)
    base_agent.py        BaseAgent: plan → execute → summarise
    embeddings.py        Gemini embeddings + ChromaDB (NO transformers)
  tools/
    jd_tools.py          write_jd
    resume_tools.py      parse_resume, score_candidate (+ loops)
    interview_tools.py   screening questions, slot booking, .ics
    onboarding_tools.py  checklist
    policy_tools.py      handbook indexing + ask_policy
    artifacts.py         save_artifact
  agents/
    manager_agent.py     delegation + final answer
    hr_agent.py          HR config + tool list
    data_agent.py        metrics
    registry.py          name → agent
  services/
    application_service.py  PIPELINE state machine (dil)
    email_service.py        SMTP + logging
    email_templates.py      8 email templates
    external_jobs.py        remotive / arbeitnow / remoteok
    job_service.py          job create + import
    scheduler.py            3 background jobs
  routers/
    admin.py jobs.py applications.py agent.py events.py
scripts/
  seed_demo.py seed_resumes.py demo_pipeline.py
docs/workflow.md
```

## 6. Production pe DB badalna

`.env` mein bas itna:
```
DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/postgres
```
aur `requirements.txt` mein `psycopg2-binary` uncomment. Code mein kuch nahi badalta.
