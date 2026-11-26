"""Максимум хітів: максимум на 1 рівні, середнє далі, кидки, мультиклас."""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.services.hit_points import (
    average_hit_points,
    hit_dice_pool,
    hit_point_maximum,
)
from dndsheet.characters.domain.vitals import HitPointState

from rules_fixture import FIGHTER, ROGUE, WARLOCK, WIZARD

DEFINITIONS = {"fighter": FIGHTER, "warlock": WARLOCK, "wizard": WIZARD, "rogue": ROGUE}


def _entries(*pairs: tuple[str, int]):
    return tuple((CharacterClass(key, level), DEFINITIONS[key]) for key, level in pairs)


def test_average_is_half_die_plus_one() -> None:
    assert average_hit_points(6) == 4
    assert average_hit_points(10) == 6
    assert average_hit_points(12) == 7


@pytest.mark.parametrize(("class_key", "maximum"), [("fighter", 10), ("rogue", 8), ("warlock", 8), ("wizard", 6)])
def test_first_level_takes_maximum_die(class_key: str, maximum: int) -> None:
    _, parts = hit_point_maximum(_entries((class_key, 1)), constitution_modifier=0)
    assert parts[0].label.startswith("level-1-max")
    assert parts[0].label.endswith(f"d{maximum}")
    assert parts[0].value == maximum


def test_constitution_modifier_applies_per_level() -> None:
    maximum, _ = hit_point_maximum(_entries(("fighter", 3)), constitution_modifier=2)
    # 10+2 (1 рівень) + 6+2 + 6+2 (середні)
    assert maximum == 12 + 8 + 8


def test_negative_constitution_still_gives_one_hit_per_level() -> None:
    maximum, _ = hit_point_maximum(_entries(("wizard", 2)), constitution_modifier=-3)
    # 1 рівень: 6-3=3, 2 рівень: 4-3=1 (мінімум 1)
    assert maximum == 4


def test_recorded_rolls_replace_average() -> None:
    state = HitPointState(current=1, rolls=(9, 4))
    maximum, parts = hit_point_maximum(_entries(("fighter", 3)), 1, state)
    # 11 + 10 + 5
    assert maximum == 26
    assert any(part.label.startswith("level-2-roll") for part in parts)


def test_multiclass_uses_each_class_die() -> None:
    maximum, _ = hit_point_maximum(
        _entries(("fighter", 2), ("wizard", 3)), constitution_modifier=1
    )
    # 10+1, 6+1, 4+1, 4+1, 4+1
    assert maximum == 11 + 7 + 5 + 5 + 5


def test_manual_override_wins() -> None:
    state = HitPointState(current=1, override_max=42)
    maximum, parts = hit_point_maximum(_entries(("fighter", 1)), 3, state)
    assert maximum == 42
    assert parts[0].label == "manual-override"


def test_bonus_is_added() -> None:
    state = HitPointState(current=1, bonus=5)
    maximum, _ = hit_point_maximum(_entries(("fighter", 1)), 0, state)
    assert maximum == 15


def test_hit_dice_pool() -> None:
    assert hit_dice_pool(_entries(("fighter", 2), ("wizard", 3))) == {10: 2, 6: 3}


def test_no_classes_means_zero() -> None:
    assert hit_point_maximum((), 2) == (0, ())
