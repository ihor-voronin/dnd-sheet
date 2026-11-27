"""Похідні характеристики: КЗ, навички, рятівні кидки, швидкість, бонуси виду."""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.inventory import InventoryItem, ItemKind
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiency,
    ProficiencyKind,
    Proficiencies,
    SourceKind,
)
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.domain.services.modifier_resolver import ModifierKind
from dndsheet.shared.kernel import Ability, AbilityScore, Skill

from helpers import make_character


def _with_abilities(rules, **scores):
    abilities = {ability: AbilityScore(10) for ability in Ability}
    for name, value in scores.items():
        abilities[Ability(name)] = AbilityScore(value)
    return make_character(rules, abilities=abilities)


def test_ability_totals_include_species_bonus(rules, calculator) -> None:
    character = _with_abilities(rules, str=15, dex=13, con=14, int=9, wis=11, cha=7)
    character.set_species("human")
    sheet = calculator.compute(character)
    assert sheet.abilities[Ability.STR].base == 15
    assert sheet.abilities[Ability.STR].bonus == 1
    assert sheet.abilities[Ability.STR].total == 16
    assert sheet.ability_modifiers[Ability.STR] == 3
    assert sheet.abilities[Ability.CHA].total == 8


def test_ability_total_is_capped_at_thirty(rules, calculator) -> None:
    character = _with_abilities(rules, str=30)
    character.set_species("human")
    sheet = calculator.compute(character)
    assert sheet.abilities[Ability.STR].total == 30, "30 — максимум характеристики"


def test_ability_choice_is_applied(rules, calculator) -> None:
    character = _with_abilities(rules, cha=14, dex=13, con=10)
    character.set_species("half-elf")
    character.choose_ability_bonuses([Ability.DEX, Ability.CON])
    sheet = calculator.compute(character)
    assert sheet.abilities[Ability.CHA].total == 16  # +2 від виду
    assert sheet.abilities[Ability.DEX].total == 14  # +1 вибір
    assert sheet.abilities[Ability.CON].total == 11
    dex_bonuses = sheet.modifiers.of(ModifierKind.ABILITY, "dex")
    assert dex_bonuses and dex_bonuses[0].source.kind is SourceKind.SPECIES


def test_no_species_means_no_bonus(rules, calculator) -> None:
    sheet = calculator.compute(_with_abilities(rules, str=12))
    assert sheet.abilities[Ability.STR].total == 12
    assert sheet.modifiers.items == ()


@pytest.mark.parametrize(
    ("armor", "shield", "expected"),
    [
        (None, False, 10),  # без броні, DEX 10
        (None, True, 12),
        ((11, None), False, 11),
        ((16, 0), False, 16),
        ((16, 0), True, 18),
        ((14, 2), False, 14),
    ],
)
def test_armor_class(rules, calculator, armor, shield, expected: int) -> None:
    character = _with_abilities(rules, dex=10)
    if armor is not None:
        base, cap = armor
        character.add_item(
            InventoryItem(
                name_en="armor", kind=ItemKind.ARMOR, equipped=True, armor_base=base, dex_cap=cap
            )
        )
    if shield:
        character.add_item(InventoryItem(name_en="shield", kind=ItemKind.SHIELD, equipped=True))
    assert calculator.compute(character).armor_class == expected


def test_dex_bonus_capped_by_heavy_armor(rules, calculator) -> None:
    character = _with_abilities(rules, dex=16)
    character.add_item(
        InventoryItem(
            name_en="chain mail", kind=ItemKind.ARMOR, equipped=True, armor_base=16, dex_cap=0
        )
    )
    sheet = calculator.compute(character)
    assert sheet.armor_class == 16
    assert all(part.label != "dexterity" for part in sheet.armor_class_parts)


def test_unarmored_defense_needs_class_rules(rules, calculator) -> None:
    """Варавр дає 10+DEX+CON — але лише якщо клас є в правилах."""
    character = _with_abilities(rules, dex=14, con=16)
    with pytest.raises(Exception):
        make_character(rules, classes=[CharacterClass("barbarian", 1)])
    assert calculator.compute(character).armor_class == 12


def test_skills_use_proficiency(rules, calculator) -> None:
    character = _with_abilities(rules, dex=14, str=12)
    character.pick(
        Proficiency(
            kind=ProficiencyKind.SKILL,
            value=Skill.ATHLETICS.value,
            source=GrantSource.of(SourceKind.CLASS, "fighter"),
        )
    )
    sheet = calculator.compute(character)
    assert sheet.skills[Skill.ATHLETICS] == 3, "STR +1 і бонус майстерності +2"
    assert sheet.skills[Skill.STEALTH] == 2, "без володіння — лише DEX"


def test_saving_throw_proficiency_from_first_class(rules, calculator) -> None:
    sheet = calculator.compute(make_character(rules))
    assert sheet.saving_throw_proficiency[Ability.STR] is True
    assert sheet.saving_throw_proficiency[Ability.INT] is False


def test_speed_comes_from_species(rules, calculator) -> None:
    character = make_character(rules)
    assert calculator.compute(character).speed == 30
    character.set_species("elf", "wood elf")
    assert calculator.compute(character).speed == 35


def test_passive_perception_includes_proficiency(rules, calculator) -> None:
    character = _with_abilities(rules, wis=14)
    character.set_species("elf")  # ельфи мають Perception
    sheet = calculator.compute(character)
    assert sheet.skills[Skill.PERCEPTION] == 4  # +2 WIS, +2 майстерність
    assert sheet.passive_perception == 14


def test_hp_current_defaults_to_maximum(rules, calculator) -> None:
    sheet = calculator.compute(make_character(rules))
    assert sheet.hit_points.maximum == 10
    assert sheet.hit_points.current == 10


def test_hp_warning_when_current_above_maximum(rules, calculator) -> None:
    from dndsheet.characters.domain.vitals import HitPointState

    character = make_character(rules)
    character.set_hit_points(HitPointState(current=99))
    sheet = calculator.compute(character)
    assert sheet.warnings and "більші за максимум" in sheet.warnings[0]


def test_prepared_limit_warning(rules, calculator) -> None:
    from dndsheet.characters.domain.spells import KnownSpell

    spells = tuple(
        KnownSpell(name_en=f"Spell {index}", level=1, class_key="wizard", prepared=True)
        for index in range(7)
    )
    character = make_character(
        rules,
        classes=[CharacterClass("wizard", 1)],
        abilities={ability: AbilityScore(16) for ability in Ability},
        spells=spells,
    )
    sheet = calculator.compute(character)
    # INT +3 і 1 рівень → 4 підготовлених; 7 — перебір.
    assert any("підготовлено" in warning for warning in sheet.warnings)
