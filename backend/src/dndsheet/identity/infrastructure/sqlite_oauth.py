"""OAuth для застосунків — у тій самій базі SQLite, що й користувачі (власні таблиці).

Секрети (коди, токени) лежать лише як SHA-256: витік бази не дає ними
скористатися. Запис застосунку (`info`) — JSON у тому вигляді, в якому його
читає SDK MCP.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from dndsheet.identity.domain.oauth import Grant, IssuedCode, PendingAuthorization, StoredToken

_SCHEMA = """
CREATE TABLE IF NOT EXISTS oauth_clients (
    client_id TEXT PRIMARY KEY,
    info TEXT NOT NULL,
    kind TEXT NOT NULL,
    saved_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS oauth_requests (
    id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    redirect_uri_explicit INTEGER NOT NULL,
    scopes TEXT NOT NULL,
    code_challenge TEXT NOT NULL,
    state TEXT,
    resource TEXT NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS oauth_codes (
    code_hash TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    redirect_uri TEXT NOT NULL,
    redirect_uri_explicit INTEGER NOT NULL,
    scopes TEXT NOT NULL,
    code_challenge TEXT NOT NULL,
    resource TEXT NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS oauth_tokens (
    token_hash TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    family TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    client_id TEXT NOT NULL,
    scopes TEXT NOT NULL,
    resource TEXT NOT NULL,
    expires_at REAL NOT NULL,
    created_at REAL NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    last_used_at REAL
);
CREATE INDEX IF NOT EXISTS oauth_tokens_family ON oauth_tokens(family);
CREATE INDEX IF NOT EXISTS oauth_tokens_owner ON oauth_tokens(user_id, client_id);
"""


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=10000")
    return connection


def _scopes(raw: str) -> tuple[str, ...]:
    return tuple(part for part in raw.split(" ") if part)


_REQUEST_COLUMNS = (
    "id, client_id, redirect_uri, redirect_uri_explicit, scopes, code_challenge, state, resource, expires_at"
)
_CODE_COLUMNS = "client_id, user_id, redirect_uri, redirect_uri_explicit, scopes, code_challenge, resource, expires_at"
_TOKEN_COLUMNS = "kind, family, user_id, client_id, scopes, resource, expires_at, used"


def _pending(row: tuple) -> PendingAuthorization:
    return PendingAuthorization(
        id=row[0],
        client_id=row[1],
        redirect_uri=row[2],
        redirect_uri_explicit=bool(row[3]),
        scopes=_scopes(row[4]),
        code_challenge=row[5],
        state=row[6],
        resource=row[7],
        expires_at=float(row[8]),
    )


def _code(row: tuple) -> IssuedCode:
    return IssuedCode(
        client_id=row[0],
        user_id=row[1],
        redirect_uri=row[2],
        redirect_uri_explicit=bool(row[3]),
        scopes=_scopes(row[4]),
        code_challenge=row[5],
        resource=row[6],
        expires_at=float(row[7]),
    )


def _token(row: tuple) -> StoredToken:
    return StoredToken(
        kind=row[0],
        family=row[1],
        user_id=row[2],
        client_id=row[3],
        scopes=_scopes(row[4]),
        resource=row[5],
        expires_at=float(row[6]),
        used=bool(row[7]),
    )


@dataclass(slots=True)
class SqliteOAuthStore:
    """Реалізує `OAuthStore`. Таблиці створюються поруч із `users`."""

    path: Path

    def __post_init__(self) -> None:
        with closing(_connect(self.path)) as connection, connection:
            connection.executescript(_SCHEMA)

    # --- застосунки ------------------------------------------------------------

    def save_client(self, client_id: str, info: str, kind: str, now: float) -> None:
        with closing(_connect(self.path)) as connection, connection:
            connection.execute(
                "INSERT INTO oauth_clients (client_id, info, kind, saved_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(client_id) DO UPDATE SET info = excluded.info, kind = excluded.kind,"
                " saved_at = excluded.saved_at",
                (client_id, info, kind, now),
            )

    def client(self, client_id: str) -> tuple[str, str, float] | None:
        with closing(_connect(self.path)) as connection:
            row = connection.execute(
                "SELECT info, kind, saved_at FROM oauth_clients WHERE client_id = ?", (client_id,)
            ).fetchone()
        return None if row is None else (row[0], row[1], float(row[2]))

    def purge_clients(self, kind: str, older_than: float) -> int:
        with closing(_connect(self.path)) as connection, connection:
            cursor = connection.execute(
                "DELETE FROM oauth_clients WHERE kind = ? AND saved_at < ?"
                " AND client_id NOT IN (SELECT DISTINCT client_id FROM oauth_tokens)",
                (kind, older_than),
            )
            return cursor.rowcount

    # --- запити на дозвіл ----------------------------------------------------

    def save_request(self, pending: PendingAuthorization) -> None:
        with closing(_connect(self.path)) as connection, connection:
            connection.execute(
                f"INSERT INTO oauth_requests ({_REQUEST_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    pending.id,
                    pending.client_id,
                    pending.redirect_uri,
                    int(pending.redirect_uri_explicit),
                    " ".join(pending.scopes),
                    pending.code_challenge,
                    pending.state,
                    pending.resource,
                    pending.expires_at,
                ),
            )

    def request(self, request_id: str, now: float) -> PendingAuthorization | None:
        with closing(_connect(self.path)) as connection:
            row = connection.execute(
                f"SELECT {_REQUEST_COLUMNS} FROM oauth_requests WHERE id = ? AND expires_at > ?",
                (request_id, now),
            ).fetchone()
        return None if row is None else _pending(row)

    def take_request(self, request_id: str, now: float) -> PendingAuthorization | None:
        with closing(_connect(self.path)) as connection, connection:
            row = connection.execute(
                f"SELECT {_REQUEST_COLUMNS} FROM oauth_requests WHERE id = ? AND expires_at > ?",
                (request_id, now),
            ).fetchone()
            deleted = connection.execute("DELETE FROM oauth_requests WHERE id = ?", (request_id,)).rowcount
        return None if row is None or not deleted else _pending(row)

    # --- коди ----------------------------------------------------------------

    def save_code(self, code_hash: str, code: IssuedCode) -> None:
        with closing(_connect(self.path)) as connection, connection:
            connection.execute(
                f"INSERT INTO oauth_codes (code_hash, {_CODE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    code_hash,
                    code.client_id,
                    code.user_id,
                    code.redirect_uri,
                    int(code.redirect_uri_explicit),
                    " ".join(code.scopes),
                    code.code_challenge,
                    code.resource,
                    code.expires_at,
                ),
            )

    def code(self, code_hash: str) -> IssuedCode | None:
        with closing(_connect(self.path)) as connection:
            row = connection.execute(
                f"SELECT {_CODE_COLUMNS} FROM oauth_codes WHERE code_hash = ?", (code_hash,)
            ).fetchone()
        return None if row is None else _code(row)

    def take_code(self, code_hash: str) -> IssuedCode | None:
        with closing(_connect(self.path)) as connection, connection:
            row = connection.execute(
                f"SELECT {_CODE_COLUMNS} FROM oauth_codes WHERE code_hash = ?", (code_hash,)
            ).fetchone()
            deleted = connection.execute("DELETE FROM oauth_codes WHERE code_hash = ?", (code_hash,)).rowcount
        return None if row is None or not deleted else _code(row)

    # --- токени --------------------------------------------------------------

    def save_token(self, token_hash: str, token: StoredToken, now: float) -> None:
        with closing(_connect(self.path)) as connection, connection:
            connection.execute(
                f"INSERT INTO oauth_tokens (token_hash, {_TOKEN_COLUMNS}, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    token_hash,
                    token.kind,
                    token.family,
                    token.user_id,
                    token.client_id,
                    " ".join(token.scopes),
                    token.resource,
                    token.expires_at,
                    int(token.used),
                    now,
                ),
            )

    def token(self, token_hash: str) -> StoredToken | None:
        with closing(_connect(self.path)) as connection:
            row = connection.execute(
                f"SELECT {_TOKEN_COLUMNS} FROM oauth_tokens WHERE token_hash = ?", (token_hash,)
            ).fetchone()
        return None if row is None else _token(row)

    def mark_used(self, token_hash: str) -> bool:
        with closing(_connect(self.path)) as connection, connection:
            cursor = connection.execute(
                "UPDATE oauth_tokens SET used = 1 WHERE token_hash = ? AND used = 0", (token_hash,)
            )
            return cursor.rowcount == 1

    def touch(self, token_hash: str, now: float) -> None:
        with closing(_connect(self.path)) as connection, connection:
            connection.execute(
                "UPDATE oauth_tokens SET last_used_at = ? WHERE token_hash = ?"
                " AND (last_used_at IS NULL OR last_used_at < ?)",
                (now, token_hash, now - 60),
            )

    def revoke_family(self, family: str) -> None:
        with closing(_connect(self.path)) as connection, connection:
            connection.execute("DELETE FROM oauth_tokens WHERE family = ?", (family,))

    def revoke_client(self, user_id: str, client_id: str) -> int:
        with closing(_connect(self.path)) as connection, connection:
            cursor = connection.execute(
                "DELETE FROM oauth_tokens WHERE user_id = ? AND client_id = ?", (user_id, client_id)
            )
            return cursor.rowcount

    def grants(self, user_id: str, now: float) -> list[Grant]:
        """Застосунки з дійсним токеном оновлення: те, що гравець бачить як «підключене»."""
        with closing(_connect(self.path)) as connection:
            rows = connection.execute(
                "SELECT t.client_id, COALESCE(json_extract(c.info, '$.client_name'), t.client_id),"
                " MAX(t.scopes), MIN(t.created_at), MAX(t.last_used_at)"
                " FROM oauth_tokens t LEFT JOIN oauth_clients c ON c.client_id = t.client_id"
                " WHERE t.user_id = ? AND t.client_id IN ("
                "   SELECT client_id FROM oauth_tokens"
                "   WHERE user_id = ? AND kind = 'refresh' AND used = 0 AND expires_at > ?)"
                " GROUP BY t.client_id ORDER BY MIN(t.created_at)",
                (user_id, user_id, now),
            ).fetchall()
        return [
            Grant(
                client_id=row[0],
                client_name=row[1],
                scopes=_scopes(row[2] or ""),
                connected_at=float(row[3]),
                last_used_at=None if row[4] is None else float(row[4]),
            )
            for row in rows
        ]

    def purge(self, now: float) -> None:
        with closing(_connect(self.path)) as connection, connection:
            connection.execute("DELETE FROM oauth_requests WHERE expires_at <= ?", (now,))
            connection.execute("DELETE FROM oauth_codes WHERE expires_at <= ?", (now,))
            # Використані токени оновлення лишаються до кінця строку: за ними видно повторне використання.
            connection.execute("DELETE FROM oauth_tokens WHERE expires_at <= ?", (now,))
