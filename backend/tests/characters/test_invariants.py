"""Інваріанти агрегату: те, що не можна зламати навіть через API.

Кожен тест тут — правило книги або межа даних, а не примха коду: рівень
1..20, сумарний рівень ≤20, підклас не раніше свого рівня, ліміти заклять за
таблицею класу, вибір навичок лише зі списку класу.
"""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiency,
    ProficiencyKind,
    Proficiencies,
    SourceKind,
)
from dndsheet.characters.domain.spells import KnownSpell
from dndsheet.characters.domain.vitals import HitPointState
from dndsheet.shared.errors import NotFoundError, ValidationError
from dndsheet.shared.kernel import Ability, AbilityScore, Skill

from helpers import make_character


def _class_pick(skill: Skill, class_key: str = "fighter") -> Proficiency:
    return Proficiency(
        kind=ProficiencyKind.SKILL,
        value=skill.value,
        source=GrantSource.of(SourceKind.CLASS, class_key),
    )


# --- шапка персонажа -------------------------------------------------------


def test_name_is_trimmed(rules) -> None:
    assert make_character(rules, name="  Імʼя  ").name == "Імʼя"


@pytest.mark.parametrize("name", ["", "   "])
def test_name_must_not_be_blank(rules, name: str) -> None:
    with pytest.raises(ValidationError):
        make_character(rules, name=name)


def test_all_six_abilities_required(rules) -> None:
    abilities = {ability: AbilityScore(10) for ability in Ability}
    del abilities[Ability.CHA]
    with pytest.raises(ValidationError, match="cha"):
        make_character(rules, abilities=abilities)


def test_draft_without_class_counts_as_level_one(rules) -> None:
    character = make_character(rules, classes=[])
    assert character.total_level == 0


# --- класи й рівні ---------------------------------------------------------


def test_same_class_twice_is_refused(rules) -> None:
    with pytest.raises(ValidationError, match="повторюється"):
        make_character(
            rules,
            classes=[CharacterClass("fighter", 1), CharacterClass("fighter", 2)],
        )


def test_total_level_cannot_exceed_twenty(rules) -> None:
    with pytest.raises(ValidationError, match="20"):
        make_character(
            rules,
            classes=[CharacterClass("fighter", 12), CharacterClass("wizard", 9)],
        )


def test_unknown_class_is_not_found(rules) -> None:
    with pytest.raises(NotFoundError):
        make_character(rules, classes=[CharacterClass("bard", 1)])


def test_subclass_requires_its_level(rules) -> None:
    with pytest.raises(ValidationError, match="підклас"):
        make_character(rules, classes=[CharacterClass("fighter", 2, "champion")])
    character = make_character(rules, classes=[CharacterClass("fighter", 3, "champion")])
    assert character.classes[0].subclass_key == "champion"


def test_dropping_level_below_subclass_clears_it(rules) -> None:
    character = make_character(rules, classes=[CharacterClass("fighter", 3, "champion")])
    character.set_class_level("fighter", 2)
    assert character.classes[0].subclass_key is None


def test_subclass_level_is_checked_per_class(rules) -> None:
    """Плут обирає підклас на 3 рівні, а не на 1."""
    with pytest.raises(ValidationError, match="обирається з 3"):
        make_character(rules, classes=[CharacterClass("rogue", 1, "thief")])


def test_add_class_bumps_version_and_emits_event(rules) -> None:
    character = make_character(rules)
    before = character.version
    character.add_class("wizard", 1)
    assert character.total_level == 2
    assert character.version == before + 1
    events = character.pull_events()
    assert events and events[-1].level == 2


def test_remove_class_clears_its_spells_and_picks(rules) -> None:
    character = make_character(
        rules,
        classes=[CharacterClass("warlock", 1)],
        chosen=Proficiencies(items=(_class_pick(Skill.ARCANA, "warlock"),)),
        spells=(
            KnownSpell(
                name_en="Eldritch Blast", level=0, class_key="warlock", entry_id=None
            ),
        ),
    )
    character.add_class("fighter", 1)
    character.remove_class("fighter")
    assert character.spells_of("fighter") == ()
    assert character.spells_of("warlock"), "закляття іншого класу лишаються"
    # Останній клас прибрати не можна: персонаж без класу не має рівня.
    with pytest.raises(ValidationError, match="хоча б один"):
        character.remove_class("warlock")


# --- вид, передісторія, вибір бонусів --------------------------------------


def test_unknown_species_is_not_found(rules) -> None:
    with pytest.raises(NotFoundError):
        make_character(rules, species_key="aarakocra")


def test_subspecies_must_belong_to_species(rules) -> None:
    with pytest.raises(ValidationError, match="підраса"):
        make_character(rules, species_key="human", subspecies_key="wood elf")


def test_ability_choice_must_match_count_and_options(rules) -> None:
    character = make_character(rules, species_key="half-elf")
    with pytest.raises(ValidationError, match="обрати 2"):
        character.choose_ability_bonuses([Ability.DEX])
    with pytest.raises(ValidationError, match="не входить"):
        character.choose_ability_bonuses([Ability.DEX, Ability.CHA])
    with pytest.raises(ValidationError, match="повторюватися"):
        character.choose_ability_bonuses([Ability.DEX, Ability.DEX])

    character.choose_ability_bonuses([Ability.DEX, Ability.CON])
    assert character.ability_bonus_choices == (Ability.DEX, Ability.CON)


