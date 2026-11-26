"""Інваріанти та VO спільного ядра."""

from __future__ import annotations

import pytest

from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import (
    SKILL_ABILITY,
    Ability,
    AbilityScore,
    Armor,
    DiceExpression,
    Skill,
    proficiency_bonus,
)


@pytest.mark.parametrize(
    ("score", "expected"),
    [(1, -5), (3, -4), (7, -2), (8, -1), (9, -1), (10, 0), (11, 0), (12, 1), (16, 3), (20, 5), (30, 10)],
)
def test_ability_modifier_uses_floor(score: int, expected: int) -> None:
    assert AbilityScore(score).modifier == expected


@pytest.mark.parametrize("score", [0, -3, 31])
def test_ability_score_rejects_out_of_range(score: int) -> None:
    with pytest.raises(ValidationError):
        AbilityScore(score)


def test_ability_score_rejects_non_int() -> None:
    with pytest.raises(ValidationError):
        AbilityScore("16")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("level", "expected"),
    [(1, 2), (4, 2), (5, 3), (8, 3), (9, 4), (12, 4), (13, 5), (16, 5), (17, 6), (20, 6)],
)
def test_proficiency_bonus(level: int, expected: int) -> None:
    assert proficiency_bonus(level) == expected


@pytest.mark.parametrize("level", [0, 21, -1])
def test_proficiency_bonus_rejects_invalid_level(level: int) -> None:
    with pytest.raises(ValidationError):
        proficiency_bonus(level)


def test_every_skill_has_ability_mapping() -> None:
    assert set(SKILL_ABILITY) == set(Skill)
    assert len(Skill) == 18


@pytest.mark.parametrize(
    ("expression", "count", "sides", "modifier"),
    [("2d6+3", 2, 6, 3), ("d20", 1, 20, 0), ("4d6-1", 4, 6, -1), (" 1d8 ", 1, 8, 0)],
)
def test_dice_parse(expression: str, count: int, sides: int, modifier: int) -> None:
    dice = DiceExpression.parse(expression)
    assert (dice.count, dice.sides, dice.modifier) == (count, sides, modifier)


def test_dice_bounds_and_average() -> None:
    dice = DiceExpression.parse("2d6+3")
    assert dice.minimum == 5
    assert dice.maximum == 15
    assert dice.average == 10.0
    assert str(dice) == "2d6+3"


def test_dice_roll_stays_in_bounds() -> None:
    dice = DiceExpression.parse("3d8+2")
    for _ in range(50):
        assert dice.minimum <= dice.roll() <= dice.maximum


@pytest.mark.parametrize("expression", ["2d6x", "d", "1d1", "0d6", "101d6", "2d6+", ""])
def test_dice_rejects_invalid(expression: str) -> None:
    with pytest.raises(ValidationError):
        DiceExpression.parse(expression)


def test_armor_validation() -> None:
    with pytest.raises(ValidationError):
        Armor(name="  ", base=12)
    with pytest.raises(ValidationError):
        Armor(name="Щит", base=9)
    with pytest.raises(ValidationError):
        Armor(name="Важка", base=16, dex_cap=-1)
    assert Armor(name="Шкіра", base=11, dex_cap=None).base == 11


def test_ability_enum_values_are_stable() -> None:
    # Значення потрапляють у SheetDocument і в URL, тому їх не можна перейменовувати.
    assert [a.value for a in Ability] == ["str", "dex", "con", "int", "wis", "cha"]
