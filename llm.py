"""
llm.py -- the ONLY file that talks to an AI provider.

Everything else in the project calls ask() or ask_json().
If you ever switch providers, you change this file and nothing else.

Set PROVIDER in your .env file:
  mock   -> no internet, no API key, fake answers (use this first!)
  gemini -> Google Gemini free tier
  groq   -> Groq free tier (backup when Gemini rate-limits you)
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("PROVIDER", "mock").lower()
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def ask(system_prompt: str, user_message: str) -> str:
    """Send a prompt to the AI, get plain text back."""
    if PROVIDER == "mock":
        return _mock(system_prompt, user_message)
    if PROVIDER == "groq":
        return _groq(system_prompt, user_message)
    return _gemini(system_prompt, user_message)


def ask_json(system_prompt: str, user_message: str) -> dict:
    """
    Same as ask(), but we NEED valid JSON back.

    AI models love wrapping JSON in ```json fences even when you tell them
    not to. This function strips that off and parses safely.
    """
    raw = ask(system_prompt, user_message)
    cleaned = raw.strip()

    # Remove markdown code fences if the model added them
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0]
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Last resort: grab the text between the first { and the last }
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"AI did not return valid JSON. It said:\n{raw[:500]}")


# ---------------------------------------------------------------- providers

def _gemini(system_prompt: str, user_message: str) -> str:
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY missing. Add it to your .env file.")

    response = requests.post(
        GEMINI_URL,
        params={"key": GEMINI_KEY},
        json={
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_message}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"]


def _groq(system_prompt: str, user_message: str) -> str:
    if not GROQ_KEY:
        raise RuntimeError("GROQ_API_KEY missing. Add it to your .env file.")

    response = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {GROQ_KEY}"},
        json={
            "model": GROQ_MODEL, 
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.3,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _mock(system_prompt: str, user_message: str) -> str:
    """Fake AI so you can build and test with no API key and no internet."""
    text = user_message.lower()

    # Scheduler's action router
    if "you handle calendar requests" in system_prompt.lower():
        if "free" in text or "slot" in text or "available" in text:
            return json.dumps({"action": "find_slots",
                               "params": {"duration_minutes": 60, "days_ahead": 7}})
        if "birthday" in text or "anniversary" in text:
            return json.dumps({"action": "people_events", "params": {"days_ahead": 30}})
        if "book" in text or "schedule" in text:
            return json.dumps({"action": "book",
                               "params": {"title": "Interview", "duration_minutes": 60}})
        return json.dumps({"action": "list_events", "params": {"days_ahead": 7}})

    # Manager's planner -- calendar-flavoured request
    calendar_words = ("calendar", "birthday", "meeting", "schedule",
                      "free", "interview slot", "anniversary")
    if ("break the user's request into" in system_prompt.lower()
            and any(w in text for w in calendar_words)):
        return json.dumps({"subtasks": [
            {"agent": "scheduler",
             "subtask": "Check upcoming birthdays and work anniversaries",
             "depends_on": None},
            {"agent": "scheduler",
             "subtask": "Find free 60 minute slots for interviews next week",
             "depends_on": None},
        ]})

    if "break the user's request into" in system_prompt.lower():
        return json.dumps({
            "subtasks": [
                {"agent": "data_analyst",
                 "subtask": "Analyse the Q3 hiring funnel and find where "
                            "candidates are dropping off",
                 "depends_on": None},
                {"agent": "hr",
                 "subtask": "Review the screening process and propose fixes "
                            "for the drop-off the analyst found",
                 "depends_on": 0},
            ]
        })
    return (
        "## The short answer\n"
        "Screening-to-interview conversion collapsed in July, which is why "
        "Q3 hiring is behind.\n\n"
        "## What we found\n"
        "- Data Analyst: conversion fell 41% in July\n"
        "- HR: the screening rubric changed on 1 July\n\n"
        "## What to do next\n"
        "- Roll back the screening rubric (Owner: HR)\n"
    )
