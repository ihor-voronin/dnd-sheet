"""Користувачі й сесії в PostgreSQL — `UserStore` і `SessionStore`, як у `sqlite_identity`."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from dndsheet.identity.domain.user import TelegramProfile, User

_COLUMNS = "id, telegram_id, first_name, last_name, username, photo_url"


def _user(row: tuple) -> User:
    return User(
        id=row[0],
        telegram_id=int(row[1]),
        first_name=row[2],
        last_name=row[3],
        username=row[4],
        photo_url=row[5],
    )


@dataclass(slots=True)
class PostgresIdentityStore:
    """Реалізує і `UserStore`, і `SessionStore`."""

    pool: ConnectionPool

    # --- користувачі ---------------------------------------------------------

    def upsert_telegram(self, profile: TelegramProfile) -> tuple[User, bool]:
        with self.pool.connection() as connection:
            # Перший вхід із двох пристроїв одночасно не створить двох користувачів:
            # другий INSERT нічого не вставить, і обидва прочитають того самого.
            inserted = connection.execute(
                "INSERT INTO users (id, telegram_id) VALUES (%s, %s) ON CONFLICT (telegram_id) DO NOTHING RETURNING id",
                (uuid.uuid4().hex, profile.telegram_id),
            ).fetchone()
            # Імʼя й фото в Telegram змінюються — оновлюємо на кожному вході.
            stored = connection.execute(
                "UPDATE users SET first_name = %s, last_name = %s, username = %s, photo_url = %s,"
                f" last_login_at = now() WHERE telegram_id = %s RETURNING {_COLUMNS}",
                (profile.first_name, profile.last_name, profile.username, profile.photo_url, profile.telegram_id),
            ).fetchone()
        assert stored is not None  # рядок щойно вставлено або він уже був
        return _user(stored), inserted is not None

    def get(self, user_id: str) -> User | None:
        with self.pool.connection() as connection:
            row = connection.execute(f"SELECT {_COLUMNS} FROM users WHERE id = %s", (user_id,)).fetchone()
        return None if row is None else _user(row)

    def count(self) -> int:
        with self.pool.connection() as connection:
            row = connection.execute("SELECT COUNT(*) FROM users").fetchone()
        return int(row[0]) if row else 0

    def exists_telegram(self, telegram_id: int) -> bool:
        with self.pool.connection() as connection:
            row = connection.execute("SELECT 1 FROM users WHERE telegram_id = %s", (telegram_id,)).fetchone()
        return row is not None

    # --- сесії ---------------------------------------------------------------

    def create(self, user_id: str, token_hash: str, expires_at: float) -> None:
        with self.pool.connection() as connection:
            connection.execute(
                "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
                (token_hash, user_id, expires_at),
            )

    def user_id(self, token_hash: str, now: float) -> str | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT user_id FROM sessions WHERE token_hash = %s AND expires_at > %s", (token_hash, now)
            ).fetchone()
        return None if row is None else row[0]

    def delete(self, token_hash: str) -> None:
        with self.pool.connection() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash,))
