"""Українські тексти видів: переклад як окремий шар, а не правка корпусу.

Корпус лишається джерелом правил; переклад лежить у
`content/translations/species/*.json` і приєднується за хешем оригіналу.
Перевіряється те, що легко зламати: пошук за хешем, терпимість до файлу без
перекладу й те, що екран візарда справді отримує `name_uk`/`text_uk`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from dndsheet.api.app import create_app
from dndsheet.characters.api import trait_uk
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    data_dir = tmp_path_factory.mktemp("uk-data")
    os.environ["DNDSHEET_DATA_DIR"] = str(data_dir)
    return TestClient(create_app())


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    """Кеш перекладів — на процес, тому між тестами його треба скидати."""
    trait_uk._CACHE = None
    yield
    trait_uk._CACHE = None


@pytest.fixture()
def content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "translations" / "species"
    folder.mkdir(parents=True)
    monkeypatch.setenv("DNDSHEET_CONTENT_DIR", str(tmp_path))
    return folder


def test_translation_is_found_by_hash_of_original(content: Path) -> None:
    folder = content
    (folder / "names.json").write_text(
        json.dumps([{"id": trait_uk.ident("Darkvision"), "name_uk": "Темний зір"}]),
        encoding="utf-8",
    )
    text = "You can see in dim light within 60 feet of you as if it were bright light."
    (folder / "texts-01.json").write_text(
        json.dumps([{"id": trait_uk.ident(text), "text_uk": "Ви бачите в тьмяному світлі."}]),
        encoding="utf-8",
    )

    assert trait_uk.name_uk("Darkvision") == "Темний зір"
    assert trait_uk.text_uk(text) == "Ви бачите в тьмяному світлі."


def test_payload_is_enriched_without_touching_the_original(content: Path) -> None:
    text = "Your walking speed is 30 feet."
    description = "Harengons originated in the Feywild."
    (content / "texts-01.json").write_text(
        json.dumps(
            [
                {"id": trait_uk.ident(text), "text_uk": "Ваша швидкість ходьби — 30 футів."},
                {"id": trait_uk.ident(description), "text_uk": "Харегони походять із Фейвайлду."},
            ]
        ),
        encoding="utf-8",
    )
    payload = {
        "description": description,
        "traits": [
            {"name_en": "Speed", "text": text},
            {"name_en": "Unknown Trait", "text": "No translation here."},
        ],
    }

    trait_uk.enrich(payload)

    assert payload["description_uk"] == "Харегони походять із Фейвайлду."
    assert payload["traits"][0]["text_uk"] == "Ваша швидкість ходьби — 30 футів."
    # Немає перекладу — немає поля: екран покаже оригінал, а не порожнечу.
    assert "text_uk" not in payload["traits"][1]
    assert payload["traits"][1]["text"] == "No translation here."


def test_broken_file_does_not_break_the_rest(content: Path) -> None:
    (content / "broken.json").write_text("{ це не json", encoding="utf-8")
    (content / "names.json").write_text(
        json.dumps([{"id": trait_uk.ident("Age"), "name_uk": "Вік"}]),
        encoding="utf-8",
    )
    assert trait_uk.name_uk("Age") == "Вік"


def test_species_api_gives_ukrainian_traits(client) -> None:  # noqa: ANN001
    """Крок «Вид» віддає українські назви й тексти Harengon."""
    draft = client.post("/api/v1/characters/wizard").json()
    step = client.get(f"/api/v1/characters/wizard/{draft['draft']['id']}/steps/species").json()
    harengon = next(item for item in step["options"]["species"] if item["key"] == "harengon")

    assert harengon["description_uk"].startswith("Харегони")
    traits = {trait["name_en"]: trait for trait in harengon["traits"]}
    assert traits["Speed"]["name_uk"] == "Швидкість"
    assert traits["Speed"]["text_uk"]
    assert traits["Hare-Trigger"]["name_uk"] == "Заяча реакція"
    assert traits["Hare-Trigger"]["text_uk"]


def test_every_species_trait_has_ukrainian_name_and_text() -> None:
    """Повнота перекладу: жодне уміння й опис не лишились англійськими."""
    from dndsheet.characters.api.species_traits import species_details
    from dndsheet.compendium.infrastructure.factory import build_service

    service = build_service()
    missing: list[str] = []
    checked = 0

    def check(details: dict, label: str) -> None:
        nonlocal checked
        texts: list[tuple[str, str]] = []
        if details.get("description"):
            texts.append((details["description"], f"{label}: опис"))
        for trait in details.get("traits") or []:
            if not trait_uk.name_uk(trait["name_en"]):
                missing.append(f"{label}: назва {trait['name_en']}")
            if trait["text"]:
                texts.append((trait["text"], f"{label}: {trait['name_en']}"))
        for entry, where in texts:
            checked += 1
            if not trait_uk.text_uk(entry):
                missing.append(where)

    for species in service.species_list():
        check(species_details(service, species.name_en) or {}, species.name_en)
        # Підрасу без батька не розібрати: половина з них описана в тексті виду.
        for child in service.subspecies_of(species.name_en):
            check(
                species_details(service, child.name_en, parent_name_en=species.name_en) or {},
                child.name_en,
            )

    assert checked > 300, "видів має бути багато — інакше перевірка нічого не варта"
    assert not missing, f"без перекладу: {missing[:10]}"
