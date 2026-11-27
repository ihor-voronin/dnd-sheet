"""Українські тексти особливостей класів: переклад як окремий шар.

Корпус лишається джерелом правил; переклад лежить у
`content/translations/classes/*.json` і приєднується за хешем оригіналу.
Перевіряється те, що легко зламати: пошук за хешем, терпимість до файлу без
перекладу, те, що крок «Клас» справді віддає `description_uk` і
`name_uk`/`text_uk`, і повнота — жодне вміння не лишилось англійським.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from dndsheet.api.app import create_app
from dndsheet.characters.api import classes_uk, uk_text
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    data_dir = tmp_path_factory.mktemp("uk-classes-data")
    os.environ["DNDSHEET_DATA_DIR"] = str(data_dir)
    return TestClient(create_app())


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    """Кеш перекладів — на процес і на шлях, тому між тестами його скидаємо."""
    uk_text.reset()
    yield
    uk_text.reset()


@pytest.fixture()
def content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "translations" / "classes"
    folder.mkdir(parents=True)
    monkeypatch.setenv("DNDSHEET_CONTENT_DIR", str(tmp_path))
    return folder


def test_name_and_text_are_found_by_hash_of_original(content: Path) -> None:
    text = "While you are not wearing any armor, your Armor Class equals 10 + your Dexterity modifier."
    (content / "names.json").write_text(
        json.dumps([{"id": uk_text.ident("Rage"), "name_uk": "Лють"}]),
        encoding="utf-8",
    )
    (content / "texts-01.json").write_text(
        json.dumps([{"id": uk_text.ident(text), "text_uk": "Поки ви не носите броні…"}]),
        encoding="utf-8",
    )

    assert classes_uk.name_uk("Rage") == "Лють"
    assert classes_uk.text_uk(text) == "Поки ви не носите броні…"


def test_feature_without_translation_keeps_english(content: Path) -> None:
    feature = {"name_en": "Rage", "text": "In battle, you fight with primal ferocity."}
    classes_uk.enrich_feature(feature)
    # Немає перекладу — немає поля: екран покаже оригінал, а не порожнечу.
    assert "name_uk" not in feature
    assert "text_uk" not in feature
    assert feature["text"].startswith("In battle")


def test_broken_file_does_not_break_the_rest(content: Path) -> None:
    (content / "broken.json").write_text("{ це не json", encoding="utf-8")
    (content / "names.json").write_text(
        json.dumps([{"id": uk_text.ident("Rage"), "name_uk": "Лють"}]),
        encoding="utf-8",
    )
    assert classes_uk.name_uk("Rage") == "Лють"


def test_wizard_class_step_gives_ukrainian_barbarian(client) -> None:  # noqa: ANN001
    """Крок «Клас» віддає український опис і текст «Rage»."""
    draft = client.post("/api/v1/characters/wizard").json()
    step = client.get(f"/api/v1/characters/wizard/{draft['draft']['id']}/steps/class").json()
    barbarian = next(item for item in step["options"]["classes"] if item["key"] == "barbarian")

    assert barbarian["description_uk"]
    features = {item["name_en"]: item for item in barbarian["feature_texts"]}
    assert features["Rage"]["name_uk"] == "Лють"
    assert "лютт" in features["Rage"]["text_uk"].casefold()
    assert features["Unarmored Defense"]["name_uk"] == "Оборона без броні"
    # Оригінал лишається поруч — з нього звіряють з книгою.
    assert features["Rage"]["text"].startswith("In battle")


def test_every_class_feature_has_ukrainian_name_and_text() -> None:
    """Повнота: жодне класове вміння й жоден опис класу не лишились англійськими."""
    from dndsheet.characters.api.features import class_details
    from dndsheet.compendium.infrastructure.factory import build_service

    service = build_service()
    missing: list[str] = []
    checked = 0

    for definition in service.class_definitions():
        details = class_details(service, definition.key)
        if details.get("description") and not details.get("description_uk"):
            missing.append(f"{definition.key}: опис класу")
        for feature in details["features"]:
            checked += 1
            if not feature.get("name_uk"):
                missing.append(f"{definition.key}: назва {feature['name_en']}")
            if feature.get("text") and not feature.get("text_uk"):
                missing.append(f"{definition.key}: {feature['name_en']}")

    assert checked > 200, "класових умінь має бути багато — інакше перевірка нічого не варта"
    assert not missing, f"без перекладу: {missing[:10]}"


def test_every_mechanics_feature_name_has_ukrainian_name() -> None:
    """Список «усі вміння за рівнями» й вкладка «Уміння» беруть назви з індексу
    механік — там варіанти («Extra Attack (2)», «Destroy Undead (CR 1)»), і вони
    теж мають бути українською, інакше список мішає дві мови."""
    from dndsheet.compendium.infrastructure.factory import build_service

    service = build_service()
    missing = {
        feature.name_en
        for definition in service.class_definitions()
        for feature in definition.features
        if not classes_uk.name_uk(feature.name_en)
    }
    assert not missing, f"без перекладу: {sorted(missing)[:10]}"
