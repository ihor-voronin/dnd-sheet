"""Користувачі й сесії в тій самій базі SQLite, що й персонажі (власні таблиці)."""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from dndsheet.identity.domain.user import TelegramProfile, User

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    telegram_id INTEGER NOT NULL UNIQUE,
    first_name TEXT NOT NULL DEFAULT '',
    last_name TEXT NOT NULL DEFAULT '',
    username TEXT NOT NULL DEFAULT '',
    photo_url TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_login_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
"""

_COLUMNS = "id, telegram_id, first_name, last_name, username, photo_url"


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=10000")
    return connection


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
class SqliteIdentityStore:
    """Реалізує і `UserStore`, і `SessionStore`: одна база, дві таблиці."""

    path: Path

    def __post_init__(self) -> None:
        with closing(_connect(self.path)) as connection, connection:
            connection.executescript(_SCHEMA)

    # --- користувачі ---------------------------------------------------------

    def upsert_telegram(self, profile: TelegramProfile) -> tuple[User, bool]:
        with closing(_connect(self.path)) as connection, connection:
            row = connection.execute("SELECT id FROM users WHERE telegram_id = ?", (profile.telegram_id,)).fetchone()
            created = row is None
            user_id = uuid.uuid4().hex if created else row[0]
            if created:
                connection.execute(
                    "INSERT INTO users (id, telegram_id) VALUES (?, ?)",
                    (user_id, profile.telegram_id),
                )
            # Імʼя й фото в Telegram змінюються — оновлюємо на кожному вході.
            connection.execute(
                "UPDATE users SET first_name = ?, last_name = ?, username = ?, photo_url = ?,"
                " last_login_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
                (profile.first_name, profile.last_name, profile.username, profile.photo_url, user_id),
            )
            stored = connection.execute(f"SELECT {_COLUMNS} FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user(stored), created

    def get(self, user_id: str) -> User | None:
        with closing(_connect(self.path)) as connection:
            row = connection.execute(f"SELECT {_COLUMNS} FROM users WHERE id = ?", (user_id,)).fetchone()
        return None if row is None else _user(row)

    def count(self) -> int:
        with closing(_connect(self.path)) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    # --- сесії ---------------------------------------------------------------

    def create(self, user_id: str, token_hash: str, expires_at: float) -> None:
        with closing(_connect(self.path)) as connection, connection:
            connection.execute(
                "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                (token_hash, user_id, expires_at),
            )

    def user_id(self, token_hash: str, now: float) -> str | None:
        with closing(_connect(self.path)) as connection:
            row = connection.execute(
                "SELECT user_id FROM sessions WHERE token_hash = ? AND expires_at > ?",
                (token_hash, now),
            ).fetchone()
        return None if row is None else row[0]

    def delete(self, token_hash: str) -> None:
        with closing(_connect(self.path)) as connection, connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
