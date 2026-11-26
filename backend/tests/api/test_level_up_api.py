"""HTTP підвищення рівня на справжньому корпусі.

Перевіряється не лише домен: план мусить принести з книг підкласи й
закляття, а застосування — повернути оновлений лист із новим рівнем.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dndsheet.api.app import create_app

DATA_DIR = Path(__file__).resolve().parent / "_tmp_level_up_api"


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
    # Еталонний Воїн 1 зберігається як звичайний персонаж: далі з ним працює
    # та сама пара ендпоінтів, що й з персонажем гравця.
    fighter = next(case for case in app.state.golden_cases if case.key == "fighter-1")
    app.state.characters.save(replace(fighter.character, id="level-up-fighter"))
    return TestClient(app)


def test_plan_for_saved_character(client: TestClient) -> None:
    response = client.get("/api/v1/characters/level-up-fighter/level-up")
    assert response.status_code == 200
    payload = response.json()

    assert payload["total_level"] == 1
    assert payload["can_level_up"] is True
    plans = {plan["class_key"]: plan for plan in payload["plans"]}
    assert plans["fighter"]["new_level"] == 2
    assert plans["fighter"]["allowed"] is True
    assert plans["fighter"]["hp"]["average"] > 0
    assert "Action Surge" in [item["name_en"] for item in plans["fighter"]["features"]]
    # Новий клас мусить показати вимоги мультикласу, а не мовчазний нуль.
    wizard = plans["wizard"]
    assert wizard["is_new_class"] is True
    assert wizard["requirements"]
    if not wizard["allowed"]:
        assert wizard["blocked_reason"]


def test_level_up_returns_new_sheet(client: TestClient) -> None:
    before = client.get("/api/v1/characters/level-up-fighter").json()["sheet"]
    response = client.post(
        "/api/v1/characters/level-up-fighter/level-up",
        json={
            "class_key": "fighter",
            "hp": {"mode": "average"},
            "version": before["character"]["version"],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["sheet"]["character"]["total_level"] == 2
    assert payload["level_up"]["hp_max_after"] > payload["level_up"]["hp_max_before"]
    assert payload["sheet"]["hit_points"]["maximum"] == payload["level_up"]["hp_max_after"]
    # Лист одразу показує нове вміння класу.
    names = [item["name_en"] for item in payload["sheet"]["features"]]
    assert "Action Surge" in names


def test_stale_version_conflicts(client: TestClient) -> None:
    response = client.post(
        "/api/v1/characters/level-up-fighter/level-up",
        json={"class_key": "fighter", "version": 1},
    )
    assert response.status_code == 409


def test_unknown_class_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/characters/level-up-fighter/level-up",
        json={"class_key": "нічого-такого"},
    )
    assert response.status_code == 404


def test_subclass_choice_comes_from_books(client: TestClient) -> None:
    """На 3 рівні план приносить підкласи з корпусу, а не порожній список."""
    # Спершу піднімаємо до 2 рівня, якщо ще не піднято.
    sheet = client.get("/api/v1/characters/level-up-fighter").json()["sheet"]
    while sheet["character"]["total_level"] < 2:
        response = client.post(
            "/api/v1/characters/level-up-fighter/level-up",
            json={"class_key": "fighter", "version": sheet["character"]["version"]},
        )
        assert response.status_code == 200, response.text
        sheet = response.json()["sheet"]

    plan = client.get("/api/v1/characters/level-up-fighter/level-up").json()["plans"]
    fighter = next(item for item in plan if item["class_key"] == "fighter")
    if fighter["new_level"] != 3:
        pytest.skip("персонаж уже вище 2 рівня")
    assert fighter["subclass"]["required"] is True
    options = fighter["subclass"]["options"]
    assert options, "у корпусі мусять бути підкласи Воїна"
    assert all("/subclass/" in item["id"] for item in options)

    response = client.post(
        "/api/v1/characters/level-up-fighter/level-up",
        json={
            "class_key": "fighter",
            "subclass_key": options[0]["id"],
            "version": sheet["character"]["version"],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["sheet"]["character"]["classes"][0]["subclass"] == options[0]["id"]


def test_twenty_level_character_cannot_grow(client: TestClient) -> None:
    fighter = next(
        case for case in client.app.state.golden_cases if case.key == "fighter-1"
    )
    twenty = replace(
        fighter.character,
        id="level-up-twenty",
        classes=[replace(fighter.character.classes[0], level=20)],
    )
    client.app.state.characters.save(twenty)

    payload = client.get("/api/v1/characters/level-up-twenty/level-up").json()
    assert payload["total_level"] == 20
    assert payload["can_level_up"] is False
    assert payload["plans"] == []


def test_ignored_requirements_are_marked_on_the_sheet(client: TestClient) -> None:
    """Галочка «ігнорувати вимоги» додає клас і лишає слід на листі."""
    from dndsheet.shared.kernel import Ability, AbilityScore

    fighter = next(
        case for case in client.app.state.golden_cases if case.key == "fighter-1"
    )
    # Усі 10: не виконано ні вимоги мага (INT 13), ні навіть Воїна (STR 13).
    weak = replace(
        fighter.character,
        id="level-up-no-requirements",
        abilities={ability: AbilityScore(10) for ability in Ability},
    )
    client.app.state.characters.save(weak)

    plan = next(
        item
        for item in client.get("/api/v1/characters/level-up-no-requirements/level-up").json()[
            "plans"
        ]
        if item["class_key"] == "wizard"
    )
    assert plan["allowed"] is False
    assert plan["requirements"]

    blocked = client.post(
        "/api/v1/characters/level-up-no-requirements/level-up",
        json={"class_key": "wizard"},
    )
    assert blocked.status_code == 422

    response = client.post(
        "/api/v1/characters/level-up-no-requirements/level-up",
        json={"class_key": "wizard", "ignore_requirements": True},
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["level_up"]["requirements_ignored"] is True
    assert payload["level_up"]["ignored_requirements"] == plan["requirements"]
    classes = {item["key"]: item for item in payload["sheet"]["character"]["classes"]}
    assert classes["wizard"]["requirements_ignored"] is True
    assert classes["fighter"]["requirements_ignored"] is False
    waivers = payload["sheet"]["character"]["multiclass_waivers"]
    assert [item["class_key"] for item in waivers] == ["wizard"]
    assert waivers[0]["requirements"] == plan["requirements"]
