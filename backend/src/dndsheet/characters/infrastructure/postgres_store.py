"""Персонажі, чернетки й посилання в PostgreSQL — той самий інтерфейс, що й у SQLite.

Документ агрегата — `jsonb` (`character_json`), тому нове поле в моделі не потребує
міграції. Решта поведінки збігається з `sqlite_store` рядок у рядок:

- версія листа — умова запису (`UPDATE … WHERE version < нова`): два запити, що прочитали ту
  саму версію, не перезапишуть один одного. У Postgres другий `UPDATE` чекає на замок рядка,
  а тоді перевіряє умову вже на новій версії — і отримує конфлікт;
- дія, що нічого не змінила, версію не підвищує й конфліктом не є, якщо документ той самий
  (порівнюємо `jsonb`, а не текст: порядок ключів не важить);
- зʼєднання береться з пулу на одну операцію; вихід із блоку — commit, виняток — rollback.
"""

from __future__ import annotations

from dataclasses import dataclass

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.ports import RulesSource
from dndsheet.characters.domain.wizard import Draft
from dndsheet.characters.infrastructure.character_json import (
    character_from_record,
    character_to_record,
    draft_from_record,
    draft_to_record,
)
from dndsheet.shared.errors import ConflictError, NotFoundError


def _conflict(version: object) -> ConflictError:
    return ConflictError(f"лист змінено на іншому пристрої (версія {version}) — оновіть сторінку")


@dataclass(slots=True)
class PostgresStore:
    """Спільний пул для персонажів, чернеток і посилань (таблиці створює міграція)."""

    pool: ConnectionPool

    def claim_unowned(self, owner_id: str) -> int:
        """Віддати персонажів без власника цьому користувачу (як у SQLite)."""
        with self.pool.connection() as connection:
            cursor = connection.execute("UPDATE characters SET owner_id = %s WHERE owner_id IS NULL", (owner_id,))
            return cursor.rowcount


@dataclass(slots=True)
class PostgresCharacterRepository:
    """Готові персонажі з власником; інтерфейс — як у `SqliteCharacterRepository`."""

    store: PostgresStore
    rules: RulesSource

    def save(self, character: Character) -> None:
        record = Jsonb(character_to_record(character))
        with self.store.pool.connection() as connection:
            cursor = connection.execute(
                "UPDATE characters SET record = %s, version = %s, updated_at = now() WHERE id = %s AND version < %s",
                (record, character.version, character.id, character.version),
            )
            if cursor.rowcount:
                return
            exists = connection.execute(
                "SELECT version, record = %s FROM characters WHERE id = %s", (record, character.id)
            ).fetchone()
            if exists is not None:
                if int(exists[0]) == character.version and exists[1]:
                    return
                raise _conflict(exists[0])
            try:
                with connection.transaction():
                    connection.execute(
                        "INSERT INTO characters (id, owner_id, version, record) VALUES (%s, NULL, %s, %s)",
                        (character.id, character.version, record),
                    )
            except UniqueViolation:
                # Той самий новий персонаж щойно записаний з іншого запиту.
                raise _conflict(character.version) from None

    def get(self, character_id: str) -> Character | None:
        with self.store.pool.connection() as connection:
            row = connection.execute("SELECT record FROM characters WHERE id = %s", (character_id,)).fetchone()
        return None if row is None else character_from_record(row[0], self.rules)

    def ids(self) -> tuple[str, ...]:
        with self.store.pool.connection() as connection:
            rows = connection.execute('SELECT id FROM characters ORDER BY id COLLATE "C"').fetchall()
        return tuple(row[0] for row in rows)

    def ids_of(self, owner_id: str) -> tuple[str, ...]:
        """Персонажі одного користувача — новіші зміни першими."""
        with self.store.pool.connection() as connection:
            rows = connection.execute(
                "SELECT id FROM characters WHERE owner_id = %s ORDER BY updated_at DESC, id", (owner_id,)
            ).fetchall()
        return tuple(row[0] for row in rows)

    def owner(self, character_id: str) -> str | None:
        with self.store.pool.connection() as connection:
            row = connection.execute("SELECT owner_id FROM characters WHERE id = %s", (character_id,)).fetchone()
        return None if row is None else row[0]

    def version(self, character_id: str) -> int | None:
        """Лише номер версії — для дешевого опитування «чи змінився лист»."""
        with self.store.pool.connection() as connection:
            row = connection.execute("SELECT version FROM characters WHERE id = %s", (character_id,)).fetchone()
        return None if row is None else int(row[0])

    def set_owner(self, character_id: str, owner_id: str) -> None:
        with self.store.pool.connection() as connection:
            connection.execute("UPDATE characters SET owner_id = %s WHERE id = %s", (owner_id, character_id))

    def delete(self, character_id: str) -> None:
        with self.store.pool.connection() as connection:
            cursor = connection.execute("DELETE FROM characters WHERE id = %s", (character_id,))
            if not cursor.rowcount:
                raise NotFoundError(f"немає персонажа {character_id!r}")


