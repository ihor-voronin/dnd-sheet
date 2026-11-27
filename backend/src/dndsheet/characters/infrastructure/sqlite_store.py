"""Персонажі й чернетки в SQLite: доступні з будь-якого пристрою, з власником.

Агрегат лежить у таблиці тим самим JSON-документом, що й у файловому сховищі
(`character_json`): схема бази не дублює модель персонажа, і перехід із файлів —
це просто копіювання документів.

Власник (`owner_id`) — стовпець поруч із документом, а не поле агрегата: домен
не знає про користувачів, доступ перевіряє шар API.

Версія листа — ще й умова запису: `UPDATE … WHERE version < нова`. Два запити,
що прочитали ту саму версію, не перезапишуть один одного — другий отримає
конфлікт, навіть якщо перевірка `expected_version` уже пройшла в обох.

Зʼєднання — на кожну операцію: FastAPI виконує синхронні обробники в пулі
потоків, а зʼєднання SQLite між потоками не ділиться. WAL дає читати під час
запису.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

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

_SCHEMA = """
CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    owner_id TEXT,
    version INTEGER NOT NULL,
    record TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS characters_owner ON characters(owner_id);
CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    owner_id TEXT,
    record TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS shares (
    token TEXT PRIMARY KEY,
    character_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS storage_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    """Зʼєднання з базою; каталог створюється, якщо його ще немає."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=10000")
    return connection


def _dump(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False)


@dataclass(slots=True)
class SqliteStore:
    """Спільна база персонажів і чернеток (один файл)."""

    path: Path

    def __post_init__(self) -> None:
        with closing(connect(self.path)) as connection, connection:
            connection.executescript(_SCHEMA)

    def connection(self) -> sqlite3.Connection:
        return connect(self.path)

    def import_json_once(self, characters_dir: Path, drafts_dir: Path) -> int:
        """Перенести персонажів і чернетки з файлів `var/` у базу (один раз).

        Файли лишаються на диску як резервна копія. Власника в них немає —
        його призначає `claim_unowned` першому власнику застосунку.
        """
        moved = 0
        with closing(self.connection()) as connection, connection:
            done = connection.execute("SELECT value FROM storage_meta WHERE key = 'json_imported'").fetchone()
            if done:
                return 0
            for table, folder in (("characters", characters_dir), ("drafts", drafts_dir)):
                if not folder.is_dir():
                    continue
                for file in sorted(folder.glob("*.json")):
                    try:
                        record = json.loads(file.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        continue
                    identifier = str(record.get("id") or file.stem)
                    if table == "characters":
                        connection.execute(
                            "INSERT OR IGNORE INTO characters (id, owner_id, version, record) VALUES (?, NULL, ?, ?)",
                            (identifier, int(record.get("version") or 1), _dump(record)),
                        )
                    else:
                        connection.execute(
                            "INSERT OR IGNORE INTO drafts (id, owner_id, record) VALUES (?, NULL, ?)",
                            (identifier, _dump(record)),
                        )
                    moved += 1
            connection.execute("INSERT INTO storage_meta (key, value) VALUES ('json_imported', ?)", (str(moved),))
        return moved

    def claim_unowned(self, owner_id: str) -> int:
        """Віддати персонажів без власника (перенесених із файлів) цьому користувачу."""
        with closing(self.connection()) as connection, connection:
            cursor = connection.execute("UPDATE characters SET owner_id = ? WHERE owner_id IS NULL", (owner_id,))
            return cursor.rowcount


@dataclass(slots=True)
class SqliteCharacterRepository:
    """Готові персонажі. Інтерфейс — той самий `CharacterRepository`, плюс власник."""

    store: SqliteStore
    rules: RulesSource

    def save(self, character: Character) -> None:
        record = _dump(character_to_record(character))
        with closing(self.store.connection()) as connection, connection:
            cursor = connection.execute(
                "UPDATE characters SET record = ?, version = ?,"
                " updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')"
                " WHERE id = ? AND version < ?",
                (record, character.version, character.id, character.version),
            )
            if cursor.rowcount:
                return
            exists = connection.execute(
                "SELECT version, record FROM characters WHERE id = ?", (character.id,)
            ).fetchone()
            if exists is not None:
                # Дія, що нічого не змінила (короткий відпочинок без витрат), версію
                # не підвищує — і це не конфлікт, якщо в базі той самий документ.
                if int(exists[0]) == character.version and exists[1] == record:
                    return
                # Хтось уже записав цю (або новішу) версію з іншого пристрою.
                raise ConflictError(f"лист змінено на іншому пристрої (версія {exists[0]}) — оновіть сторінку")
            connection.execute(
                "INSERT INTO characters (id, owner_id, version, record) VALUES (?, NULL, ?, ?)",
                (character.id, character.version, record),
            )

    def get(self, character_id: str) -> Character | None:
        with closing(self.store.connection()) as connection:
            row = connection.execute("SELECT record FROM characters WHERE id = ?", (character_id,)).fetchone()
        return None if row is None else character_from_record(json.loads(row[0]), self.rules)

    def ids(self) -> tuple[str, ...]:
        with closing(self.store.connection()) as connection:
            rows = connection.execute("SELECT id FROM characters ORDER BY id").fetchall()
        return tuple(row[0] for row in rows)

    def ids_of(self, owner_id: str) -> tuple[str, ...]:
        """Персонажі одного користувача — новіші зміни першими."""
        with closing(self.store.connection()) as connection:
            rows = connection.execute(
                "SELECT id FROM characters WHERE owner_id = ? ORDER BY updated_at DESC",
                (owner_id,),
            ).fetchall()
        return tuple(row[0] for row in rows)

    def owner(self, character_id: str) -> str | None:
        with closing(self.store.connection()) as connection:
            row = connection.execute("SELECT owner_id FROM characters WHERE id = ?", (character_id,)).fetchone()
        return None if row is None else row[0]

    def version(self, character_id: str) -> int | None:
        """Лише номер версії — для дешевого опитування «чи змінився лист»."""
        with closing(self.store.connection()) as connection:
            row = connection.execute("SELECT version FROM characters WHERE id = ?", (character_id,)).fetchone()
        return None if row is None else int(row[0])

    def set_owner(self, character_id: str, owner_id: str) -> None:
        with closing(self.store.connection()) as connection, connection:
            connection.execute("UPDATE characters SET owner_id = ? WHERE id = ?", (owner_id, character_id))

    def delete(self, character_id: str) -> None:
        with closing(self.store.connection()) as connection, connection:
            cursor = connection.execute("DELETE FROM characters WHERE id = ?", (character_id,))
            if not cursor.rowcount:
                raise NotFoundError(f"немає персонажа {character_id!r}")


@dataclass(slots=True)
class SqliteDraftRepository:
    """Чернетки візарда з власником: продовжити можна з іншого пристрою."""

    store: SqliteStore
    rules: RulesSource

    def save(self, draft: Draft) -> None:
        record = _dump(draft_to_record(draft))
        with closing(self.store.connection()) as connection, connection:
            connection.execute(
                "INSERT INTO drafts (id, owner_id, record) VALUES (?, NULL, ?)"
                " ON CONFLICT(id) DO UPDATE SET record = excluded.record,"
                " updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')",
                (draft.id, record),
            )

    def get(self, draft_id: str) -> Draft | None:
        with closing(self.store.connection()) as connection:
            row = connection.execute("SELECT record FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        return None if row is None else draft_from_record(json.loads(row[0]), self.rules)

    def delete(self, draft_id: str) -> None:
        with closing(self.store.connection()) as connection, connection:
            cursor = connection.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
            if not cursor.rowcount:
                raise NotFoundError(f"немає чернетки {draft_id!r}")

    def owner(self, draft_id: str) -> str | None:
        with closing(self.store.connection()) as connection:
            row = connection.execute("SELECT owner_id FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        return None if row is None else row[0]

    def set_owner(self, draft_id: str, owner_id: str) -> None:
        with closing(self.store.connection()) as connection, connection:
            connection.execute("UPDATE drafts SET owner_id = ? WHERE id = ?", (owner_id, draft_id))

    def latest_of(self, owner_id: str) -> str | None:
        """Остання незавершена чернетка користувача — щоб продовжити на іншому пристрої."""
        with closing(self.store.connection()) as connection:
            row = connection.execute(
                "SELECT id FROM drafts WHERE owner_id = ? ORDER BY updated_at DESC LIMIT 1",
                (owner_id,),
            ).fetchone()
        return None if row is None else row[0]


@dataclass(slots=True)
class SqliteShareRepository:
    """Посилання «лише читати» на персонажа: одне на персонажа, власник може відкликати.

    Токен — випадковий рядок у самому посиланні (capability URL): хто має
    посилання, той бачить лист, але змінити нічого не може — публічні
    ендпоінти лише читають. Нове посилання замінює старе, і старе перестає
    працювати.
    """

    store: SqliteStore

    def token_of(self, character_id: str) -> str | None:
        with closing(self.store.connection()) as connection:
            row = connection.execute("SELECT token FROM shares WHERE character_id = ?", (character_id,)).fetchone()
        return None if row is None else row[0]

    def character_of(self, token: str) -> str | None:
        with closing(self.store.connection()) as connection:
            row = connection.execute("SELECT character_id FROM shares WHERE token = ?", (token,)).fetchone()
        return None if row is None else row[0]

    def replace(self, character_id: str, token: str) -> None:
        with closing(self.store.connection()) as connection, connection:
            connection.execute("DELETE FROM shares WHERE character_id = ?", (character_id,))
            connection.execute("INSERT INTO shares (token, character_id) VALUES (?, ?)", (token, character_id))

    def revoke(self, character_id: str) -> None:
        with closing(self.store.connection()) as connection, connection:
            connection.execute("DELETE FROM shares WHERE character_id = ?", (character_id,))
