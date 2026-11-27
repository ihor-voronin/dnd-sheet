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

import pytest
from fastapi.testclient import TestClient

from dndsheet.api.app import create_app
from dndsheet.identity.domain.user import verify_telegram_login
from dndsheet.shared.errors import ValidationError

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
    ("abilities", {"method": "standard_array", "scores": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8}}),
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
    assert config == {"auth_enabled": True, "telegram_bot": "dndsheet_test_bot", "telegram_ready": True, "dev_login": True}


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
        source.app.state.characters.store.connection().execute(
            "SELECT record FROM characters WHERE id = ?", (character_id,)
        ).fetchone()[0]
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
