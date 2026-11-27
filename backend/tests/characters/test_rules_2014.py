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
    assert not owned.has(ProficiencyKind.SAVING_THROW, "str"), "рятівні кидки — лише перший клас"


# --- закляття ----------------------------------------------------------------


def test_paladin_prepares_charisma_plus_half_level(rules) -> None:
    character = make_character(rules, abilities=_scores(cha=16), classes=[CharacterClass("paladin", 5)])
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
    dwarf = make_character(
        rules,
        classes=[CharacterClass("fighter", 3)],
        species_key="dwarf",
        subspecies_key="hill dwarf",
    )
    parts = {part.label: part.value for part in _sheet(dwarf).hit_points.parts}
    assert parts.get("dwarven-toughness") == 3  # +1 за кожен із 3 рівнів


def test_tough_feat_adds_two_per_level(rules) -> None:
    plain = make_character(rules, classes=[CharacterClass("fighter", 4)])
    tough = make_character(rules, classes=[CharacterClass("fighter", 4)], feats=("phb-2014/feat/tough",))
    assert _sheet(tough).hit_points.maximum == _sheet(plain).hit_points.maximum + 8


# --- атаки (PHB, p. 146) -------------------------------------------------------


def test_no_proficiency_bonus_without_weapon_proficiency() -> None:
    profile = WeaponProfile(name_en="Longsword", damage="1d8 slashing", group="Martial Melee Weapons")
    trained = attack_profile(profile, strength_modifier=2, dexterity_modifier=0, proficiency=2)
    untrained = attack_profile(profile, strength_modifier=2, dexterity_modifier=0, proficiency=2, proficient=False)
    assert trained.attack_bonus == 4
    assert untrained.attack_bonus == 2


# --- закляття підкласу за рівнями, третинки, книга мага ----------------------


def test_life_domain_grants_higher_spells_by_cleric_level(rules) -> None:
    cleric = make_character(
        rules,
        abilities=_scores(wis=13),
        classes=[CharacterClass("cleric", 5, subclass_key="phb-2014/subclass/life-domain")],
    )
    granted = {view.name_en: view.spell_level for view in _sheet(cleric).granted_spells}
    assert granted["spiritual weapon"] == 2
    assert granted["revivify"] == 3
    assert "death ward" not in granted  # з 7 рівня


def test_eldritch_knight_casts_from_third_level(rules) -> None:
    knight = make_character(
        rules,
        abilities=_scores(int=14, str=13),
        classes=[CharacterClass("fighter", 4, subclass_key="phb-2014/subclass/eldritch-knight")],
    )
    casting = _sheet(knight).spellcasting
    assert dict(casting.slots.by_level) == {1: 3}
    assert casting.for_class("fighter").spells_known_limit == 4


def test_wizard_preparation_keeps_spellbook(rules) -> None:
    from dndsheet.characters.domain.spells import KnownSpell

    book = tuple(
        KnownSpell(name_en=name, level=1, class_key="wizard") for name in ("Shield", "Sleep", "Magic Missile")
    )
    wizard = make_character(rules, abilities=_scores(int=10), classes=[CharacterClass("wizard", 1)], spells=book)
    wizard.prepare_spells("wizard", (book[0],))
    assert {spell.name_en for spell in wizard.spells} == {"Shield", "Sleep", "Magic Missile"}
    with pytest.raises(Exception):
        wizard.prepare_spells("wizard", (KnownSpell(name_en="Fireball", level=1, class_key="wizard"),))


# --- риси, мультиклас, броня -------------------------------------------------


def test_half_feat_adds_one_but_not_past_twenty(rules) -> None:
    character = make_character(
        rules,
        abilities=_scores(cha=19),
        feats=("phb-2014/feat/actor",),
        feat_abilities={"phb-2014/feat/actor": Ability.CHA},
    )
    assert _sheet(character).abilities[Ability.CHA].total == 20
    character.feat_abilities = {
        "phb-2014/feat/actor": Ability.CHA,
        "phb-2014/feat/resilient": Ability.CHA,
    }
    assert _sheet(character).abilities[Ability.CHA].total == 20


