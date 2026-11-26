"""Формат похідних індексів механік (`contract/mechanics-format.json`).

Складач (`scripts/ingest/mechanics.py`) і читач
(`compendium/infrastructure/mechanics_index.py`) — різні мови, тому контракт
перевіряється на **готових файлах**: обовʼязкові поля, типи, межі, ключі,
форми таблиць. Тест стрибає без індексів (свіжий клон).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CONTENT = ROOT / "content"
CONTRACT = ROOT / "contract" / "mechanics-format.json"

pytestmark = pytest.mark.skipif(
    not (CONTENT / "index" / "class-mechanics.json").is_file(),
    reason="немає content/index/class-mechanics.json",
)


@pytest.fixture(scope="module")
def spec() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def classes() -> dict:
    payload = json.loads(
        (CONTENT / "index" / "class-mechanics.json").read_text(encoding="utf-8")
    )
    return payload


@pytest.fixture(scope="module")
def origins() -> dict:
    payload = json.loads(
        (CONTENT / "index" / "origin-mechanics.json").read_text(encoding="utf-8")
    )
    return payload


def test_schemas_match_contract(spec: dict, classes: dict, origins: dict) -> None:
    assert classes["schema"] == spec["files"]["class"]["schema"]
    assert origins["schema"] == spec["files"]["origin"]["schema"]


def test_class_entries_have_required_fields(spec: dict, classes: dict) -> None:
    required = spec["files"]["class"]["required"]
    problems: list[str] = []
    for key, entry in classes["classes"].items():
        missing = [field for field in required if field not in entry]
        if missing:
            problems.append(f"{key}: немає {missing}")
    assert not problems, "\n".join(problems[:10])


def test_class_keys_are_normalized(classes: dict) -> None:
    for key in classes["classes"]:
        assert key == key.strip().casefold(), f"ключ класу {key!r} не нормалізований"


def test_class_numbers_are_in_range(spec: dict, classes: dict) -> None:
    limits = spec["rules"]
    problems: list[str] = []
    for key, entry in classes["classes"].items():
        if not limits["hit_die"]["min"] <= entry["hit_die"] <= limits["hit_die"]["max"]:
            problems.append(f"{key}: хіт-дайс d{entry['hit_die']}")
        if not entry["saving_throws"]:
            problems.append(f"{key}: без кидків порятунку")
        for ability in entry["saving_throws"]:
            if ability not in limits["abilities"]:
                problems.append(f"{key}: невідома характеристика {ability!r}")
        level = entry.get("subclass_level")
        if level is not None and not 1 <= level <= limits["levels"]:
            problems.append(f"{key}: рівень підкласу {level}")
        progression = entry.get("caster_progression")
        if progression is not None and progression not in limits["caster_progressions"]:
            problems.append(f"{key}: невідомий прогрес заклять {progression!r}")
        for feature in entry["features"]:
            if not 1 <= feature["level"] <= limits["levels"]:
                problems.append(f"{key}: риса {feature['name']} на рівні {feature['level']}")
    assert not problems, "\n".join(problems[:10])


def test_spell_tables_have_canonical_shape(spec: dict, classes: dict) -> None:
    levels = spec["rules"]["levels"]
    spell_levels = spec["rules"]["spell_levels"]
    problems: list[str] = []
    for key, entry in classes["classes"].items():
        slots = entry["spell_slots"]
        if slots and len(slots) != levels:
            problems.append(f"{key}: таблиця слотів на {len(slots)} рядків, треба {levels}")
        for row in slots:
            if len(row) != spell_levels:
                problems.append(f"{key}: рядок слотів на {len(row)} рівнів")
        pact = entry["pact_slots"]
        if pact and len(pact) != levels:
            problems.append(f"{key}: таблиця Pact Magic на {len(pact)} рядків")
        for row in pact:
            if len(row) != 2:
                problems.append(f"{key}: Pact Magic рядок {row}")
    assert not problems, "\n".join(problems[:10])


def test_cantrip_and_known_tables_are_per_level(spec: dict, classes: dict) -> None:
    levels = spec["rules"]["levels"]
    problems: list[str] = []
    for key, entry in classes["classes"].items():
        for field in ("cantrips_known", "spells_known"):
            table = entry.get(field) or []
            if table and len(table) != levels:
                problems.append(f"{key}.{field}: {len(table)} значень, треба {levels}")
    assert not problems, "\n".join(problems[:10])


def test_multiclass_requirements_use_abilities(spec: dict, classes: dict) -> None:
    abilities = set(spec["rules"]["abilities"])
    problems: list[str] = []
    for key, entry in classes["classes"].items():
        for alternative in entry["multiclass_requirements"]:
            extra = set(alternative) - abilities
            if extra:
                problems.append(f"{key}: невідомі характеристики {extra}")
            for score in alternative.values():
                if score < 8:
                    problems.append(f"{key}: вимога {score} < 8")
    assert not problems, "\n".join(problems[:10])


def test_species_entries_have_required_fields(spec: dict, origins: dict) -> None:
    required = spec["files"]["origin"]["required_species"]
    problems: list[str] = []
    for collection in ("species", "subspecies"):
        for key, entry in origins[collection].items():
            missing = [field for field in required if field not in entry]
            if missing:
                problems.append(f"{collection}/{key}: немає {missing}")
    assert not problems, "\n".join(problems[:10])


def test_backgrounds_have_required_fields(spec: dict, origins: dict) -> None:
    required = spec["files"]["origin"]["required_background"]
    problems: list[str] = []
    for key, entry in origins["backgrounds"].items():
        missing = [field for field in required if field not in entry]
        if missing:
            problems.append(f"{key}: немає {missing}")
        if not entry["skill_proficiencies"] and not entry["skill_any"]:
            problems.append(f"{key}: без володінь навичками")
    assert not problems, "\n".join(problems[:10])


def test_species_numbers_are_in_range(spec: dict, origins: dict) -> None:
    rules = spec["rules"]
    problems: list[str] = []
    for collection in ("species", "subspecies"):
        for key, entry in origins[collection].items():
            if not rules["speed"]["min"] <= entry["speed"] <= rules["speed"]["max"]:
                problems.append(f"{collection}/{key}: швидкість {entry['speed']}")
            if not rules["darkvision"]["min"] <= entry["darkvision"] <= rules["darkvision"]["max"]:
                problems.append(f"{collection}/{key}: темний зір {entry['darkvision']}")
            for size in entry["size"]:
                if size not in rules["sizes"]:
                    problems.append(f"{collection}/{key}: розмір {size!r}")
            for ability, bonus in entry["ability_fixed"].items():
                if ability not in rules["abilities"]:
                    problems.append(f"{collection}/{key}: характеристика {ability!r}")
                if not -8 <= bonus <= 8:
                    problems.append(f"{collection}/{key}: бонус {ability} {bonus}")
            # 2022-перевидання (MPMM, RHW) мають вільний розподіл, якого немає
            # в дзеркалі: для них `ability_unresolved: true`, і вибір робить
            # гравець, а не таблиця.
            if (
                not entry["ability_fixed"]
                and not entry["ability_choice"]
                and not entry.get("ability_unresolved")
            ):
                problems.append(f"{collection}/{key}: без бонусів характеристик")
    assert not problems, "\n".join(problems[:10])


def test_subspecies_point_to_existing_species(origins: dict) -> None:
    known = set(origins["species"])
    orphans = sorted(
        key
        for key, entry in origins["subspecies"].items()
        if entry["subrace_of"] and entry["subrace_of"] not in known
    )
    assert not orphans, f"підраси без базового виду: {orphans[:10]}"


def test_variants_are_known_sources(spec: dict, classes: dict) -> None:
    """`variants` перелічує книги-дублі; їх має бути щонайменше дві."""
    for key, entry in classes["classes"].items():
        variants = entry.get("variants") or []
        if variants:
            assert len(variants) >= 2, f"{key}: variants з однією книгою"
