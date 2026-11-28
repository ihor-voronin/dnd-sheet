"""Портрет і стать персонажа через HTTP: файли, каталог, поради, зміна під версією."""

from __future__ import annotations

import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from dndsheet.api.app import create_app
from dndsheet.characters.infrastructure.character_json import character_from_record, character_to_record
from dndsheet.visuals.application import avatars
from fastapi.testclient import TestClient

DATA_DIR = Path(__file__).resolve().parent / "_tmp_avatar_api"
API = "/api/v1/characters"


@pytest.fixture(scope="module")
def client() -> TestClient:
    shutil.rmtree(DATA_DIR, ignore_errors=True)
    DATA_DIR.mkdir(parents=True)
    previous = os.environ.get("DNDSHEET_DATA_DIR")
    os.environ["DNDSHEET_DATA_DIR"] = str(DATA_DIR)
    try:
        app = create_app()
    finally:
        if previous is None:
            os.environ.pop("DNDSHEET_DATA_DIR", None)
        else:
            os.environ["DNDSHEET_DATA_DIR"] = previous
    try:
        yield TestClient(app)
    finally:
        shutil.rmtree(DATA_DIR, ignore_errors=True)


def _clone(client: TestClient, key: str, new_id: str) -> dict:
    if not client.app.state.golden_cases:
        pytest.skip("немає корпусу механік")
    case = next(item for item in client.app.state.golden_cases if item.key == key)
    client.app.state.characters.save(replace(case.character, id=new_id))
    return client.get(f"{API}/{new_id}").json()["sheet"]


# ---------------------------------------------------------------------------
# файли й каталог — без входу й без корпусу
# ---------------------------------------------------------------------------


def test_portrait_file_is_cached_for_a_year(client: TestClient) -> None:
    response = client.get(avatars.url("elf-f-wizard-1"))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "immutable" in response.headers["cache-control"]
    assert response.text.startswith("<svg")


def test_old_version_is_served_but_not_for_long(client: TestClient) -> None:
    response = client.get("/assets/avatars/0000000000/elf-f-wizard-1.svg")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300"


def test_unknown_portrait_is_404(client: TestClient) -> None:
    assert client.get(avatars.url("nobody-x-wizard-1")).status_code == 404


def test_catalog_lists_every_portrait(client: TestClient) -> None:
    body = client.get("/api/v1/avatars").json()
    assert body["base"] == f"/assets/avatars/{avatars.VERSION}/"
    assert body["total"] == len(body["items"]) >= 1000
    assert ["elf-f-wizard-1", "elf", "f", "wizard"] in body["items"]
    assert {"key": "wizard", "label": "чарівник"} in body["classes"]
    assert {group["key"] for group in body["groups"]} >= {"human", "dragonborn", "tabaxi"}


def test_recommended_for_a_hero(client: TestClient) -> None:
    body = client.get(
        "/api/v1/avatars/recommended", params={"species": "Hill Dwarf", "class": "cleric", "gender": "male"}
    ).json()
    assert body["group"] == "dwarf"
    assert body["items"][0]["id"].startswith("dwarf-m-cleric-")
    assert body["items"][0]["url"] == avatars.url(body["items"][0]["id"])
    assert 20 <= len(body["items"]) <= 30


# ---------------------------------------------------------------------------
# портрет і стать на листі
# ---------------------------------------------------------------------------


def test_sheet_has_a_default_portrait(client: TestClient) -> None:
    sheet = _clone(client, "fighter-1", "avatar-default")
    character = sheet["character"]
    assert character["avatar"] is None and character["gender"] is None
    portrait = character["portrait"]
    assert portrait["chosen"] is False
    assert portrait["id"].startswith("human-") and "-fighter-" in portrait["id"]
    assert portrait["url"] == avatars.url(portrait["id"])
    assert portrait["label"].startswith("Портрет: людина")


def test_choose_portrait_and_gender(client: TestClient) -> None:
    sheet = _clone(client, "fighter-1", "avatar-choose")
    version = sheet["character"]["version"]
    response = client.patch(
        f"{API}/avatar-choose", json={"version": version, "gender": "female", "avatar": "tiefling-f-bard-2"}
    )
    assert response.status_code == 200, response.text
    character = response.json()["sheet"]["character"]
    assert character["gender"] == "female"
    assert character["avatar"] == "tiefling-f-bard-2"
    assert character["portrait"] == {**character["portrait"], "id": "tiefling-f-bard-2", "chosen": True}
    assert response.json()["version"] > version

    roster = client.get(API).json()["items"]
    entry = next(item for item in roster if item["id"] == "avatar-choose")
    assert entry["portrait"]["id"] == "tiefling-f-bard-2"

    # Стара версія — 409, як для будь-якої зміни листа.
    stale = client.patch(f"{API}/avatar-choose", json={"version": version, "avatar": "elf-f-bard-1"})
    assert stale.status_code == 409

    # Скинути: null повертає типовий портрет (уже з урахуванням статі).
    fresh = response.json()["version"]
    reset = client.patch(f"{API}/avatar-choose", json={"version": fresh, "avatar": None})
    character = reset.json()["sheet"]["character"]
    assert character["avatar"] is None and character["portrait"]["chosen"] is False
    assert character["portrait"]["id"].startswith("human-f-fighter-")


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"avatar": "elf-f-wizard-9"}, 422),
        ({"avatar": "../../etc"}, 422),
        ({"avatar": 5}, 422),
        ({"gender": "dragon"}, 422),
        ({"gender": 1}, 422),
    ],
)
def test_bad_values_are_rejected(client: TestClient, body: dict, status: int) -> None:
    _clone(client, "fighter-1", "avatar-bad")
    assert client.patch(f"{API}/avatar-bad", json=body).status_code == status


