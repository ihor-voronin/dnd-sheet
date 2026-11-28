"""Вхід через Telegram, сесії й доступ до персонажів.

Гість бачить лише довідник; персонажі й чернетки — тільки власнику, а чужий id
виглядає як відсутній (404, не 403: існування чужого листа не розкривається).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import shutil
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest
from dndsheet.api.app import create_app
from dndsheet.identity.domain.user import verify_telegram_login, verify_telegram_webapp
from dndsheet.shared.errors import ValidationError
from fastapi.testclient import TestClient

BOT_TOKEN = "123456:TEST-TOKEN"
ROOT = Path(__file__).resolve().parent / "_tmp_auth"


def _signed(fields: dict, token: str = BOT_TOKEN) -> dict:
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hashlib.sha256(token.encode()).digest()
    return {**fields, "hash": hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()}


def _fields(telegram_id: int = 42, **extra: object) -> dict:
    return {"id": telegram_id, "first_name": "Ігор", "auth_date": int(time.time()), **extra}


# --- підпис Telegram ---------------------------------------------------------


def test_valid_signature_gives_profile() -> None:
    profile = verify_telegram_login(_signed(_fields(username="igor")), BOT_TOKEN)
    assert profile.telegram_id == 42
    assert profile.first_name == "Ігор"
    assert profile.username == "igor"


def test_tampered_field_is_rejected() -> None:
    payload = _signed(_fields())
    payload["id"] = 43
    with pytest.raises(ValidationError, match="підпис"):
        verify_telegram_login(payload, BOT_TOKEN)


def test_other_bot_signature_is_rejected() -> None:
    with pytest.raises(ValidationError):
        verify_telegram_login(_signed(_fields(), token="999:OTHER"), BOT_TOKEN)


def test_stale_login_is_rejected() -> None:
    old = _signed(_fields(auth_date=int(time.time()) - 3 * 24 * 3600))
    with pytest.raises(ValidationError, match="застарів"):
        verify_telegram_login(old, BOT_TOKEN)


# --- HTTP ---------------------------------------------------------------------


def _app(monkeypatch: pytest.MonkeyPatch, name: str, **env: str) -> TestClient:
    data = ROOT / name
    shutil.rmtree(data, ignore_errors=True)
    data.mkdir(parents=True)
    monkeypatch.setenv("DNDSHEET_DATA_DIR", str(data))
    monkeypatch.setenv("DNDSHEET_AUTH", "on")
    monkeypatch.setenv("DNDSHEET_TELEGRAM_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("DNDSHEET_TELEGRAM_BOT", "dndsheet_test_bot")
    monkeypatch.setenv("DNDSHEET_DEV_LOGIN", "1")
    monkeypatch.delenv("DNDSHEET_OWNER_TELEGRAM_ID", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return TestClient(create_app())


@pytest.fixture(scope="module", autouse=True)
def _cleanup() -> None:
    yield
    shutil.rmtree(ROOT, ignore_errors=True)


FIGHTER = [
    ("species", {"name": "Дарія", "species_key": "human"}),
    ("class", {"class_key": "fighter"}),
    (
        "abilities",
        {"method": "standard_array", "scores": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8}},
    ),
    (
        "background",
        {
            "background_key": "soldier",
            "picks": [
                {"kind": "skill", "value": "acrobatics", "source": {"kind": "class", "key": "fighter"}},
                {"kind": "skill", "value": "perception", "source": {"kind": "class", "key": "fighter"}},
            ],
        },
    ),
    ("equipment", {"items": [], "money": {}}),
]


def _create(client: TestClient) -> str:
    draft_id = client.post("/api/v1/characters/wizard").json()["draft"]["id"]
    for step, body in FIGHTER:
        response = client.put(f"/api/v1/characters/wizard/{draft_id}/steps/{step}", json=body)
        assert response.status_code == 200, f"{step}: {response.text}"
    response = client.post(f"/api/v1/characters/wizard/{draft_id}/finish")
    assert response.status_code == 200, response.text
    return response.json()["character_id"]


def test_guest_sees_compendium_but_not_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app(monkeypatch, "guest")
    assert client.get("/api/v1/auth/me").json() == {"user": None}
    assert client.get("/api/v1/compendium/items", params={"q": "Shield", "limit": 1}).status_code == 200
    assert client.get("/api/v1/characters").status_code == 401
    assert client.post("/api/v1/characters/wizard").status_code == 401
    config = client.get("/api/v1/auth/config").json()
    assert config == {
        "auth_enabled": True,
        "telegram_bot": "dndsheet_test_bot",
        "telegram_ready": True,
        "dev_login": True,
    }


def test_telegram_login_sets_session_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app(monkeypatch, "telegram")
    response = client.post("/api/v1/auth/telegram", json=_signed(_fields(last_name="В.")))
    assert response.status_code == 200, response.text
    assert response.json()["user"]["name"] == "Ігор В."
    cookie = response.headers["set-cookie"]
    assert "dndsheet_session=" in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.casefold()
    assert client.get("/api/v1/auth/me").json()["user"]["name"] == "Ігор В."

    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/auth/me").json() == {"user": None}


def test_forged_telegram_login_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app(monkeypatch, "forged")
    forged = _signed(_fields(), token="1:WRONG")
    assert client.post("/api/v1/auth/telegram", json=forged).status_code == 401
    assert client.get("/api/v1/auth/me").json() == {"user": None}


def test_dev_login_is_off_unless_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app(monkeypatch, "no-dev", DNDSHEET_DEV_LOGIN="")
    assert client.post("/api/v1/auth/dev", json={"name": "Хтось"}).status_code == 404


def test_characters_belong_to_their_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app(monkeypatch, "owners")
    client.post("/api/v1/auth/dev", json={"name": "Аня"})
    character_id = _create(client)
    listed = client.get("/api/v1/characters").json()
    assert [item["id"] for item in listed["items"]] == [character_id]
    assert client.get(f"/api/v1/characters/{character_id}/version").json() == {"version": 1}

    # Інший гравець: список порожній, чужий лист «не існує», змінити його не можна.
    other = TestClient(client.app)
    other.post("/api/v1/auth/dev", json={"name": "Богдан"})
    assert other.get("/api/v1/characters").json()["items"] == []
    assert other.get(f"/api/v1/characters/{character_id}").status_code == 404
    assert other.patch(f"/api/v1/characters/{character_id}", json={"hp_current": 1}).status_code == 404
    assert other.get(f"/api/v1/characters/{character_id}/version").status_code == 404

    # Чернетку теж не підглянути.
    draft_id = client.post("/api/v1/characters/wizard").json()["draft"]["id"]
    assert other.get(f"/api/v1/characters/wizard/{draft_id}").status_code == 404
    assert client.get("/api/v1/characters").json()["draft_id"] == draft_id


def test_same_session_works_from_another_device(monkeypatch: pytest.MonkeyPatch) -> None:
    """Персонажі в базі, а не в браузері: новий вхід того ж гравця бачить їх."""
    client = _app(monkeypatch, "devices")
    client.post("/api/v1/auth/telegram", json=_signed(_fields(telegram_id=7)))
    character_id = _create(client)

    phone = TestClient(client.app)
    phone.post("/api/v1/auth/telegram", json=_signed(_fields(telegram_id=7)))
    assert [item["id"] for item in phone.get("/api/v1/characters").json()["items"]] == [character_id]


def test_concurrent_edit_of_same_version_conflicts(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app(monkeypatch, "conflict")
    client.post("/api/v1/auth/dev", json={"name": "Аня"})
    character_id = _create(client)
    store = client.app.state.characters
    laptop = store.get(character_id)
    phone = store.get(character_id)
    # Обидва пристрої прочитали версію 1 і змінили різне: другий запис — конфлікт.
    laptop.name = "Дарія з ноутбука"
    laptop.bump_version()
    store.save(laptop)
    phone.name = "Дарія з телефона"
    phone.bump_version()
    with pytest.raises(Exception, match="іншому пристрої"):
        store.save(phone)


def test_json_characters_move_to_first_user(monkeypatch: pytest.MonkeyPatch) -> None:
    """Старі файли `var/characters/*.json` переносяться в базу й дістаються першому гравцю."""
    source = TestClient(_app(monkeypatch, "legacy-source", DNDSHEET_AUTH="off").app)
    character_id = _create(source)
    record = json.loads(
        source.app.state.characters.store.connection()
        .execute("SELECT record FROM characters WHERE id = ?", (character_id,))
        .fetchone()[0]
    )
    legacy = ROOT / "legacy"
    shutil.rmtree(legacy, ignore_errors=True)
    (legacy / "characters").mkdir(parents=True)
    (legacy / "characters" / f"{character_id}.json").write_text(json.dumps(record), encoding="utf-8")
    monkeypatch.setenv("DNDSHEET_DATA_DIR", str(legacy))
    monkeypatch.setenv("DNDSHEET_AUTH", "on")
    client = TestClient(create_app())
    client.post("/api/v1/auth/dev", json={"name": "Власник"})
    assert [item["id"] for item in client.get("/api/v1/characters").json()["items"]] == [character_id]

    second = TestClient(client.app)
    second.post("/api/v1/auth/dev", json={"name": "Гість"})
    assert second.get("/api/v1/characters").json()["items"] == []


def test_guest_reads_knowledge_base(monkeypatch: pytest.MonkeyPatch) -> None:
    """Довідник — без входу: ті самі картки, що й у візарді, плюс усі підкласи."""
    client = _app(monkeypatch, "kb")
    species = client.get("/api/v1/kb/species").json()["items"]
    dwarf = next(item for item in species if item["key"] == "dwarf")
    assert dwarf["traits"] and {sub["key"] for sub in dwarf["subspecies"]} >= {"hill dwarf", "mountain dwarf"}
    classes = client.get("/api/v1/kb/classes").json()["items"]
    paladin = next(item for item in classes if item["key"] == "paladin")
    assert paladin["casts_from_level"] == 2
    assert any(sub["name_en"] == "Oath of Devotion" for sub in paladin["subclasses_all"])
    backgrounds = client.get("/api/v1/kb/backgrounds").json()["items"]
    assert "custom" not in {item["key"] for item in backgrounds}
    assert client.get("/api/v1/characters/wizard/class-features/paladin").status_code == 200


def test_share_link_is_read_only_and_revocable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Посилання «лише читати»: гість бачить і друкує лист, але змінити нічого не може."""
    owner = _app(monkeypatch, "share")
    owner.post("/api/v1/auth/dev", json={"name": "Аня"})
    character_id = _create(owner)
    assert owner.get(f"/api/v1/characters/{character_id}/share").json() == {"token": None, "path": None}
    token = owner.post(f"/api/v1/characters/{character_id}/share").json()["token"]
    assert token and len(token) >= 16

    guest = TestClient(owner.app)
    shared = guest.get(f"/api/v1/shared/{token}")
    assert shared.status_code == 200
    assert shared.json()["sheet"]["character"]["id"] == character_id
    assert shared.json()["read_only"] is True
    assert guest.get(f"/api/v1/shared/{token}/version").json() == {"version": 1}
    assert "data:font/woff2" in guest.get(f"/api/v1/shared/{token}/print").text
    # Посилання не дає прав власника: зміни — лише з входом і своїм листом.
    assert guest.patch(f"/api/v1/characters/{character_id}", json={"hp": {"damage": 1}}).status_code == 401
    assert guest.post(f"/api/v1/characters/{character_id}/share").status_code == 401

    stranger = TestClient(owner.app)
    stranger.post("/api/v1/auth/dev", json={"name": "Богдан"})
    assert stranger.post(f"/api/v1/characters/{character_id}/share").status_code == 404

    # Нове посилання замінює старе; відкликане — недійсне.
    fresh = owner.post(f"/api/v1/characters/{character_id}/share").json()["token"]
    assert guest.get(f"/api/v1/shared/{token}").status_code == 404
    owner.delete(f"/api/v1/characters/{character_id}/share")
    assert guest.get(f"/api/v1/shared/{fresh}").status_code == 404