def test_resilient_grants_saving_throw(rules) -> None:
    character = make_character(
        rules,
        feats=("phb-2014/feat/resilient",),
        feat_abilities={"phb-2014/feat/resilient": Ability.WIS},
    )
    assert _sheet(character).saving_throw_proficiency[Ability.WIS] is True


def test_feat_ability_options_parsed_from_text() -> None:
    from dndsheet.shared.rules import feat_ability_options

    assert feat_ability_options("Increase your Strength or Dexterity score by 1") == (
        Ability.STR,
        Ability.DEX,
    )
    assert len(feat_ability_options("Increase the chosen ability score by 1")) == 6
    assert feat_ability_options("You gain a +5 bonus to initiative.") == ()


def test_multiclass_rogue_gives_one_skill(rules) -> None:
    from dndsheet.characters.domain.proficiencies import (
        GrantSource,
        Proficiency,
        SourceKind,
    )
    from dndsheet.shared.errors import ValidationError

    character = make_character(
        rules,
        abilities=_scores(str=13, dex=13),
        classes=[CharacterClass("fighter", 1), CharacterClass("rogue", 1)],
    )

    def pick(skill: Skill) -> Proficiency:
        return Proficiency(
            kind=ProficiencyKind.SKILL, value=skill.value, source=GrantSource.of(SourceKind.CLASS, "rogue")
        )

    character.pick(pick(Skill.STEALTH))
    with pytest.raises(ValidationError):
        character.pick(pick(Skill.ACROBATICS))


def test_heavy_armor_without_strength_slows(rules) -> None:
    mail = InventoryItem(name_en="Chain mail", kind=ItemKind.ARMOR, equipped=True, armor_base=16, dex_cap=0)
    weak = make_character(rules, abilities=_scores(str=12), inventory=Inventory(items=(mail,)))
    strong = make_character(rules, abilities=_scores(str=13), inventory=Inventory(items=(mail,)))
    assert _sheet(weak).speed == _sheet(strong).speed - 10


def test_class_choice_slots(rules) -> None:
    champion = make_character(rules, classes=[CharacterClass("fighter", 10, subclass_key="champion")])
    assert champion.class_choice_slots["fighter:Fighting Style"] == 2  # PHB, p. 72
    master = make_character(rules, classes=[CharacterClass("fighter", 7, subclass_key="battle-master")])
    assert master.class_choice_slots["fighter:Maneuvers"] == 5
    warlock = make_character(rules, classes=[CharacterClass("warlock", 5)])
    assert warlock.class_choice_slots == {"warlock:Eldritch Invocations": 3, "warlock:Pact Boon": 1}
    ranger = make_character(rules, classes=[CharacterClass("ranger", 6)])
    assert ranger.class_choice_slots["ranger:Favored Enemy"] == 2


def test_defense_style_adds_ac_in_armor(rules) -> None:
    mail = InventoryItem(name_en="Chain mail", kind=ItemKind.ARMOR, equipped=True, armor_base=16, dex_cap=0)
    fighter = make_character(
        rules, abilities=_scores(str=15), classes=[CharacterClass("fighter", 1)], inventory=Inventory(items=(mail,))
    )
    before = _sheet(fighter).armor_class
    with pytest.raises(Exception):
        fighter.set_class_choice("fighter:Fighting Style", ["Defense", "Archery"], ["Defense", "Archery"])
    with pytest.raises(Exception):
        fighter.set_class_choice("fighter:Fighting Style", ["Flying"], ["Defense", "Archery"])
    fighter.set_class_choice("fighter:Fighting Style", ["defense"], ["Defense", "Archery"])
    assert fighter.class_choices == {"fighter:Fighting Style": ("Defense",)}
    assert _sheet(fighter).armor_class == before + 1


def test_circle_of_the_land_terrain_spells(rules) -> None:
    druid = make_character(
        rules, abilities=_scores(wis=16), classes=[CharacterClass("druid", 5, subclass_key="circle-of-the-land")]
    )
    assert druid.class_choice_slots["druid:Circle Terrain"] == 1
    druid.set_class_choice("druid:Circle Terrain", ["mountain"], ["mountain", "forest"])
    names = {spell.name_en for spell in _sheet(druid).granted_spells}
    assert {"spider climb", "spike growth", "lightning bolt", "meld into stone"} <= {n.casefold() for n in names}


