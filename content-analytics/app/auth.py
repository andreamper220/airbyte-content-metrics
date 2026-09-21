from functools import lru_cache
import json
import logging
from pathlib import Path

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import HTMLResponse, RedirectResponse

from app.config import settings

logger = logging.getLogger(__name__)

YOUTUBE_COMMENT_SCOPE = (
    "openid email profile https://www.googleapis.com/auth/youtube.force-ssl"
)

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


def _save_youtube_refresh_token(refresh_token: str, email: str) -> None:
    path = Path(settings.youtube_token_path or "/secrets/youtube-comment-token.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "refresh_token": refresh_token,
                "email": email,
                "client_id": settings.google_client_id,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass


@router.get("/auth/login")
async def login(request: Request):
    if not is_auth_enabled():
        return RedirectResponse(url="/", status_code=302)
    request.session.pop("oauth_purpose", None)
    return await oauth.google.authorize_redirect(request, settings.oauth_redirect_uri)


@router.get("/auth/youtube-comment")
async def youtube_comment_login(request: Request):
    if not is_auth_enabled():
        return RedirectResponse(url="/login", status_code=302)
    request.session["oauth_purpose"] = "youtube_comments"
    return await oauth.google.authorize_redirect(
        request,
        settings.oauth_redirect_uri,
        scope=YOUTUBE_COMMENT_SCOPE,
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )


@router.get("/auth/callback")
async def callback(request: Request):
    if not is_auth_enabled():
        return RedirectResponse(url="/", status_code=302)
    purpose = request.session.pop("oauth_purpose", None)
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        logger.exception("Google OAuth callback failed")
        return RedirectResponse(url="/login?error=oauth_failed", status_code=302)

    userinfo = token.get("userinfo") or {}
    email = (userinfo.get("email") or "").lower()
    if not email or email not in get_allowed_emails():
        request.session.clear()
        return RedirectResponse(url="/login?error=access_denied", status_code=302)

    request.session["email"] = email
    if purpose == "youtube_comments":
        refresh = str(token.get("refresh_token") or "")
        if not refresh:
            return HTMLResponse(
                "<html><body style='font-family:sans-serif;padding:2rem'>"
                "<h2>Google не вернул refresh token</h2>"
                "<p>Откройте ссылку ещё раз и нажмите «Разрешить». "
                "Нужно разрешить доступ к YouTube.</p>"
                "<p><a href='/auth/youtube-comment'>Повторить</a></p>"
                "</body></html>",
                status_code=400,
            )
        try:
            _save_youtube_refresh_token(refresh, email)
        except OSError:
            logger.exception("Failed to save YouTube refresh token")
            return HTMLResponse(
                "<html><body style='font-family:sans-serif;padding:2rem'>"
                "<h2>Не удалось сохранить токен на сервере</h2>"
                "<p>Напишите в чат — проверим права на /secrets.</p>"
                "</body></html>",
                status_code=500,
            )
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;padding:2rem'>"
            "<h2>YouTube подключён для комментариев</h2>"
            "<p>Можно закрыть вкладку и писать комментарии в дашборде.</p>"
            "<p><a href='/'>Открыть дашборд</a></p>"
            "</body></html>"
        )
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
