"""HTTP листа: зміни під час гри зберігаються й повертаються.

Персонаж створюється справжнім візардом, далі лист змінюється через
`PATCH` / `rest` / `hit-dice` — так перевіряється весь шлях, а не окремий
сервіс.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dndsheet.api.app import create_app

DATA_DIR = Path(__file__).resolve().parent / "_tmp_sheet_api"


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
    return TestClient(app)


def _create_fighter(client: TestClient) -> str:
    draft = client.post("/api/v1/characters/wizard").json()
    draft_id = draft["draft"]["id"]
    steps = [
        ("species", {"name": "Дарія", "species_key": "human"}),
        ("class", {"class_key": "fighter"}),
        (
            "abilities",
            {
                "method": "standard_array",
                "scores": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
            },
        ),
        (
            "background",
            {
                "background_key": "soldier",
                "picks": [
                    {"kind": "skill", "value": "athletics", "source": {"kind": "class", "key": "fighter"}},
                    {"kind": "skill", "value": "perception", "source": {"kind": "class", "key": "fighter"}},
                ],
            },
        ),
        (
            "equipment",
            {
                "items": [
                    {"name_en": "chain mail", "kind": "armor", "armor_base": 16, "dex_cap": 0, "equipped": True},
                    {"name_en": "longsword", "kind": "weapon", "weight_lb": 3, "equipped": True},
                ],
                "money": {"gp": 10},
            },
        ),
    ]
    for step, body in steps:
        response = client.put(f"/api/v1/characters/wizard/{draft_id}/steps/{step}", json=body)
        assert response.status_code == 200, f"{step}: {response.text}"
    finished = client.post(f"/api/v1/characters/wizard/{draft_id}/finish")
    assert finished.status_code == 200, finished.text
    return finished.json()["character_id"]


def _patch(client: TestClient, character_id: str, body: dict) -> dict:
    response = client.patch(f"/api/v1/characters/{character_id}", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_sheet_has_state_resources_and_attacks(client: TestClient) -> None:
    character_id = _create_fighter(client)
    sheet = client.get(f"/api/v1/characters/{character_id}").json()["sheet"]

    assert sheet["state"]["death_saves"] == {"successes": 0, "failures": 0}
    assert sheet["state"]["inspiration"] is False
    assert sheet["resources"]["hit_dice"]["d10"] == {"total": 1, "used": 0}

    attacks = {item["name_en"].casefold(): item for item in sheet["attacks"]}
    assert "longsword" in attacks, "зброя з довідника дає атаку"
    sword = attacks["longsword"]
    assert sword["attack_bonus"] == 5  # майстерність 2 + STR 3
    assert sword["damage"] == "1d8+3 slashing"
    assert sword["ability"] == "str"

    features = {item["name_en"] for item in sheet["features"]}
    assert {"Second Wind", "Fighting Style"} <= features


def test_hp_changes_are_saved(client: TestClient) -> None:
    character_id = _create_fighter(client)
    payload = _patch(client, character_id, {"hp": {"current": 5, "temporary": 3}})
    sheet = payload["sheet"]
    assert sheet["hit_points"]["current"] == 5
    assert sheet["hit_points"]["temporary"] == 3

    reloaded = client.get(f"/api/v1/characters/{character_id}").json()["sheet"]
    assert reloaded["hit_points"]["current"] == 5
    assert reloaded["hit_points"]["temporary"] == 3


def test_override_is_marked_and_can_be_cleared(client: TestClient) -> None:
    character_id = _create_fighter(client)
    sheet = _patch(client, character_id, {"overrides": {"armor_class": 19}})["sheet"]
    assert sheet["armor_class"]["value"] == 19
    assert "armor_class" in sheet["overridden"]
    assert sheet["state"]["overrides"] == {"armor_class": 19}

    sheet = _patch(client, character_id, {"overrides": {"armor_class": None}})["sheet"]
    assert sheet["armor_class"]["value"] == 16
    assert "armor_class" not in sheet["overridden"]


def test_slots_cannot_exceed_the_maximum(client: TestClient) -> None:
    character_id = _create_fighter(client)
    response = client.patch(
        f"/api/v1/characters/{character_id}", json={"slots": {"1": 1}}
    )
    assert response.status_code == 422
    assert "слотів 1 рівня" in response.json()["detail"]


def test_death_saves_inspiration_and_notes(client: TestClient) -> None:
    character_id = _create_fighter(client)
    sheet = _patch(
        client,
        character_id,
        {
            "death_saves": {"successes": 1, "failures": 2},
            "inspiration": True,
            "exhaustion": 2,
            "notes": {"appearance": "шрам на щоці", "notes": "боїться води"},
        },
    )["sheet"]
    assert sheet["state"]["death_saves"] == {"successes": 1, "failures": 2}
    assert sheet["state"]["inspiration"] is True
    assert sheet["state"]["exhaustion"] == 2
    assert sheet["state"]["notes"]["appearance"] == "шрам на щоці"


def test_hit_die_spend_heals(client: TestClient) -> None:
    character_id = _create_fighter(client)
    _patch(client, character_id, {"hp": {"current": 2}})
    response = client.post(
        f"/api/v1/characters/{character_id}/hit-dice", json={"die": 10, "roll": 6}
    )
    assert response.status_code == 200, response.text
    sheet = response.json()["sheet"]
    # 2 + 6 + CON 2 = 10, максимум 12.
    assert sheet["hit_points"]["current"] == 10
    assert sheet["resources"]["hit_dice"]["d10"]["used"] == 1

    again = client.post(
        f"/api/v1/characters/{character_id}/hit-dice", json={"die": 10, "roll": 6}
    )
    assert again.status_code == 422


def test_long_rest_restores_hp_and_dice(client: TestClient) -> None:
    character_id = _create_fighter(client)
    _patch(
        client,
        character_id,
        {"hp": {"current": 1, "temporary": 4}, "hit_dice": {"d10": 1}, "exhaustion": 2},
    )
    response = client.post(f"/api/v1/characters/{character_id}/rest", json={"kind": "long"})
    assert response.status_code == 200, response.text
    payload = response.json()
    sheet = payload["sheet"]
    assert sheet["hit_points"]["current"] == sheet["hit_points"]["maximum"] == 12
    assert sheet["hit_points"]["temporary"] == 4, "тимчасові хіти відпочинок не знімає"
    assert sheet["resources"]["hit_dice"]["d10"]["used"] == 0
    assert sheet["state"]["exhaustion"] == 1

    report = payload["rest"]
    assert report["kind"] == "long"
    assert report["hp_before"] == 1
    assert report["hp_after"] == 12
    assert report["temporary"] == 4
    assert report["hit_dice_before"] == 1
    assert report["hit_dice_after"] == 0
    assert report["exhaustion_before"] == 2
    assert report["exhaustion_after"] == 1


def test_rest_kind_is_validated(client: TestClient) -> None:
    character_id = _create_fighter(client)
    response = client.post(
        f"/api/v1/characters/{character_id}/rest", json={"kind": "nap"}
    )
    assert response.status_code == 422


def test_feature_resource_is_spent_and_reset_by_short_rest(client: TestClient) -> None:
    character_id = _create_fighter(client)
    sheet = _patch(client, character_id, {"feature_used": {"fighter:second-wind": 1}})[
        "sheet"
    ]
    resources = {item["key"]: item for item in sheet["feature_resources"]}
    assert resources["fighter:second-wind"]["used"] == 1

    response = client.post(
        f"/api/v1/characters/{character_id}/rest", json={"kind": "short"}
    )
    assert response.status_code == 200, response.text
    resources = {item["key"]: item for item in response.json()["sheet"]["feature_resources"]}
    assert resources["fighter:second-wind"]["used"] == 0, "Друге дихання — на короткому"


def test_feature_resource_cannot_exceed_its_total(client: TestClient) -> None:
    character_id = _create_fighter(client)
    response = client.patch(
        f"/api/v1/characters/{character_id}",
        json={"feature_used": {"fighter:second-wind": 2}},
    )
    assert response.status_code == 422
    assert "усього 1" in response.json()["detail"]


def test_unknown_feature_resource_is_rejected(client: TestClient) -> None:
    character_id = _create_fighter(client)
    response = client.patch(
        f"/api/v1/characters/{character_id}",
        json={"feature_used": {"wizard:arcane-recovery": 1}},
    )
    assert response.status_code == 422


def _create_cleric(client: TestClient) -> str:
    draft = client.post("/api/v1/characters/wizard").json()
    draft_id = draft["draft"]["id"]
    steps = [
        ("species", {"name": "Сестра Анна", "species_key": "human"}),
        ("class", {"class_key": "cleric", "subclass_key": "phb-2014/subclass/war-domain"}),
        (
            "abilities",
            {
                "method": "standard_array",
                "scores": {"str": 12, "dex": 10, "con": 14, "int": 8, "wis": 15, "cha": 13},
            },
        ),
        (
            "background",
            {
                "background_key": "acolyte",
                "picks": [
                    {"kind": "skill", "value": "history", "source": {"kind": "class", "key": "cleric"}},
                    {"kind": "skill", "value": "persuasion", "source": {"kind": "class", "key": "cleric"}},
                ],
            },
        ),
        ("equipment", {"items": [], "money": {}}),
        (
            "spells",
            {
                "spells": [
                    {"name_en": "Light", "level": 0, "class_key": "cleric"},
                    {"name_en": "Sacred Flame", "level": 0, "class_key": "cleric"},
                    {"name_en": "Guidance", "level": 0, "class_key": "cleric"},
                ]
            },
        ),
    ]
    for step, body in steps:
        response = client.put(f"/api/v1/characters/wizard/{draft_id}/steps/{step}", json=body)
        assert response.status_code == 200, f"{step}: {response.text}"
    finished = client.post(f"/api/v1/characters/wizard/{draft_id}/finish")
    assert finished.status_code == 200, finished.text
    return finished.json()["character_id"]


def test_subclass_features_have_descriptions(client: TestClient) -> None:
    character_id = _create_cleric(client)
    sheet = client.get(f"/api/v1/characters/{character_id}").json()["sheet"]
    features = {item["name_en"]: item for item in sheet["features"]}

    war_priest = features["War Priest"]
    assert war_priest["source"] == "subclass"
    assert war_priest["level"] == 1
    assert war_priest["subclass_name"] == "War Domain"
    assert "bonus action" in war_priest["description"].casefold()
    assert "Channel Divinity" not in features, "вміння 2 рівня на 1 рівні не показується"

    domain = features["Divine Domain"]
    assert domain["source"] == "class"
    assert "domain" in domain["description"].casefold()


def test_resource_recharge_depends_on_rest_kind(client: TestClient) -> None:
    character_id = _create_cleric(client)
    sheet = _patch(client, character_id, {"feature_used": {"cleric:war-priest": 3}})["sheet"]
    resources = {item["key"]: item for item in sheet["feature_resources"]}
    assert resources["cleric:war-priest"]["total"] == 3, "WIS 16 → +3 використання"
    assert resources["cleric:war-priest"]["recharge"] == "long"

    short = client.post(
        f"/api/v1/characters/{character_id}/rest", json={"kind": "short"}
    ).json()["sheet"]
    resources = {item["key"]: item for item in short["feature_resources"]}
    assert resources["cleric:war-priest"]["used"] == 3, "довгий ресурс короткий не повертає"

    long = client.post(
        f"/api/v1/characters/{character_id}/rest", json={"kind": "long"}
    ).json()["sheet"]
    resources = {item["key"]: item for item in long["feature_resources"]}
    assert resources["cleric:war-priest"]["used"] == 0


def test_background_details_come_from_compendium(client: TestClient) -> None:
    character_id = _create_fighter(client)
    sheet = client.get(f"/api/v1/characters/{character_id}").json()["sheet"]
    background = sheet["background_details"]
    assert background["name_en"] == "Soldier"
    assert background["feature_en"] == "Military Rank"
    assert "military rank" in background["feature_text"].casefold()
    assert "athletics" in background["skills"]
    assert "insignia" in background["equipment"]
    assert "Skill Proficiencies" not in background["description"]
    assert background["tools_any"] == 1, "у солдата лишається вибір одного набору"


def test_stale_version_returns_409(client: TestClient) -> None:
    character_id = _create_fighter(client)
    first = _patch(client, character_id, {"hp": {"current": 7}})
    version = first["version"]
    ok = client.patch(
        f"/api/v1/characters/{character_id}",
        json={"hp": {"current": 6}, "version": version},
    )
    assert ok.status_code == 200
    stale = client.patch(
        f"/api/v1/characters/{character_id}",
        json={"hp": {"current": 5}, "version": version},
    )
    assert stale.status_code == 409


def test_equipping_armor_changes_ac(client: TestClient) -> None:
    character_id = _create_fighter(client)
    _patch(client, character_id, {"equip": {"name": "chain mail", "equipped": False}})
    sheet = client.get(f"/api/v1/characters/{character_id}").json()["sheet"]
    assert sheet["armor_class"]["value"] == 12, "без кольчуги: 10 + DEX 2"
    _patch(client, character_id, {"equip": {"name": "chain mail", "equipped": True}})
    sheet = client.get(f"/api/v1/characters/{character_id}").json()["sheet"]
    assert sheet["armor_class"]["value"] == 16


# --- бій: шкода й лікування -------------------------------------------------


def test_damage_eats_temporary_hp_first(client: TestClient) -> None:
    character_id = _create_fighter(client)
    _patch(client, character_id, {"hp": {"current": 10, "temporary": 4}})
    sheet = _patch(client, character_id, {"hp": {"damage": 6}})["sheet"]
    assert sheet["hit_points"]["temporary"] == 0
    assert sheet["hit_points"]["current"] == 8
    assert sheet["hit_points"]["bloodied"] is False, "8 із 12 — ще не половина"


def test_damage_without_known_current_starts_from_maximum(client: TestClient) -> None:
    character_id = _create_fighter(client)
    sheet = _patch(client, character_id, {"hp": {"damage": 5}})["sheet"]
    assert sheet["hit_points"]["current"] == 7, "12 максимум − 5"


def test_damage_stops_at_zero(client: TestClient) -> None:
    character_id = _create_fighter(client)
    sheet = _patch(client, character_id, {"hp": {"damage": 50}})["sheet"]
    assert sheet["hit_points"]["current"] == 0


def test_healing_caps_at_maximum(client: TestClient) -> None:
    character_id = _create_fighter(client)
    _patch(client, character_id, {"hp": {"current": 2}})
    sheet = _patch(client, character_id, {"hp": {"heal": 100}})["sheet"]
    assert sheet["hit_points"]["current"] == sheet["hit_points"]["maximum"] == 12


def test_damage_and_heal_are_separate(client: TestClient) -> None:
    character_id = _create_fighter(client)
    response = client.patch(
        f"/api/v1/characters/{character_id}",
        json={"hp": {"damage": 3, "heal": 3}},
    )
    assert response.status_code == 422


# --- інвентар ----------------------------------------------------------------


def test_item_can_be_added_edited_and_removed(client: TestClient) -> None:
    character_id = _create_fighter(client)
    response = client.post(
        f"/api/v1/characters/{character_id}/items",
        json={
            "item": {
                "name_en": "Flaming Sword",
                "kind": "weapon",
                "damage": "1d8+3 fire",
                "weight_lb": 3,
                "equipped": True,
            }
        },
    )
    assert response.status_code == 200, response.text
    sheet = response.json()["sheet"]
    items = sheet["inventory"]["items"]
    index = next(i for i, item in enumerate(items) if item["name_en"] == "Flaming Sword")
    assert items[index]["damage"] == "1d8+3 fire"
    assert items[index]["kind"] == "weapon"

    attacks = {item["name_en"]: item for item in sheet["attacks"]}
    assert attacks["Flaming Sword"]["damage"] == "1d8+3 fire", "власний урон важливіший"

    edited = client.patch(
        f"/api/v1/characters/{character_id}/items/{index}",
        json={"fields": {"name_en": "Flaming Longsword", "damage": "2d6+3 fire"}},
    )
    assert edited.status_code == 200, edited.text
    sheet = edited.json()["sheet"]
    assert sheet["inventory"]["items"][index]["name_en"] == "Flaming Longsword"
    attacks = {item["name_en"]: item for item in sheet["attacks"]}
    assert attacks["Flaming Longsword"]["damage"] == "2d6+3 fire"

    removed = client.request(
        "DELETE",
        f"/api/v1/characters/{character_id}/items/{index}",
        json={},
    )
    assert removed.status_code == 200, removed.text
    names = [item["name_en"] for item in removed.json()["sheet"]["inventory"]["items"]]
    assert "Flaming Longsword" not in names


def test_item_index_must_exist(client: TestClient) -> None:
    character_id = _create_fighter(client)
    response = client.patch(
        f"/api/v1/characters/{character_id}/items/99",
        json={"fields": {"quantity": 2}},
    )
    assert response.status_code == 422


def test_custom_damage_only_for_weapons(client: TestClient) -> None:
    character_id = _create_fighter(client)
    response = client.post(
        f"/api/v1/characters/{character_id}/items",
        json={"item": {"name_en": "Rope", "kind": "gear", "damage": "1d4 fire"}},
    )
    assert response.status_code == 422
    assert "лише у зброї" in response.json()["detail"]


def test_equipped_armor_can_be_added_directly(client: TestClient) -> None:
    character_id = _create_fighter(client)
    response = client.post(
        f"/api/v1/characters/{character_id}/items",
        json={"item": {"name_en": "plate", "kind": "armor", "armor_base": 18, "dex_cap": 0, "equipped": True}},
    )
    assert response.status_code == 200, response.text
    sheet = response.json()["sheet"]
    assert sheet["armor_class"]["value"] == 18
    equipped = [
        item["name_en"]
        for item in sheet["inventory"]["items"]
        if item["equipped"] and item["kind"] in {"armor", "shield"}
    ]
    assert equipped == ["plate"], "нова броня знімає стару"


def test_armor_can_be_equipped_through_item_edit(client: TestClient) -> None:
    character_id = _create_fighter(client)
    added = client.post(
        f"/api/v1/characters/{character_id}/items",
        json={"item": {"name_en": "leather", "kind": "armor", "armor_base": 11}},
    )
    assert added.status_code == 200, added.text
    sheet = added.json()["sheet"]
    index = next(
        i for i, item in enumerate(sheet["inventory"]["items"]) if item["name_en"] == "leather"
    )
    equipped = client.patch(
        f"/api/v1/characters/{character_id}/items/{index}",
        json={"fields": {"equipped": True}},
    )
    assert equipped.status_code == 200, equipped.text
    sheet = equipped.json()["sheet"]
    assert sheet["armor_class"]["value"] == 13, "легка броня: 11 + DEX 2"
    names = [
        item["name_en"] for item in sheet["inventory"]["items"] if item["equipped"]
    ]
    assert "chain mail" not in names, "нова броня знімає стару"
