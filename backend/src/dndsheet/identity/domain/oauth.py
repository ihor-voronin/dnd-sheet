"""OAuth для застосунків (MCP): хто що дозволив і які токени діють.

Сайт сам видає токени застосункам на кшталт Claude (ADR 0005). Тут — лише
модель: записи й терміни. Протокол (PKCE, редиректи, помилки) — у SDK MCP,
зберігання — в інфраструктурі.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

#: Єдиний дозвіл: керувати своїми персонажами (читати й змінювати).
SCOPE_CHARACTERS = "characters"
SCOPES: tuple[str, ...] = (SCOPE_CHARACTERS,)

#: Скільки живе запит на дозвіл, поки гравець вирішує (10 хвилин).
REQUEST_TTL = 10 * 60
#: Код авторизації: одноразовий і короткий.
CODE_TTL = 60
#: Токен доступу: година.
ACCESS_TTL = 60 * 60
#: Токен оновлення: 30 днів; міняється на кожному оновленні.
REFRESH_TTL = 30 * 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class PendingAuthorization:
    """Запит застосунку, який чекає на «Дозволити» чи «Відмовити»."""

    id: str
    client_id: str
    redirect_uri: str
    redirect_uri_explicit: bool
    scopes: tuple[str, ...]
    code_challenge: str
    state: str | None
    resource: str
    expires_at: float


@dataclass(frozen=True, slots=True)
class IssuedCode:
    """Код авторизації, виданий після згоди: прив'язаний до застосунку, адреси, PKCE й ресурсу."""

    client_id: str
    user_id: str
    redirect_uri: str
    redirect_uri_explicit: bool
    scopes: tuple[str, ...]
    code_challenge: str
    resource: str
    expires_at: float


@dataclass(frozen=True, slots=True)
class StoredToken:
    """Токен доступу чи оновлення. `family` — одна згода: усі токени, що з неї виросли."""

    kind: str  # "access" | "refresh"
    family: str
    user_id: str
    client_id: str
    scopes: tuple[str, ...]
    resource: str
    expires_at: float
    used: bool = False


@dataclass(frozen=True, slots=True)
class Grant:
    """Підключений застосунок у профілі гравця."""

    client_id: str
    client_name: str
    scopes: tuple[str, ...]
    connected_at: float
    last_used_at: float | None


class OAuthStore(Protocol):
    """Де лежать застосунки, запити, коди й токени (лише хеші секретів)."""

    def save_client(self, client_id: str, info: str, kind: str, now: float) -> None: ...

    def client(self, client_id: str) -> tuple[str, str, float] | None:
        """`(info JSON, kind, коли записано)` або `None`."""

    def purge_clients(self, kind: str, older_than: float) -> int:
        """Прибрати застосунки цього виду без жодного токена, записані раніше за `older_than`."""

    def save_request(self, pending: PendingAuthorization) -> None: ...

    def take_request(self, request_id: str, now: float) -> PendingAuthorization | None:
        """Забрати запит (одноразово), якщо він ще дійсний."""

    def request(self, request_id: str, now: float) -> PendingAuthorization | None: ...

    def save_code(self, code_hash: str, code: IssuedCode) -> None: ...

    def code(self, code_hash: str) -> IssuedCode | None: ...

    def take_code(self, code_hash: str) -> IssuedCode | None:
        """Забрати код (одноразово): другий виклик з тим самим кодом — `None`."""

    def save_token(self, token_hash: str, token: StoredToken, now: float) -> None: ...

    def token(self, token_hash: str) -> StoredToken | None: ...

    def mark_used(self, token_hash: str) -> bool:
        """Позначити токен оновлення використаним; `False` — його вже використали."""

    def touch(self, token_hash: str, now: float) -> None:
        """Коли востаннє скористалися доступом (для списку застосунків)."""

    def revoke_family(self, family: str) -> None: ...

    def revoke_client(self, user_id: str, client_id: str) -> int: ...

    def grants(self, user_id: str, now: float) -> list[Grant]: ...

    def purge(self, now: float) -> None:
        """Прибрати прострочені запити, коди й токени."""
