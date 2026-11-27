"""Українські тексти передісторій: переклад окремим шаром.

Корпус лишається джерелом правил; переклад лежить у
`content/translations/backgrounds/*.json` і приєднується за хешем оригіналу.
Перевіряється те, що легко зламати: пошук за хешем, терпимість до файлу без
перекладу, те, що крок «Передісторія» справді віддає український опис, рису й
спорядження, і повнота — жодна передісторія не лишилась англійською.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dndsheet.api.app import create_app
from dndsheet.characters.api import backgrounds_uk, uk_text


@pytest.fixture(scope="module")
def client(tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    data_dir = tmp_path_factory.mktemp("uk-backgrounds-data")
    os.environ["DNDSHEET_DATA_DIR"] = str(data_dir)
    return TestClient(create_app())


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    uk_text.reset()
    yield
    uk_text.reset()


@pytest.fixture()
def content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "translations" / "backgrounds"
    folder.mkdir(parents=True)
    monkeypatch.setenv("DNDSHEET_CONTENT_DIR", str(tmp_path))
    return folder


def test_translation_is_found_by_hash_of_original(content: Path) -> None:
    text = "War has been your life for as long as you care to remember."
    (content / "features-01.json").write_text(
        json.dumps([{"id": uk_text.ident(text), "text_uk": "Війна була вашим життям."}]),
        encoding="utf-8",
    )
    (content / "names.json").write_text(
        json.dumps([{"id": uk_text.ident("Military Rank"), "name_uk": "Військове звання"}]),
        encoding="utf-8",
    )

    assert backgrounds_uk.text_uk(text) == "Війна була вашим життям."
    assert backgrounds_uk.name_uk("Military Rank") == "Військове звання"


def test_wizard_payload_is_enriched_without_touching_the_original(content: Path) -> None:
    description = "You have spent your life in service."
    (content / "descriptions-01.json").write_text(
        json.dumps([{"id": uk_text.ident(description), "text_uk": "Ви присвятили життя службі."}]),
        encoding="utf-8",
    )
    payload = {
        "description": description,
        "feature_en": "Unknown Feature",
        "feature_text": "No translation here.",
        "equipment": [{"text": "uniform", "choices": []}],
    }

    backgrounds_uk.enrich_details(payload)

    assert payload["description_uk"] == "Ви присвятили життя службі."
    # Немає перекладу — немає поля: екран покаже оригінал, а не порожнечу.
    assert "feature_text_uk" not in payload
    assert "text_uk" not in payload["equipment"][0]
    assert payload["equipment"][0]["text"] == "uniform"


def test_equipment_row_keeps_choices(content: Path) -> None:
    (content / "equipment.json").write_text(
        json.dumps(
            [
                {"id": uk_text.ident("bone dice"), "text_uk": "кістки з кості"},
                {"id": uk_text.ident("deck of cards"), "text_uk": "колода карт"},
                {"id": uk_text.ident("bone dice set"), "text_uk": "набір кісток із кості"},
            ]
        ),
        encoding="utf-8",
    )
    row = {"text": "bone dice", "choices": ["bone dice", "deck of cards"]}
    backgrounds_uk.enrich_equipment_row(row)
    assert row["text_uk"] == "кістки з кості"
    assert row["choices_uk"] == ["кістки з кості", "колода карт"]
    # Оригінал лишається: за ним шукають предмет у довіднику.
    assert row["text"] == "bone dice"


def test_wizard_background_step_gives_ukrainian_soldier(client) -> None:  # noqa: ANN001
    draft = client.post("/api/v1/characters/wizard").json()
    step = client.get(
        f"/api/v1/characters/wizard/{draft['draft']['id']}/steps/background"
    ).json()
    soldier = next(
        item for item in step["options"]["backgrounds"] if item["name_en"] == "Soldier"
    )

    assert soldier["description_uk"].startswith("Війна була вашим життям")
    assert soldier["feature_uk"] == "Військове звання"
    assert soldier["feature_text_uk"]
    texts = [row["text_uk"] for row in soldier["equipment"]]
    assert any("знаки" in text for text in texts), texts
    # Гроші з набору рахуються окремо й не залежать від перекладу.
    assert soldier["money"]["gp"] == 10


def test_every_background_has_ukrainian_texts() -> None:
    """Повнота: кожен опис, риса й фраза спорядження мають переклад."""
    from dndsheet.characters.api.background_info import background_details
    from dndsheet.compendium.infrastructure.factory import build_service

    service = build_service()
    missing: list[str] = []
    checked = 0

    for item in service.backgrounds():
        details = background_details(service, item.name_en, item.feature_en)
        if not backgrounds_uk.name_uk(item.name_en):
            missing.append(f"{item.name_en}: назва")
        if details.get("description"):
            checked += 1
            if not details.get("description_uk"):
                missing.append(f"{item.name_en}: опис")
        if details.get("feature_text"):
            checked += 1
            if not details.get("feature_text_uk"):
                missing.append(f"{item.name_en}: риса")
        if item.feature_en and not details.get("feature_uk"):
            missing.append(f"{item.name_en}: назва риси {item.feature_en}")
        for row in details["equipment"]:
            for phrase in [row["text"], *row["choices"]]:
                checked += 1
                if not backgrounds_uk.text_uk(phrase):
                    missing.append(f"{item.name_en}: спорядження {phrase!r}")

    assert checked > 300, "передісторій має бути багато — інакше перевірка нічого не варта"
    assert not missing, f"без перекладу: {missing[:10]}"
