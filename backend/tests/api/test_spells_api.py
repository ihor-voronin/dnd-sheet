"""HTTP заклять поза рівнем: додати, прибрати, підготувати на день.

Перевіряється не лише домен: відповідь мусить повернути новий лист, у якому
власне закляття позначене, а підготовка замінила вчорашній набір.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from dndsheet.api.app import create_app
from fastapi.testclient import TestClient

DATA_DIR = Path(__file__).resolve().parent / "_tmp_spells_api"


@pytest.fixture(scope="module")
def data_dir() -> Path:
    shutil.rmtree(DATA_DIR, ignore_errors=True)
    DATA_DIR.mkdir(parents=True)
    try:
        yield DATA_DIR
    finally:
        shutil.rmtree(DATA_DIR, ignore_errors=True)


@pytest.fixture(scope="module")
def client(data_dir: Path) -> TestClient:
    previous = os.environ.get("DNDSHEET_DATA_DIR")
    os.environ["DNDSHEET_DATA_DIR"] = str(data_dir)
    try:
        app = create_app()
    finally:
        if previous is None:
            os.environ.pop("DNDSHEET_DATA_DIR", None)
        else:
            os.environ["DNDSHEET_DATA_DIR"] = previous
    if not app.state.golden_cases:
        pytest.skip("немає корпусу механік")
    return TestClient(app)


def _clone(client: TestClient, key: str, new_id: str) -> dict:
    """Копія еталонного персонажа під власним id — тести не заважають один одному."""
    case = next(item for item in client.app.state.golden_cases if item.key == key)
    character = replace(case.character, id=new_id)
    client.app.state.characters.save(character)
    return client.get(f"/api/v1/characters/{new_id}").json()["sheet"]


def _spell(sheet: dict, name: str) -> dict:
    for item in sheet["spells"]:
        if item["name_en"] == name:
            return item
    raise AssertionError(f"немає закляття {name!r}: {[i['name_en'] for i in sheet['spells']]}")


def test_custom_spell_is_marked_on_the_sheet(client: TestClient) -> None:
    sheet = _clone(client, "fighter-2-wizard-3", "spells-custom")
    version = sheet["character"]["version"]

    response = client.post(
        "/api/v1/characters/spells-custom/spells",
        json={
            "version": version,
            "class_key": "wizard",
            "name_en": "Свій вогонь",
            "level": 1,
            "custom": True,
            "description": "1d6 вогню в ціль; рятунок СПР.",
            # Власне закляття завжди підготовлене — навіть якщо клієнт
            # надіслав prepared: false. Місце в ліміті воно займає.
            "prepared": False,
        },
    )
    assert response.status_code == 200, response.text
    sheet = response.json()["sheet"]

    spell = _spell(sheet, "Свій вогонь")
    assert spell["custom"] is True
    assert spell["prepared"] is True
    assert spell["description"].startswith("1d6 вогню")
    assert not spell["entry_id"]
    # Довідник не підміняє текст власного закляття: жодних книжкових полів.
    assert not spell.get("school")


def test_preparation_replaces_yesterdays_set(client: TestClient) -> None:
    sheet = _clone(client, "fighter-2-wizard-3", "spells-prepare")
    # У золотому персонажі Wizard 3 з ІНТ 14: ліміт 2 + 3 = 5.
    response = client.post(
        "/api/v1/characters/spells-prepare/spells/prepare",
        json={
            "version": sheet["character"]["version"],
            "class_key": "wizard",
            "spells": [
                {"name_en": "Shield", "level": 1},
                {"name_en": "Misty Step", "level": 2},
            ],
        },
    )
    assert response.status_code == 200, response.text
    sheet = response.json()["sheet"]

    prepared = [
        item["name_en"]
        for item in sheet["spells"]
        if item["class_key"] == "wizard" and item["prepared"] and item["level"] > 0
    ]
    assert sorted(prepared) == ["Misty Step", "Shield"]
    # Заговори лишилися: їх підготовка не чіпає.
    cantrips = [item["name_en"] for item in sheet["spells"] if item["level"] == 0]
    assert "Fire Bolt" in cantrips


def test_preparation_over_the_limit_is_refused(client: TestClient) -> None:
    sheet = _clone(client, "fighter-2-wizard-3", "spells-over-limit")
    limit = next(item["prepared_limit"] for item in sheet["spellcasting"]["classes"] if item["key"] == "wizard")
    assert limit == 5

    response = client.post(
        "/api/v1/characters/spells-over-limit/spells/prepare",
        json={
            "version": sheet["character"]["version"],
            "class_key": "wizard",
            "spells": [{"name_en": f"Spell {index}", "level": 1} for index in range(limit + 1)],
        },
    )
    assert response.status_code == 422
    assert "можна 5" in response.text


def test_fighter_does_not_prepare_spells(client: TestClient) -> None:
    sheet = _clone(client, "fighter-1", "spells-fighter")
    response = client.post(
        "/api/v1/characters/spells-fighter/spells/prepare",
        json={"version": sheet["character"]["version"], "class_key": "fighter"},
    )
    assert response.status_code == 422
    assert "не готує" in response.text


def test_remove_spell(client: TestClient) -> None:
    sheet = _clone(client, "fighter-2-wizard-3", "spells-remove")
    version = sheet["character"]["version"]

    response = client.request(
        "DELETE",
        "/api/v1/characters/spells-remove/spells",
        json={"version": version, "name_en": "Misty Step", "class_key": "wizard"},
    )
    assert response.status_code == 200, response.text
    names = [item["name_en"] for item in response.json()["sheet"]["spells"]]
    assert "Misty Step" not in names


def test_unknown_spell_cannot_be_removed(client: TestClient) -> None:
    sheet = _clone(client, "fighter-2-wizard-3", "spells-remove-unknown")
    response = client.request(
        "DELETE",
        "/api/v1/characters/spells-remove-unknown/spells",
        json={
            "version": sheet["character"]["version"],
            "name_en": "Wish",
            "class_key": "wizard",
        },
    )
    assert response.status_code == 422