def test_invocation_prerequisites(rules) -> None:
    from dndsheet.characters.api.class_choices import missing_prerequisite
    from dndsheet.characters.domain.spells import KnownSpell

    warlock = make_character(rules, abilities=_scores(cha=16), classes=[CharacterClass("warlock", 5)])
    assert missing_prerequisite(None, warlock, "warlock") is None
    assert missing_prerequisite("Level 7 Warlock", warlock, "warlock")
    assert missing_prerequisite("Pact of the Blade, Level 5 Warlock", warlock, "warlock")
    assert missing_prerequisite("Spell: eldritch blast cantrip", warlock, "warlock")
    warlock.set_class_choice("warlock:Pact Boon", ["Pact of the Blade"], ["Pact of the Blade"])
    warlock.learn_spell(KnownSpell(name_en="Eldritch Blast", level=0, class_key="warlock"))
    assert missing_prerequisite("Pact of the Blade, Level 5 Warlock", warlock, "warlock") is None
    assert missing_prerequisite("Spell: eldritch blast cantrip", warlock, "warlock") is None


def test_armor_without_proficiency(rules) -> None:
    mail = InventoryItem(name_en="Chain mail", kind=ItemKind.ARMOR, equipped=True, armor_base=16)
    wizard = make_character(
        rules,
        abilities=_scores(str=15, dex=14),
        classes=[CharacterClass("wizard", 1)],
        inventory=Inventory(items=(mail,)),
    )
    sheet = _sheet(wizard)
    assert sheet.armor_untrained == ("Chain mail",)
    assert sheet.armor_class == 16  # важка броня: без Спритності, навіть коли dex_cap не задано
    assert any("Без володіння" in warning for warning in sheet.warnings)
    fighter = make_character(
        rules, abilities=_scores(str=15), classes=[CharacterClass("fighter", 1)], inventory=Inventory(items=(mail,))
    )
    assert _sheet(fighter).armor_untrained == ()


def test_multiclass_bard_gives_one_instrument(rules) -> None:
    from dndsheet.characters.domain.proficiencies import GrantSource, Proficiency, SourceKind
    from dndsheet.shared.errors import ValidationError

    character = make_character(
        rules, abilities=_scores(str=13, cha=13), classes=[CharacterClass("fighter", 1), CharacterClass("bard", 1)]
    )

    def tool(name: str) -> Proficiency:
        return Proficiency(kind=ProficiencyKind.TOOL, value=name, source=GrantSource.of(SourceKind.CLASS, "bard"))

    with pytest.raises(ValidationError):
        character.pick(tool("smith's tools"))
    character.pick(tool("lute"))
    assert character.all_proficiencies().has(ProficiencyKind.TOOL, "lute")
    with pytest.raises(ValidationError):
        character.pick(tool("flute"))


def test_eldritch_knight_spell_schools(rules) -> None:
    from dndsheet.api.app import create_app
    from dndsheet.characters.api.school_limits import check_schools
    from dndsheet.characters.domain.spells import KnownSpell
    from dndsheet.shared.errors import ValidationError

    compendium = create_app().state.compendium
    knight = make_character(
        rules,
        abilities=_scores(str=15, int=13),
        classes=[CharacterClass("fighter", 3, subclass_key="eldritch-knight")],
    )
    knight.learn_spell(KnownSpell(name_en="Shield", level=1, class_key="fighter"))
    # Одне закляття будь-якої школи на 3 рівні — дозволено (Sleep — зачарування).
    check_schools(knight, compendium, "fighter", [{"name_en": "Sleep", "level": 1}])
    knight.learn_spell(KnownSpell(name_en="Sleep", level=1, class_key="fighter"))
    with pytest.raises(ValidationError):
        check_schools(knight, compendium, "fighter", [{"name_en": "Charm Person", "level": 1}])
    check_schools(knight, compendium, "fighter", [{"name_en": "Magic Missile", "level": 1}])
