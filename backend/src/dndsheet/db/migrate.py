"""Міграції схеми PostgreSQL: пронумеровані SQL-файли й маленький раннер.

Файли лежать у `dndsheet/db/migrations/` під іменами `NNNN_що_робить.sql` і виконуються
за номером, кожен — в окремій транзакції (DDL у Postgres транзакційний: міграція або
застосована вся, або ніяк). Застосовані записуються в `schema_migrations` разом із
SHA-256 файлу: змінити вже застосовану міграцію не можна — раннер відмовиться працювати,
поки не відновлять файл. Виправлення — нова міграція.

Лише вперед: міграцій «вниз» немає. Відкат — нова міграція або відновлення з копії.
Файл, що не може йти в транзакції (`CREATE INDEX CONCURRENTLY`), починається рядком
`-- migrate: no-transaction` і містить одну інструкцію (кілька інструкцій в одному
запиті Postgres однаково виконує як одну неявну транзакцію).

Двоє раннерів одночасно не заважають одне одному: перший бере advisory-lock, другий чекає.
Замок і таблиця версій — у межах бази, тож у кожного проєкту на спільному сервері своя
історія. Застосунок міграцій не запускає (його роль не має права на DDL): це окремий крок
деплою — `python -m dndsheet.db migrate` під роллю власника схеми. На старті застосунок лише
перевіряє, що всі відомі йому міграції вже в базі (`pending`).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import psycopg

#: Ключ advisory-lock: однаковий для всіх раннерів dnd-sheet, а в інших проєктів — свої бази.
LOCK_KEY = 0x646E_6473_6865_6574 & 0x7FFF_FFFF_FFFF_FFFF  # "dndsheet"
_NAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")
_NO_TRANSACTION = "-- migrate: no-transaction"

_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version text PRIMARY KEY,
    name text NOT NULL,
    checksum text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


class MigrationError(RuntimeError):
    """Міграції в базі не збігаються з файлами або файл названо не за правилом."""


@dataclass(frozen=True, slots=True)
class Migration:
    version: str
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()

    @property
    def transactional(self) -> bool:
        return not self.sql.lstrip().startswith(_NO_TRANSACTION)


def default_directory() -> Path:
    return Path(str(resources.files("dndsheet.db") / "migrations"))


def load(directory: Path | None = None) -> list[Migration]:
    """Міграції з каталогу за номером; номери не повторюються."""
    folder = directory or default_directory()
    migrations: list[Migration] = []
    for file in sorted(folder.glob("*.sql")):
        match = _NAME.match(file.name)
        if not match:
            raise MigrationError(f"{file.name}: імʼя має бути NNNN_snake_case.sql")
        migrations.append(Migration(match.group(1), match.group(2), file.read_text(encoding="utf-8")))
    versions = [migration.version for migration in migrations]
    if len(set(versions)) != len(versions):
        raise MigrationError(f"повторений номер міграції в {folder}")
    return migrations


def _applied(connection: psycopg.Connection) -> dict[str, str]:
    exists = connection.execute("SELECT to_regclass('schema_migrations') IS NOT NULL").fetchone()
    if not exists or not exists[0]:
        return {}
    rows = connection.execute("SELECT version, checksum FROM schema_migrations").fetchall()
    return {row[0]: row[1] for row in rows}


def _verify(migrations: list[Migration], applied: dict[str, str]) -> list[Migration]:
    """Що ще не застосовано; застосовані мусять мати той самий вміст."""
    for migration in migrations:
        stored = applied.get(migration.version)
        if stored is not None and stored != migration.checksum:
            raise MigrationError(
                f"міграцію {migration.version}_{migration.name} змінено після застосування — "
                "поверніть файл і напишіть нову міграцію"
            )
    return [migration for migration in migrations if migration.version not in applied]


def pending(conninfo: str, directory: Path | None = None) -> list[Migration]:
    """Відомі застосунку міграції, яких ще немає в базі (новіші в базі — не помилка)."""
    with psycopg.connect(conninfo, autocommit=True) as connection:
        return _verify(load(directory), _applied(connection))


def migrate(conninfo: str, directory: Path | None = None) -> list[Migration]:
    """Застосувати все, чого бракує; повертає застосовані зараз."""
    migrations = load(directory)
    done: list[Migration] = []
    with psycopg.connect(conninfo, autocommit=True) as connection:
        connection.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
        try:
            connection.execute(_TABLE)
            # Після замка: поки ми чекали, інший раннер міг усе застосувати.
            for migration in _verify(migrations, _applied(connection)):
                record = (migration.version, migration.name, migration.checksum)
                insert = "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)"
                if migration.transactional:
                    with connection.transaction():
                        connection.execute(migration.sql.encode("utf-8"))
                        connection.execute(insert, record)
                else:
                    connection.execute(migration.sql.encode("utf-8"))
                    connection.execute(insert, record)
                done.append(migration)
        finally:
            connection.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
    return done
