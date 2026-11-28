"""Сайт як сервер авторизації для застосунків (ADR 0005).

Що тут вирішується: хто дозволив, що видати, коли токен уже не дійсний.
Що НЕ тут: розбір запитів OAuth, PKCE, формат відповідей — це SDK MCP
(`dndsheet.identity.api.oauth_provider` з'єднує його з цим сервісом).

Правила:

* дозвіл дає лише гравець, що вже має акаунт (увійшов через Telegram);
* код — одноразовий, 60 секунд, прив'язаний до застосунку, адреси й PKCE;
* токен доступу — година; токен оновлення — 30 днів і міняється щоразу;
* повторне використання старого токена оновлення означає крадіжку:
  відкликається вся згода (усі токени цієї «родини»);
* кожен токен — лише для одного ресурсу (`/mcp`), іншим його не приймуть.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dndsheet.identity.application.auth import token_hash
from dndsheet.identity.domain.oauth import (
    ACCESS_TTL,
    CODE_TTL,
    REFRESH_TTL,
    REQUEST_TTL,
    SCOPES,
    Grant,
    IssuedCode,
    OAuthStore,
    PendingAuthorization,
    StoredToken,
)
from dndsheet.identity.domain.user import User
from dndsheet.shared.errors import NotFoundError, ValidationError


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int
    scopes: tuple[str, ...]


def with_query(url: str, **params: str | None) -> str:
    """Дописати параметри до адреси повернення, не зачепивши наявні."""
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.extend((key, value) for key, value in params.items() if value is not None)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@dataclass(slots=True)
class OAuthService:
    store: OAuthStore
    #: Адреса сервера авторизації (`iss` у відповіді, RFC 9207).
    issuer: str
    #: Єдиний ресурс, для якого видаються токени: адреса MCP.
    resource: str

    # --- запит на дозвіл -----------------------------------------------------

    def start(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        redirect_uri_explicit: bool,
        scopes: tuple[str, ...] | None,
        code_challenge: str,
        state: str | None,
        resource: str | None,
        now: float | None = None,
    ) -> PendingAuthorization:
        """Запам'ятати запит застосунку до рішення гравця."""
        moment = time.time() if now is None else now
        if resource is not None and canonical(resource) != canonical(self.resource):
            raise ValidationError(f"токени видаються лише для {self.resource}")
        requested = tuple(scopes) if scopes else SCOPES
        unknown = [scope for scope in requested if scope not in SCOPES]
        if unknown:
            raise ValidationError(f"невідомий дозвіл: {', '.join(unknown)}")
        self.store.purge(moment)
        pending = PendingAuthorization(
            id=secrets.token_urlsafe(24),
            client_id=client_id,
            redirect_uri=redirect_uri,
            redirect_uri_explicit=redirect_uri_explicit,
            scopes=requested,
            code_challenge=code_challenge,
            state=state,
            resource=self.resource,
            expires_at=moment + REQUEST_TTL,
        )
        self.store.save_request(pending)
        return pending

    def pending(self, request_id: str, *, now: float | None = None) -> PendingAuthorization:
        found = self.store.request(request_id, time.time() if now is None else now)
        if found is None:
            raise NotFoundError("запит на дозвіл не знайдено або він застарів — почніть підключення ще раз")
        return found

    def decide(self, request_id: str, user: User, approve: bool, *, now: float | None = None) -> str:
        """Рішення гравця → адреса, куди повернути браузер (з кодом або з відмовою)."""
        moment = time.time() if now is None else now
        pending = self.store.take_request(request_id, moment)
        if pending is None:
            raise NotFoundError("запит на дозвіл не знайдено або він застарів — почніть підключення ще раз")
        if not approve:
            return with_query(
                pending.redirect_uri,
                error="access_denied",
                error_description="гравець не дозволив доступ",
                state=pending.state,
                iss=self.issuer,
            )
        code = secrets.token_urlsafe(32)
        self.store.save_code(
            token_hash(code),
            IssuedCode(
                client_id=pending.client_id,
                user_id=user.id,
                redirect_uri=pending.redirect_uri,
                redirect_uri_explicit=pending.redirect_uri_explicit,
                scopes=pending.scopes,
                code_challenge=pending.code_challenge,
                resource=pending.resource,
                expires_at=moment + CODE_TTL,
            ),
        )
        return with_query(pending.redirect_uri, code=code, state=pending.state, iss=self.issuer)

    # --- коди й токени -------------------------------------------------------

    def code(self, code: str) -> IssuedCode | None:
        return self.store.code(token_hash(code))

    def exchange_code(self, code: str, client_id: str, *, now: float | None = None) -> TokenPair:
        """Код → пара токенів. Код одноразовий: вдруге його вже немає."""
        moment = time.time() if now is None else now
        issued = self.store.take_code(token_hash(code))
        if issued is None or issued.client_id != client_id:
            raise ValidationError("код авторизації не дійсний")
        if issued.expires_at < moment:
            raise ValidationError("код авторизації застарів")
        return self._issue(
            family=secrets.token_urlsafe(16),
            user_id=issued.user_id,
            client_id=client_id,
            scopes=issued.scopes,
            resource=issued.resource,
            now=moment,
        )

    def refresh_token(self, token: str, client_id: str, *, now: float | None = None) -> StoredToken | None:
        """Токен оновлення, якщо він дійсний. Повторне використання — відкликати всю згоду."""
        moment = time.time() if now is None else now
        stored = self.store.token(token_hash(token))
        if stored is None or stored.kind != "refresh" or stored.client_id != client_id:
            return None
        if stored.used:
            self.store.revoke_family(stored.family)
            return None
        if stored.expires_at < moment:
            return None
        return stored

    def rotate(self, token: str, client_id: str, scopes: tuple[str, ...], *, now: float | None = None) -> TokenPair:
        """Новий токен доступу й новий токен оновлення; старий оновлення більше не діє."""
        moment = time.time() if now is None else now
        stored = self.refresh_token(token, client_id, now=moment)
        if stored is None or not self.store.mark_used(token_hash(token)):
            if stored is not None:
                self.store.revoke_family(stored.family)
            raise ValidationError("токен оновлення не дійсний")
        narrowed = tuple(scope for scope in scopes if scope in stored.scopes) or stored.scopes
        return self._issue(
            family=stored.family,
            user_id=stored.user_id,
            client_id=client_id,
            scopes=narrowed,
            resource=stored.resource,
            now=moment,
        )

    def access(self, token: str, *, now: float | None = None) -> StoredToken | None:
        """Чий це токен доступу і на що він дає право; `None` — не дійсний."""
        moment = time.time() if now is None else now
        hashed = token_hash(token)
        stored = self.store.token(hashed)
        if stored is None or stored.kind != "access" or stored.expires_at < moment:
            return None
        self.store.touch(hashed, moment)
        return stored

    def revoke(self, token: str) -> None:
        """RFC 7009: відкликати токен — і всю згоду, з якої він виріс."""
        stored = self.store.token(token_hash(token))
        if stored is not None:
            self.store.revoke_family(stored.family)

    # --- профіль гравця ------------------------------------------------------

    def grants(self, user: User, *, now: float | None = None) -> list[Grant]:
        return self.store.grants(user.id, time.time() if now is None else now)

    def disconnect(self, user: User, client_id: str) -> None:
        if not self.store.revoke_client(user.id, client_id):
            raise NotFoundError("такого підключеного застосунку немає")

    def _issue(
        self,
        *,
        family: str,
        user_id: str,
        client_id: str,
        scopes: tuple[str, ...],
        resource: str,
        now: float,
    ) -> TokenPair:
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        base = {"family": family, "user_id": user_id, "client_id": client_id, "scopes": scopes, "resource": resource}
        self.store.save_token(token_hash(access), StoredToken(kind="access", expires_at=now + ACCESS_TTL, **base), now)
        self.store.save_token(
            token_hash(refresh), StoredToken(kind="refresh", expires_at=now + REFRESH_TTL, **base), now
        )
        return TokenPair(access_token=access, refresh_token=refresh, expires_in=ACCESS_TTL, scopes=scopes)


def canonical(url: str) -> str:
    """Порівнянна форма адреси ресурсу: схема й хост малими, без кінцевої «/»."""
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))
