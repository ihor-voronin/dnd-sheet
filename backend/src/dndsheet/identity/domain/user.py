"""Користувач і перевірка входу через Telegram.

Вхід — Telegram Login Widget (https://core.telegram.org/widgets/login). Віджет
віддає браузеру поля користувача й `hash`; сервер перевіряє, що їх підписав
саме Telegram для нашого бота:

    data_check_string = рядки «ключ=значення» без `hash`, за абеткою, через «\\n»
    secret_key        = SHA256(токен бота)
    hash              = HMAC_SHA256(secret_key, data_check_string) у hex

Підпис без перевірки свіжості можна було б повторити будь-коли, тому
`auth_date` має бути не старшим за `max_age`.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any, Mapping

from dndsheet.shared.errors import ValidationError

#: Скільки секунд підпис Telegram вважається свіжим.
LOGIN_MAX_AGE = 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class User:
    """Гравець. `telegram_id` — стабільний ідентифікатор, імʼя може змінитися."""

    id: str
    telegram_id: int
    first_name: str
    last_name: str = ""
    username: str = ""
    photo_url: str = ""

    @property
    def display_name(self) -> str:
        full = " ".join(part for part in (self.first_name, self.last_name) if part)
        return full or (f"@{self.username}" if self.username else "гравець")


@dataclass(frozen=True, slots=True)
class TelegramProfile:
    """Перевірені дані з віджета Telegram."""

    telegram_id: int
    first_name: str
    last_name: str
    username: str
    photo_url: str


def verify_telegram_login(
    payload: Mapping[str, Any],
    bot_token: str,
    *,
    now: float | None = None,
    max_age: int = LOGIN_MAX_AGE,
) -> TelegramProfile:
    """Перевірити підпис віджета й повернути профіль; інакше `ValidationError`."""
    if not bot_token:
        raise ValidationError("вхід через Telegram не налаштовано (немає токена бота)")
    received = str(payload.get("hash") or "")
    if not received:
        raise ValidationError("немає підпису Telegram")
    fields = {
        str(key): str(value)
        for key, value in payload.items()
        if key != "hash" and value is not None
    }
    check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hashlib.sha256(bot_token.encode("utf-8")).digest()
    expected = hmac.new(secret, check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received.lower()):
        raise ValidationError("підпис Telegram не збігається")
    try:
        auth_date = int(fields.get("auth_date", "0"))
        telegram_id = int(fields["id"])
    except (KeyError, ValueError) as exc:
        raise ValidationError("неповні дані Telegram") from exc
    current = time.time() if now is None else now
    if auth_date <= 0 or current - auth_date > max_age:
        raise ValidationError("вхід застарів — увійдіть через Telegram ще раз")
    return TelegramProfile(
        telegram_id=telegram_id,
        first_name=fields.get("first_name", ""),
        last_name=fields.get("last_name", ""),
        username=fields.get("username", ""),
        photo_url=fields.get("photo_url", ""),
    )
