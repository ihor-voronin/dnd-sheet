"""HTTP входу: Telegram, вхід для розробки, «хто я», вихід.

Сесія — cookie `dndsheet_session` (HttpOnly, SameSite=Lax): JavaScript сторінки
її не бачить, а з чужого сайту вона не йде разом із POST-запитом.

Режим одного користувача (`DNDSHEET_AUTH=off`) — для тестів і локального
запуску без входу: кожен запит виконується від імені «локального гравця».
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request, Response

from dndsheet.identity.application.auth import SESSION_TTL, AuthService, LoginResult
from dndsheet.identity.domain.user import User
from dndsheet.shared.errors import ValidationError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

COOKIE = "dndsheet_session"

#: Користувач режиму без входу.
LOCAL_USER = User(id="local", telegram_id=0, first_name="Локальний гравець")


def auth_enabled() -> bool:
    return os.environ.get("DNDSHEET_AUTH", "on").strip().casefold() not in {"off", "0", "false", "no"}


def _service(request: Request) -> AuthService:
    return request.app.state.auth


def current_user(request: Request) -> User | None:
    """Хто робить запит; `None` — гість."""
    if not request.app.state.auth_enabled:
        return LOCAL_USER
    cached = getattr(request.state, "user", False)
    if cached is not False:
        return cached
    user = _service(request).current(request.cookies.get(COOKIE))
    request.state.user = user
    return user


def require_user(request: Request) -> User:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="увійдіть через Telegram, щоб працювати з персонажами")
    return user


def _user_payload(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "name": user.display_name,
        "username": user.username or None,
        "photo_url": user.photo_url or None,
    }


def _secure(request: Request) -> bool:
    forced = os.environ.get("DNDSHEET_COOKIE_SECURE", "").strip().casefold()
    if forced in {"1", "true", "yes", "on"}:
        return True
    if forced in {"0", "false", "no", "off"}:
        return False
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"


def _start_session(request: Request, response: Response, result: LoginResult) -> dict[str, Any]:
    hook = getattr(request.app.state, "on_login", None)
    if hook is not None:
        hook(result)
    response.set_cookie(
        COOKIE,
        result.token,
        max_age=SESSION_TTL,
        httponly=True,
        samesite="lax",
        secure=_secure(request),
        path="/",
    )
    return {"user": _user_payload(result.user)}


@router.get("/config")
def config(request: Request) -> dict[str, Any]:
    """Які способи входу доступні: бот для віджета, вхід для розробки, чи вхід узагалі потрібен."""
    service = _service(request)
    return {
        "auth_enabled": request.app.state.auth_enabled,
        "telegram_bot": request.app.state.telegram_bot or None,
        "telegram_ready": bool(service.bot_token and request.app.state.telegram_bot),
        "dev_login": service.dev_login_enabled,
    }


@router.get("/me")
def me(request: Request) -> dict[str, Any]:
    user = current_user(request)
    return {"user": None if user is None else _user_payload(user)}


@router.post("/telegram")
def login_telegram(
    request: Request, response: Response, payload: dict[str, Any] = Body(default_factory=dict)
) -> dict[str, Any]:
    try:
        result = _service(request).login_telegram(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return _start_session(request, response, result)


@router.post("/dev")
def login_dev(
    request: Request, response: Response, payload: dict[str, Any] = Body(default_factory=dict)
) -> dict[str, Any]:
    service = _service(request)
    if not service.dev_login_enabled:
        raise HTTPException(status_code=404, detail="вхід для розробки вимкнено")
    try:
        result = service.login_dev(str(payload.get("name") or ""))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _start_session(request, response, result)


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, Any]:
    _service(request).logout(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")
    return {"user": None}
