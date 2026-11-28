"""Перенесення SQLite ↔ PostgreSQL: копія збігається з джерелом, а розбіжність помітна."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import psycopg
import pytest
from dndsheet.characters.application.golden import build_golden_cases
from dndsheet.characters.domain.wizard import Draft
from dndsheet.characters.infrastructure.sqlite_store import (
    SqliteCharacterRepository,
    SqliteDraftRepository,
    SqliteShareRepository,
    SqliteStore,
)
from dndsheet.db import transfer
from dndsheet.db.__main__ import main
from dndsheet.identity.domain.oauth import IssuedCode, PendingAuthorization, StoredToken
from dndsheet.identity.domain.user import TelegramProfile
from dndsheet.identity.infrastructure.sqlite_identity import SqliteIdentityStore
from dndsheet.identity.infrastructure.sqlite_oauth import SqliteOAuthStore
from rules_fixture import FixtureRules


def _sample(path: Path) -> Path:
    """Файл SQLite, як його лишає застосунок: усі таблиці, власники, OAuth."""
    rules = FixtureRules()
    store = SqliteStore(path)
    characters = SqliteCharacterRepository(store, rules)
    for case in build_golden_cases(rules):
        characters.save(case.character)
    identity = SqliteIdentityStore(path)
    user, _ = identity.upsert_telegram(TelegramProfile(9_007_199_254, "Ігор", "", "ih", "https://t.me/p.jpg"))
    store.claim_unowned(user.id)
    identity.create(user.id, "session-hash", 1_900_000_000.25)
    draft = Draft(id="drf_1", rules=rules)
    draft.apply_species(name="Чернетка «з лапками»", species_key="human")
    drafts = SqliteDraftRepository(store, rules)
    drafts.save(draft)
    drafts.set_owner("drf_1", user.id)
    SqliteShareRepository(store).replace(build_golden_cases(rules)[0].character.id, "share-token")
    oauth = SqliteOAuthStore(path)
    oauth.save_client("c1", '{"client_name": "Claude", "redirect_uris": ["https://x/cb"]}', "cimd", 1.5)
    oauth.save_request(
        PendingAuthorization("r1", "c1", "https://x/cb", True, ("characters",), "ch", "st", "res", 1_900_000_000.0)
    )
    oauth.save_code("code", IssuedCode("c1", user.id, "https://x/cb", False, ("characters",), "ch", "res", 2e9))
    oauth.save_token("tok", StoredToken("refresh", "fam", user.id, "c1", ("characters",), "res", 2e9, True), 3.0)
    oauth.touch("tok", 100.0)
    return path


def _counts(reports: list[transfer.TableReport]) -> dict[str, int]:
    return {report.name: report.rows for report in reports}


def test_copy_verifies_and_roundtrips_back_to_sqlite(tmp_dir: Path, migrated_url: str) -> None:
    source = _sample(tmp_dir / "source.sqlite3")
    copied = transfer.copy_to_postgres(source, migrated_url)
    counts = _counts(copied)
    assert counts["characters"] == len(build_golden_cases(FixtureRules()))
    assert (counts["users"], counts["sessions"], counts["drafts"], counts["shares"]) == (1, 1, 1, 1)
    assert (counts["oauth_clients"], counts["oauth_requests"], counts["oauth_codes"], counts["oauth_tokens"]) == (
        1,
        1,
        1,
        1,
    )
    assert transfer.verify(source, migrated_url) == copied

    # Відкат: Postgres → новий файл SQLite з тими самими даними, який застосунок відкриє як свій.
    back = tmp_dir / "back.sqlite3"
    assert transfer.copy_to_sqlite(migrated_url, back) == copied
    assert transfer.read_sqlite(back) == transfer.read_sqlite(source)
    with closing(sqlite3.connect(back)) as connection:
        meta = connection.execute("SELECT value FROM storage_meta WHERE key = 'json_imported'").fetchone()
    assert meta == ("0",)
    with pytest.raises(transfer.TransferError, match="уже існує"):
        transfer.copy_to_sqlite(migrated_url, back)


def test_copy_refuses_a_database_with_data_unless_replacing(tmp_dir: Path, migrated_url: str) -> None:
    source = _sample(tmp_dir / "source.sqlite3")
    transfer.copy_to_postgres(source, migrated_url)
    with pytest.raises(transfer.TransferError, match="--replace"):
        transfer.copy_to_postgres(source, migrated_url)
    assert transfer.copy_to_postgres(source, migrated_url, replace=True) == transfer.verify(source, migrated_url)


def test_mismatch_is_reported(tmp_dir: Path, migrated_url: str) -> None:
    source = _sample(tmp_dir / "source.sqlite3")
    transfer.copy_to_postgres(source, migrated_url)
    with psycopg.connect(migrated_url) as connection:
        connection.execute("UPDATE characters SET record = jsonb_set(record, '{name}', '\"Підмінений\"')")
    with pytest.raises(transfer.TransferError, match="characters"):
        transfer.verify(source, migrated_url)


def test_orphan_rows_need_an_explicit_decision(tmp_dir: Path, migrated_url: str) -> None:
    source = _sample(tmp_dir / "source.sqlite3")
    with closing(sqlite3.connect(source)) as connection, connection:  # SQLite не перевіряє зовнішні ключі
        connection.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES ('ghost', 'nobody', 1.0)")
    with pytest.raises(transfer.TransferError, match="sessions: 1"):
        transfer.copy_to_postgres(source, migrated_url)
    reports = transfer.copy_to_postgres(source, migrated_url, drop_orphans=True)
    sessions = next(report for report in reports if report.name == "sessions")
    assert (sessions.rows, sessions.skipped) == (1, 1)
    lines: list[str] = []
    transfer.format_report(reports, lines.append)
    assert any("пропущено" in line for line in lines)
    transfer.verify(source, migrated_url)  # сироти не рахуються і при перевірці


def test_empty_sqlite_without_oauth_tables(tmp_dir: Path, migrated_url: str) -> None:
    source = tmp_dir / "empty.sqlite3"
    SqliteStore(source)  # лише персонажі — так виглядає база з вимкненим входом
    assert set(_counts(transfer.copy_to_postgres(source, migrated_url)).values()) == {0}


def test_missing_source_file(tmp_dir: Path, migrated_url: str) -> None:
    with pytest.raises(transfer.TransferError, match="немає файлу"):
        transfer.copy_to_postgres(tmp_dir / "nope.sqlite3", migrated_url)


def test_live_database_with_a_wal_is_refused(tmp_dir: Path, migrated_url: str) -> None:
    source = _sample(tmp_dir / "source.sqlite3")
    (tmp_dir / "source.sqlite3-wal").write_bytes(b"frames")
    with pytest.raises(transfer.TransferError, match="backup"):
        transfer.copy_to_postgres(source, migrated_url)


def test_cli(tmp_dir: Path, pg_url: str, capsys: pytest.CaptureFixture[str]) -> None:
    source = _sample(tmp_dir / "source.sqlite3")
    assert main(["--url", pg_url, "status"]) == 1  # бракує міграцій
    assert main(["--url", pg_url, "migrate"]) == 0
    assert main(["--url", pg_url, "migrate"]) == 0
    assert main(["--url", pg_url, "status"]) == 0
    assert main(["--url", pg_url, "copy-from-sqlite", str(source)]) == 0
    assert main(["--url", pg_url, "verify", str(source)]) == 0
    assert main(["--url", pg_url, "copy-from-sqlite", str(source)]) == 1  # уже є дані
    assert main(["--url", pg_url, "copy-from-sqlite", str(source), "--replace"]) == 0
    assert main(["--url", pg_url, "copy-to-sqlite", str(tmp_dir / "back.sqlite3")]) == 0
    output = capsys.readouterr()
    assert "скопійовано й перевірено" in output.out
    assert "--replace" in output.err


def test_cli_needs_a_url(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("DNDSHEET_DATABASE_URL", raising=False)
    assert main(["status"]) == 2
    assert "DNDSHEET_DATABASE_URL" in capsys.readouterr().err
