"""Free job boards se jobs fetch karna — koi API key nahi chahiye.

IMPORTANT (imandari se):
Indeed ka public API 2026 mein band hai aur scraping unke ToS ke khilaf hai.
Neeche wale 3 official free feeds Indeed jaisa hi kaam dete hain aur legal hain.
Remotive attribution maangta hai — original URL zaroor dikhana.
"""
import httpx

TIMEOUT = 20


def _remotive(query: str, limit: int) -> list[dict]:
    url = "https://remotive.com/api/remote-jobs"
    r = httpx.get(url, params={"search": query, "limit": limit}, timeout=TIMEOUT)
    r.raise_for_status()
    return [{
        "source": "remotive",
        "external_id": str(j["id"]),
        "title": j["title"],
        "company_name": j.get("company_name", ""),
        "location": j.get("candidate_required_location", "Remote"),
        "employment_type": j.get("job_type", "full_time"),
        "description": j.get("description", "")[:8000],
        "url": j.get("url", ""),
        "tags": j.get("tags", []),
    } for j in r.json().get("jobs", [])]


def _arbeitnow(query: str, limit: int) -> list[dict]:
    url = "https://www.arbeitnow.com/api/job-board-api"
    r = httpx.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    jobs = r.json().get("data", [])
    q = query.lower()
    picked = [j for j in jobs if q in j.get("title", "").lower()] or jobs
    return [{
        "source": "arbeitnow",
        "external_id": j.get("slug", ""),
        "title": j.get("title", ""),
        "company_name": j.get("company_name", ""),
        "location": j.get("location", "Remote"),
        "employment_type": ", ".join(j.get("job_types", []) or ["full_time"]),
        "description": (j.get("description", "") or "")[:8000],
        "url": j.get("url", ""),
        "tags": j.get("tags", []),
    } for j in picked[:limit]]


def _remoteok(query: str, limit: int) -> list[dict]:
    r = httpx.get("https://remoteok.com/api", timeout=TIMEOUT,
                  headers={"User-Agent": "hr-agent/1.0"})
    r.raise_for_status()
    rows = [x for x in r.json() if isinstance(x, dict) and x.get("position")]
    q = query.lower()
    picked = [j for j in rows if q in j["position"].lower()] or rows
    return [{
        "source": "remoteok",
        "external_id": str(j.get("id", "")),
        "title": j.get("position", ""),
        "company_name": j.get("company", ""),
        "location": j.get("location") or "Remote",
        "employment_type": "full_time",
        "description": (j.get("description", "") or "")[:8000],
        "url": j.get("url", ""),
        "tags": j.get("tags", []),
    } for j in picked[:limit]]


PROVIDERS = {"remotive": _remotive, "arbeitnow": _arbeitnow, "remoteok": _remoteok}


def fetch_jobs(query: str, limit: int = 20, providers: list[str] | None = None) -> list[dict]:
    out: list[dict] = []
    for name in (providers or list(PROVIDERS)):
        try:
            out.extend(PROVIDERS[name](query, limit))
        except Exception as e:
            print(f"[job-fetch] {name} fail: {e}")
    # dedupe (company + title)
    seen, unique = set(), []
    for j in out:
        key = (j["company_name"].lower(), j["title"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(j)
    return unique
