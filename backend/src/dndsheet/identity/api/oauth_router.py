"""HTTP екрана згоди й «Підключених застосунків».

Протокол OAuth (`/authorize`, `/token`…) веде SDK MCP. Тут — те, що потрібне
SPA: показати запит застосунку, прийняти рішення гравця, перелічити й
відключити застосунки.

Рішення приймається лише POST із JSON: форма з чужого сайту так не надішле
(до того ж cookie сесії `SameSite=Lax` у чужий POST не йде).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Body, HTTPException, Request

from dndsheet.identity.api.oauth_provider import SiteOAuthProvider, client_summary
from dndsheet.identity.api.router import current_user, require_user
from dndsheet.identity.application.oauth import OAuthService
from dndsheet.identity.domain.oauth import SCOPE_CHARACTERS
from dndsheet.shared.errors import NotFoundError

router = APIRouter(prefix="/api/v1/oauth", tags=["oauth"])

#: Що означає кожен дозвіл — так, як його побачить гравець.
SCOPE_TITLES = {
    SCOPE_CHARACTERS: "Бачити й змінювати ваших персонажів: створювати, вести лист, відпочивати, підвищувати рівень",
}


def _oauth(request: Request) -> tuple[OAuthService, SiteOAuthProvider]:
    service = getattr(request.app.state, "oauth", None)
    provider = getattr(request.app.state, "oauth_provider", None)
    if service is None or provider is None:
        raise HTTPException(status_code=404, detail="підключення застосунків вимкнено")
    return service, provider


@router.get("/requests/{request_id}")
async def read_request(request_id: str, request: Request) -> dict[str, Any]:
    """Що просить застосунок: показати на екрані згоди."""
    service, provider = _oauth(request)
    try:
        pending = service.pending(request_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    client = await provider.get_client(pending.client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="застосунок більше недоступний — почніть підключення ще раз")
    user = current_user(request)
    return {
        "client": client_summary(client),
        # Куди повернеться браузер — показуємо завжди (вимога специфікації MCP).
        "redirect_host": urlsplit(pending.redirect_uri).hostname or pending.redirect_uri,
        "scopes": [{"key": scope, "title": SCOPE_TITLES.get(scope, scope)} for scope in pending.scopes],
        "expires_at": pending.expires_at,
        "signed_in": user is not None,
    }


@router.post("/requests/{request_id}")
def decide(request_id: str, request: Request, payload: dict[str, Any] = Body(...)) -> dict[str, str]:
    """«Дозволити» чи «Відмовити» → адреса, куди браузер повертається до застосунку."""
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(status_code=415, detail="лише JSON")
    service, _ = _oauth(request)
    user = require_user(request)
    try:
        redirect = service.decide(request_id, user, bool(payload.get("approve")))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"redirect": redirect}


@router.get("/grants")
def grants(request: Request) -> dict[str, Any]:
    """Підключені застосунки гравця."""
    user = require_user(request)
    service = getattr(request.app.state, "oauth", None)
    if service is None:
        return {"items": []}
    return {
        "items": [
            {
                "client_id": grant.client_id,
                "name": grant.client_name,
                "scopes": list(grant.scopes),
                "connected_at": grant.connected_at,
                "last_used_at": grant.last_used_at,
            }
            for grant in service.grants(user)
        ]
    }


@router.delete("/grants")
def disconnect(client_id: str, request: Request) -> dict[str, Any]:
    """Відключити застосунок: усі його токени цього гравця перестають діяти одразу."""
    service, _ = _oauth(request)
    user = require_user(request)
    try:
        service.disconnect(user, client_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return grants(request)
