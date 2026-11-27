"""Вхід і сесії.

Після перевірки Telegram сервер видає власний випадковий токен сесії (cookie).
У базі лежить лише SHA-256 від нього: витік файлу бази не дає увійти чужим
токеном. Сесія живе `SESSION_TTL` секунд.

Вхід для розробки (`dev_login`) існує, бо віджет Telegram не працює на
`localhost`: BotFather не прийме такий домен. Він вмикається лише явним
прапорцем у середовищі й створює окремих користувачів із відʼємним telegram_id,
які ніколи не збігаються зі справжніми.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any, Mapping

from dndsheet.identity.domain.ports import SessionStore, UserStore
from dndsheet.identity.domain.user import (
    TelegramProfile,
    User,
    verify_telegram_login,
    verify_telegram_webapp,
)
from dndsheet.shared.errors import ValidationError

#: Скільки живе сесія: 30 днів.
SESSION_TTL = 30 * 24 * 60 * 60

#: Скільки живе посилання для завантаження (PDF з Mini App): Telegram качає файл
#: сам, без нашої сесії, тож у посиланні — окремий короткий токен.
LINK_TTL = 5 * 60


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class LoginResult:
    user: User
    token: str
    #: Щойно зареєстрований користувач (перший вхід).
    created: bool


@dataclass(slots=True)
class AuthService:
    users: UserStore
    sessions: SessionStore
    bot_token: str = ""
    dev_login_enabled: bool = False

    def login_telegram(self, payload: Mapping[str, Any], *, now: float | None = None) -> LoginResult:
        profile = verify_telegram_login(payload, self.bot_token, now=now)
        return self._login(profile, now)

    def login_telegram_webapp(self, init_data: str, *, now: float | None = None) -> LoginResult:
        """Вхід із Mini App: Telegram уже підписав, хто відкрив застосунок."""
        profile = verify_telegram_webapp(init_data, self.bot_token, now=now)
        return self._login(profile, now)

    def link_token(self, user: User, *, now: float | None = None) -> str:
        """Короткий токен для посилання на файл (живе `LINK_TTL`)."""
        token = secrets.token_urlsafe(24)
        moment = time.time() if now is None else now
        self.sessions.create(user.id, token_hash(token), moment + LINK_TTL)
        return token

    def login_dev(self, name: str, *, now: float | None = None) -> LoginResult:
        if not self.dev_login_enabled:
            raise ValidationError("вхід для розробки вимкнено")
        cleaned = " ".join((name or "").split())[:64]
        if not cleaned:
            raise ValidationError("вкажіть імʼя")
        # Стабільний відʼємний id з імені: той самий «гравець» — той самий користувач.
        fake_id = -int(hashlib.sha256(cleaned.casefold().encode("utf-8")).hexdigest()[:12], 16)
        profile = TelegramProfile(
            telegram_id=fake_id, first_name=cleaned, last_name="", username="", photo_url=""
        )
        return self._login(profile, now)

    def current(self, token: str | None, *, now: float | None = None) -> User | None:
        if not token:
            return None
        user_id = self.sessions.user_id(token_hash(token), time.time() if now is None else now)
        return None if user_id is None else self.users.get(user_id)

    def logout(self, token: str | None) -> None:
        if token:
            self.sessions.delete(token_hash(token))

    def _login(self, profile: TelegramProfile, now: float | None) -> LoginResult:
        user, created = self.users.upsert_telegram(profile)
        token = secrets.token_urlsafe(32)
        moment = time.time() if now is None else now
        self.sessions.create(user.id, token_hash(token), moment + SESSION_TTL)
        return LoginResult(user=user, token=token, created=created)
