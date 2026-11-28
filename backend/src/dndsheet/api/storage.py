"""Де лежать дані: SQLite (типово) чи PostgreSQL (`DNDSHEET_DATABASE_URL`) — docs/database.md.

Обидва варіанти реалізують ті самі порти, тож застосунок і домен не знають, котрий
обрано. Тут лише композиція: який адаптер створити й з чим.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dndsheet.characters.domain.ports import RulesSource
from dndsheet.characters.infrastructure.json_store import default_data_dir
from dndsheet.characters.infrastructure.postgres_store import (
    PostgresCharacterRepository,
    PostgresDraftRepository,
    PostgresShareRepository,
    PostgresStore,
)
from dndsheet.characters.infrastructure.sqlite_store import (
    SqliteCharacterRepository,
    SqliteDraftRepository,
    SqliteShareRepository,
    SqliteStore,
)
from dndsheet.db.postgres import database_url, open_pool, require_schema
from dndsheet.identity.domain.oauth import OAuthStore
from dndsheet.identity.infrastructure.postgres_identity import PostgresIdentityStore
from dndsheet.identity.infrastructure.postgres_oauth import PostgresOAuthStore
from dndsheet.identity.infrastructure.sqlite_identity import SqliteIdentityStore
from dndsheet.identity.infrastructure.sqlite_oauth import SqliteOAuthStore


@dataclass(slots=True)
class Storage:
    """Сховища застосунку. `oauth` — фабрика: таблиці OAuth потрібні лише з увімкненим входом."""

    backend: str
    characters: Any
    drafts: Any
    shares: Any
    identity: Any
    oauth: Callable[[], OAuthStore]
    claim_unowned: Callable[[str], int]
    close: Callable[[], None]


def build_storage(rules: RulesSource) -> Storage:
    url = database_url()
    return _postgres(url, rules) if url else _sqlite(rules)


def _sqlite(rules: RulesSource) -> Storage:
    # Чернетки й персонажі — у базі SQLite `var/dndsheet.sqlite3` з власником;
    # старі файли `var/characters/*.json` переносяться туди один раз і лишаються
    # як резервна копія. Каталог можна перевизначити `DNDSHEET_DATA_DIR`.
    data_dir = default_data_dir()
    database = data_dir / "dndsheet.sqlite3"
    store = SqliteStore(database)
    store.import_json_once(data_dir / "characters", data_dir / "drafts")
    return Storage(
        backend="sqlite",
        characters=SqliteCharacterRepository(store, rules),
        drafts=SqliteDraftRepository(store, rules),
        shares=SqliteShareRepository(store),
        identity=SqliteIdentityStore(database),
        oauth=lambda: SqliteOAuthStore(database),
        claim_unowned=store.claim_unowned,
        close=lambda: None,
    )


def _postgres(url: str, rules: RulesSource) -> Storage:
    # Схему готує деплой (`python -m dndsheet.db migrate`); застосунок лише перевіряє її.
    require_schema(url)
    pool = open_pool(url)
    store = PostgresStore(pool)
    oauth = PostgresOAuthStore(pool)
    return Storage(
        backend="postgres",
        characters=PostgresCharacterRepository(store, rules),
        drafts=PostgresDraftRepository(store, rules),
        shares=PostgresShareRepository(store),
        identity=PostgresIdentityStore(pool),
        oauth=lambda: oauth,
        claim_unowned=store.claim_unowned,
        close=pool.close,
    )
