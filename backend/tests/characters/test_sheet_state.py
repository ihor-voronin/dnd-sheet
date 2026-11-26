"""Стан листа: лічильники, виправлення, відпочинок, атаки зброєю."""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.attacks import WeaponProfile, attack_profile
from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.domain.services.rest import RestService
from dndsheet.characters.domain.state import DeathSaves, SheetState
from dndsheet.characters.domain.vitals import HitPointState
from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import Ability

from helpers import make_character


def _warlock(rules):
    from dndsheet.shared.kernel import Ability as A, AbilityScore

    return make_character(
        rules,
        id="c-w",
        name="Тіра",
        abilities={ability: AbilityScore(10) for ability in Ability}
        | {A.CHA: AbilityScore(15), A.CON: AbilityScore(13)},
        classes=[CharacterClass(class_key="warlock", level=1)],
        species_key="tiefling",
    )


# ---------------------------------------------------------------------------
# валідація стану
# ---------------------------------------------------------------------------


def test_death_saves_are_three() -> None:
    assert DeathSaves(3, 3).dead and DeathSaves(3, 3).stable
    with pytest.raises(ValidationError, match="успіхи"):
        DeathSaves(successes=4)
    with pytest.raises(ValidationError, match="провали"):
        DeathSaves(failures=4)


def test_state_rejects_unknown_override_and_notes() -> None:
    with pytest.raises(ValidationError, match="не можна виправити"):
        SheetState(overrides={"level": 3})
    with pytest.raises(ValidationError, match="розділ нотаток"):
        SheetState(notes={"dreams": "..."})
    state = SheetState(overrides={"skill:athletics": 9}, notes={"notes": "ok"})
    assert state.overrides["skill:athletics"] == 9


def test_character_state_cannot_use_more_hit_dice_than_owned(rules) -> None:
    character = make_character(rules)
    with pytest.raises(ValidationError, match="більше"):
        character.set_state(SheetState(hit_dice_used={10: 2}))
    character.set_state(SheetState(hit_dice_used={10: 1}))
    assert character.state.hit_die_used(10) == 1


# ---------------------------------------------------------------------------
# виправлення полів
# ---------------------------------------------------------------------------


def test_override_replaces_computed_value(rules) -> None:
    character = make_character(rules)
    sheet = DerivedStatsCalculator().compute(character)
    assert sheet.armor_class == 10
    assert "armor_class" not in sheet.overridden

    character.set_override("armor_class", 17)
    sheet = DerivedStatsCalculator().compute(character)
    assert sheet.armor_class == 17
    assert sheet.overridden == frozenset({"armor_class"})
    assert sheet.armor_class_parts[0].label == "override"

    character.clear_override("armor_class")
    assert DerivedStatsCalculator().compute(character).armor_class == 10


def test_override_skill_and_save(rules) -> None:
    character = make_character(rules)
    character.set_override("skill:stealth", 11)
    character.set_override("save:dex", 6)
    sheet = DerivedStatsCalculator().compute(character)
    from dndsheet.shared.kernel import Skill

    assert sheet.skills[Skill.STEALTH] == 11
    assert sheet.saving_throws[Ability.DEX] == 6
    assert {"skill:stealth", "save:dex"} <= sheet.overridden


def test_override_max_hp_changes_current_too(rules) -> None:
    character = make_character(rules, hp=HitPointState())
    character.set_override("hit_points_max", 77)
    sheet = DerivedStatsCalculator().compute(character)
    assert sheet.hit_points.maximum == 77
    assert sheet.hit_points.current == 77


def test_zero_hp_stays_zero(rules) -> None:
    """Нуль хітів — це непритомний персонаж, а не «хіти не задано»."""
    character = make_character(rules, hp=HitPointState(current=0))
    sheet = DerivedStatsCalculator().compute(character)
    assert sheet.hit_points.current == 0
    assert sheet.hit_points.maximum == 10


def test_unset_hp_is_not_the_same_as_zero(rules) -> None:
    character = make_character(rules)
    assert character.hp.current is None, "нового персонажа не чіпали — хіти не задані"
    assert DerivedStatsCalculator().compute(character).hit_points.current == 10
    character.set_hp(current=0)
    assert DerivedStatsCalculator().compute(character).hit_points.current == 0


def test_damage_needs_known_hp(rules) -> None:
    from dndsheet.characters.domain.vitals import HitPointState

    with pytest.raises(ValidationError, match="спершу задайте"):
        HitPointState().apply_damage(3)


# ---------------------------------------------------------------------------
# відпочинок
# ---------------------------------------------------------------------------


