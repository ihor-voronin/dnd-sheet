"""HTTP візарда: створити персонажа 1 рівня, повернутись, перезапуститись.

Тести йдуть на справжньому корпусі: так перевіряється не лише домен, а й те,
що вибір у візарді справді приходить із книг (список видів, класів, заклять).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from dndsheet.api.app import create_app
from fastapi.testclient import TestClient

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
    (
        "equipment",
        {
            "items": [{"name_en": "chain mail", "kind": "armor", "armor_base": 16, "dex_cap": 0, "equipped": True}],
            "money": {"gp": 10},
        },
    ),
]


def _start(client: TestClient) -> dict:
    response = client.post("/api/v1/characters/wizard")
    assert response.status_code == 200, response.text
    return response.json()


def _walk(client: TestClient, draft_id: str, steps: list[tuple[str, dict]]) -> dict:
    payload: dict = {}
    for step, body in steps:
        response = client.put(f"/api/v1/characters/wizard/{draft_id}/steps/{step}", json=body)
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
    # Картка у «Моїх персонажах»: вид, клас із рівнем і стан — ті самі числа, що на листі.
    entry = next(item for item in listing["items"] if item["id"] == character_id)
    assert entry["species"]["name_en"] and entry["classes"][0]["level"] == 1
    assert entry["hit_points"] == {"maximum": 12, "current": 12, "temporary": 0}
    assert entry["armor_class"] == 16

    # Чернетка після фінішу зникає — персонаж уже не «недобудований».
    assert client.get(f"/api/v1/characters/wizard/{draft_id}").status_code == 404


def test_character_survives_restart(client: TestClient, data_dir: Path) -> None:
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    _walk(client, draft_id, FIGHTER_STEPS)
    character_id = client.post(f"/api/v1/characters/wizard/{draft_id}/finish").json()["character_id"]

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
    client.put(f"/api/v1/characters/wizard/{draft_id}/steps/class", json={"class_key": "fighter"})
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
    soldier = next(item for item in step["options"]["backgrounds"] if item["key"] == "soldier")

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

    life = next(item for item in classes["cleric"]["subclass"]["options"] if item["id"].endswith("/life-domain"))
    assert life["grants"] == {"prepared": ["bless", "cure wounds"], "expanded": []}

    fiend = next(item for item in classes["warlock"]["subclass"]["options"] if item["id"].endswith("/the-fiend"))
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
    granted = {spell["name_en"].casefold(): spell for spell in sheet["spells"] if spell["source"] == "subclass"}
    assert set(granted) == {"bless", "cure wounds"}
    assert all(item["always_prepared"] for item in granted.values())
    # Клас підкласу — щоб у мультикласі брати складність і атаку від Мудрості жреця.
    assert all(item["class_key"] == "cleric" for item in granted.values())


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
                "species_feat": "phb-2014/feat/alert",
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
            "species_feat": "phb-2014/feat/alert",
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
        response = client.put(f"/api/v1/characters/wizard/{draft_id}/steps/{step}", json=payload)
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

    answers = client.get(f"/api/v1/characters/wizard/{draft_id}/steps/equipment").json()["answers"]
    saved = {row["name_en"]: row for row in answers["items"]}
    assert saved["common clothes"]["notes"] == "від передісторії"
    assert saved["longsword"]["damage"] == "1d8 slashing"


def test_custom_background_reaches_sheet(client: TestClient) -> None:
    """Власна передісторія: гравець пише текст, правила вибору стандартні."""
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    _walk(
        client,
        draft_id,
        [
            ("species", {"name": "Тест Власної", "species_key": "human"}),
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
                    "background_key": "custom",
                    "alignment": "neutral",
                    "picks": [
                        {"kind": "skill", "value": "athletics", "source": {"kind": "class", "key": "fighter"}},
                        {"kind": "skill", "value": "intimidation", "source": {"kind": "class", "key": "fighter"}},
                        {"kind": "skill", "value": "arcana", "source": {"kind": "background", "key": "custom"}},
                        {"kind": "skill", "value": "history", "source": {"kind": "background", "key": "custom"}},
                        {"kind": "tool", "value": "smith's tools", "source": {"kind": "background", "key": "custom"}},
                        {"kind": "language", "value": "dwarvish", "source": {"kind": "background", "key": "custom"}},
                    ],
                    "custom_background": {
                        "name": "Син гільдії ковалів",
                        "description": "Ви виросли біля горна й знаєте ціну металу.",
                        "feature_name": "Звʼязки в гільдії",
                        "feature_text": "Вас приймуть у будь-якій кузні гільдії.",
                        "items": [
                            {"name_en": "dagger", "quantity": 2},
                            {"name_en": "rope", "quantity": 1},
                        ],
                        "equipment": "",
                        "money_gp": 10,
                    },
                },
            ),
            ("equipment", {"items": [], "money": {"gp": 10}}),
        ],
    )
    # Крок «Спорядження» має побачити обрані предмети як звичайне спорядження
    # передісторії — з них він і наповнює інвентар.
    equipment_step = client.get(f"/api/v1/characters/wizard/{draft_id}/steps/equipment").json()
    rows = equipment_step["options"]["background"]["equipment"]
    assert [row["text"] for row in rows] == ["dagger", "rope"]

    finish = client.post(f"/api/v1/characters/wizard/{draft_id}/finish")
    assert finish.status_code == 200, finish.text
    sheet = finish.json()["sheet"]
    details = sheet["background_details"]
    assert details["name_en"] == "Син гільдії ковалів"
    assert details["description"].startswith("Ви виросли біля горна")
    assert details["feature_en"] == "Звʼязки в гільдії"
    assert details["feature_text"] == "Вас приймуть у будь-якій кузні гільдії."
    assert "smith's tools" in details["tools"]
    assert "dwarvish" in details["languages"]
    assert "arcana" in details["skills"]
    assert details["equipment"] == "dagger, rope"
    assert details["money"] == {"gp": 10}


def test_custom_backgrounds_are_not_shared_between_characters(
    client: TestClient,
) -> None:
    """Два персонажі з різними власними передісторіями не плутають текст.

    Раніше деталі кешувалися за назвою з довідника ("Custom Background"), і
    другий персонаж бачив опис першого.
    """
    from dataclasses import replace

    cases = getattr(client.app.state, "golden_cases", [])
    if not cases:
        pytest.skip("немає еталонних персонажів")
    base = next(case for case in cases if case.key == "fighter-1").character
    first = replace(
        base,
        id="custom-bg-first",
        background_key="custom",
        custom_background={
            "name": "Перша гільдія",
            "description": "Текст першої.",
            "feature_name": "Риса перша",
            "feature_text": "Що дає перша.",
            "items": [{"name_en": "dagger", "quantity": 1}],
            "equipment": "",
            "money_gp": 3,
        },
    )
    second = replace(
        base,
        id="custom-bg-second",
        background_key="custom",
        custom_background={
            "name": "Друга гільдія",
            "description": "Текст другої.",
            "feature_name": "Риса друга",
            "feature_text": "Що дає друга.",
            "items": [{"name_en": "rope", "quantity": 2}],
            "equipment": "",
            "money_gp": 7,
        },
    )
    client.app.state.characters.save(first)
    client.app.state.characters.save(second)

    one = client.get("/api/v1/characters/custom-bg-first").json()["sheet"]
    two = client.get("/api/v1/characters/custom-bg-second").json()["sheet"]
    assert one["background_details"]["name_en"] == "Перша гільдія"
    assert one["background_details"]["equipment"] == "dagger"
    assert two["background_details"]["name_en"] == "Друга гільдія"
    assert two["background_details"]["equipment"] == "rope"
    assert two["background_details"]["money"] == {"gp": 7}


def test_custom_background_requires_name(client: TestClient) -> None:
    draft = _start(client)
    draft_id = draft["draft"]["id"]
    _walk(
        client,
        draft_id,
        [
            ("species", {"name": "Без Назви", "species_key": "human"}),
            ("class", {"class_key": "fighter"}),
            (
                "abilities",
                {
                    "method": "standard_array",
                    "scores": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
                },
            ),
        ],
    )
    response = client.put(
        f"/api/v1/characters/wizard/{draft_id}/steps/background",
        json={
            "background_key": "custom",
            "alignment": None,
            "picks": [
                {"kind": "skill", "value": "athletics", "source": {"kind": "class", "key": "fighter"}},
                {"kind": "skill", "value": "intimidation", "source": {"kind": "class", "key": "fighter"}},
            ],
            "custom_background": {"name": "  "},
        },
    )
    assert response.status_code == 422, response.text


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


def test_subclass_endpoint_gives_description_and_path(client: TestClient) -> None:
    """Вибір підкласу: назва, опис-вступ і всі вміння з рівнями й текстами."""
    response = client.get("/api/v1/characters/wizard/subclass/phb-2014/subclass/wild-magic")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["name_uk"] == "Дика магія"
    assert data["description_uk"], "вступ до глави теж перекладений"
    levels = {feature["level"] for feature in data["features"]}
    assert {1, 6, 14, 18} <= levels, "видно, що підклас дає далі"
    assert all(feature.get("name_uk") for feature in data["features"])
    assert all(feature.get("text_uk") for feature in data["features"] if feature["description"])


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


PALADIN_STEPS: list[tuple[str, dict]] = [
    ("species", {"name": "Торін", "species_key": "dwarf", "subspecies_key": "mountain dwarf"}),
    ("class", {"class_key": "paladin"}),
    (
        "abilities",
        {
            "method": "standard_array",
            "scores": {"str": 15, "dex": 10, "con": 13, "int": 8, "wis": 12, "cha": 14},
        },
    ),
]


def test_half_casters_start_casting_at_level_two(client: TestClient) -> None:
    """Паладин і рейнджер чарують з 2 рівня (PHB, pp. 84, 91): крок «Закляття» порожній."""
    draft_id = _start(client)["draft"]["id"]
    classes = client.get(f"/api/v1/characters/wizard/{draft_id}/steps/class").json()["options"]["classes"]
    starts = {item["key"]: item.get("casts_from_level") for item in classes}
    assert starts["paladin"] == 2 and starts["ranger"] == 2
    assert starts["cleric"] == 1 and starts["warlock"] == 1
    assert starts["fighter"] is None

    payload = _walk(client, draft_id, PALADIN_STEPS)
    # Гірський дворф: +2 СИЛ, +2 СТА — підсумок чернетки бачить бонуси виду.
    assert payload["draft"]["ability_bonuses"] == {"str": 2, "con": 2}
    spells = client.get(f"/api/v1/characters/wizard/{draft_id}/steps/spells").json()
    assert spells["options"]["casting"] is None
    assert "2 рівня" in spells["options"]["hint"]


def test_background_list_starts_with_players_handbook(client: TestClient) -> None:
    draft_id = _start(client)["draft"]["id"]
    backgrounds = client.get(f"/api/v1/characters/wizard/{draft_id}/steps/background").json()["options"]["backgrounds"]
    sources = [item["source_id"].casefold() for item in backgrounds if item["key"] != "custom"]
    first_other = next(index for index, source in enumerate(sources) if source != "phb")
    assert all(source != "phb" for source in sources[first_other:])


def test_item_search_puts_exact_name_first(client: TestClient) -> None:
    """«Shield» зі стартового набору не має ставати «Ruidium Shield» через абетку."""
    for name in ("Shield", "Longsword", "Javelin"):
        found = client.get("/api/v1/compendium/items", params={"q": name, "limit": 3}).json()["items"]
        assert found[0]["name_en"] == name, [item["name_en"] for item in found]
