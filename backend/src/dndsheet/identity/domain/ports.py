"""Порти контексту identity: де лежать користувачі й сесії."""

from __future__ import annotations

from typing import Protocol

from dndsheet.identity.domain.user import TelegramProfile, User


class UserStore(Protocol):
    def upsert_telegram(self, profile: TelegramProfile) -> tuple[User, bool]:
        """Знайти чи створити користувача за telegram_id; `True` — щойно створений."""

    def get(self, user_id: str) -> User | None:
        """Користувач за id."""

    def count(self) -> int:
        """Скільки користувачів зареєстровано."""


class SessionStore(Protocol):
    def create(self, user_id: str, token_hash: str, expires_at: float) -> None:
        """Записати сесію (зберігається лише хеш токена)."""

    def user_id(self, token_hash: str, now: float) -> str | None:
        """Чия це сесія, якщо вона ще дійсна."""

    def delete(self, token_hash: str) -> None:
        """Вийти: прибрати сесію."""
