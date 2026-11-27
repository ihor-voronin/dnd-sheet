"""HTTP-шар довідника: форми відповідей, коди помилок, пагінація."""

from __future__ import annotations

from pathlib import Path

import pytest
from dndsheet.api.app import create_app
from fastapi.testclient import TestClient


@pytest.fixture()
def client(content_dir: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DNDSHEET_CONTENT_DIR", str(content_dir))
    return TestClient(create_app())


def test_summary_shape(client: TestClient) -> None:
    body = client.get("/api/v1/compendium/summary").json()
    assert body["entries"] == 17
    assert body["spell_lists"] is True
    assert {"category": "spell", "entries": 5} in body["categories"]
    assert {"source_id": "demo", "title": "Demo Book", "entries": 16} in body["books"]


def test_entries_are_paginated(client: TestClient) -> None:
    body = client.get("/api/v1/compendium/entries", params={"category": "spell", "limit": 2}).json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["has_more"] is True
    assert body["items"][0]["category"] == "spell"


def test_entries_list_has_no_book_text(client: TestClient) -> None:
    items = client.get("/api/v1/compendium/entries", params={"limit": 5}).json()["items"]
    assert items and all("text_en" not in item for item in items)


def test_entries_reject_bad_window(client: TestClient) -> None:
    assert client.get("/api/v1/compendium/entries", params={"limit": 999}).status_code == 422
    assert client.get("/api/v1/compendium/entries", params={"level": 42}).status_code == 422
    assert client.get("/api/v1/compendium/entries", params={"offset": -1}).status_code == 422


def test_entry_card_contains_text(client: TestClient) -> None:
    response = client.get("/api/v1/compendium/entries/demo/class/fighter")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "demo/class/fighter"
    assert body["text_en"].startswith("# Fighter")
    assert body["text_uk"] is None


def test_unknown_entry_is_404(client: TestClient) -> None:
    response = client.get("/api/v1/compendium/entries/demo/class/nope")
    assert response.status_code == 404
    assert "demo/class/nope" in response.json()["detail"]


def test_classes_and_subclasses(client: TestClient) -> None:
    classes = client.get("/api/v1/compendium/classes").json()
    assert classes["total"] == 2
    fighter = next(item for item in classes["items"] if item["name_en"] == "Fighter")
    assert fighter["subclasses"] == 2

    subclasses = client.get("/api/v1/compendium/classes/fighter/subclasses").json()
    assert {item["name_en"] for item in subclasses["items"]} == {"Champion", "Battle Master"}


def test_class_spells_report_source(client: TestClient) -> None:
    body = client.get("/api/v1/compendium/classes/wizard/spells").json()
    assert body["source"] == "spell-lists"
    assert body["total"] == 4
    assert [item["name_en"] for item in body["items"]][:2] == ["Chill Touch", "Burning Hands"]


def test_class_spells_respect_max_level(client: TestClient) -> None:
    body = client.get("/api/v1/compendium/classes/wizard/spells", params={"max_level": 1}).json()
    assert body["total"] == 3


def test_spells_by_level(client: TestClient) -> None:
    body = client.get("/api/v1/compendium/spells", params={"level": 1}).json()
    assert body["total"] == 3


def test_items_by_magic(client: TestClient) -> None:
    body = client.get("/api/v1/compendium/items", params={"magical": True}).json()
    assert body["total"] == 1 and body["items"][0]["name_en"] == "Bag of Holding"


def test_optional_features_by_group(client: TestClient) -> None:
    body = client.get(
        "/api/v1/compendium/optional-features",
        params={"feature_type": "eldritch invocation"},
    ).json()
    assert [item["name_en"] for item in body["items"]] == ["Agonizing Blast"]


def test_search_by_partial_name(client: TestClient) -> None:
    body = client.get("/api/v1/compendium/entries", params={"q": "bag of"}).json()
    assert body["total"] == 1