def test_player_deletes_own_character_for_good(monkeypatch: pytest.MonkeyPatch) -> None:
    """Видалення: лист, посилання «лише читати» й рядок у списку зникають; чужого не видалити."""
    owner = _app(monkeypatch, "delete")
    owner.post("/api/v1/auth/dev", json={"name": "Аня"})
    keep = _create(owner)
    gone = _create(owner)
    token = owner.post(f"/api/v1/characters/{gone}/share").json()["token"]

    stranger = TestClient(owner.app)
    stranger.post("/api/v1/auth/dev", json={"name": "Богдан"})
    assert stranger.delete(f"/api/v1/characters/{gone}").status_code == 404
    assert TestClient(owner.app).delete(f"/api/v1/characters/{gone}").status_code == 401

    response = owner.delete(f"/api/v1/characters/{gone}")
    assert response.status_code == 200
    assert response.json() == {"deleted": gone}
    assert owner.get(f"/api/v1/characters/{gone}").status_code == 404
    assert TestClient(owner.app).get(f"/api/v1/shared/{token}").status_code == 404
    assert [item["id"] for item in owner.get("/api/v1/characters").json()["items"]] == [keep]
    assert owner.delete(f"/api/v1/characters/{gone}").status_code == 404


def test_character_limit_blocks_new_ones(monkeypatch: pytest.MonkeyPatch) -> None:
    """Межа на гравця: новий візард не почати, а почату чернетку не завершити."""
    from dndsheet.characters.api import router as characters_router  # noqa: PLC0415

    monkeypatch.setattr(characters_router, "CHARACTER_LIMIT", 1)
    client = _app(monkeypatch, "limit")
    client.post("/api/v1/auth/dev", json={"name": "Аня"})
    early = client.post("/api/v1/characters/wizard").json()["draft"]["id"]
    for step, body in FIGHTER:
        assert client.put(f"/api/v1/characters/wizard/{early}/steps/{step}", json=body).status_code == 200
    _create(client)
    listed = client.get("/api/v1/characters").json()
    assert (listed["total"], listed["limit"]) == (1, 1)

    refused = client.post("/api/v1/characters/wizard")
    assert refused.status_code == 409
    assert "межа" in refused.json()["detail"]
    assert client.post(f"/api/v1/characters/wizard/{early}/finish").status_code == 409

    # Інший гравець має власну межу.
    other = TestClient(client.app)
    other.post("/api/v1/auth/dev", json={"name": "Богдан"})
    assert other.post("/api/v1/characters/wizard").status_code == 200


