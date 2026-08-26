# Workflow Diagrams

## 1. Multi-agent orchestration (bara picture)

```
                          ┌──────────────┐
             User / Admin │   FastAPI    │
             ────────────►│  /api/agent  │
                          └──────┬───────┘
                                 │ run_task()
                                 ▼
                        ┌────────────────────┐
                        │  MANAGER AGENT     │  purple #8B5CF6
                        │  (user se baat)    │
                        │  tool: delegate()  │
                        └───┬────────────┬───┘
                 delegate   │            │  delegate
                            ▼            ▼
              ┌──────────────────┐  ┌──────────────────┐
              │   HR AGENT       │  │  DATA AGENT      │
              │   green #10B981  │◄─┤  blue #3B82F6    │
              │                  ├─►│                  │
              │ write_jd         │  │ time_to_hire     │
              │ parse_resumes    │  │ funnel_stats     │
              │ score_candidates │  │ score_distribution│
              │ screen_application│ │ open_jobs        │
              │ schedule_interview│ └──────────────────┘
              │ make_offer       │        ▲
              │ ask_policy       │        │ handoff("Data", "...")
              │ import_external  │────────┘
              └────────┬─────────┘
                       │ har step pe emit()
                       ▼
              ┌────────────────────┐
              │ EVENT BUS          │──► DB (events table)
              │ thinking/tool_call │──► SSE /api/events/stream
              │ artifact/handoff   │
              │ done/error         │
              └────────────────────┘
```

Har agent **ek hi** `BaseAgent` class hai — sirf config alag hai:
system_prompt + tools + color. Teen program nahi likhne.

## 2. Ek agent ke andar kya hota hai

```
instruction
   │
   ▼
[PLAN]      LLM ek JSON array deta hai: [{tool, args, why}, ...]
   │        emit type="thinking"
   ▼
[EXECUTE]   plain Python for-loop, LLM yahan involve nahi
   │        har step pe emit type="tool_call"
   │        document bane to save_artifact() + emit type="artifact"
   ▼
[SUMMARISE] LLM 100 words ka summary Manager ke liye
   │        emit type="done"
   ▼
{summary, results, artifact_ids}
```

> Ahem: 12 resumes ke liye LLM ko 12 baar tool call karne ka faisla **nahi** dena.
> Ek tool (`parse_resumes`) andar loop chalata hai. Warna free quota khatam + slow + unreliable.

## 3. Hiring pipeline (state machine)

```
 candidate POST /api/jobs/{id}/apply  (name, email, resume)
        │
        ▼
   ┌──────────┐   email #1: "application mil gayi"
   │ received │───────────────────────────────────►📧
   └────┬─────┘
        │ background task / scheduler (har 2 min)
        ▼
   ┌───────────┐  parse_resume()  →  score_candidate()
   │ screening │
   └────┬──────┘
        │
        ├── score ≥ 75 ──► ┌─────────────┐ email #2: "shortlist" 📧
        │                  │ shortlisted │
        │                  └──────┬──────┘
        │                         │ schedule_interview()  (auto)
        │                         ▼
        │                  ┌────────────────────┐ email #3: invite + .ics 📧
        │                  │interview_scheduled │ email #4: interviewer brief 📧
        │                  └──────┬─────────────┘
        │                         │ 24h pehle → email #5: reminder 📧
        │                         ▼
        │                  ┌──────────────┐
        │                  │ interviewed  │ admin: passed = true/false
        │                  └──────┬───────┘
        │                         ▼
        │                  ┌────────┐ email #6: offer 📧
        │                  │ hired  │ email #7: onboarding checklist 📧
        │                  └────────┘
        │
        ├── 55–74 ──────► ┌──────────┐ email: "waiting list" 📧
        │                 │ on_hold  │
        │                 └──────────┘
        │
        └── < 55 ────────► ┌──────────┐ email: "rejection" 📧
                           │ rejected │
                           └──────────┘
```

## 4. External job fetch (free boards)

```
scheduler (har 6 ghante)        admin POST /api/admin/jobs/import
        │                                    │
        └────────────┬───────────────────────┘
                     ▼
        ┌─────────────────────────────┐
        │  fetch_jobs(query)          │
        │  ├─ remotive.com/api        │ (no key)
        │  ├─ arbeitnow.com/api       │ (no key)
        │  └─ remoteok.com/api        │ (no key)
        └───────────┬─────────────────┘
                    │ dedupe (company+title)
                    ▼
             jobs table (source='remotive', external_url=...)
                    │
                    ▼
        User usi apply endpoint se apply karta hai
        → wohi screening + email pipeline chalti hai
        → external_url bhi candidate ko dikhaya jata hai (attribution)
```
