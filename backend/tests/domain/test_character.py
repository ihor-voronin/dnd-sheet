"""Поведінка агрегату Character."""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.character import Character
from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import Ability, AbilityScore, Armor, Skill


def make_character(**overrides: object) -> Character:
    params: dict[str, object] = {
        "id": "c-1",
        "name": "  Імʼя  ",
        "level": 1,
        "abilities": {ability: AbilityScore(10) for ability in Ability},
    }
    params.update(overrides)
    return Character(**params)  # type: ignore[arg-type]


def test_name_is_trimmed() -> None:
    assert make_character().name == "Імʼя"


@pytest.mark.parametrize("name", ["", "   "])
def test_name_must_not_be_blank(name: str) -> None:
    with pytest.raises(ValidationError):
        make_character(name=name)


@pytest.mark.parametrize("level", [0, 21, 100])
def test_level_out_of_range(level: int) -> None:
    with pytest.raises(ValidationError):
        make_character(level=level)


def test_all_six_abilities_required() -> None:
    abilities = {ability: AbilityScore(10) for ability in Ability}
    del abilities[Ability.CHA]
    with pytest.raises(ValidationError, match="cha"):
        make_character(abilities=abilities)


def test_set_ability_bumps_version_once_on_change() -> None:
    character = make_character()
    assert character.version == 1

    character.set_ability(Ability.STR, 12)
    assert character.version == 2
    assert character.ability(Ability.STR).value == 12

    character.set_ability(Ability.STR, 12)
    assert character.version == 2, "повторне те саме значення не має змінювати версію"


def test_set_ability_validates() -> None:
    character = make_character()
    with pytest.raises(ValidationError):
        character.set_ability(Ability.STR, 31)


def test_set_level_bumps_version() -> None:
    character = make_character()
    character.set_level(5)
    assert character.version == 2
    assert character.level == 5

    with pytest.raises(ValidationError):
        character.set_level(0)


def test_defaults() -> None:
    character = make_character()
    assert character.armor is None
    assert character.shield is False
    assert character.skill_proficiencies == set()
    assert character.save_proficiencies == set()


def test_armor_and_proficiencies_are_kept() -> None:
    character = make_character(
        armor=Armor(name="Кольчуга", base=16, dex_cap=0),
        shield=True,
        skill_proficiencies={Skill.STEALTH},
        save_proficiencies={Ability.DEX},
    )
    assert character.armor is not None
    assert character.armor.base == 16
    assert character.shield is True
    assert Skill.STEALTH in character.skill_proficiencies
