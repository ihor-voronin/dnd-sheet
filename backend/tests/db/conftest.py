"""Фікстури PostgreSQL: кожен тест — у власній тимчасовій схемі, яка зникає після нього.

Базу дає `DNDSHEET_TEST_DATABASE_URL` (локально — Postgres у Docker, docs/database.md;
у CI — сервіс-контейнер). Без неї тести Postgres пропускаються, але з
`DNDSHEET_REQUIRE_POSTGRES=1` (CI) пропуск — помилка: інакше покриття тихо впало б.
"""

from __future__ import annotations

import os
import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from dndsheet.db.migrate import migrate
from dndsheet.db.postgres import open_pool
from psycopg.conninfo import make_conninfo
from psycopg_pool import ConnectionPool

TMP = Path(__file__).resolve().parent / "_tmp_db"


def _server_url() -> str:
    url = os.environ.get("DNDSHEET_TEST_DATABASE_URL", "").strip()
    if not url:
        if os.environ.get("DNDSHEET_REQUIRE_POSTGRES", "").strip() == "1":
            pytest.fail("DNDSHEET_REQUIRE_POSTGRES=1, але DNDSHEET_TEST_DATABASE_URL не задано")
        pytest.skip("немає DNDSHEET_TEST_DATABASE_URL — тести PostgreSQL пропущено")
    return url


@pytest.fixture()
def pg_url() -> Iterator[str]:
    """Адреса з `search_path` на нову порожню схему."""
    server = _server_url()
    schema = f"t_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(server, autocommit=True) as connection:
        connection.execute(f"CREATE SCHEMA {schema}")
    try:
        yield make_conninfo(server, options=f"-c search_path={schema}")
    finally:
        with psycopg.connect(server, autocommit=True) as connection:
            connection.execute(f"DROP SCHEMA {schema} CASCADE")


@pytest.fixture()
def migrated_url(pg_url: str) -> str:
    migrate(pg_url)
    return pg_url


@pytest.fixture()
def pool(migrated_url: str) -> Iterator[ConnectionPool]:
    connections = open_pool(migrated_url, max_size=3)
    try:
        yield connections
    finally:
        connections.close()


@pytest.fixture()
def tmp_dir(request: pytest.FixtureRequest) -> Iterator[Path]:
    """Тека для файлів SQLite у репозиторії (`_tmp_*`), а не в системному temp."""
    folder = TMP / request.node.name.replace("[", "_").replace("]", "")
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    try:
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)
        if TMP.is_dir() and not any(TMP.iterdir()):
            TMP.rmdir()
