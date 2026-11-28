"""Сервер авторизації для застосунків: SDK MCP + наш `OAuthService`.

SDK веде протокол — `/authorize`, `/token`, `/register`, `/revoke`, PKCE,
перевірку адрес повернення й формат помилок. Тут лише відповіді на його
питання: «хто цей застосунок», «що робити із запитом», «чий це токен».

Застосунки ідентифікуються двома способами:

* адресою опису (Client ID Metadata Document) — `client_id` є https-адресою,
  опис завантажується й тримається годину;
* реєстрацією (`/register`, RFC 7591) — застаріла в специфікації, але її досі
  використовують клієнти; кількість реєстрацій обмежена.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import anyio.to_thread
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    RegistrationError,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl
from pydantic import ValidationError as PydanticValidationError

from dndsheet.identity.application.oauth import OAuthService, TokenPair
from dndsheet.identity.domain.oauth import SCOPES, OAuthStore
from dndsheet.shared.errors import ValidationError

#: Скільки тримати завантажений опис застосунку.
METADATA_TTL = 60 * 60
#: Не більше стількох реєстрацій за `REGISTER_WINDOW` секунд (на весь сервер).
REGISTER_LIMIT = 30
REGISTER_WINDOW = 10 * 60
#: Зареєстровані застосунки, які так і не отримали токена, живуть добу.
REGISTERED_TTL = 24 * 60 * 60

_LOOPBACK = {"localhost", "127.0.0.1", "[::1]", "::1"}


def redirect_allowed(uri: str) -> bool:
    """Адреса повернення: https або локальна (застосунки на компʼютері)."""
    parts = urlsplit(uri)
    if parts.fragment:
        return False
    if parts.scheme == "https":
        return bool(parts.hostname)
    return parts.scheme == "http" and (parts.hostname or "") in _LOOPBACK


def is_url_client_id(client_id: str) -> bool:
    return client_id.startswith("https://")


@dataclass(slots=True)
class SiteOAuthProvider:
    """Реалізує `OAuthAuthorizationServerProvider` з SDK MCP."""

    service: OAuthService
    store: OAuthStore
    #: Адреса сторінки згоди в SPA; до неї дописується id запиту.
    consent_url: str
    fetch_metadata: Callable[[str], dict[str, Any]]
    _registrations: deque[float] = field(default_factory=deque)

    # --- застосунки ------------------------------------------------------------

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        stored = self.store.client(client_id)
        if is_url_client_id(client_id):
            if stored is not None and stored[2] > time.time() - METADATA_TTL:
                return OAuthClientInformationFull.model_validate_json(stored[0])
            return await self._fetch_client(client_id)
        if stored is None:
            return None
        return OAuthClientInformationFull.model_validate_json(stored[0])

    async def _fetch_client(self, client_id: str) -> OAuthClientInformationFull | None:
        try:
            document = await anyio.to_thread.run_sync(self.fetch_metadata, client_id)
        except Exception:  # опис недоступний — застосунку для нас немає
            return None
        if document.get("client_id") != client_id:
            return None
        redirects = document.get("redirect_uris")
        if not isinstance(redirects, list) or not redirects:
            return None
        if not all(isinstance(uri, str) and redirect_allowed(uri) for uri in redirects):
            return None
        try:
            client = OAuthClientInformationFull(
                client_id=client_id,
                client_name=str(document.get("client_name") or urlsplit(client_id).hostname),
                client_uri=document.get("client_uri") or None,
                redirect_uris=[AnyUrl(uri) for uri in redirects],
                token_endpoint_auth_method="none",
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
                scope=" ".join(SCOPES),
            )
        except PydanticValidationError:
            return None
        self.store.save_client(client_id, client.model_dump_json(exclude_none=True), "cimd", time.time())
        return client

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        now = time.time()
        while self._registrations and self._registrations[0] < now - REGISTER_WINDOW:
            self._registrations.popleft()
        if len(self._registrations) >= REGISTER_LIMIT:
            raise RegistrationError("invalid_client_metadata", "забагато реєстрацій — спробуйте за кілька хвилин")
        uris = [str(uri) for uri in client_info.redirect_uris or []]
        if not uris or not all(redirect_allowed(uri) for uri in uris):
            raise RegistrationError("invalid_redirect_uri", "адреси повернення — лише https або localhost")
        self._registrations.append(now)
        self.store.purge_clients("dcr", now - REGISTERED_TTL)
        client_info.scope = " ".join(SCOPES)
        self.store.save_client(client_info.client_id, client_info.model_dump_json(exclude_none=True), "dcr", now)

    # --- згода ---------------------------------------------------------------

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        try:
            pending = self.service.start(
                client_id=client.client_id,
                redirect_uri=str(params.redirect_uri),
                redirect_uri_explicit=params.redirect_uri_provided_explicitly,
                scopes=tuple(params.scopes) if params.scopes else None,
                code_challenge=params.code_challenge,
                state=params.state,
                resource=params.resource,
            )
        except ValidationError as exc:
            code = "invalid_target" if params.resource else "invalid_scope"
            raise AuthorizeError(code, str(exc)) from exc
        return self.consent_url + pending.id

    # --- коди й токени -------------------------------------------------------

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        issued = self.service.code(authorization_code)
        if issued is None or issued.client_id != client.client_id:
            return None
        return AuthorizationCode(
            code=authorization_code,
            scopes=list(issued.scopes),
            expires_at=issued.expires_at,
            client_id=issued.client_id,
            code_challenge=issued.code_challenge,
            redirect_uri=AnyUrl(issued.redirect_uri),
            redirect_uri_provided_explicitly=issued.redirect_uri_explicit,
            resource=issued.resource,
            subject=issued.user_id,
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        try:
            pair = self.service.exchange_code(authorization_code.code, client.client_id)
        except ValidationError as exc:
            raise TokenError("invalid_grant", str(exc)) from exc
        return _token_response(pair)

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        stored = self.service.refresh_token(refresh_token, client.client_id)
        if stored is None:
            return None
        return RefreshToken(
            token=refresh_token,
            client_id=stored.client_id,
            scopes=list(stored.scopes),
            expires_at=int(stored.expires_at),
            resource=stored.resource,
            subject=stored.user_id,
        )

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        try:
            pair = self.service.rotate(refresh_token.token, client.client_id, tuple(scopes))
        except ValidationError as exc:
            raise TokenError("invalid_grant", str(exc)) from exc
        return _token_response(pair)

    async def load_access_token(self, token: str) -> AccessToken | None:
        stored = self.service.access(token)
        if stored is None:
            return None
        return AccessToken(
            token=token,
            client_id=stored.client_id,
            scopes=list(stored.scopes),
            expires_at=int(stored.expires_at),
            resource=stored.resource,
            subject=stored.user_id,
        )

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        self.service.revoke(token.token)

    async def exchange_identity_assertion(self, client: Any, params: Any) -> OAuthToken:  # noqa: ANN401
        # SDK кличе це лише з `identity_assertion_enabled`, а ми його не вмикаємо.
        raise TokenError("unsupported_grant_type", "не підтримується")  # pragma: no cover


def _token_response(pair: TokenPair) -> OAuthToken:
    return OAuthToken(
        access_token=pair.access_token,
        expires_in=pair.expires_in,
        scope=" ".join(pair.scopes),
        refresh_token=pair.refresh_token,
    )


def client_summary(client: OAuthClientInformationFull) -> dict[str, Any]:
    """Що показати на екрані згоди про застосунок."""
    hosts = sorted({urlsplit(str(uri)).hostname or "" for uri in client.redirect_uris or []})
    return {
        "client_id": client.client_id,
        "name": client.client_name or client.client_id,
        "uri": str(client.client_uri) if client.client_uri else None,
        "redirect_hosts": hosts,
        "local_only": bool(hosts) and all(host in _LOOPBACK for host in hosts),
        "verified_by_url": is_url_client_id(client.client_id),
    }