# --- Mini App у Telegram ------------------------------------------------------


def _init_data(telegram_id: int = 42, token: str = BOT_TOKEN, auth_date: int | None = None, **user: object) -> str:
    """initData так, як його підписує Telegram для Mini App."""
    fields = {
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "user": json.dumps(
            {"id": telegram_id, "first_name": "Ігор", **user}, ensure_ascii=False, separators=(",", ":")
        ),
        "signature": "ed25519-signature-is-part-of-the-check-string",
    }
    check = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


def test_webapp_init_data_gives_profile() -> None:
    profile = verify_telegram_webapp(_init_data(username="igor", last_name="В."), BOT_TOKEN)
    assert (profile.telegram_id, profile.first_name, profile.last_name, profile.username) == (42, "Ігор", "В.", "igor")


def test_webapp_tampered_or_foreign_init_data_is_rejected() -> None:
    forged = _init_data().replace("%22id%22%3A42", "%22id%22%3A43")
    assert forged != _init_data()
    with pytest.raises(ValidationError, match="підпис"):
        verify_telegram_webapp(forged, BOT_TOKEN)
    with pytest.raises(ValidationError):
        verify_telegram_webapp(_init_data(token="999:OTHER"), BOT_TOKEN)
    # Підпис віджета на сайті не підходить для Mini App і навпаки: різні ключі.
    widget = urlencode(_signed({"id": 42, "first_name": "Ігор", "auth_date": int(time.time())}))
    with pytest.raises(ValidationError):
        verify_telegram_webapp(widget, BOT_TOKEN)
    with pytest.raises(ValidationError):
        verify_telegram_webapp("", BOT_TOKEN)