@dataclass(slots=True)
class PostgresDraftRepository:
    """Чернетки візарда з власником."""

    store: PostgresStore
    rules: RulesSource

    def save(self, draft: Draft) -> None:
        with self.store.pool.connection() as connection:
            connection.execute(
                "INSERT INTO drafts (id, owner_id, record) VALUES (%s, NULL, %s)"
                " ON CONFLICT (id) DO UPDATE SET record = excluded.record, updated_at = now()",
                (draft.id, Jsonb(draft_to_record(draft))),
            )

    def get(self, draft_id: str) -> Draft | None:
        with self.store.pool.connection() as connection:
            row = connection.execute("SELECT record FROM drafts WHERE id = %s", (draft_id,)).fetchone()
        return None if row is None else draft_from_record(row[0], self.rules)

    def delete(self, draft_id: str) -> None:
        with self.store.pool.connection() as connection:
            cursor = connection.execute("DELETE FROM drafts WHERE id = %s", (draft_id,))
            if not cursor.rowcount:
                raise NotFoundError(f"немає чернетки {draft_id!r}")

    def owner(self, draft_id: str) -> str | None:
        with self.store.pool.connection() as connection:
            row = connection.execute("SELECT owner_id FROM drafts WHERE id = %s", (draft_id,)).fetchone()
        return None if row is None else row[0]

    def set_owner(self, draft_id: str, owner_id: str) -> None:
        with self.store.pool.connection() as connection:
            connection.execute("UPDATE drafts SET owner_id = %s WHERE id = %s", (owner_id, draft_id))

    def latest_of(self, owner_id: str) -> str | None:
        """Остання незавершена чернетка користувача."""
        with self.store.pool.connection() as connection:
            row = connection.execute(
                "SELECT id FROM drafts WHERE owner_id = %s ORDER BY updated_at DESC, id LIMIT 1", (owner_id,)
            ).fetchone()
        return None if row is None else row[0]


@dataclass(slots=True)
class PostgresShareRepository:
    """Посилання «лише читати»: одне на персонажа, нове замінює старе."""

    store: PostgresStore

    def token_of(self, character_id: str) -> str | None:
        with self.store.pool.connection() as connection:
            row = connection.execute("SELECT token FROM shares WHERE character_id = %s", (character_id,)).fetchone()
        return None if row is None else row[0]

    def character_of(self, token: str) -> str | None:
        with self.store.pool.connection() as connection:
            row = connection.execute("SELECT character_id FROM shares WHERE token = %s", (token,)).fetchone()
        return None if row is None else row[0]

    def replace(self, character_id: str, token: str) -> None:
        with self.store.pool.connection() as connection:
            connection.execute("DELETE FROM shares WHERE character_id = %s", (character_id,))
            connection.execute("INSERT INTO shares (token, character_id) VALUES (%s, %s)", (token, character_id))

    def revoke(self, character_id: str) -> None:
        with self.store.pool.connection() as connection:
            connection.execute("DELETE FROM shares WHERE character_id = %s", (character_id,))
