"""Механіки на справжніх індексах `content/index/*-mechanics.json`.

Стрибає, якщо індексів немає (свіжий клон). Коли є — перевіряє, що числа
не суперечать книзі: 13 класів 2014, хіт-дайси на місці, підкласи з
правильних рівнів, Pact Magic лише у варлока, види мають бонуси характеристик.
"""

from __future__ import annotations

import pytest

from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.infrastructure.factory import build_service
from dndsheet.shared.rules import CasterProgression

pytestmark = pytest.mark.skipif(
    not build_service().mechanics_available(),
    reason="немає індексів механік content/index/*-mechanics.json",
)


@pytest.fixture(scope="module")
def service() -> CompendiumService:
    return build_service()


def test_all_player_classes_present(service: CompendiumService) -> None:
    keys = {item.key for item in service.class_definitions()}
    core = {
        "barbarian",
        "bard",
        "cleric",
        "druid",
        "fighter",
        "monk",
        "paladin",
        "ranger",
        "rogue",
        "sorcerer",
        "warlock",
        "wizard",
    }
    assert core <= keys
    assert "artificer" in keys, "артифіцер (TCE) — теж клас 2014"


def test_hit_dice_match_the_book(service: CompendiumService) -> None:
    expected = {
        "barbarian": 12,
        "fighter": 10,
        "paladin": 10,
        "ranger": 10,
        "bard": 8,
        "cleric": 8,
        "druid": 8,
        "monk": 8,
        "rogue": 8,
        "warlock": 8,
        "artificer": 8,
        "sorcerer": 6,
        "wizard": 6,
    }
    for key, die in expected.items():
        assert service.class_mechanics(key).hit_die == die, key


def test_saving_throw_proficiencies(service: CompendiumService) -> None:
    expected = {
        "fighter": {"str", "con"},
        "wizard": {"int", "wis"},
        "rogue": {"dex", "int"},
        "warlock": {"wis", "cha"},
        "barbarian": {"str", "con"},
        "cleric": {"wis", "cha"},
    }
    for key, abilities in expected.items():
        saved = {ability.value for ability in service.class_mechanics(key).saving_throws}
        assert saved == abilities, key


def test_subclass_levels(service: CompendiumService) -> None:
    assert service.class_mechanics("cleric").subclass_level == 1
    assert service.class_mechanics("warlock").subclass_level == 1
    assert service.class_mechanics("druid").subclass_level == 2
    assert service.class_mechanics("wizard").subclass_level == 2
    assert service.class_mechanics("fighter").subclass_level == 3


def test_only_warlock_has_pact_magic(service: CompendiumService) -> None:
    pact = [
        item.key
        for item in service.class_definitions()
        if item.caster_progression is CasterProgression.PACT
    ]
    assert pact == ["warlock"]
    warlock = service.class_mechanics("warlock")
    assert warlock.pact_at(1) == (1, 1)
    assert warlock.pact_at(2) == (2, 1)
    assert warlock.pact_at(11) == (3, 5)


def test_full_casters_share_the_slot_table(service: CompendiumService) -> None:
    wizard = service.class_mechanics("wizard")
    cleric = service.class_mechanics("cleric")
    assert wizard.caster_progression is CasterProgression.FULL
    assert wizard.slots_at(3) == cleric.slots_at(3)
    assert wizard.slots_at(3)[:2] == (4, 2)


def test_half_casters_start_at_level_two(service: CompendiumService) -> None:
    paladin = service.class_mechanics("paladin")
    assert paladin.caster_progression is CasterProgression.HALF
    assert all(count == 0 for count in paladin.slots_at(1)), "на 1 рівні слотів немає"
    assert paladin.slots_at(2)[0] == 2


def test_species_have_ability_bonuses(service: CompendiumService) -> None:
    for key in ("human", "elf", "dwarf", "halfling", "tiefling", "half-elf"):
        species = service.species_mechanics(key)
        assert species.ability_bonuses or species.ability_choice, key

    human = service.species_mechanics("human")
    assert {bonus.amount for bonus in human.ability_bonuses} == {1}
    assert len(human.ability_bonuses) == 6, "людина: +1 до всіх шести"


def test_subspecies_inherit_parent_numbers(service: CompendiumService) -> None:
    hill = service.species_mechanics("hill dwarf")
    assert hill.is_subspecies
    assert hill.speed == 25, "швидкість успадкована від дворфа"
    assert hill.darkvision == 60
    fixed = {bonus.ability.value: bonus.amount for bonus in hill.ability_bonuses}
    assert fixed == {"con": 2, "wis": 1}


def test_backgrounds_have_skills(service: CompendiumService) -> None:
    acolyte = service.background_mechanics("acolyte")
    assert {skill.value for skill in acolyte.skill_proficiencies} == {"insight", "religion"}
    assert acolyte.languages_any_standard == 2
    assert acolyte.feature_en == "Shelter of the Faithful"


def test_fighter_skill_list_matches_phb(service: CompendiumService) -> None:
    fighter = service.class_mechanics("fighter")
    assert fighter.skill_limit == 2
    options = {skill.value for skill in fighter.skill_options()}
    assert options == {
        "acrobatics",
        "animal_handling",
        "athletics",
        "history",
        "insight",
        "intimidation",
        "perception",
        "survival",
    }


def test_warlock_spell_limits(service: CompendiumService) -> None:
    warlock = service.class_mechanics("warlock")
    assert warlock.cantrips_at(1) == 2
    assert warlock.spells_known_at(1) == 2
    assert warlock.prepares_spells is False
    assert warlock.spellcasting_ability is not None
    assert warlock.spellcasting_ability.value == "cha"


def test_indexes_are_clean(service: CompendiumService) -> None:
    summary = service.summary()
    assert summary.mechanics is True
    assert service.mechanics_warnings() == ()