def test_webapp_stale_init_data_is_rejected() -> None:
    with pytest.raises(ValidationError, match="застарів"):
        verify_telegram_webapp(_init_data(auth_date=int(time.time()) - 3 * 24 * 3600), BOT_TOKEN)


def test_mini_app_login_uses_bearer_token_and_same_account(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mini App: initData → токен у заголовку; той самий Telegram id — той самий гравець і ті самі персонажі."""
    site = _app(monkeypatch, "webapp")
    site.post("/api/v1/auth/telegram", json=_signed(_fields()))
    character_id = _create(site)

    # Інший «пристрій» без cookie (Telegram у браузері: iframe без сторонніх cookie).
    mini = TestClient(site.app)
    response = mini.post("/api/v1/auth/telegram-webapp", json={"init_data": _init_data()})
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    mini.cookies.clear()
    bearer = {"Authorization": f"Bearer {token}"}
    assert mini.get("/api/v1/auth/me").json()["user"] is None
    assert mini.get("/api/v1/auth/me", headers=bearer).json()["user"]["name"] == "Ігор"
    listed = mini.get("/api/v1/characters", headers=bearer).json()["items"]
    assert [item["id"] for item in listed] == [character_id]

    assert (
        mini.post("/api/v1/auth/telegram-webapp", json={"init_data": _init_data(token="999:OTHER")}).status_code == 401
    )
    mini.post("/api/v1/auth/logout", headers=bearer)
    assert mini.get("/api/v1/auth/me", headers=bearer).json()["user"] is None


def test_link_token_opens_files_only_for_get(monkeypatch: pytest.MonkeyPatch) -> None:
    """Файл з Mini App качає сам Telegram: короткий токен у посиланні, лише для читання."""
    owner = _app(monkeypatch, "link")
    owner.post("/api/v1/auth/dev", json={"name": "Аня"})
    character_id = _create(owner)
    link = owner.post("/api/v1/auth/link-token").json()
    assert link["token"] and link["ttl"] == 300

    outsider = TestClient(owner.app)
    assert outsider.get(f"/api/v1/characters/{character_id}/print").status_code == 401
    page = outsider.get(f"/api/v1/characters/{character_id}/print", params={"link": link["token"]})
    assert page.status_code == 200 and "data:font/woff2" in page.text
    # Для змін посилання не годиться.
    patch = outsider.patch(
        f"/api/v1/characters/{character_id}", params={"link": link["token"]}, json={"hp": {"damage": 1}}
    )
    assert patch.status_code == 401
    assert outsider.post("/api/v1/auth/link-token").status_code == 401
