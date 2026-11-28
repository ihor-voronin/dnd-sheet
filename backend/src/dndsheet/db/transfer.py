"""Перенесення даних SQLite → PostgreSQL (і назад, для відкату) з перевіркою.

Таблиці в обох базах однакові за складом стовпців (міграція `0001_initial` повторює схему
SQLite), різняться лише типи: JSON-текст ↔ `jsonb`, 0/1 ↔ `boolean`, ISO-рядок ↔ `timestamptz`.
Кожен рядок зводиться до канонічного вигляду (JSON із відсортованими ключами, час у UTC з
точністю до мілісекунд — як пише SQLite), і для кожної таблиці рахуються кількість рядків і
SHA-256 відсортованих канонічних рядків. Копія вдалася, лише якщо обидва числа збігаються.

Копіювання в Postgres — одна транзакція: запис, перевірка прочитаного назад і лише тоді
commit. Не збіглося — rollback, у базі нічого не змінилося. Джерело відкривається лише для
читання. Запускати під роллю власника схеми (потрібні INSERT і TRUNCATE), як і міграції.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from dndsheet.characters.infrastructure.sqlite_store import SqliteStore
from dndsheet.identity.infrastructure.sqlite_identity import SqliteIdentityStore
from dndsheet.identity.infrastructure.sqlite_oauth import SqliteOAuthStore

# Види стовпців: як значення виглядає в кожній базі.
TEXT, INT, FLOAT, BOOL, JSON, TIME = "text", "int", "float", "bool", "json", "time"


@dataclass(frozen=True, slots=True)
class Table:
    name: str
    key: tuple[str, ...]
    columns: tuple[tuple[str, str], ...]
    #: Стовпець → батьківська таблиця (`users`): рядки без батька в SQLite можливі,
    #: бо там зовнішні ключі не перевіряються, а Postgres їх не прийме.
    parents: dict[str, str] = field(default_factory=dict)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.columns)


#: У порядку зовнішніх ключів: батьки раніше за дітей.
TABLES: tuple[Table, ...] = (
    Table(
        "users",
        ("id",),
        (
            ("id", TEXT),
            ("telegram_id", INT),
            ("first_name", TEXT),
            ("last_name", TEXT),
            ("username", TEXT),
            ("photo_url", TEXT),
            ("created_at", TIME),
            ("last_login_at", TIME),
        ),
    ),
    Table(
        "sessions",
        ("token_hash",),
        (("token_hash", TEXT), ("user_id", TEXT), ("expires_at", FLOAT)),
        {"user_id": "users"},
    ),
    Table(
        "characters",
        ("id",),
        (("id", TEXT), ("owner_id", TEXT), ("version", INT), ("record", JSON), ("updated_at", TIME)),
    ),
    Table("drafts", ("id",), (("id", TEXT), ("owner_id", TEXT), ("record", JSON), ("updated_at", TIME))),
    Table("shares", ("token",), (("token", TEXT), ("character_id", TEXT), ("created_at", TIME))),
    Table("oauth_clients", ("client_id",), (("client_id", TEXT), ("info", TEXT), ("kind", TEXT), ("saved_at", FLOAT))),
    Table(
        "oauth_requests",
        ("id",),
        (
            ("id", TEXT),
            ("client_id", TEXT),
            ("redirect_uri", TEXT),
            ("redirect_uri_explicit", BOOL),
            ("scopes", TEXT),
            ("code_challenge", TEXT),
            ("state", TEXT),
            ("resource", TEXT),
            ("expires_at", FLOAT),
        ),
    ),
    Table(
        "oauth_codes",
        ("code_hash",),
        (
            ("code_hash", TEXT),
            ("client_id", TEXT),
            ("user_id", TEXT),
            ("redirect_uri", TEXT),
            ("redirect_uri_explicit", BOOL),
            ("scopes", TEXT),
            ("code_challenge", TEXT),
            ("resource", TEXT),
            ("expires_at", FLOAT),
        ),
        {"user_id": "users"},
    ),
    Table(
        "oauth_tokens",
        ("token_hash",),
        (
            ("token_hash", TEXT),
            ("kind", TEXT),
            ("family", TEXT),
            ("user_id", TEXT),
            ("client_id", TEXT),
            ("scopes", TEXT),
            ("resource", TEXT),
            ("expires_at", FLOAT),
            ("created_at", FLOAT),
            ("used", BOOL),
            ("last_used_at", FLOAT),
        ),
        {"user_id": "users"},
    ),
)


class TransferError(RuntimeError):
    """Копіювати не можна або копія не збіглася з джерелом."""


@dataclass(frozen=True, slots=True)
class TableReport:
    name: str
    rows: int
    digest: str
    skipped: int = 0


# --- канонічний вигляд ---------------------------------------------------------


def _time(value: Any) -> datetime | None:
    if value is None:
        return None
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    moment = moment.astimezone(UTC)
    return moment.replace(microsecond=moment.microsecond // 1000 * 1000)


def _from_sqlite(kind: str, value: Any) -> Any:
    if value is None:
        return None
    if kind == JSON:
        return json.loads(value)
    if kind == BOOL:
        return bool(value)
    if kind == TIME:
        return _time(value)
    if kind == INT:
        return int(value)
    if kind == FLOAT:
        return float(value)
    return value


def _from_postgres(kind: str, value: Any) -> Any:
    if value is None:
        return None
    if kind == TIME:
        return _time(value)
    if kind == FLOAT:
        return float(value)
    return value


def _to_postgres(kind: str, value: Any) -> Any:
    return Jsonb(value) if kind == JSON and value is not None else value


def _to_sqlite(kind: str, value: Any) -> Any:
    if value is None:
        return None
    if kind == JSON:
        return json.dumps(value, ensure_ascii=False)
    if kind == BOOL:
        return int(value)
    if kind == TIME:
        return value.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return value


def _canonical(row: Iterable[Any]) -> str:
    def default(value: Any) -> str:
        if isinstance(value, datetime):
            return value.isoformat(timespec="milliseconds")
        raise TypeError(type(value).__name__)  # pragma: no cover — інших типів у таблицях немає

    return json.dumps(list(row), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=default)


def _digest(rows: list[tuple[Any, ...]]) -> str:
    lines = sorted(_canonical(row) for row in rows)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


# --- читання -----------------------------------------------------------------


def _sqlite_readonly(path: Path) -> sqlite3.Connection:
    """Знімок SQLite лише для читання, без замків і без файлів поруч (каталог може бути `:ro`).

    `immutable=1` не дивиться в журнал WAL — тому файл із непорожнім `-wal` (живу базу)
    не приймаємо: копіювати треба знімок `sqlite3 … ".backup …"`, у якому все вже в файлі.
    """
    if not path.is_file():
        raise TransferError(f"немає файлу {path}")
    wal = path.with_name(path.name + "-wal")
    if wal.is_file() and wal.stat().st_size > 0:
        raise TransferError(f'{path} має незаписаний журнал WAL — зробіть знімок: sqlite3 БАЗА ".backup КОПІЯ"')
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro&immutable=1", uri=True)


def _sqlite_rows(connection: sqlite3.Connection, table: Table) -> list[tuple[Any, ...]]:
    exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table.name,))
    if exists.fetchone() is None:
        return []  # таблиці OAuth зʼявляються лише з увімкненим входом
    columns = ", ".join(table.names)
    rows = connection.execute(f"SELECT {columns} FROM {table.name}").fetchall()  # noqa: S608 — імена з TABLES
    return [
        tuple(_from_sqlite(kind, value) for (_, kind), value in zip(table.columns, row, strict=True)) for row in rows
    ]


def _postgres_rows(connection: psycopg.Connection, table: Table) -> list[tuple[Any, ...]]:
    columns = ", ".join(table.names)
    rows = connection.execute(f"SELECT {columns} FROM {table.name}").fetchall()  # noqa: S608 — імена з TABLES
    return [
        tuple(_from_postgres(kind, value) for (_, kind), value in zip(table.columns, row, strict=True)) for row in rows
    ]


def read_sqlite(path: Path) -> dict[str, list[tuple[Any, ...]]]:
    """Усі таблиці файлу SQLite в канонічних значеннях Python."""
    connection = _sqlite_readonly(path)
    try:
        return {table.name: _sqlite_rows(connection, table) for table in TABLES}
    finally:
        connection.close()


def _orphans(data: dict[str, list[tuple[Any, ...]]]) -> dict[str, list[tuple[Any, ...]]]:
    """Рядки, що посилаються на відсутнього батька (по таблицях)."""
    keys = {table.name: {row[0] for row in data[table.name]} for table in TABLES}
    found: dict[str, list[tuple[Any, ...]]] = {}
    for table in TABLES:
        for column, parent in table.parents.items():
            index = table.names.index(column)
            bad = [row for row in data[table.name] if row[index] not in keys[parent]]
            if bad:
                found[table.name] = bad
    return found


def _report(data: dict[str, list[tuple[Any, ...]]], skipped: dict[str, int] | None = None) -> list[TableReport]:
    skipped = skipped or {}
    return [
        TableReport(table.name, len(data[table.name]), _digest(data[table.name]), skipped.get(table.name, 0))
        for table in TABLES
    ]


def _compare(expected: list[TableReport], actual: list[TableReport]) -> None:
    wrong = [
        f"{want.name}: очікувано {want.rows} рядків ({want.digest[:12]}), є {have.rows} ({have.digest[:12]})"
        for want, have in zip(expected, actual, strict=True)
        if (want.rows, want.digest) != (have.rows, have.digest)
    ]
    if wrong:
        raise TransferError("копія не збіглася з джерелом:\n  " + "\n  ".join(wrong))


# --- SQLite → PostgreSQL ---------------------------------------------------------


def copy_to_postgres(
    source: Path, conninfo: str, *, replace: bool = False, drop_orphans: bool = False
) -> list[TableReport]:
    """Скопіювати файл SQLite у Postgres і перевірити; повертає звіт по таблицях."""
    data = read_sqlite(source)
    skipped: dict[str, int] = {}
    orphans = _orphans(data)
    if orphans and not drop_orphans:
        details = ", ".join(f"{name}: {len(rows)}" for name, rows in orphans.items())
        raise TransferError(f"рядки без користувача ({details}) — перевірте або додайте --drop-orphans")
    for name, rows in orphans.items():
        data[name] = [row for row in data[name] if row not in rows]
        skipped[name] = len(rows)
    expected = _report(data, skipped)

    with psycopg.connect(conninfo) as connection:
        with connection.cursor() as cursor:
            occupied = [
                table.name
                for table in TABLES
                if cursor.execute(f"SELECT EXISTS (SELECT 1 FROM {table.name})").fetchone()[0]  # type: ignore[index]  # noqa: S608
            ]
            if occupied and not replace:
                raise TransferError(f"у базі вже є дані ({', '.join(occupied)}) — додайте --replace, щоб замінити")
            if occupied:
                cursor.execute("TRUNCATE " + ", ".join(table.name for table in TABLES))
            for table in TABLES:
                rows = data[table.name]
                if not rows:
                    continue
                placeholders = ", ".join(["%s"] * len(table.columns))
                cursor.executemany(
                    f"INSERT INTO {table.name} ({', '.join(table.names)}) VALUES ({placeholders})",  # noqa: S608
                    [
                        tuple(_to_postgres(kind, value) for (_, kind), value in zip(table.columns, row, strict=True))
                        for row in rows
                    ],
                )
        # Перевірка в тій самій транзакції: не збіглося — виняток, і `with` відкотить усе.
        actual = _report({table.name: _postgres_rows(connection, table) for table in TABLES}, skipped)
        _compare(expected, actual)
    return expected


def verify(source: Path, conninfo: str) -> list[TableReport]:
    """Порівняти файл SQLite з базою Postgres, нічого не змінюючи."""
    data = read_sqlite(source)
    for name, rows in _orphans(data).items():
        data[name] = [row for row in data[name] if row not in rows]
    expected = _report(data)
    with psycopg.connect(conninfo) as connection:
        actual = _report({table.name: _postgres_rows(connection, table) for table in TABLES})
    _compare(expected, actual)
    return actual


# --- PostgreSQL → SQLite (відкат) --------------------------------------------------


def copy_to_sqlite(conninfo: str, target: Path) -> list[TableReport]:
    """Записати вміст Postgres у НОВИЙ файл SQLite — щоб повернутися на SQLite з новими даними.

    Схему створюють самі адаптери SQLite, тож файл такий, яким його зробив би застосунок.
    `json_imported` позначається одразу: застосунок не переноситиме старі JSON-файли вдруге.
    """
    if target.exists():
        raise TransferError(f"{target} уже існує — оберіть нове імʼя (старий файл — ваша резервна копія)")
    with psycopg.connect(conninfo) as connection:
        data = {table.name: _postgres_rows(connection, table) for table in TABLES}
    SqliteStore(target)
    SqliteIdentityStore(target)
    SqliteOAuthStore(target)
    connection_ = sqlite3.connect(target)
    try:
        with connection_:
            for table in TABLES:
                placeholders = ", ".join(["?"] * len(table.columns))
                connection_.executemany(
                    f"INSERT INTO {table.name} ({', '.join(table.names)}) VALUES ({placeholders})",  # noqa: S608
                    [
                        tuple(_to_sqlite(kind, value) for (_, kind), value in zip(table.columns, row, strict=True))
                        for row in data[table.name]
                    ],
                )
            connection_.execute("INSERT OR REPLACE INTO storage_meta (key, value) VALUES ('json_imported', '0')")
    finally:
        connection_.close()
    expected = _report(data)
    _compare(expected, _report(read_sqlite(target)))
    return expected


def format_report(reports: list[TableReport], out: Callable[[str], None]) -> None:
    for report in reports:
        note = f"  (пропущено без користувача: {report.skipped})" if report.skipped else ""
        out(f"{report.name:<16} {report.rows:>7}  sha256:{report.digest[:16]}{note}")