def test_unchanged_values_keep_the_version(client: TestClient) -> None:
    sheet = _clone(client, "fighter-1", "avatar-same")
    first = client.patch(
        f"{API}/avatar-same", json={"version": sheet["character"]["version"], "avatar": "human-m-fighter-2"}
    )
    version = first.json()["version"]
    same = client.patch(f"{API}/avatar-same", json={"version": version, "avatar": " human-m-fighter-2 "})
    assert same.status_code == 200, same.text
    assert same.json()["version"] == version


def test_stored_with_the_character(client: TestClient) -> None:
    store = client.app.state.characters
    sheet = _clone(client, "fighter-1", "avatar-store")
    client.patch(
        f"{API}/avatar-store",
        json={"version": sheet["character"]["version"], "gender": "male", "avatar": "dwarf-m-fighter-1"},
    )
    character = store.get("avatar-store")
    record = character_to_record(character)
    assert record["gender"] == "male" and record["avatar"] == "dwarf-m-fighter-1"
    again = character_from_record(record, character.rules)
    assert (again.gender, again.avatar) == ("male", "dwarf-m-fighter-1")
    # Старі записи без цих полів читаються як «не вказано».
    legacy = {key: value for key, value in record.items() if key not in ("gender", "avatar")}
    old = character_from_record(legacy, character.rules)
    assert old.gender is None and old.avatar is None


def test_shared_sheet_shows_the_portrait(client: TestClient) -> None:
    sheet = _clone(client, "fighter-1", "avatar-shared")
    client.patch(
        f"{API}/avatar-shared", json={"version": sheet["character"]["version"], "avatar": "goliath-f-fighter-1"}
    )
    link = client.post(f"{API}/avatar-shared/share").json()
    token = link["path"].rsplit("/", 1)[-1]
    shared = client.get(f"/api/v1/shared/{token}")
    assert shared.status_code == 200, shared.text
    assert shared.json()["sheet"]["character"]["portrait"]["id"] == "goliath-f-fighter-1"


def test_wizard_keeps_the_gender(client: TestClient) -> None:
    if not client.app.state.golden_cases:
        pytest.skip("немає корпусу механік")
    draft_id = client.post(f"{API}/wizard").json()["draft"]["id"]
    step = f"{API}/wizard/{draft_id}/steps/species"
    bad = client.put(step, json={"name": "Іва", "gender": "ghost", "species_key": "human"})
    assert bad.status_code == 422
    good = client.put(step, json={"name": "Іва", "gender": "female", "species_key": "human"})
    assert good.status_code == 200, good.text
    assert client.get(step).json()["answers"]["gender"] == "female"
    record = client.app.state.drafts.get(draft_id)
    assert record.gender == "female"


def test_emblem_files(client: TestClient) -> None:
    from dndsheet.visuals.application import emblems

    response = client.get(emblems.url("class-bard"))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert "immutable" in response.headers["cache-control"]
    assert client.get("/assets/emblems/old/class-bard.svg").headers["cache-control"] == "public, max-age=300"
    assert client.get(emblems.url("class-nobody")).status_code == 404


def test_wizard_cards_carry_pictures(client: TestClient) -> None:
    if not client.app.state.golden_cases:
        pytest.skip("немає корпусу механік")
    started = client.post(f"{API}/wizard").json()
    species = {item["key"]: item for item in started["options"]["species"]}
    assert species["dwarf"]["portrait"].startswith("/assets/avatars/")
    assert "/dwarf-" in species["dwarf"]["portrait"]
    assert any("/duergar-" in (child.get("portrait") or "") for child in species["dwarf"]["subspecies"])
    draft_id = started["draft"]["id"]
    client.put(f"{API}/wizard/{draft_id}/steps/species", json={"name": "Іва", "species_key": "human"})
    classes = client.get(f"{API}/wizard/{draft_id}/steps/class").json()["options"]["classes"]
    wizard = next(item for item in classes if item["key"] == "wizard")
    assert wizard["emblem"].startswith("/assets/emblems/") and wizard["emblem"].endswith("/class-wizard.svg")