def test_long_rest_restores_everything(rules) -> None:
    character = make_character(rules, hp=HitPointState(current=3, temporary=2))
    character.set_state(
        SheetState(
            hit_dice_used={10: 1},
            death_saves=DeathSaves(successes=1, failures=2),
            exhaustion=3,
        )
    )
    RestService().long_rest(character)
    sheet = DerivedStatsCalculator().compute(character)
    assert character.hp.current == sheet.hit_points.maximum
    # Тимчасові хіти живуть, доки їх не знімуть: відпочинок їх не чистить.
    assert character.hp.temporary == 2
    assert character.state.hit_dice_used == {}
    assert character.state.death_saves == DeathSaves()
    assert character.state.exhaustion == 2


def test_long_rest_returns_half_of_hit_dice(rules) -> None:
    from dndsheet.shared.kernel import AbilityScore

    character = make_character(
        rules,
        abilities={ability: AbilityScore(10) for ability in Ability},
        classes=[CharacterClass(class_key="fighter", level=5)],
        hp=HitPointState(current=5),
    )
    character.set_state(SheetState(hit_dice_used={10: 4}))
    RestService().long_rest(character)
    # П'ять рівнів = п'ять d10; половина — 2.5, тобто 2 кістки (округлення вниз).
    assert character.state.hit_die_used(10) == 2


def test_long_rest_minimum_one_hit_die(rules) -> None:
    character = make_character(rules, hp=HitPointState(current=5))
    character.set_state(SheetState(hit_dice_used={10: 1}))
    RestService().long_rest(character)
    assert character.state.hit_die_used(10) == 0, "на 1 рівні повертається єдина кістка"


def test_short_rest_restores_pact_only(rules) -> None:
    character = _warlock(rules)
    character.set_state(SheetState(pact_used=1, slots_used={1: 1}, hit_dice_used={8: 0}))
    RestService().short_rest(character)
    assert character.state.pact_used == 0
    assert character.state.slot_used(1) == 1, "звичайні слоти короткий відпочинок не відновлює"


def test_spend_hit_die_heals(rules) -> None:
    character = make_character(rules, hp=HitPointState(current=2))
    healed = RestService().spend_hit_die(character, 10, 7)
    sheet = DerivedStatsCalculator().compute(character)
    # d10 кидок 7 + CON 5 (10 → модифікатор 0)? ні: у make_character CON 10.
    assert healed == 7
    assert character.hp.current == 9
    assert character.state.hit_die_used(10) == 1
    assert 9 <= sheet.hit_points.maximum
    with pytest.raises(ValidationError, match="усі"):
        RestService().spend_hit_die(character, 10, 7)


def test_spend_hit_die_checks_roll(rules) -> None:
    character = make_character(rules)
    with pytest.raises(ValidationError, match="1..10"):
        RestService().spend_hit_die(character, 10, 11)
    with pytest.raises(ValidationError, match="немає"):
        RestService().spend_hit_die(character, 12, 3)


# ---------------------------------------------------------------------------
# атаки
# ---------------------------------------------------------------------------


def test_longsword_uses_strength() -> None:
    attack = attack_profile(
        WeaponProfile("Longsword", "1d8 slashing", "Versatile (1d10)"),
        strength_modifier=3,
        dexterity_modifier=1,
        proficiency=2,
    )
    assert attack is not None
    assert attack.attack_bonus == 5
    assert attack.damage == "1d8+3 slashing"
    assert attack.ability is Ability.STR


def test_finesse_takes_the_better_modifier() -> None:
    attack = attack_profile(
        WeaponProfile("Dagger", "1d4 piercing", "Finesse, light, thrown"),
        strength_modifier=-1,
        dexterity_modifier=3,
        proficiency=2,
    )
    assert attack is not None
    assert attack.ability is Ability.DEX
    assert attack.attack_bonus == 5
    assert attack.damage == "1d4+3 piercing"


def test_ranged_weapon_uses_dexterity() -> None:
    attack = attack_profile(
        WeaponProfile("Shortbow", "1d6 piercing", "Ammunition (range 80/320)"),
        strength_modifier=3,
        dexterity_modifier=1,
        proficiency=2,
    )
    assert attack is not None
    assert attack.ability is Ability.DEX
    assert attack.damage == "1d6+1 piercing"


def test_weapon_without_damage_has_no_attack() -> None:
    assert (
        attack_profile(
            WeaponProfile("Shield", None, ""),
            strength_modifier=1,
            dexterity_modifier=1,
            proficiency=2,
        )
        is None
    )
