"""H2 + H3 — resume parse aur candidate scoring.

Stage 1: raw text nikalna (free, offline, instant)
Stage 2: LLM us text ko structure karta hai
Poori PDF kabhi LLM ko mat bhejna — free quota minute mein khatam ho jayega.
"""
import os

from app.core.llm import llm_json

PARSE_PROMPT = """Extract from this resume. Return ONLY JSON:
{{"name":"", "email":"", "phone":"", "years_experience":0,
  "skills":[], "current_role":"", "education":"",
  "notable":"one line on what stands out"}}

Resume:
{text}
"""

SCORE_PROMPT = """Score this candidate against the job description.

Return ONLY JSON:
{{"score": 0-100,
  "strengths": ["2-3 specific things, quoting the resume"],
  "gaps": ["1-2 honest concerns"],
  "verdict": "advance" | "hold" | "pass",
  "one_liner": "one sentence a hiring manager can read in 3 seconds"}}

Be honest. A 95 for everyone is useless. Spread the scores across the full range.
Never mention age, gender, nationality, marital status, religion or photos.
Judge skills and experience only.

JOB DESCRIPTION:
{jd}

CANDIDATE (parsed JSON):
{candidate}
"""


# ---------- STAGE 1 ----------
def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    if ext == ".docx":
        from docx import Document
        return "\n".join(p.text for p in Document(file_path).paragraphs)
    if ext in (".txt", ".md"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    raise ValueError(f"Support nahi karta: {ext} (pdf / docx / txt chalein)")


# ---------- STAGE 2 ----------
def parse_resume(file_path: str) -> dict:
    text = extract_text(file_path)
    if not text.strip():
        return {"name": "", "email": "", "skills": [], "years_experience": 0,
                "notable": "Resume se text nahi nikla (scanned image ho sakti hai)"}
    data = llm_json(PARSE_PROMPT.format(text=text[:6000]))
    data["_raw_chars"] = len(text)
    return data


def parse_resumes(file_paths: list[str]) -> list[dict]:
    """Yeh loop plain Python hai — LLM ko 12 baar decide nahi karne dena."""
    out = []
    for i, path in enumerate(file_paths, 1):
        try:
            parsed = parse_resume(path)
            parsed["_file"] = path
            out.append(parsed)
        except Exception as e:
            out.append({"_file": path, "error": str(e)})
    return out


def score_candidate(candidate: dict, jd: str) -> dict:
    import json
    safe = {k: v for k, v in candidate.items() if not k.startswith("_")}
    result = llm_json(SCORE_PROMPT.format(jd=jd[:4000], candidate=json.dumps(safe)[:3000]))
    result["score"] = max(0, min(100, int(result.get("score", 0))))
    if result.get("verdict") not in ("advance", "hold", "pass"):
        result["verdict"] = ("advance" if result["score"] >= 75
                             else "hold" if result["score"] >= 55 else "pass")
    return result


def score_candidates(candidates: list[dict], jd: str) -> list[dict]:
    """Bhi plain loop. Ranked list return karta hai."""
    scored = []
    for c in candidates:
        if c.get("error"):
            continue
        s = score_candidate(c, jd)
        scored.append({**c, **s})
    return sorted(scored, key=lambda x: x["score"], reverse=True)
