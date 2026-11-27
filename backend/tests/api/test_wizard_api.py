"""HTTP візарда: створити персонажа 1 рівня, повернутись, перезапуститись.

Тести йдуть на справжньому корпусі: так перевіряється не лише домен, а й те,
що вибір у візарді справді приходить із книг (список видів, класів, заклять).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dndsheet.api.app import create_app

#: Тека даних для тестів — у репозиторії: системний temp у пісочниці недоступний.
DATA_DIR = Path(__file__).resolve().parent / "_tmp_wizard_api"


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


FIGHTER_STEPS: list[tuple[str, dict]] = [
    ("species", {"name": "Дарія Залізний Крок", "species_key": "human"}),
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
            "alignment": "lawful good",
            "picks": [
                {"kind": "skill", "value": "athletics", "source": {"kind": "class", "key": "fighter"}},
                {"kind": "skill", "value": "intimidation", "source": {"kind": "class", "key": "fighter"}},
            ],
        },
    ),
    ("equipment", {"items": [{"name_en": "chain mail", "kind": "armor", "armor_base": 16, "dex_cap": 0, "equipped": True}], "money": {"gp": 10}}),
]


def _start(client: TestClient) -> dict:
    response = client.post("/api/v1/characters/wizard")
    assert response.status_code == 200, response.text
    return response.json()


def _walk(client: TestClient, draft_id: str, steps: list[tuple[str, dict]]) -> dict:
    payload: dict = {}
    for step, body in steps:
        response = client.put(
            f"/api/v1/characters/wizard/{draft_id}/steps/{step}", json=body
        )
        assert response.status_code == 200, f"{step}: {response.text}"
        payload = response.json()
    return payload


def test_start_returns_first_step_with_options(client: TestClient) -> None:
    payload = _start(client)
    assert payload["step"] == "species"
    assert payload["locked"] is False
    names = {item["key"] for item in payload["options"]["species"]}
    assert {"human", "dwarf", "elf"} <= names
    dwarf = next(item for item in payload["options"]["species"] if item["key"] == "dwarf")
    assert [child["key"] for child in dwarf["subspecies"]], "підраси приходять разом із видом"
    assert payload["draft"]["next_step"] == "species"
    assert payload["draft"]["ready_to_finish"] is False


def test_locked_step_cannot_be_written(client: TestClient) -> None:
    draft = _start(client)
    response = client.put(
        f"/api/v1/characters/wizard/{draft['draft']['id']}/steps/abilities",
        json={"method": "standard_array", "scores": {}},
    )
    assert response.status_code == 422
    assert "попередній крок" in response.json()["detail"]


def test_class_options_include_subclasses_at_level_one(client: TestClient) -> None:
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={"name": "Тіра", "species_key": "human"},
    )
    step = client.get(f"/api/v1/characters/wizard/{draft_id}/steps/class").json()
    warlock = next(item for item in step["options"]["classes"] if item["key"] == "warlock")
    assert warlock["subclass"]["level"] == 1
    assert warlock["subclass"]["options"], "патрони мають прийти з довідника"
    fighter = next(item for item in step["options"]["classes"] if item["key"] == "fighter")
    assert fighter["subclass"]["options"] == [], "у воїна підклас на 3 рівні"


def test_unknown_subclass_is_rejected_by_server(client: TestClient) -> None:
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={"name": "Тіра", "species_key": "human"},
    )
    response = client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/class",
        json={"class_key": "warlock", "subclass_key": "phb-2014/subclass/nonexistent"},
    )
    assert response.status_code == 422
    assert "підклас" in response.json()["detail"]


def test_full_creation_and_saved_sheet(client: TestClient) -> None:
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    _walk(client, draft_id, FIGHTER_STEPS)

    finish = client.post(f"/api/v1/characters/wizard/{draft_id}/finish")
    assert finish.status_code == 200, finish.text
    payload = finish.json()
    character_id = payload["character_id"]
    sheet = payload["sheet"]

    assert sheet["character"]["name"] == "Дарія Залізний Крок"
    assert sheet["character"]["total_level"] == 1
    assert sheet["abilities"]["str"] == {"base": 15, "bonus": 1, "total": 16, "modifier": 3}
    assert sheet["armor_class"]["value"] == 16
    assert sheet["hit_points"]["maximum"] == 12, "d10 + 2 (CON 14 після бонусу людини)"
    assert sheet["proficiency_bonus"] == 2

    saved = client.get(f"/api/v1/characters/{character_id}")
    assert saved.status_code == 200
    assert saved.json()["sheet"]["character"]["id"] == character_id

    listing = client.get("/api/v1/characters").json()
    assert character_id in {item["id"] for item in listing["items"]}

    # Чернетка після фінішу зникає — персонаж уже не «недобудований».
    assert client.get(f"/api/v1/characters/wizard/{draft_id}").status_code == 404


def test_character_survives_restart(client: TestClient, data_dir: Path) -> None:
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    _walk(client, draft_id, FIGHTER_STEPS)
    character_id = client.post(
        f"/api/v1/characters/wizard/{draft_id}/finish"
    ).json()["character_id"]

    previous = os.environ.get("DNDSHEET_DATA_DIR")
    os.environ["DNDSHEET_DATA_DIR"] = str(data_dir)
    try:
        restarted = TestClient(create_app())
    finally:
        if previous is None:
            os.environ.pop("DNDSHEET_DATA_DIR", None)
        else:
            os.environ["DNDSHEET_DATA_DIR"] = previous

    sheet = restarted.get(f"/api/v1/characters/{character_id}").json()["sheet"]
    assert sheet["character"]["id"] == character_id
    assert sheet["hit_points"]["maximum"] == 12
    assert sheet["armor_class"]["value"] == 16


def test_draft_is_saved_between_requests(client: TestClient) -> None:
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={"name": "Мірта", "species_key": "elf", "subspecies_key": "wood elf"},
    )
    reloaded = client.get(f"/api/v1/characters/wizard/{draft_id}").json()["draft"]
    assert reloaded["name"] == "Мірта"
    assert reloaded["answers"]["species"]["subspecies_key"] == "wood elf"
    assert reloaded["revision"] == 1


def test_stale_revision_returns_409(client: TestClient) -> None:
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={"name": "А", "species_key": "human"},
    )
    response = client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={"name": "Б", "species_key": "human", "revision": 0},
    )
    assert response.status_code == 409


def test_unknown_draft_returns_404(client: TestClient) -> None:
    assert client.get("/api/v1/characters/wizard/nope").status_code == 404
    assert client.get("/api/v1/characters/nope").status_code == 404


def test_abilities_options_explain_point_buy(client: TestClient) -> None:
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={"name": "Хтось", "species_key": "human"},
    )
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/class", json={"class_key": "fighter"}
    )
    step = client.get(f"/api/v1/characters/wizard/{draft_id}/steps/abilities").json()
    options = step["options"]
    assert options["standard_array"] == [15, 14, 13, 12, 10, 8]
    assert options["point_buy"]["budget"] == 27
    assert options["point_buy"]["costs"]["15"] == 9
    assert options["species_bonuses"]["str"] == 1, "людина дає +1 до всього"


# ---------------------------------------------------------------------------
# вибір на 1 рівні: заговори виду, домен жреця, патрон варлока
# ---------------------------------------------------------------------------


def test_class_options_carry_description_and_feature_texts(client: TestClient) -> None:
    """Клас показує не лише числа: «що це за клас» і що робить кожне вміння."""
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={"name": "Дарія", "species_key": "human"},
    )
    step = client.get(f"/api/v1/characters/wizard/{draft_id}/steps/class").json()
    classes = {item["key"]: item for item in step["options"]["classes"]}

    fighter = classes["fighter"]
    assert fighter["description"].startswith("A human in clanging plate armor")
    texts = {item["name_en"]: item["text"] for item in fighter["feature_texts"]}
    assert "Second Wind" in texts
    assert "well of stamina" in texts["Second Wind"]
    # Базові розділи книги теж потрібні: хіти, володіння, спорядження.
    assert "Hit Points" in texts
    # «Quick Build» і підкласи — не вміння 1 рівня, тому їх тут немає.
    assert "Quick Build" not in texts
    assert "Champion" not in texts
    # Навички: скільки з якого списку — для екрана «2 зі списку (8)».
    assert fighter["skill_limit"] == 2
    assert len(fighter["skill_options"]) == 8

    # У артифіцера тексту в корпусі немає — це чесна порожнеча, не помилка.
    assert classes["artificer"]["description"] == ""
    assert classes["artificer"]["feature_texts"] == []


def test_background_options_show_description_and_equipment(client: TestClient) -> None:
    """Передісторія показує опис, рису й спорядження — а не лише назви навичок."""
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={"name": "Дарія", "species_key": "human"},
    )
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/class",
        json={"class_key": "fighter"},
    )
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/abilities",
        json={
            "method": "standard_array",
            "scores": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
        },
    )
    step = client.get(f"/api/v1/characters/wizard/{draft_id}/steps/background").json()
    soldier = next(
        item for item in step["options"]["backgrounds"] if item["key"] == "soldier"
    )

    assert soldier["description"].startswith("War has been your life")
    assert "military rank" in (soldier["feature_en"] or "").casefold()
    assert soldier["feature_text"].startswith("You have a military rank")

    equipment = soldier["equipment"]
    texts = [row["text"] for row in equipment]
    assert "insignia of rank" in texts
    # «bone dice or deck of cards» — вибір книги лишається вибором.
    dice = next(row for row in equipment if row["text"] == "bone dice")
    assert dice["choices"] == ["bone dice", "deck of cards"]
    assert soldier["money"] == {"gp": 10}


def test_equipment_options_carry_background_items(client: TestClient) -> None:
    """Крок «Спорядження» отримує предмети передісторії, щоб додати їх сам."""
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    _walk(client, draft_id, FIGHTER_STEPS[:4])
    step = client.get(f"/api/v1/characters/wizard/{draft_id}/steps/equipment").json()
    background = step["options"]["background"]

    assert background["key"] == "soldier"
    assert any(row["text"] == "common clothes" for row in background["equipment"])
    assert background["money"] == {"gp": 10}


def test_species_options_carry_traits_from_the_book(client: TestClient) -> None:
    """Harengon раніше показувався як «без бонусів» — без жодного вміння."""
    payload = _start(client)
    species = {item["key"]: item for item in payload["options"]["species"]}

    harengon = species["harengon"]
    names = [trait["name_en"] for trait in harengon["traits"]]
    assert "Hare-Trigger" in names
    assert "Rabbit Hop" in names
    assert all(trait["text"] for trait in harengon["traits"])
    assert harengon["description"]
    assert harengon["text_lang"] == "en"

    # Опис приходить і для підрас — включно з тими, що описані в главі книги.
    wood = next(item for item in species["elf"]["subspecies"] if item["key"] == "wood elf")
    assert wood["traits"]


def test_species_options_mark_required_subspecies(client: TestClient) -> None:
    payload = _start(client)
    species = {item["key"]: item for item in payload["options"]["species"]}

    assert species["elf"]["subspecies_required"] is True
    assert species["dwarf"]["subspecies_required"] is True
    # Людина без «Variant Human» — звичайний, повний вид.
    assert species["human"]["subspecies_required"] is False


def test_subspecies_is_enforced_by_the_server(client: TestClient) -> None:
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    response = client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={"name": "Ільвен", "species_key": "elf"},
    )
    assert response.status_code == 422
    assert "підрасу" in response.text

    response = client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={"name": "Ільвен", "species_key": "elf", "subspecies_key": "wood elf"},
    )
    assert response.status_code == 200, response.text


def test_species_options_carry_cantrip_grants(client: TestClient) -> None:
    payload = _start(client)
    species = {item["key"]: item for item in payload["options"]["species"]}
    assert species["tiefling"]["shared_cantrips"] == ["thaumaturgy"]
    elf = species["elf"]
    high = next(item for item in elf["subspecies"] if item["key"] == "high elf")
    assert high["cantrip_choice"] == {"from_class": "wizard", "count": 1}
    assert payload["options"]["class_cantrips"]["wizard"], "список заговорів візарда"


def test_class_options_show_subclass_spells(client: TestClient) -> None:
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={"name": "Хтось", "species_key": "human"},
    )
    step = client.get(f"/api/v1/characters/wizard/{draft_id}/steps/class").json()
    classes = {item["key"]: item for item in step["options"]["classes"]}

    life = next(
        item for item in classes["cleric"]["subclass"]["options"] if item["id"].endswith("/life-domain")
    )
    assert life["grants"] == {"prepared": ["bless", "cure wounds"], "expanded": []}

    fiend = next(
        item for item in classes["warlock"]["subclass"]["options"] if item["id"].endswith("/the-fiend")
    )
    assert fiend["grants"] == {"prepared": [], "expanded": ["burning hands", "command"]}


def test_high_elf_wizard_keeps_chosen_cantrip(client: TestClient) -> None:
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    steps = [
        (
            "species",
            {
                "name": "Ільвен",
                "species_key": "elf",
                "subspecies_key": "high elf",
                "spell_choices": ["fire bolt"],
            },
        ),
        ("class", {"class_key": "wizard"}),
        (
            "abilities",
            {
                "method": "standard_array",
                "scores": {"str": 8, "dex": 14, "con": 13, "int": 15, "wis": 12, "cha": 10},
            },
        ),
        (
            "background",
            {
                "background_key": "acolyte",
                "picks": [
                    {"kind": "skill", "value": "arcana", "source": {"kind": "class", "key": "wizard"}},
                    {"kind": "skill", "value": "history", "source": {"kind": "class", "key": "wizard"}},
                ],
            },
        ),
        ("equipment", {"items": [], "money": {}}),
        (
            "spells",
            {
                "spells": [
                    {"name_en": "Light", "level": 0, "class_key": "wizard"},
                    {"name_en": "Mage Hand", "level": 0, "class_key": "wizard"},
                    {"name_en": "Magic Missile", "level": 1, "class_key": "wizard", "prepared": True},
                ]
            },
        ),
    ]
    _walk(client, draft_id, steps)
    sheet = client.post(f"/api/v1/characters/wizard/{draft_id}/finish").json()["sheet"]
    names = {spell["name_en"].casefold(): spell for spell in sheet["spells"]}
    assert names["fire bolt"]["source"] == "species", "вибір високого ельфа не загубився"
    assert names["fire bolt"]["level"] == 0
    assert names["magic missile"]["source"] == "class"


def test_cleric_domain_spells_reach_the_sheet(client: TestClient) -> None:
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    steps = [
        ("species", {"name": "Сестра Анна", "species_key": "human"}),
        ("class", {"class_key": "cleric", "subclass_key": "phb-2014/subclass/life-domain"}),
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
    _walk(client, draft_id, steps)
    sheet = client.post(f"/api/v1/characters/wizard/{draft_id}/finish").json()["sheet"]
    granted = {
        spell["name_en"].casefold(): spell
        for spell in sheet["spells"]
        if spell["source"] == "subclass"
    }
    assert set(granted) == {"bless", "cure wounds"}
    assert all(item["always_prepared"] for item in granted.values())


def test_2022_species_requires_ability_spread(client: TestClient) -> None:
    """Без розподілу виду 2022 не створити — і в повідомленні сказано чому."""
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    response = client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={"name": "Хтось", "species_key": "deep gnome"},
    )
    assert response.status_code == 422
    assert "2022" in response.json()["detail"]

    # З розподілом +2/+1 крок проходить.
    response = client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={
            "name": "Хтось",
            "species_key": "deep gnome",
            "ability_spread": {"int": 2, "dex": 1},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["answers"]["ability_spread"] == {"int": 2, "dex": 1}


def test_2022_spread_reaches_the_sheet(client: TestClient) -> None:
    """+2 і +1 — це справжні бонуси: вони у характеристиках листа й у модифікаторі."""
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    steps = [
        (
            "species",
            {
                "name": "Безіменний",
                "species_key": "custom lineage",
                "ability_spread": {"int": 2, "con": 1},
            },
        ),
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
                    {"kind": "skill", "value": "intimidation", "source": {"kind": "class", "key": "fighter"}},
                    # Custom Lineage дає одну навичку на вибір.
                    {"kind": "skill", "value": "perception", "source": {"kind": "species", "key": "custom lineage"}},
                ],
            },
        ),
    ]
    _walk(client, draft_id, steps)
    response = client.post(f"/api/v1/characters/wizard/{draft_id}/finish")
    assert response.status_code == 200, response.text
    sheet = response.json()["sheet"]

    assert sheet["abilities"]["int"]["base"] == 12
    assert sheet["abilities"]["int"]["bonus"] == 2
    assert sheet["abilities"]["int"]["total"] == 14
    assert sheet["abilities"]["con"]["bonus"] == 1
    assert sheet["abilities"]["str"]["bonus"] == 0
    # Бонус походить із виду, тому й у розкладі модифікаторів він із цим джерелом.
    sources = {
        (item["key"], item["value"], item["source"]["kind"])
        for item in sheet["modifiers"]
        if item["kind"] == "ability"
    }
    assert ("int", 2, "species") in sources


def test_2022_spread_cannot_break_the_twenty_cap(client: TestClient) -> None:
    """Межа 20 діє разом із вільним розподілом: 19 + 2 — відмова."""
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={
            "name": "Хтось",
            "species_key": "custom lineage",
            "ability_spread": {"int": 2, "con": 1},
        },
    )
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/class",
        json={"class_key": "fighter"},
    )
    response = client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/abilities",
        json={
            "method": "manual",
            "scores": {"str": 10, "dex": 10, "con": 10, "int": 19, "wis": 10, "cha": 10},
        },
    )
    assert response.status_code == 422
    assert "20" in response.text


def test_equipment_step_keeps_notes_and_weapon_damage(client: TestClient) -> None:
    """Нотатки предмета й власний урон зброї переживають «Далі».

    Без цього «від передісторії» зникало після збереження, і повторний вхід
    у крок додавав спорядження передісторії вдруге.
    """
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    for step, payload in FIGHTER_STEPS[:-1]:
        response = client.put(
            f"/api/v1/characters/wizard/{draft_id}/steps/{step}", json=payload
        )
        assert response.status_code == 200, response.text
    items = [
        {
            "name_en": "common clothes",
            "kind": "gear",
            "quantity": 1,
            "notes": "від передісторії",
        },
        {
            "name_en": "longsword",
            "kind": "weapon",
            "quantity": 1,
            "damage": "1d8 slashing",
        },
    ]
    response = client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/equipment",
        json={"items": items, "money": {"gp": 10}},
    )
    assert response.status_code == 200, response.text

    answers = client.get(
        f"/api/v1/characters/wizard/{draft_id}/steps/equipment"
    ).json()["answers"]
    saved = {row["name_en"]: row for row in answers["items"]}
    assert saved["common clothes"]["notes"] == "від передісторії"
    assert saved["longsword"]["damage"] == "1d8 slashing"


def test_class_features_endpoint_explains_every_feature(client: TestClient) -> None:
    """«Усі вміння класу за рівнями» — з перекладом і текстом правила.

    Список на кроці показує лише назви; тексти приходять окремим запитом, коли
    гравець розгорнув блок. Тут — що цей запит справді дає пояснення.
    """
    payload = client.get("/api/v1/characters/wizard/class-features/sorcerer").json()
    rows = {row["name_en"]: row for row in payload["features"]}

    assert rows["Sorcerous Origin"]["name_uk"] == "Чарівниче походження"
    assert rows["Sorcerous Origin"]["text"]
    assert rows["Sorcerous Origin"]["text_uk"]
    # Опційне вміння з TCoE: його немає в главі PHB, але текст мусить бути.
    assert rows["Magical Guidance"]["name_uk"] == "Магічний провід"
    assert rows["Magical Guidance"]["text"]
    # Заглушка рівня («Sorcerous Origin feature») лишається без тексту — і це
    # видно на екрані окремим підписом, а не порожнечею.
    assert not rows["Sorcerous Origin feature"].get("text")


def test_warlock_patron_expands_spell_choices(client: TestClient) -> None:
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/species",
        json={"name": "Тіра", "species_key": "tiefling"},
    )
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/class",
        json={"class_key": "warlock", "subclass_key": "phb-2014/subclass/the-fiend"},
    )
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/abilities",
        json={
            "method": "standard_array",
            "scores": {"str": 8, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 15},
        },
    )
    client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/background",
        json={
            "background_key": "acolyte",
            "picks": [
                {"kind": "skill", "value": "arcana", "source": {"kind": "class", "key": "warlock"}},
                {"kind": "skill", "value": "deception", "source": {"kind": "class", "key": "warlock"}},
            ],
        },
    )
    step = client.get(f"/api/v1/characters/wizard/{draft_id}/steps/spells").json()
    options = step["options"]
    assert options["granted"], "тифлінг дає thaumaturgy"
    assert {"burning hands", "command"} <= {name.casefold() for name in options["expanded"]}
    names = {entry["name_en"].casefold() for entry in options["spells"]}
    assert {"burning hands", "command"} <= names, "розширений список патрона у виборі"
