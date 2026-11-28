"""Раннер міграцій: порядок, одноразовість, захист застосованих файлів, перевірка на старті."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from dndsheet.db.migrate import MigrationError, load, migrate, pending
from dndsheet.db.postgres import database_url, require_schema


def _write(folder: Path, name: str, sql: str) -> None:
    (folder / name).write_text(sql, encoding="utf-8")


def test_bundled_migrations_are_numbered_in_order() -> None:
    versions = [migration.version for migration in load()]
    assert versions == sorted(versions)
    assert versions[0] == "0001"


def test_bad_file_name_is_refused(tmp_dir: Path) -> None:
    _write(tmp_dir, "1_initial.sql", "SELECT 1;")
    with pytest.raises(MigrationError, match="NNNN_snake_case"):
        load(tmp_dir)


def test_duplicate_number_is_refused(tmp_dir: Path) -> None:
    _write(tmp_dir, "0001_a.sql", "SELECT 1;")
    _write(tmp_dir, "0001_b.sql", "SELECT 1;")
    with pytest.raises(MigrationError, match="повторений"):
        load(tmp_dir)


def test_migrate_applies_once_and_records_versions(pg_url: str) -> None:
    assert [m.version for m in pending(pg_url)] == [m.version for m in load()]
    first = migrate(pg_url)
    assert [m.version for m in first] == [m.version for m in load()]
    assert migrate(pg_url) == []
    assert pending(pg_url) == []
    require_schema(pg_url)  # нічого не бракує — не падає
    with psycopg.connect(pg_url) as connection:
        rows = connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    assert [row[0] for row in rows] == [m.version for m in load()]


def test_require_schema_stops_an_unmigrated_start(pg_url: str) -> None:
    with pytest.raises(RuntimeError, match="0001_initial"):
        require_schema(pg_url)


def test_edited_migration_is_refused(pg_url: str, tmp_dir: Path) -> None:
    _write(tmp_dir, "0001_things.sql", "CREATE TABLE things (id int);")
    migrate(pg_url, tmp_dir)
    _write(tmp_dir, "0001_things.sql", "CREATE TABLE things (id bigint);")
    with pytest.raises(MigrationError, match="змінено"):
        migrate(pg_url, tmp_dir)


def test_failed_migration_leaves_nothing_behind(pg_url: str, tmp_dir: Path) -> None:
    _write(tmp_dir, "0001_ok.sql", "CREATE TABLE ok (id int);")
    _write(tmp_dir, "0002_broken.sql", "CREATE TABLE half (id int);\nSELECT * FROM missing_table;")
    with pytest.raises(psycopg.errors.UndefinedTable):
        migrate(pg_url, tmp_dir)
    with psycopg.connect(pg_url) as connection:
        assert connection.execute("SELECT to_regclass('half')").fetchone() == (None,)
        assert connection.execute("SELECT version FROM schema_migrations").fetchall() == [("0001",)]
    # Виправлена міграція застосовується наступного разу.
    _write(tmp_dir, "0002_broken.sql", "CREATE TABLE half (id int);")
    assert [m.version for m in migrate(pg_url, tmp_dir)] == ["0002"]


def test_no_transaction_migration_runs_outside_a_transaction(pg_url: str, tmp_dir: Path) -> None:
    _write(tmp_dir, "0001_table.sql", "CREATE TABLE t (id int);")
    # CREATE INDEX CONCURRENTLY у транзакції заборонено: проходить лише без неї.
    _write(tmp_dir, "0002_index.sql", "-- migrate: no-transaction\nCREATE INDEX CONCURRENTLY t_id ON t (id);")
    assert [m.version for m in migrate(pg_url, tmp_dir)] == ["0001", "0002"]


def test_newer_migrations_in_the_database_are_not_an_error(pg_url: str, tmp_dir: Path) -> None:
    """Відкат на старіший образ: база вже знає міграцію, якої в коді ще немає."""
    _write(tmp_dir, "0001_a.sql", "CREATE TABLE a (id int);")
    _write(tmp_dir, "0002_b.sql", "CREATE TABLE b (id int);")
    migrate(pg_url, tmp_dir)
    (tmp_dir / "0002_b.sql").unlink()
    assert pending(pg_url, tmp_dir) == []


def test_database_url_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DNDSHEET_DATABASE_URL", raising=False)
    assert database_url() is None
    monkeypatch.setenv("DNDSHEET_DATABASE_URL", "  postgresql://x@y/z  ")
    assert database_url() == "postgresql://x@y/z"
