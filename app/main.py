"""FastAPI entry point. Chalane ke liye: uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import admin, agent, applications, events, jobs
from app.services.scheduler import start_scheduler
from app.routers import admin, agent, applications, calendar, events, jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield


app = FastAPI(title="Autonomous HR Agent — Backend", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(admin.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(agent.router)
app.include_router(events.router)
app.include_router(calendar.router)


@app.get("/health")
def health():
    return {"ok": True}
