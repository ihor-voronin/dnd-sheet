"""HTTP: еталонні персонажі й механіки довідника.

Тести стрибають без корпусу механік — як і `test_real_mechanics.py`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dndsheet.api.app import create_app

app = create_app()

pytestmark = pytest.mark.skipif(
    not app.state.golden_cases, reason="немає корпусу механік для еталонних персонажів"
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_golden_list(client: TestClient) -> None:
    response = client.get("/api/v1/characters/golden")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    keys = {item["key"] for item in payload["items"]}
    assert keys == {"fighter-1", "warlock-1", "fighter-2-wizard-3"}


def test_golden_fighter_sheet(client: TestClient) -> None:
    sheet = client.get("/api/v1/characters/golden/fighter-1").json()["sheet"]
    assert sheet["character"]["name"]
    assert sheet["character"]["total_level"] == 1
    assert sheet["armor_class"]["value"] == 18
    assert sheet["hit_points"]["maximum"] == 12
    assert sheet["proficiency_bonus"] == 2
    assert sheet["abilities"]["str"]["total"] == 16
    assert sheet["spellcasting"]["caster_level"] == 0
    # Джерела володінь видно: без них неможливо пояснити число.
    athletes = [
        item
        for item in sheet["proficiencies"]
        if item["kind"] == "skill" and item["value"] == "athletics"
    ]
    assert athletes and athletes[0]["source"]["kind"] == "background"


def test_golden_warlock_pact_magic(client: TestClient) -> None:
    sheet = client.get("/api/v1/characters/golden/warlock-1").json()["sheet"]
    casting = sheet["spellcasting"]
    assert casting["slots"]["pact"] == {"slots": 1, "level": 1}
    assert casting["slots"]["by_level"] == {}
    assert casting["classes"][0]["save_dc"] == 13
    assert sheet["darkvision"] == 60
    assert "fire" in sheet["resistances"]


def test_golden_multiclass_slots(client: TestClient) -> None:
    sheet = client.get("/api/v1/characters/golden/fighter-2-wizard-3").json()["sheet"]
    assert sheet["spellcasting"]["caster_level"] == 3
    assert sheet["spellcasting"]["slots"]["by_level"] == {"1": 4, "2": 2}
    assert sheet["proficiency_bonus"] == 3
    assert sheet["hit_dice"] == {"d10": 2, "d6": 3}


def test_golden_warlock_spells_carry_action_meta(client: TestClient) -> None:
    """Вкладка «Дії» показує час, дистанцію й урон закляттів."""
    sheet = client.get("/api/v1/characters/golden/warlock-1").json()["sheet"]
    spells = {item["name_en"]: item for item in sheet["spells"]}

    blast = spells["Eldritch Blast"]
    assert blast["casting_time"] == "1 action"
    assert blast["range"] == "120 feet"
    assert blast["damage"] == {"dice": "1d10", "type": "force"}
    assert blast["attack_roll"] is True
    assert blast["save"] is None

    hex_spell = spells["Hex"]
    assert hex_spell["casting_time"] == "1 bonus action"
    assert hex_spell["concentration"] is True
    assert hex_spell["damage"] == {"dice": "1d6", "type": "necrotic"}

    charm = spells["Charm Person"]
    assert charm["save"] == "wis"
    assert charm["damage"] is None


def test_golden_features_have_descriptions(client: TestClient) -> None:
    """Вкладка «Уміння» показує не лише назви: текст правил іде з довідника."""
    sheet = client.get("/api/v1/characters/golden/fighter-1").json()["sheet"]
    features = {item["name_en"]: item for item in sheet["features"]}

    second_wind = features["Second Wind"]
    assert second_wind["source"] == "class"
    assert "1d10" in second_wind["description"]
    assert "short or long rest" in second_wind["description"]


def test_golden_warlock_weapon_range(client: TestClient) -> None:
    sheet = client.get("/api/v1/characters/golden/warlock-1").json()["sheet"]
    dagger = next(item for item in sheet["attacks"] if item["name_en"] == "Dagger")
    assert dagger["range"] == "20/60 feet", "кинджал можна метати"


def test_golden_fighter_has_second_wind_resource(client: TestClient) -> None:
    sheet = client.get("/api/v1/characters/golden/fighter-1").json()["sheet"]
    resources = {item["key"]: item for item in sheet["feature_resources"]}
    second_wind = resources["fighter:second-wind"]
    assert second_wind["total"] == 1
    assert second_wind["used"] == 0
    assert second_wind["recharge"] == "short"
    assert second_wind["action"] == "bonus"


def test_unknown_golden_case_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/characters/golden/nobody")
    assert response.status_code == 404


def test_golden_export_markdown(client: TestClient) -> None:
    response = client.get("/api/v1/characters/golden/fighter-1/export/markdown")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "Дарія Залізний Крок" in response.text
    assert "Клас захисту" in response.text


def test_golden_export_unknown_format(client: TestClient) -> None:
    assert client.get("/api/v1/characters/golden/fighter-1/export/docx").status_code == 404


# --- механіки через довідник ------------------------------------------------


def test_mechanics_summary(client: TestClient) -> None:
    payload = client.get("/api/v1/compendium/mechanics").json()
    assert payload["available"] is True
    assert payload["classes"] >= 12
    assert payload["species"] >= 9
    assert payload["backgrounds"] >= 10


def test_class_mechanics_endpoint(client: TestClient) -> None:
    payload = client.get("/api/v1/compendium/classes/fighter/mechanics").json()
    assert payload["hit_die"] == 10
    assert payload["saving_throws"] == ["str", "con"]
    assert payload["skill_limit"] == 2
    assert payload["subclass"] == {"title": "Martial Archetype", "level": 3}


def test_unknown_class_mechanics_returns_404(client: TestClient) -> None:
    assert client.get("/api/v1/compendium/classes/nobody/mechanics").status_code == 404


def test_species_subspecies_endpoint(client: TestClient) -> None:
    payload = client.get("/api/v1/compendium/species/dwarf/subspecies").json()
    names = {item["name_en"] for item in payload["items"]}
    assert "Hill Dwarf" in names
    hill = next(item for item in payload["items"] if item["name_en"] == "Hill Dwarf")
    assert hill["speed"] == 25
    assert hill["ability_bonuses"] == {"con": 2, "wis": 1}


def test_background_mechanics_endpoint(client: TestClient) -> None:
    payload = client.get("/api/v1/compendium/backgrounds/acolyte/mechanics").json()
    assert payload["skill_proficiencies"] == ["insight", "religion"]
    assert payload["languages_any_standard"] == 2


def test_golden_fighter_class_choices(client: TestClient) -> None:
    sheet = client.get("/api/v1/characters/golden/fighter-1").json()["sheet"]
    (style,) = sheet["class_choices"]
    assert style["key"] == "fighter:Fighting Style" and style["slots"] == 1
    assert "Defense" in {option["name_en"] for option in style["options"]}
