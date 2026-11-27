"""Комірки заклять: мультиклас, Pact Magic, DC і бонус атаки."""

from __future__ import annotations

import pytest
from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.services.spell_slots import (
    SpellSlotService,
    pact_magic_for,
    spellcasting_for_classes,
)
from dndsheet.shared.kernel import Ability
from rules_fixture import FIGHTER, WARLOCK, WIZARD


def _entries(*pairs: tuple[str, int]):
    definitions = {"fighter": FIGHTER, "warlock": WARLOCK, "wizard": WIZARD}
    return tuple((CharacterClass(key, level), definitions[key]) for key, level in pairs)


@pytest.mark.parametrize(
    ("classes", "expected"),
    [
        ((("wizard", 1),), 1),
        ((("wizard", 3),), 3),
        ((("wizard", 5),), 5),
        ((("fighter", 1), ("wizard", 3)), 3),
        ((("warlock", 1),), 0),  # Pact Magic не рахується в рівень заклинателя
        ((("warlock", 5), ("wizard", 1)), 1),
        ((("fighter", 5),), 0),
    ],
)
def test_caster_level(classes, expected: int) -> None:
    casting = spellcasting_for_classes(_entries(*classes))
    assert casting.caster_level == expected


@pytest.mark.parametrize(
    ("level", "expected_slots"),
    [
        (1, {1: 2}),
        (2, {1: 3}),
        (3, {1: 4, 2: 2}),
        (5, {1: 4, 2: 3, 3: 2}),
        (9, {1: 4, 2: 3, 3: 3, 4: 3, 5: 1}),
    ],
)
def test_slots_follow_caster_table(level: int, expected_slots: dict[int, int]) -> None:
    casting = spellcasting_for_classes(_entries(("wizard", level)))
    assert dict(casting.slots.by_level) == expected_slots


@pytest.mark.parametrize(
    ("level", "slots", "slot_level"),
    [(1, 1, 1), (2, 2, 1), (3, 2, 2), (5, 2, 3), (11, 3, 5), (20, 4, 5)],
)
def test_pact_magic_table(level: int, slots: int, slot_level: int) -> None:
    pact = pact_magic_for(level)
    assert pact is not None
    assert (pact.slots, pact.slot_level) == (slots, slot_level)


def test_multiclass_slots_are_shared_but_pact_is_separate() -> None:
    casting = spellcasting_for_classes(_entries(("wizard", 3), ("warlock", 2)), {Ability.INT: 16})
    assert casting.caster_level == 3, "рівні волшебника, варлок не додається"
    assert dict(casting.slots.by_level) == {1: 4, 2: 2}
    assert casting.slots.pact is not None
    assert casting.slots.pact.slots == 2


def test_save_dc_and_attack_bonus() -> None:
    casting = spellcasting_for_classes(
        _entries(("wizard", 5)),
        {Ability.INT: 18},
        proficiency_bonus=3,
    )
    wizard = casting.for_class("wizard")
    assert wizard is not None
    assert wizard.modifier == 4
    assert wizard.save_dc == 15  # 8 + 3 + 4
    assert wizard.attack_bonus == 7


def test_known_and_prepared_limits() -> None:
    service = SpellSlotService()
    casting = service.compute(
        _entries(("wizard", 3), ("warlock", 1)),
        {Ability.INT: 14, Ability.CHA: 16},
        proficiency_bonus=2,
    )
    wizard = casting.for_class("wizard")
    warlock = casting.for_class("warlock")
    assert wizard is not None and warlock is not None
    assert wizard.prepares is True
    assert wizard.prepared_limit == 5  # INT +2 і 3 рівні
    assert wizard.spells_known_limit is None, "волшебник готує, а не знає"
    assert warlock.prepares is False
    assert warlock.prepared_limit is None
    assert warlock.spells_known_limit == 2
    assert warlock.cantrips_limit == 2


def test_class_without_spellcasting_is_skipped() -> None:
    casting = spellcasting_for_classes(_entries(("fighter", 5)))
    assert casting.classes == ()
    assert casting.slots.total == 0
