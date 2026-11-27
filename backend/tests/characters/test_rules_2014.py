"""Звірка з PHB 2014: правила, які лист рахував неправильно або не рахував зовсім.

Кожен тест — одне правило з посиланням на сторінку книги.
"""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.attacks import WeaponProfile, attack_profile
from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.inventory import Inventory, InventoryItem, ItemKind
from dndsheet.characters.domain.proficiencies import ProficiencyKind
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.compendium.infrastructure.mechanics_index import JsonMechanicsRepository
from dndsheet.shared.kernel import Ability, AbilityScore, Skill

from helpers import make_character


@pytest.fixture()
def rules():
    repository = JsonMechanicsRepository()
    if not repository.available():
        pytest.skip("немає індексу механік (content/index/*-mechanics.json)")
    return repository


def _scores(**values: int) -> dict[Ability, AbilityScore]:
    scores = {ability: AbilityScore(10) for ability in Ability}
    for key, value in values.items():
        scores[Ability(key)] = AbilityScore(value)
    return scores


def _sheet(character):
    return DerivedStatsCalculator().compute(character)


# --- мультиклас (PHB, p. 163–164) -------------------------------------------


def test_fighter_multiclass_needs_strength_or_dexterity(rules) -> None:
    fighter = rules.class_mechanics("fighter")
    assert fighter.satisfies_multiclass({Ability.STR: 8, Ability.DEX: 13})
    assert fighter.satisfies_multiclass({Ability.STR: 13, Ability.DEX: 8})
    assert not fighter.satisfies_multiclass({Ability.STR: 12, Ability.DEX: 12})


def test_monk_multiclass_needs_dexterity_and_wisdom(rules) -> None:
    monk = rules.class_mechanics("monk")
    assert not monk.satisfies_multiclass({Ability.DEX: 13, Ability.WIS: 12})
    assert monk.satisfies_multiclass({Ability.DEX: 13, Ability.WIS: 13})


def test_second_class_grants_only_multiclass_proficiencies(rules) -> None:
    character = make_character(
        rules,
        abilities=_scores(int=13, str=13),
        classes=[CharacterClass("wizard", 1), CharacterClass("fighter", 1)],
    )
    owned = character.all_proficiencies()
    assert owned.has(ProficiencyKind.ARMOR, "medium"), "воїн мультикласом дає середню броню"
    assert owned.has(ProficiencyKind.WEAPON, "martial")
    assert not owned.has(ProficiencyKind.ARMOR, "heavy"), "важкої броні мультиклас не дає"
    assert not owned.has(ProficiencyKind.SAVING_THROW, "str"), "порятунки — лише перший клас"


# --- закляття ----------------------------------------------------------------


def test_paladin_prepares_charisma_plus_half_level(rules) -> None:
    character = make_character(
        rules, abilities=_scores(cha=16), classes=[CharacterClass("paladin", 5)]
    )
    casting = _sheet(character).spellcasting.for_class("paladin")
    assert casting.prepared_limit == 3 + 2  # CHA +3, половина від 5 — 2


def test_paladin_has_no_spellcasting_at_level_one(rules) -> None:
    character = make_character(rules, classes=[CharacterClass("paladin", 1)])
    assert _sheet(character).spellcasting.for_class("paladin") is None


def test_pact_magic_does_not_force_multiclass_table(rules) -> None:
    character = make_character(
        rules,
        abilities=_scores(cha=13, str=13),
        classes=[CharacterClass("paladin", 5), CharacterClass("warlock", 1)],
    )
    slots = _sheet(character).spellcasting.slots
    assert dict(slots.by_level) == {1: 4, 2: 2}, "таблиця паладина 5, а не мультикласу"
    assert slots.pact is not None and slots.pact.slots == 1


# --- КЗ, ініціатива, хіти ----------------------------------------------------


def test_monk_loses_unarmored_defense_with_shield(rules) -> None:
    shield = InventoryItem(name_en="Shield", kind=ItemKind.SHIELD, equipped=True)
    monk = make_character(
        rules,
        abilities=_scores(dex=16, wis=16),
        classes=[CharacterClass("monk", 1)],
    )
    assert _sheet(monk).armor_class == 16  # 10 + 3 + 3
    monk.inventory = Inventory(items=(shield,))
    assert _sheet(monk).armor_class == 15  # 10 + 3 + щит 2, без Мудрості


def test_jack_of_all_trades_adds_half_proficiency(rules) -> None:
    bard = make_character(rules, classes=[CharacterClass("bard", 2)])
    sheet = _sheet(bard)
    assert sheet.skills[Skill.ATHLETICS] == 1  # 0 + половина від +2
    assert sheet.initiative == 1


def test_hill_dwarf_gets_hit_point_per_level(rules) -> None:
    plain = make_character(rules, classes=[CharacterClass("fighter", 3)])
    dwarf = make_character(
        rules,
        classes=[CharacterClass("fighter", 3)],
        species_key="dwarf",
        subspecies_key="hill dwarf",
    )
    assert _sheet(dwarf).hit_points.maximum == _sheet(plain).hit_points.maximum + 3


def test_tough_feat_adds_two_per_level(rules) -> None:
    plain = make_character(rules, classes=[CharacterClass("fighter", 4)])
    tough = make_character(
        rules, classes=[CharacterClass("fighter", 4)], feats=("phb-2014/feat/tough",)
    )
    assert _sheet(tough).hit_points.maximum == _sheet(plain).hit_points.maximum + 8


# --- атаки (PHB, p. 146) -------------------------------------------------------


def test_no_proficiency_bonus_without_weapon_proficiency() -> None:
    profile = WeaponProfile(name_en="Longsword", damage="1d8 slashing", group="Martial Melee Weapons")
    trained = attack_profile(profile, strength_modifier=2, dexterity_modifier=0, proficiency=2)
    untrained = attack_profile(
        profile, strength_modifier=2, dexterity_modifier=0, proficiency=2, proficient=False
    )
    assert trained.attack_bonus == 4
    assert untrained.attack_bonus == 2
