"""Calendar connect / disconnect / status ke endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse

from app.routers.admin import require_admin
from app.services import google_calendar as gcal

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/status")
def status(email: str):
    """Check karein ke kisi interviewer ka calendar juda hua hai ya nahi."""
    return {"email": email, "connected": gcal.is_connected(email),
            "oauth_configured": gcal.enabled()}


@router.get("/connect", dependencies=[Depends(require_admin)])
def connect():
    """Yeh URL interviewer ko bhejein — wo Google pe login karke permission dega."""
    if not gcal.enabled():
        raise HTTPException(400, "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET .env mein set karein")
    return {"auth_url": gcal.build_auth_url(),
            "note": "Yeh link browser mein kholein aur apne Google account se login karein"}


@router.get("/callback", response_class=HTMLResponse)
def callback(code: str | None = None, state: str | None = None, error: str | None = None):
    """Google is URL pe wapis bhejta hai. Yeh khud khulta hai, aap manually nahi kholte."""
    if error:
        return HTMLResponse(f"<h2>Connect nahi hua</h2><p>{error}</p>", status_code=400)
    if not code or not state:
        return HTMLResponse("<h2>code/state missing</h2>", status_code=400)
    try:
        res = gcal.exchange_code(code, state)
    except Exception as e:
        return HTMLResponse(f"<h2>Fail</h2><p>{e}</p>", status_code=400)
    return HTMLResponse(
        f"<div style='font-family:sans-serif;padding:40px'>"
        f"<h2>Calendar juR gaya</h2><p><b>{res['email']}</b> ka calendar connect ho gaya hai.</p>"
        f"<p>Ab jab bhi koi candidate shortlist hoga, interview seedha is calendar mein "
        f"aa jayega — Google Meet link ke saath.</p>"
        f"<p>Yeh tab band kar dein.</p></div>")


@router.delete("/disconnect", dependencies=[Depends(require_admin)])
def disconnect(email: str):
    return {"email": email, "removed": gcal.disconnect(email)}
