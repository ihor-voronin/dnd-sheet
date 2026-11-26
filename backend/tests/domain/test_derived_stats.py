"""Обчислювач похідних характеристик: golden-числа."""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.shared.kernel import Ability, AbilityScore, Armor, Skill


def make_character(
    level: int = 3,
    armor: Armor | None = None,
    shield: bool = False,
) -> Character:
    return Character(
        id="c-1",
        name="Елара",
        level=level,
        abilities={
            Ability.STR: AbilityScore(16),
            Ability.DEX: AbilityScore(14),
            Ability.CON: AbilityScore(12),
            Ability.INT: AbilityScore(10),
            Ability.WIS: AbilityScore(13),
            Ability.CHA: AbilityScore(8),
        },
        skill_proficiencies={Skill.ATHLETICS, Skill.PERCEPTION, Skill.SURVIVAL},
        save_proficiencies={Ability.STR, Ability.CON},
        armor=armor,
        shield=shield,
    )


@pytest.fixture(scope="module")
def computed():
    return DerivedStatsCalculator().compute(make_character())


def test_ability_modifiers(computed) -> None:
    assert computed.ability_modifiers == {
        Ability.STR: 3,
        Ability.DEX: 2,
        Ability.CON: 1,
        Ability.INT: 0,
        Ability.WIS: 1,
        Ability.CHA: -1,
    }


def test_proficiency_bonus_for_level_3(computed) -> None:
    assert computed.proficiency_bonus == 2


def test_unarmored_armor_class_without_shield(computed) -> None:
    # 10 + DEX 2
    assert computed.armor_class == 12


def test_unarmored_armor_class_with_shield() -> None:
    computed = DerivedStatsCalculator().compute(make_character(shield=True))
    assert computed.armor_class == 14


def test_light_armor_keeps_dex_bonus() -> None:
    computed = DerivedStatsCalculator().compute(
        make_character(armor=Armor(name="Шкіряна броня", base=11))
    )
    assert computed.armor_class == 13


def test_heavy_armor_caps_dex_bonus() -> None:
    computed = DerivedStatsCalculator().compute(
        make_character(armor=Armor(name="Кольчуга", base=16, dex_cap=0), shield=True)
    )
    # 16 + min(2, 0) + 2 (щит)
    assert computed.armor_class == 18


def test_saving_throws(computed) -> None:
    assert computed.saving_throws == {
        Ability.STR: 5,  # 3 + prof 2
        Ability.DEX: 2,
        Ability.CON: 3,  # 1 + prof 2
        Ability.INT: 0,
        Ability.WIS: 1,
        Ability.CHA: -1,
    }


def test_skill_values(computed) -> None:
    assert computed.skills[Skill.ATHLETICS] == 5
    assert computed.skills[Skill.PERCEPTION] == 3
    assert computed.skills[Skill.SURVIVAL] == 3
    assert computed.skills[Skill.STEALTH] == 2, "без володіння — лише DEX"
    assert computed.skills[Skill.PERSUASION] == -1


def test_initiative_and_passive_perception(computed) -> None:
    assert computed.initiative == 2
    assert computed.passive_perception == 13  # 10 + perception 3


def test_level_scales_proficiency() -> None:
    computed = DerivedStatsCalculator().compute(make_character(level=9))
    assert computed.proficiency_bonus == 4
    assert computed.saving_throws[Ability.STR] == 7
