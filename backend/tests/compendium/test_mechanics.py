"""Читання похідних індексів механік: битий файл не валить застосунок."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from dndsheet.compendium.infrastructure.mechanics_index import (
    CLASS_SCHEMA,
    ORIGIN_SCHEMA,
    JsonMechanicsRepository,
)
from dndsheet.shared.rules import CasterProgression, Size

#: Тека для тимчасових файлів — у репозиторії, а не в системному temp:
#: пісочниця Windows-середовища не завжди дає писати в `%TEMP%`.
TMP_ROOT = Path(__file__).resolve().parent / "_tmp_mechanics"


@pytest.fixture()
def tmp_dir() -> Path:
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    TMP_ROOT.mkdir(parents=True)
    yield TMP_ROOT
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _class_record(name: str = "Fighter") -> dict:
    return {
        "name_en": name,
        "source_id": "PHB",
        "hit_die": 10,
        "saving_throws": ["str", "con"],
        "skill_choices": [{"count": 2, "from": ["athletics", "perception"]}],
        "armor_training": ["light", "medium", "heavy", "shield"],
        "weapon_training": ["simple", "martial"],
        "cantrips_known": [0],
        "spells_known": [],
        "spell_slots": [],
        "pact_slots": [],
        "subclass_level": 3,
        "subclass_title": "Martial Archetype",
        "features": [{"name": "Second Wind", "level": 1}],
    }


def _origin_payload() -> dict:
    return {
        "schema": ORIGIN_SCHEMA,
        "species": {
            "human": {
                "name_en": "Human",
                "source_id": "PHB",
                "size": ["medium"],
                "speed": 30,
                "ability_fixed": {"str": 1, "dex": 1},
                "ability_choice": None,
                "darkvision": 0,
            }
        },
        "subspecies": {
            "hill dwarf": {
                "name_en": "Hill Dwarf",
                "source_id": "PHB",
                "size": ["medium"],
                "speed": 25,
                "subrace_of": "dwarf",
                "ability_fixed": {"wis": 1, "con": 2},
                "darkvision": 60,
            }
        },
        "backgrounds": {
            "acolyte": {
                "name_en": "Acolyte",
                "source_id": "PHB",
                "skill_proficiencies": ["insight", "religion"],
                "languages_any_standard": 2,
                "feature": "Shelter of the Faithful",
            }
        },
    }


@pytest.fixture()
def repo(tmp_dir: Path) -> JsonMechanicsRepository:
    classes = tmp_dir / "class-mechanics.json"
    origins = tmp_dir / "origin-mechanics.json"
    _write(classes, {"schema": CLASS_SCHEMA, "classes": {"fighter": _class_record()}})
    _write(origins, _origin_payload())
    return JsonMechanicsRepository(classes_path=classes, origins_path=origins)


def test_classes_are_parsed(repo: JsonMechanicsRepository) -> None:
    assert repo.available()
    fighter = repo.class_mechanics("fighter")
    assert fighter is not None
    assert fighter.hit_die == 10
    assert fighter.skill_limit == 2
    assert fighter.subclass_level == 3
    assert fighter.cantrips_at(1) == 0
    assert fighter.features_at(2) == () or fighter.features_at(2)[0].name_en == "Second Wind"


def test_lookup_is_case_and_punctuation_insensitive(repo: JsonMechanicsRepository) -> None:
    assert repo.species_mechanics("HUMAN") is not None
    assert repo.class_mechanics("  Fighter ") is not None
    assert repo.background_mechanics("ACOLYTE") is not None


def test_species_and_background_fields(repo: JsonMechanicsRepository) -> None:
    human = repo.species_mechanics("human")
    assert human is not None
    assert human.size is Size.MEDIUM
    assert human.ability_bonuses[0].amount == 1

    dwarf = repo.species_mechanics("hill dwarf")
    assert dwarf is not None
    assert dwarf.is_subspecies
    assert dwarf.speed == 25
    assert dwarf.darkvision == 60

    acolyte = repo.background_mechanics("acolyte")
    assert acolyte is not None
    assert acolyte.feature_en == "Shelter of the Faithful"


def test_missing_files_are_reported_not_raised(tmp_dir: Path) -> None:
    repo = JsonMechanicsRepository(classes_path=tmp_dir / "nope.json", origins_path=tmp_dir / "nope2.json")
    assert repo.available() is False
    warnings = repo.warnings()
    assert len(warnings) == 2
    assert "немає індексу" in warnings[0]


def test_broken_json_is_reported(tmp_dir: Path) -> None:
    path = tmp_dir / "class-mechanics.json"
    path.write_text("{не json", encoding="utf-8")
    repo = JsonMechanicsRepository(classes_path=path, origins_path=tmp_dir / "none.json")
    assert repo.available() is False
    assert any("невірний JSON" in warning for warning in repo.warnings())


def test_wrong_schema_is_reported(tmp_dir: Path) -> None:
    path = tmp_dir / "class-mechanics.json"
    _write(path, {"schema": "class-mechanics/99", "classes": {}})
    repo = JsonMechanicsRepository(classes_path=path, origins_path=tmp_dir / "none.json")
    assert repo.available() is False
    assert any("схема" in warning for warning in repo.warnings())


def test_unknown_class_returns_none(repo: JsonMechanicsRepository) -> None:
    assert repo.class_mechanics("bard") is None


def test_pact_progression_parses() -> None:
    assert CasterProgression.parse("1/2") is CasterProgression.HALF
    assert CasterProgression.parse("pact") is CasterProgression.PACT
    assert CasterProgression.parse(None) is None
    assert CasterProgression.HALF.divisor == 2
    assert CasterProgression.ARTIFICER.rounds_up is True
