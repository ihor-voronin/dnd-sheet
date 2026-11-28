"""Застосунок на PostgreSQL: `DNDSHEET_DATABASE_URL` перемикає сховища, решта не змінюється."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from dndsheet.api.app import create_app
from fastapi.testclient import TestClient


@pytest.fixture()
def env(monkeypatch: pytest.MonkeyPatch, tmp_dir: Path) -> Iterator[pytest.MonkeyPatch]:
    # Каталог даних — порожня тимчасова тека: SQLite тут не має зʼявитися.
    monkeypatch.setenv("DNDSHEET_DATA_DIR", str(tmp_dir))
    monkeypatch.setenv("DNDSHEET_AUTH", "off")
    yield monkeypatch


def test_app_refuses_to_start_on_an_unmigrated_database(env: pytest.MonkeyPatch, pg_url: str) -> None:
    env.setenv("DNDSHEET_DATABASE_URL", pg_url)
    with pytest.raises(RuntimeError, match="migrate"):
        create_app()


def test_app_keeps_characters_in_postgres(env: pytest.MonkeyPatch, migrated_url: str, tmp_dir: Path) -> None:
    env.setenv("DNDSHEET_DATABASE_URL", migrated_url)
    app = create_app()
    assert app.state.storage.backend == "postgres"
    with TestClient(app) as client:  # з lifespan: пул закривається на виході
        assert client.get("/healthz").status_code == 200
        created = client.post("/api/v1/characters/wizard")
        assert created.status_code in {200, 201}
        draft_id = created.json()["draft"]["id"]
        assert client.get(f"/api/v1/characters/wizard/{draft_id}").status_code == 200
        assert client.get("/api/v1/characters").status_code == 200
    # Пул уже закрито — перевіряємо саму базу.
    with psycopg.connect(migrated_url) as connection:
        assert connection.execute("SELECT owner_id FROM drafts WHERE id = %s", (draft_id,)).fetchone() == ("local",)
    assert not (tmp_dir / "dndsheet.sqlite3").exists()
