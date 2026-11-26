"""Закляття не з класу: вид (тифлінг, високий ельф) і підклас (домен жреця)."""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import Ability, AbilityScore

from helpers import make_character

A = Ability


def _scores(**values: int) -> dict[Ability, AbilityScore]:
    return {A(name): AbilityScore(score) for name, score in values.items()}


def test_tiefling_grants_thaumaturgy(rules) -> None:
    character = make_character(rules, species_key="tiefling", ability_bonus_choices=())
    sheet = DerivedStatsCalculator().compute(character)
    granted = {(item.name_en, item.spell_level, item.source) for item in sheet.granted_spells}
    assert ("thaumaturgy", 0, "species") in granted
    # hellish rebuke — з 3 рівня, тому на 1 його ще немає.
    assert all(item.name_en != "hellish rebuke" for item in sheet.granted_spells)


def test_high_elf_choice_is_required_and_kept(rules) -> None:
    base = dict(
        abilities=_scores(str=8, dex=14, con=13, int=15, wis=10, cha=12),
        species_key="elf",
        subspecies_key="high elf",
        classes=[CharacterClass(class_key="wizard", level=1)],
    )
    with pytest.raises(ValidationError, match="обрано 0"):
        Character(id="c-1", name="Ельф", rules=rules, spell_choices=(), **base)

    character = Character(id="c-1", name="Ельф", rules=rules, spell_choices=("fire bolt",), **base)
    assert character.spell_choices == ("fire bolt",)
    with pytest.raises(ValidationError, match="повторюватися"):
        character.set_spell_choices(("fire bolt", "fire bolt"))
    with pytest.raises(ValidationError, match="обрано 2"):
        character.set_spell_choices(("fire bolt", "light"))


def test_species_without_choice_cannot_take_one(rules) -> None:
    with pytest.raises(ValidationError, match="не дає вибору"):
        Character(
            id="c-1",
            name="Людина",
            abilities=_scores(str=10, dex=10, con=10, int=10, wis=10, cha=10),
            rules=rules,
            classes=[CharacterClass(class_key="fighter", level=1)],
            species_key="human",
            spell_choices=("light",),
        )


def test_cleric_domain_spells_are_always_prepared(rules) -> None:
    character = Character(
        id="c-1",
        name="Жрець",
        abilities=_scores(str=12, dex=10, con=14, int=10, wis=15, cha=8),
        rules=rules,
        classes=[
            CharacterClass(class_key="cleric", level=1, subclass_key="phb-2014/subclass/life-domain")
        ],
        species_key="human",
    )
    sheet = DerivedStatsCalculator().compute(character)
    prepared = {
        item.name_en for item in sheet.granted_spells if item.source == "subclass" and item.prepared
    }
    assert prepared == {"bless", "cure wounds"}
    assert character.classes[0].subclass_key == "phb-2014/subclass/life-domain"


def test_cleric_without_domain_has_no_granted_spells(rules) -> None:
    character = Character(
        id="c-1",
        name="Жрець",
        abilities=_scores(str=12, dex=10, con=14, int=10, wis=15, cha=8),
        rules=rules,
        classes=[CharacterClass(class_key="cleric", level=1)],
        species_key="human",
    )
    sheet = DerivedStatsCalculator().compute(character)
    assert sheet.granted_spells == ()
