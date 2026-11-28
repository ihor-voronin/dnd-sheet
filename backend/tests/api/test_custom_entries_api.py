"""HTTP власних умінь і заклять: додати, змінити, прибрати — і що їх видно скрізь.

Відповідь кожної зміни — новий лист (як у предметів і заклять), де власне
позначене `source: "custom"` / `custom: true`; експорт показує їх теж.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from dndsheet.api.app import create_app
from fastapi.testclient import TestClient

DATA_DIR = Path(__file__).resolve().parent / "_tmp_custom_entries_api"
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
    if not app.state.golden_cases:
        pytest.skip("немає корпусу механік")
    try:
        yield TestClient(app)
    finally:
        shutil.rmtree(DATA_DIR, ignore_errors=True)


def _clone(client: TestClient, key: str, new_id: str) -> dict:
    case = next(item for item in client.app.state.golden_cases if item.key == key)
    client.app.state.characters.save(replace(case.character, id=new_id))
    return client.get(f"{API}/{new_id}").json()["sheet"]


def _ok(response) -> dict:  # noqa: ANN001
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# власні вміння
# ---------------------------------------------------------------------------


def test_custom_feature_lifecycle(client: TestClient) -> None:
    sheet = _clone(client, "fighter-1", "custom-feature")
    assert sheet["custom_features"] == []

    added = _ok(
        client.post(
            f"{API}/custom-feature/custom-features",
            json={
                "version": sheet["character"]["version"],
                "feature": {"name": "Іскра майстра", "text": "Раз на бій — +1d4.", "origin": "дар майстра", "uses": 2},
            },
        )
    )
    feature_id = added["feature_id"]
    item = added["sheet"]["custom_features"][0]
    assert item == {
        "id": feature_id,
        "name": "Іскра майстра",
        "source": "custom",
        "origin": "дар майстра",
        "level": None,
        "text": "Раз на бій — +1d4.",
        "uses": 2,
        "recharge": "long",
        "used": 0,
        "resource_key": f"custom:{feature_id}",
    }
    resource = next(row for row in added["sheet"]["feature_resources"] if row["key"] == f"custom:{feature_id}")
    assert resource["total"] == 2 and "name_uk" not in resource

    # Лічильник — той самий `feature_used`, що в класових ресурсів.
    spent = _ok(
        client.patch(
            f"{API}/custom-feature", json={"version": added["version"], "feature_used": {f"custom:{feature_id}": 2}}
        )
    )
    assert spent["sheet"]["custom_features"][0]["used"] == 2
    over = client.patch(
        f"{API}/custom-feature", json={"version": spent["version"], "feature_used": {f"custom:{feature_id}": 3}}
    )
    assert over.status_code == 422

    changed = _ok(
        client.patch(
            f"{API}/custom-feature/custom-features/{feature_id}",
            json={"version": spent["version"], "fields": {"uses": 1, "recharge": "short", "level": 3}},
        )
    )
    item = changed["sheet"]["custom_features"][0]
    assert (item["uses"], item["recharge"], item["level"], item["used"]) == (1, "short", 3, 1)

    rested = _ok(client.post(f"{API}/custom-feature/rest", json={"kind": "short"}))
    assert rested["sheet"]["custom_features"][0]["used"] == 0

    plain = _ok(
        client.patch(
            f"{API}/custom-feature/custom-features/{feature_id}",
            json={"version": rested["version"], "fields": {"uses": None, "origin": None}},
        )
    )
    item = plain["sheet"]["custom_features"][0]
    assert (item["uses"], item["recharge"], item["origin"], item["resource_key"]) == (None, None, None, None)

    removed = _ok(
        client.request(
            "DELETE", f"{API}/custom-feature/custom-features/{feature_id}", json={"version": plain["version"]}
        )
    )
    assert removed["sheet"]["custom_features"] == []
    gone = client.request("DELETE", f"{API}/custom-feature/custom-features/{feature_id}", json={})
    assert gone.status_code == 404


def test_custom_feature_errors(client: TestClient) -> None:
    sheet = _clone(client, "fighter-1", "custom-feature-errors")
    url = f"{API}/custom-feature-errors/custom-features"
    version = sheet["character"]["version"]

    assert client.post(url, json={"version": version, "feature": "текст"}).status_code == 422
    assert client.post(url, json={"version": version, "feature": {"name": ""}}).status_code == 422
    assert client.post(url, json={"version": version, "feature": {"name": "x", "colour": "red"}}).status_code == 422
    assert client.post(url, json={"version": version, "feature": {"name": "x", "text": 5}}).status_code == 422
    assert (
        client.post(
            url, json={"version": version, "feature": {"name": "x", "uses": 1, "recharge": "dawn"}}
        ).status_code
        == 422
    )
    # Застаріла версія — конфлікт, як і в будь-якої іншої зміни листа.
    assert client.post(url, json={"version": version - 1, "feature": {"name": "x"}}).status_code == 409

    added = _ok(client.post(url, json={"version": version, "feature": {"name": "x"}}))
    feature_url = f"{url}/{added['feature_id']}"
    assert client.patch(feature_url, json={"fields": "x"}).status_code == 422
    assert client.patch(feature_url, json={"fields": {"colour": "red"}}).status_code == 422
    assert client.patch(f"{url}/nope", json={"fields": {"name": "y"}}).status_code == 404


# ---------------------------------------------------------------------------
# власні закляття
# ---------------------------------------------------------------------------


def test_fighter_gets_a_spell_outside_any_class(client: TestClient) -> None:
    sheet = _clone(client, "fighter-1", "custom-spell-other")
    added = _ok(
        client.post(
            f"{API}/custom-spell-other/spells",
            json={
                "version": sheet["character"]["version"],
                "class_key": "other",
                "name_en": "Полумʼя перстня",
                "level": 2,
                "custom": True,
                "description": "Раз на день: 3d6 вогню.",
                "school": "воплочення",
                "casting_time": "1 дія",
                "range": "18 м",
                "duration": "миттєво",
                "components": "В",
                "concentration": False,
                "ritual": False,
            },
        )
    )
    spell = next(item for item in added["sheet"]["spells"] if item["name_en"] == "Полумʼя перстня")
    assert spell["custom"] is True and spell["class_key"] == "other" and spell["prepared"] is True
    assert (spell["school"], spell["casting_time"], spell["range"]) == ("воплочення", "1 дія", "18 м")

    changed = _ok(
        client.patch(
            f"{API}/custom-spell-other/spells",
            json={
                "version": added["version"],
                "name_en": "Полумʼя перстня",
                "class_key": "other",
                "fields": {"name_en": "Вогонь перстня", "level": 3, "concentration": True},
            },
        )
    )
    spell = next(item for item in changed["sheet"]["spells"] if item["custom"])
    assert (spell["name_en"], spell["level"], spell["concentration"]) == ("Вогонь перстня", 3, True)
    assert spell["description"] == "Раз на день: 3d6 вогню."

    duplicate = client.post(
        f"{API}/custom-spell-other/spells",
        json={"class_key": "other", "name_en": "вогонь перстня", "level": 1, "custom": True},
    )
    assert duplicate.status_code == 422
    assert (
        client.post(
            f"{API}/custom-spell-other/spells",
            json={"class_key": "other", "name_en": "x", "level": 1, "custom": True, "ritual": "так"},
        ).status_code
        == 422
    )

    removed = _ok(
        client.request(
            "DELETE",
            f"{API}/custom-spell-other/spells",
            json={"version": changed["version"], "name_en": "Вогонь перстня", "class_key": "other"},
        )
    )
    assert not any(item["custom"] for item in removed["sheet"]["spells"])


def test_only_custom_spells_are_edited(client: TestClient) -> None:
    sheet = _clone(client, "fighter-2-wizard-3", "custom-spell-edit")
    book = next(item for item in sheet["spells"] if item["class_key"] == "wizard" and not item["custom"])
    url = f"{API}/custom-spell-edit/spells"
    refused = client.patch(
        url, json={"name_en": book["name_en"], "class_key": "wizard", "fields": {"description": "своє"}}
    )
    assert refused.status_code == 422
    assert "лише власне" in refused.json()["detail"]
    assert client.patch(url, json={"name_en": "немає", "class_key": "wizard", "fields": {}}).status_code == 422

    _ok(client.post(url, json={"class_key": "other", "name_en": "Своє", "level": 1, "custom": True}))
    assert client.patch(url, json={"name_en": "Своє", "class_key": "other", "fields": []}).status_code == 422
    assert (
        client.patch(url, json={"name_en": "Своє", "class_key": "other", "fields": {"entry_id": "x"}}).status_code
        == 422
    )


# ---------------------------------------------------------------------------
# експорт
# ---------------------------------------------------------------------------


def test_exports_show_custom_entries(client: TestClient) -> None:
    sheet = _clone(client, "fighter-1", "custom-export")
    added = _ok(
        client.post(
            f"{API}/custom-export/custom-features",
            json={
                "version": sheet["character"]["version"],
                "feature": {
                    "name": "Око ворона",
                    "text": "Бачить крізь туман.",
                    "origin": "амулет",
                    "level": 2,
                    "uses": 1,
                    "recharge": "short",
                },
            },
        )
    )
    _ok(
        client.post(
            f"{API}/custom-export/spells",
            json={
                "version": added["version"],
                "class_key": "other",
                "name_en": "Шепіт амулета",
                "level": 0,
                "custom": True,
                "description": "Чути шепіт.",
                "school": "віщування",
                "ritual": True,
                "concentration": True,
            },
        )
    )

    markdown = _ok_text(client.get(f"{API}/custom-export/export/markdown"))
    assert "Око ворона" in markdown and "власне · амулет · 2 рівень · 1/1, короткий відпочинок" in markdown
    assert "Шепіт амулета" in markdown and "поза класом" in markdown
    assert "віщування" in markdown and "Чути шепіт." in markdown

    printed = _ok_text(client.get(f"{API}/custom-export/print"))
    assert "Власні вміння" in printed and "Бачить крізь туман." in printed
    assert "Шепіт амулета" in printed and "власне" in printed


def _ok_text(response) -> str:  # noqa: ANN001
    assert response.status_code == 200, response.text
    return response.text
