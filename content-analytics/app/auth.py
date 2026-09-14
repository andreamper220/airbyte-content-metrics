from functools import lru_cache

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import RedirectResponse

from app.config import settings

oauth = OAuth()

if settings.google_client_id and settings.google_client_secret:
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def is_auth_enabled() -> bool:
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and settings.session_secret
    )


@lru_cache
def get_allowed_emails() -> frozenset[str]:
    return frozenset(
        email.strip().lower()
        for email in settings.allowed_emails.split(",")
        if email.strip()
    )


async def require_user(request: Request) -> str:
    if not is_auth_enabled():
        return "anonymous"
    email = request.session.get("email")
    if not email or email.lower() not in get_allowed_emails():
        raise HTTPException(status_code=401, detail="Not authenticated")
    return email


router = APIRouter(tags=["auth"])


@router.get("/auth/login")
async def login(request: Request):
    if not is_auth_enabled():
        return RedirectResponse(url="/", status_code=302)
    return await oauth.google.authorize_redirect(request, settings.oauth_redirect_uri)


@router.get("/auth/callback")
async def callback(request: Request):
    if not is_auth_enabled():
        return RedirectResponse(url="/", status_code=302)
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return RedirectResponse(url="/login?error=oauth_failed", status_code=302)

    userinfo = token.get("userinfo") or {}
    email = (userinfo.get("email") or "").lower()
    if not email or email not in get_allowed_emails():
        request.session.clear()
        return RedirectResponse(url="/login?error=access_denied", status_code=302)

    request.session["email"] = email
    return RedirectResponse(url="/", status_code=302)


@router.get("/auth/me")
async def me(request: Request):
    if not is_auth_enabled():
        return {"email": None, "auth_enabled": False}
    email = request.session.get("email")
    if not email or email.lower() not in get_allowed_emails():
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"email": email, "auth_enabled": True}


@router.post("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}