# --- володіння -------------------------------------------------------------


def test_class_skill_must_be_in_class_list(rules) -> None:
    character = make_character(rules)
    with pytest.raises(ValidationError, match="не дає навички"):
        character.pick(_class_pick(Skill.ARCANA))


def test_class_skill_limit_is_enforced(rules) -> None:
    character = make_character(rules, chosen=Proficiencies(items=(_class_pick(Skill.ATHLETICS),)))
    character.pick(_class_pick(Skill.PERCEPTION))
    with pytest.raises(ValidationError, match="не більше 2"):
        character.pick(_class_pick(Skill.SURVIVAL))


def test_background_skill_must_be_offered(rules) -> None:
    character = make_character(rules, background_key="soldier")
    pick = Proficiency(
        kind=ProficiencyKind.SKILL,
        value=Skill.ARCANA.value,
        source=GrantSource.of(SourceKind.BACKGROUND, "soldier"),
    )
    with pytest.raises(ValidationError, match="не дає навички"):
        character.pick(pick)


def test_manual_proficiency_is_allowed(rules) -> None:
    character = make_character(rules)
    character.add_manual_proficiency(ProficiencyKind.SKILL, "athletics")
    assert character.all_proficiencies().has(ProficiencyKind.SKILL, "athletics")
    assert character.all_proficiencies().sources(ProficiencyKind.SKILL, "athletics")


def test_proficiencies_keep_their_sources(rules) -> None:
    character = make_character(rules, background_key="soldier")
    athletics = character.all_proficiencies().sources(ProficiencyKind.SKILL, "athletics")
    assert any(source.kind is SourceKind.BACKGROUND for source in athletics)
    assert character.all_proficiencies().has(ProficiencyKind.SAVING_THROW, "str")
    assert not character.all_proficiencies().has(ProficiencyKind.SAVING_THROW, "dex")


def test_multiclass_does_not_grant_saving_throws(rules) -> None:
    character = make_character(
        rules,
        classes=[CharacterClass("fighter", 1), CharacterClass("wizard", 1)],
    )
    sources = character.all_proficiencies().sources(ProficiencyKind.SAVING_THROW, "int")
    assert sources == (), "другий клас не дає кидків порятунку"


# --- закляття --------------------------------------------------------------


def test_spell_requires_its_class(rules) -> None:
    with pytest.raises(ValidationError, match="немає класу"):
        make_character(
            rules,
            spells=(KnownSpell(name_en="Hex", level=1, class_key="warlock"),),
        )


def test_cantrip_limit_from_class_table(rules) -> None:
    with pytest.raises(ValidationError, match="заговори"):
        make_character(
            rules,
            classes=[CharacterClass("warlock", 1)],
            spells=tuple(
                KnownSpell(name_en=f"Cantrip {index}", level=0, class_key="warlock")
                for index in range(3)
            ),
        )


def test_spell_level_above_available_slots_is_refused(rules) -> None:
    with pytest.raises(ValidationError, match="немає заклять"):
        make_character(
            rules,
            classes=[CharacterClass("wizard", 1)],
            spells=(
                KnownSpell(name_en="Fireball", level=3, class_key="wizard"),
            ),
        )


def test_warlock_known_spells_limit(rules) -> None:
    with pytest.raises(ValidationError, match="ліміт"):
        make_character(
            rules,
            classes=[CharacterClass("warlock", 1)],
            spells=tuple(
                KnownSpell(name_en=f"Spell {index}", level=1, class_key="warlock")
                for index in range(3)
            ),
        )


def test_prepare_and_forget_spell(rules) -> None:
    character = make_character(
        rules,
        classes=[CharacterClass("wizard", 1)],
        spells=(KnownSpell(name_en="Magic Missile", level=1, class_key="wizard"),),
    )
    character.prepare_spell("Magic Missile", "wizard")
    assert character.spells[0].prepared is True
    character.forget_spell("Magic Missile", "wizard")
    assert character.spells == ()
    with pytest.raises(ValidationError):
        character.forget_spell("Magic Missile", "wizard")


# --- хіти й інвентар -------------------------------------------------------


def test_hp_rolls_cannot_exceed_levels_gained(rules) -> None:
    character = make_character(rules)
    with pytest.raises(ValidationError, match="кидків"):
        character.set_hit_points(HitPointState(current=5, rolls=(7,)))


def test_hp_state_validates(rules) -> None:
    with pytest.raises(ValidationError):
        HitPointState(current=-1)
    with pytest.raises(ValidationError):
        HitPointState(current=5, rolls=(25,))
    with pytest.raises(ValidationError):
        HitPointState(current=5, override_max=-3)


def test_character_keeps_inventory_and_money(rules) -> None:
    from dndsheet.characters.domain.inventory import InventoryItem
    from dndsheet.shared.kernel import Money

    character = make_character(rules)
    character.add_item(InventoryItem(name_en="rope", weight_lb=10, quantity=2))
    character.set_money(Money(gp=5, sp=3))
    assert character.inventory.total_weight == 20
    assert character.inventory.money.total_gp == 5.3
    with pytest.raises(ValidationError, match="немає предмета"):
        character.equip_item("sword")
