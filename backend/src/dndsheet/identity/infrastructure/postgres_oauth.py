"""OAuth для застосунків у PostgreSQL — `OAuthStore`, як у `sqlite_oauth`.

Секрети (коди, токени) лежать лише як SHA-256. «Забрати» запит чи код — один
`DELETE … RETURNING`: два одночасні обміни того самого коду не отримають його обидва.
"""

from __future__ import annotations

from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from dndsheet.identity.domain.oauth import Grant, IssuedCode, PendingAuthorization, StoredToken

_REQUEST_COLUMNS = (
    "id, client_id, redirect_uri, redirect_uri_explicit, scopes, code_challenge, state, resource, expires_at"
)
_CODE_COLUMNS = "client_id, user_id, redirect_uri, redirect_uri_explicit, scopes, code_challenge, resource, expires_at"
_TOKEN_COLUMNS = "kind, family, user_id, client_id, scopes, resource, expires_at, used"


def _scopes(raw: str) -> tuple[str, ...]:
    return tuple(part for part in raw.split(" ") if part)


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
class PostgresOAuthStore:
    """Реалізує `OAuthStore` (таблиці створює міграція)."""

    pool: ConnectionPool

    # --- застосунки ------------------------------------------------------------

    def save_client(self, client_id: str, info: str, kind: str, now: float) -> None:
        with self.pool.connection() as connection:
            connection.execute(
                "INSERT INTO oauth_clients (client_id, info, kind, saved_at) VALUES (%s, %s, %s, %s)"
                " ON CONFLICT (client_id) DO UPDATE SET info = excluded.info, kind = excluded.kind,"
                " saved_at = excluded.saved_at",
                (client_id, info, kind, now),
            )

    def client(self, client_id: str) -> tuple[str, str, float] | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                "SELECT info, kind, saved_at FROM oauth_clients WHERE client_id = %s", (client_id,)
            ).fetchone()
        return None if row is None else (row[0], row[1], float(row[2]))

    def purge_clients(self, kind: str, older_than: float) -> int:
        with self.pool.connection() as connection:
            cursor = connection.execute(
                "DELETE FROM oauth_clients c WHERE kind = %s AND saved_at < %s"
                " AND NOT EXISTS (SELECT 1 FROM oauth_tokens t WHERE t.client_id = c.client_id)",
                (kind, older_than),
            )
            return cursor.rowcount

    # --- запити на дозвіл ----------------------------------------------------

    def save_request(self, pending: PendingAuthorization) -> None:
        with self.pool.connection() as connection:
            connection.execute(
                f"INSERT INTO oauth_requests ({_REQUEST_COLUMNS}) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    pending.id,
                    pending.client_id,
                    pending.redirect_uri,
                    pending.redirect_uri_explicit,
                    " ".join(pending.scopes),
                    pending.code_challenge,
                    pending.state,
                    pending.resource,
                    pending.expires_at,
                ),
            )

    def request(self, request_id: str, now: float) -> PendingAuthorization | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                f"SELECT {_REQUEST_COLUMNS} FROM oauth_requests WHERE id = %s AND expires_at > %s",
                (request_id, now),
            ).fetchone()
        return None if row is None else _pending(row)

    def take_request(self, request_id: str, now: float) -> PendingAuthorization | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                f"DELETE FROM oauth_requests WHERE id = %s RETURNING {_REQUEST_COLUMNS}", (request_id,)
            ).fetchone()
        # Прострочений запит теж прибираємо, але не віддаємо.
        return None if row is None or float(row[8]) <= now else _pending(row)

    # --- коди ----------------------------------------------------------------

    def save_code(self, code_hash: str, code: IssuedCode) -> None:
        with self.pool.connection() as connection:
            connection.execute(
                f"INSERT INTO oauth_codes (code_hash, {_CODE_COLUMNS}) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    code_hash,
                    code.client_id,
                    code.user_id,
                    code.redirect_uri,
                    code.redirect_uri_explicit,
                    " ".join(code.scopes),
                    code.code_challenge,
                    code.resource,
                    code.expires_at,
                ),
            )

    def code(self, code_hash: str) -> IssuedCode | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                f"SELECT {_CODE_COLUMNS} FROM oauth_codes WHERE code_hash = %s", (code_hash,)
            ).fetchone()
        return None if row is None else _code(row)

    def take_code(self, code_hash: str) -> IssuedCode | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                f"DELETE FROM oauth_codes WHERE code_hash = %s RETURNING {_CODE_COLUMNS}", (code_hash,)
            ).fetchone()
        return None if row is None else _code(row)

    # --- токени --------------------------------------------------------------

    def save_token(self, token_hash: str, token: StoredToken, now: float) -> None:
        with self.pool.connection() as connection:
            connection.execute(
                f"INSERT INTO oauth_tokens (token_hash, {_TOKEN_COLUMNS}, created_at)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    token_hash,
                    token.kind,
                    token.family,
                    token.user_id,
                    token.client_id,
                    " ".join(token.scopes),
                    token.resource,
                    token.expires_at,
                    token.used,
                    now,
                ),
            )

    def token(self, token_hash: str) -> StoredToken | None:
        with self.pool.connection() as connection:
            row = connection.execute(
                f"SELECT {_TOKEN_COLUMNS} FROM oauth_tokens WHERE token_hash = %s", (token_hash,)
            ).fetchone()
        return None if row is None else _token(row)

    def mark_used(self, token_hash: str) -> bool:
        with self.pool.connection() as connection:
            cursor = connection.execute(
                "UPDATE oauth_tokens SET used = true WHERE token_hash = %s AND NOT used", (token_hash,)
            )
            return cursor.rowcount == 1

    def touch(self, token_hash: str, now: float) -> None:
        with self.pool.connection() as connection:
            connection.execute(
                "UPDATE oauth_tokens SET last_used_at = %s WHERE token_hash = %s"
                " AND (last_used_at IS NULL OR last_used_at < %s)",
                (now, token_hash, now - 60),
            )

    def revoke_family(self, family: str) -> None:
        with self.pool.connection() as connection:
            connection.execute("DELETE FROM oauth_tokens WHERE family = %s", (family,))

    def revoke_client(self, user_id: str, client_id: str) -> int:
        with self.pool.connection() as connection:
            cursor = connection.execute(
                "DELETE FROM oauth_tokens WHERE user_id = %s AND client_id = %s", (user_id, client_id)
            )
            return cursor.rowcount

    def grants(self, user_id: str, now: float) -> list[Grant]:
        """Застосунки з дійсним токеном оновлення: те, що гравець бачить як «підключене»."""
        with self.pool.connection() as connection:
            rows = connection.execute(
                "SELECT t.client_id, COALESCE(c.info::jsonb ->> 'client_name', t.client_id),"
                " MAX(t.scopes), MIN(t.created_at), MAX(t.last_used_at)"
                " FROM oauth_tokens t LEFT JOIN oauth_clients c ON c.client_id = t.client_id"
                " WHERE t.user_id = %s AND t.client_id IN ("
                "   SELECT client_id FROM oauth_tokens"
                "   WHERE user_id = %s AND kind = 'refresh' AND NOT used AND expires_at > %s)"
                " GROUP BY t.client_id, c.info ORDER BY MIN(t.created_at)",
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
        with self.pool.connection() as connection:
            connection.execute("DELETE FROM oauth_requests WHERE expires_at <= %s", (now,))
            connection.execute("DELETE FROM oauth_codes WHERE expires_at <= %s", (now,))
            # Використані токени оновлення лишаються до кінця строку: за ними видно повторне використання.
            connection.execute("DELETE FROM oauth_tokens WHERE expires_at <= %s", (now,))
