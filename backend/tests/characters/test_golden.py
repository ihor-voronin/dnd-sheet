"""Золоті персонажі: числа зобовʼязані збігатися з правилами 2014.

Ці тести — головний доказ етапу 2. Кожне очікуване число можна перевірити
з книгою:

* Воїн 1: кість хітів d10 → 10 + 2 (CON 15) = 12; КЗ 16 (кольчуга) + 2 (щит) = 18;
  рятівні кидки STR/CON по +2 майстерності;
* Варлок 1: d8 → 8 + 1 (CON 13) = 9; Pact Magic 1 комірка 1 рівня; DC 8+2+3 = 13;
  КЗ 11 (шкіряна) + 1 (DEX 13) = 12;
* Воїн 2 / Візард 3: сумарний рівень 5 → бонус 3; рівень заклинателя 3 →
  комірки 4×1 і 2×2; хіти 33; КЗ 16 (кольчуга, без бонусу DEX).
"""

from __future__ import annotations

import pytest
from dndsheet.characters.application.golden import build_golden_cases
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.shared.kernel import Ability, Skill


@pytest.fixture()
def cases(any_rules):
    return {case.key: case for case in build_golden_cases(any_rules)}


def test_three_golden_cases(cases) -> None:
    assert set(cases) == {"fighter-1", "warlock-1", "fighter-2-wizard-3"}


def test_fighter_numbers(cases, calculator: DerivedStatsCalculator) -> None:
    sheet = calculator.compute(cases["fighter-1"].character)

    assert sheet.total_level == 1
    assert sheet.proficiency_bonus == 2
    # Людина: +1 до всього, тому 15 → 16.
    assert sheet.abilities[Ability.STR].total == 16
    assert sheet.abilities[Ability.STR].bonus == 1
    assert sheet.ability_modifiers[Ability.STR] == 3
    # Кольчуга 16 + щит 2, бонус DEX не додається (dex_cap=0).
    assert sheet.armor_class == 18
    # d10 + CON +2.
    assert sheet.hit_points.maximum == 12
    assert sheet.hit_points.current == 12
    assert sheet.hit_dice == {10: 1}
    # Володіння кидками: лише STR і CON, по +2.
    assert sheet.saving_throws[Ability.STR] == 5
    assert sheet.saving_throws[Ability.CON] == 4
    assert sheet.saving_throws[Ability.DEX] == 2
    assert sheet.saving_throw_proficiency[Ability.DEX] is False
    # Солдат дає Атлетику й Залякування, клас — Спостережливість і Виживання.
    assert sheet.skills[Skill.ATHLETICS] == 5
    assert sheet.skills[Skill.INTIMIDATION] == 1
    assert sheet.skills[Skill.PERCEPTION] == 3
    assert sheet.skills[Skill.SURVIVAL] == 3
    assert sheet.skills[Skill.ARCANA] == 0
    assert sheet.passive_perception == 13
    assert sheet.initiative == 2
    assert sheet.speed == 30
    assert sheet.spellcasting.casts_spells is False
    assert sheet.carrying_capacity == 240


def test_warlock_numbers(cases, calculator: DerivedStatsCalculator) -> None:
    sheet = calculator.compute(cases["warlock-1"].character)

    assert sheet.total_level == 1
    assert sheet.abilities[Ability.CHA].total == 17  # 15 + 2 (тифлінг)
    assert sheet.abilities[Ability.INT].total == 13  # 12 + 1 (тифлінг)
    assert sheet.armor_class == 12  # шкіряна 11 + DEX 1
    assert sheet.hit_points.maximum == 9  # d8 + CON 1

    casting = sheet.spellcasting
    assert casting.caster_level == 0, "Pact Magic не входить у рівень заклинателя"
    assert casting.slots.pact is not None
    assert casting.slots.pact.slots == 1
    assert casting.slots.pact.slot_level == 1
    assert casting.slots.by_level == (), "Pact Magic не додається до звичайних комірок"
    warlock = casting.for_class("warlock")
    assert warlock is not None
    assert warlock.save_dc == 13  # 8 + 2 + 3
    assert warlock.attack_bonus == 5
    assert warlock.cantrips_limit == 2
    assert warlock.spells_known_limit == 2
    assert warlock.prepared_limit is None, "варлок знає закляття, а не готує"

    assert sheet.darkvision == 60
    assert "fire" in sheet.resistances
    assert sheet.saving_throws[Ability.CHA] == 5
    assert sheet.saving_throws[Ability.WIS] == 2
    assert sheet.skills[Skill.ARCANA] == 3
    assert sheet.skills[Skill.DECEPTION] == 5
    assert sheet.skills[Skill.INSIGHT] == 2
    assert sheet.skills[Skill.RELIGION] == 3


def test_multiclass_numbers(cases, calculator: DerivedStatsCalculator) -> None:
    character = cases["fighter-2-wizard-3"].character
    sheet = calculator.compute(character)

    assert character.total_level == 5
    assert sheet.proficiency_bonus == 3
    assert sheet.hit_dice == {10: 2, 6: 3}
    # 11 (d10 max) + 7 (d10 середнє) + 5 + 5 + 5 (d6 середнє), CON 12 → +1
    assert sheet.hit_points.maximum == 33
    assert sheet.armor_class == 16  # кольчуга, DEX не додається

    casting = sheet.spellcasting
    assert casting.caster_level == 3
    assert dict(casting.slots.by_level) == {1: 4, 2: 2}
    assert casting.slots.pact is None
    wizard = casting.for_class("wizard")
    assert wizard is not None
    assert wizard.save_dc == 13  # 8 + 3 + 2 (INT 15)
    assert wizard.attack_bonus == 5
    assert wizard.cantrips_limit == 3
    assert wizard.prepared_limit == 5  # INT +2 і 3 рівні волшебника

    # Мультиклас НЕ дає рятівних кидків другого класу (PHB, p. 164).
    assert sheet.saving_throw_proficiency[Ability.INT] is False
    assert sheet.saving_throw_proficiency[Ability.STR] is True
    assert sheet.saving_throws[Ability.STR] == 4  # 1 + 3
    assert sheet.saving_throws[Ability.INT] == 2, "без майстерності — лише INT"


def test_fighter_has_no_spellcasting(cases) -> None:
    sheet = DerivedStatsCalculator().compute(cases["fighter-1"].character)
    assert sheet.spellcasting.classes == ()
    assert sheet.spellcasting.slots.total == 0
