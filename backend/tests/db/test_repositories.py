"""Сховища SQLite і PostgreSQL поводяться однаково: ті самі тести для обох адаптерів.

Домен і API не знають, яку базу обрано (`api/storage.py`), тож контракт сховища —
це поведінка, яку бачать вони: конфлікт версій, власники, порядок, одноразові коди.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest
from dndsheet.characters.application.golden import build_golden_cases
from dndsheet.characters.domain.wizard import Draft
from dndsheet.characters.infrastructure.character_json import character_to_record, draft_to_record
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
from dndsheet.identity.domain.oauth import IssuedCode, PendingAuthorization, StoredToken
from dndsheet.identity.domain.user import TelegramProfile
from dndsheet.identity.infrastructure.postgres_identity import PostgresIdentityStore
from dndsheet.identity.infrastructure.postgres_oauth import PostgresOAuthStore
from dndsheet.identity.infrastructure.sqlite_identity import SqliteIdentityStore
from dndsheet.identity.infrastructure.sqlite_oauth import SqliteOAuthStore
from dndsheet.shared.errors import ConflictError, NotFoundError
from rules_fixture import FixtureRules


@dataclass
class Stores:
    characters: Any
    drafts: Any
    shares: Any
    identity: Any
    oauth: Any
    claim_unowned: Any


@pytest.fixture(params=["sqlite", "postgres"])
def stores(request: pytest.FixtureRequest, tmp_dir: Path) -> Iterator[Stores]:
    rules = FixtureRules()
    if request.param == "sqlite":
        path = tmp_dir / "db.sqlite3"
        store = SqliteStore(path)
        yield Stores(
            SqliteCharacterRepository(store, rules),
            SqliteDraftRepository(store, rules),
            SqliteShareRepository(store),
            SqliteIdentityStore(path),
            SqliteOAuthStore(path),
            store.claim_unowned,
        )
        return
    pool = request.getfixturevalue("pool")
    store_pg = PostgresStore(pool)
    yield Stores(
        PostgresCharacterRepository(store_pg, rules),
        PostgresDraftRepository(store_pg, rules),
        PostgresShareRepository(store_pg),
        PostgresIdentityStore(pool),
        PostgresOAuthStore(pool),
        store_pg.claim_unowned,
    )


def _character(index: int = 2):  # noqa: ANN202
    return build_golden_cases(FixtureRules())[index].character


# --- персонажі -------------------------------------------------------------------


def test_character_roundtrip(stores: Stores) -> None:
    character = _character()
    stores.characters.save(character)
    restored = stores.characters.get(character.id)
    assert restored is not None
    assert character_to_record(restored) == character_to_record(character)
    assert stores.characters.get("missing") is None
    assert stores.characters.version(character.id) == character.version
    assert stores.characters.version("missing") is None


def test_stale_version_is_a_conflict_and_a_noop_is_not(stores: Stores) -> None:
    character = _character()
    stores.characters.save(character)
    stores.characters.save(character)  # нічого не змінилося — не конфлікт

    newer = _character()
    newer.version = character.version + 1
    newer.name = "Новіше"
    stores.characters.save(newer)
    assert stores.characters.version(character.id) == newer.version

    stale = _character()
    stale.version = newer.version
    stale.name = "Інший пристрій"
    with pytest.raises(ConflictError):
        stores.characters.save(stale)  # та сама версія, інший документ
    with pytest.raises(ConflictError):
        stores.characters.save(character)  # старіша версія
    restored = stores.characters.get(character.id)
    assert restored is not None
    assert restored.name == "Новіше"


def test_owners_and_listing(stores: Stores) -> None:
    first, second = _character(0), _character(1)
    stores.characters.save(first)
    stores.characters.save(second)
    assert stores.characters.ids() == tuple(sorted((first.id, second.id)))
    assert stores.characters.owner(first.id) is None
    assert stores.characters.owner("missing") is None

    assert stores.claim_unowned("u1") == 2
    assert stores.claim_unowned("u2") == 0
    stores.characters.set_owner(second.id, "u2")
    assert stores.characters.ids_of("u1") == (first.id,)
    assert stores.characters.ids_of("u2") == (second.id,)

    # Нова зміна піднімає персонажа на початок списку власника.
    stores.characters.set_owner(second.id, "u1")
    second.version += 1
    second.name = "Свіжий"
    stores.characters.save(second)
    assert stores.characters.ids_of("u1")[0] == second.id

    stores.characters.delete(first.id)
    assert stores.characters.get(first.id) is None
    with pytest.raises(NotFoundError):
        stores.characters.delete(first.id)


def test_new_fields_inside_the_record_need_no_schema_change(stores: Stores) -> None:
    """Аватар чи інше нове поле — всередині документа: зберігається без міграції."""
    character = _character()
    stores.characters.save(character)
    assert stores.characters.get(character.id) is not None


# --- чернетки ---------------------------------------------------------------------


def test_drafts(stores: Stores) -> None:
    rules = FixtureRules()
    draft = Draft(id="drf_1", rules=rules)
    draft.apply_species(name="Тест", species_key="human")
    stores.drafts.save(draft)
    draft.apply_class(class_key="fighter")
    stores.drafts.save(draft)  # перезапис за id
    restored = stores.drafts.get("drf_1")
    assert restored is not None
    assert draft_to_record(restored) == draft_to_record(draft)
    assert stores.drafts.get("missing") is None

    assert stores.drafts.owner("drf_1") is None
    assert stores.drafts.latest_of("u1") is None
    stores.drafts.set_owner("drf_1", "u1")
    assert stores.drafts.owner("drf_1") == "u1"
    assert stores.drafts.owner("missing") is None
    assert stores.drafts.latest_of("u1") == "drf_1"

    stores.drafts.delete("drf_1")
    with pytest.raises(NotFoundError):
        stores.drafts.delete("drf_1")


# --- посилання --------------------------------------------------------------------


def test_shares(stores: Stores) -> None:
    assert stores.shares.token_of("c1") is None
    stores.shares.replace("c1", "tok-a")
    assert stores.shares.token_of("c1") == "tok-a"
    assert stores.shares.character_of("tok-a") == "c1"
    stores.shares.replace("c1", "tok-b")  # нове посилання замінює старе
    assert stores.shares.character_of("tok-a") is None
    assert stores.shares.character_of("tok-b") == "c1"
    stores.shares.revoke("c1")
    assert stores.shares.token_of("c1") is None


# --- користувачі й сесії ------------------------------------------------------------


def test_users_and_sessions(stores: Stores) -> None:
    profile = TelegramProfile(telegram_id=5_000_000_001, first_name="Ігор", last_name="", username="ih", photo_url="")
    user, created = stores.identity.upsert_telegram(profile)
    assert created
    assert user.telegram_id == 5_000_000_001  # більше за int32
    again, created_again = stores.identity.upsert_telegram(
        TelegramProfile(telegram_id=5_000_000_001, first_name="Ігор", last_name="В", username="ih", photo_url="p")
    )
    assert not created_again
    assert again.id == user.id
    assert (again.last_name, again.photo_url) == ("В", "p")
    assert stores.identity.get(user.id) == again
    assert stores.identity.get("missing") is None
    assert stores.identity.count() == 1
    assert stores.identity.exists_telegram(5_000_000_001)
    assert not stores.identity.exists_telegram(1)

    stores.identity.create(user.id, "hash-1", expires_at=2000.5)
    assert stores.identity.user_id("hash-1", now=1000.0) == user.id
    assert stores.identity.user_id("hash-1", now=2000.5) is None  # прострочена
    stores.identity.delete("hash-1")
    assert stores.identity.user_id("hash-1", now=1000.0) is None


# --- OAuth ------------------------------------------------------------------------


def _user(stores: Stores) -> str:
    user, _ = stores.identity.upsert_telegram(
        TelegramProfile(telegram_id=7, first_name="Гравець", last_name="", username="", photo_url="")
    )
    return user.id


def test_oauth_clients(stores: Stores) -> None:
    info = '{"client_id": "c1", "client_name": "Claude"}'
    stores.oauth.save_client("c1", info, "cimd", now=100.0)
    assert stores.oauth.client("c1") == (info, "cimd", 100.0)
    assert stores.oauth.client("missing") is None
    stores.oauth.save_client("c1", info, "dcr", now=200.0)
    assert stores.oauth.client("c1") == (info, "dcr", 200.0)
    assert stores.oauth.purge_clients("dcr", older_than=150.0) == 0
    assert stores.oauth.purge_clients("dcr", older_than=250.0) == 1


def test_oauth_requests_and_codes_are_taken_once(stores: Stores) -> None:
    user_id = _user(stores)
    pending = PendingAuthorization(
        id="r1",
        client_id="c1",
        redirect_uri="https://claude.example/cb",
        redirect_uri_explicit=True,
        scopes=("characters",),
        code_challenge="chal",
        state=None,
        resource="https://dnd.example/mcp",
        expires_at=500.0,
    )
    stores.oauth.save_request(pending)
    assert stores.oauth.request("r1", now=100.0) == pending
    assert stores.oauth.request("r1", now=600.0) is None
    assert stores.oauth.take_request("r1", now=100.0) == pending
    assert stores.oauth.take_request("r1", now=100.0) is None

    stores.oauth.save_request(replace(pending, id="r2"))
    assert stores.oauth.take_request("r2", now=600.0) is None  # прострочений: прибрано, не віддано
    assert stores.oauth.request("r2", now=100.0) is None

    code = IssuedCode(
        client_id="c1",
        user_id=user_id,
        redirect_uri="https://claude.example/cb",
        redirect_uri_explicit=False,
        scopes=("characters",),
        code_challenge="chal",
        resource="https://dnd.example/mcp",
        expires_at=160.0,
    )
    stores.oauth.save_code("code-hash", code)
    assert stores.oauth.code("code-hash") == code
    assert stores.oauth.take_code("code-hash") == code
    assert stores.oauth.take_code("code-hash") is None
    assert stores.oauth.code("code-hash") is None


def test_oauth_tokens_and_grants(stores: Stores) -> None:
    user_id = _user(stores)
    stores.oauth.save_client("c1", '{"client_name": "Claude"}', "cimd", now=1.0)
    refresh = StoredToken("refresh", "fam1", user_id, "c1", ("characters",), "res", expires_at=10_000.0)
    access = StoredToken("access", "fam1", user_id, "c1", ("characters",), "res", expires_at=3_000.0)
    stores.oauth.save_token("r-hash", refresh, now=100.0)
    stores.oauth.save_token("a-hash", access, now=100.0)
    assert stores.oauth.token("r-hash") == refresh
    assert stores.oauth.token("missing") is None

    stores.oauth.touch("a-hash", now=1_000.0)
    stores.oauth.touch("a-hash", now=1_030.0)  # частіше ніж раз на хвилину не записується
    grants = stores.oauth.grants(user_id, now=200.0)
    assert [(g.client_id, g.client_name, g.scopes) for g in grants] == [("c1", "Claude", ("characters",))]
    assert grants[0].connected_at == 100.0
    assert grants[0].last_used_at == 1_000.0

    assert stores.oauth.mark_used("r-hash")
    assert not stores.oauth.mark_used("r-hash")  # повторне використання видно
    assert stores.oauth.token("r-hash").used
    assert stores.oauth.grants(user_id, now=200.0) == []  # дійсного refresh більше немає

    stores.oauth.save_token("r2", StoredToken("refresh", "fam2", user_id, "c1", (), "res", 10_000.0), now=300.0)
    stores.oauth.revoke_family("fam1")
    assert stores.oauth.token("a-hash") is None
    assert stores.oauth.revoke_client(user_id, "c1") == 1
    assert stores.oauth.revoke_client(user_id, "c1") == 0


def test_oauth_purge_removes_only_expired(stores: Stores) -> None:
    user_id = _user(stores)
    stores.oauth.save_token("old", StoredToken("access", "f", user_id, "c1", (), "res", 50.0), now=1.0)
    stores.oauth.save_token("new", StoredToken("access", "f", user_id, "c1", (), "res", 500.0), now=1.0)
    stores.oauth.save_code(
        "old-code", IssuedCode("c1", user_id, "https://x/cb", False, (), "chal", "res", expires_at=50.0)
    )
    stores.oauth.purge(now=100.0)
    assert stores.oauth.token("old") is None
    assert stores.oauth.token("new") is not None
    assert stores.oauth.code("old-code") is None
