"""Вибори підкласів і дару угоди, ресурси рис, кенсей, книга виду, книга мага.

Кожен тест — одне правило з посиланням на книгу (PHB 2014, XGtE, TCoE).
"""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.inventory import Inventory, InventoryItem, ItemKind
from dndsheet.characters.domain.proficiencies import ProficiencyKind
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.domain.services.feature_resources import resources_for
from dndsheet.compendium.infrastructure.mechanics_index import JsonMechanicsRepository
from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import Ability, AbilityScore, Skill

from helpers import make_character


@pytest.fixture()
def rules():
    repository = JsonMechanicsRepository()
    if not repository.available():
        pytest.skip("немає індексу механік (content/index/*-mechanics.json)")
    return repository


@pytest.fixture(scope="module")
def compendium():
    from dndsheet.api.app import create_app

    return create_app().state.compendium


def _scores(**values: int) -> dict[Ability, AbilityScore]:
    scores = {ability: AbilityScore(10) for ability in Ability}
    for key, value in values.items():
        scores[Ability(key)] = AbilityScore(value)
    return scores


def _sheet(character):
    return DerivedStatsCalculator().compute(character)


def _attacks(character, compendium) -> dict[str, dict]:
    from dndsheet.characters.api.attacks import attacks_for

    return {row["name_en"]: row for row in attacks_for(character, _sheet(character), compendium, {})}


# --- підкласи й дар угоди -----------------------------------------------------


def test_knowledge_domain_skills_get_expertise(rules, compendium) -> None:
    """Blessings of Knowledge: 2 мови й 2 навички з подвоєним бонусом (PHB, p. 59)."""
    from dndsheet.characters.api.class_choices import allowed_names

    cleric = make_character(rules, classes=[CharacterClass("cleric", 1, subclass_key="knowledge-domain")])
    key = "sub:knowledge-domain:Skills"
    assert cleric.class_choice_slots[key] == 2
    options = allowed_names(key, compendium, cleric)
    assert set(options) == {"Arcana", "History", "Nature", "Religion"}
    cleric.set_class_choice(key, ["Arcana", "History"], options)
    cleric.set_class_choice("sub:knowledge-domain:Languages", ["draconic", "elvish"], ["draconic", "elvish"])
    sheet = _sheet(cleric)
    assert sheet.skill_expertise[Skill.ARCANA] and sheet.skills[Skill.ARCANA] == 2 * 2
    assert cleric.all_proficiencies().has(ProficiencyKind.LANGUAGE, "draconic")


def test_college_of_lore_waits_for_third_level(rules) -> None:
    bard = make_character(rules, abilities=_scores(cha=13), classes=[CharacterClass("bard", 2)])
    assert not any(key.startswith("sub:") for key in bard.class_choice_slots)
    lore = make_character(rules, abilities=_scores(cha=13), classes=[CharacterClass("bard", 3, subclass_key="college-of-lore")])
    assert lore.class_choice_slots["sub:college-of-lore:Skills"] == 3


def test_college_of_swords_style_takes_effect(rules, compendium) -> None:
    bard = make_character(
        rules,
        abilities=_scores(dex=16, cha=13),
        classes=[CharacterClass("bard", 3, subclass_key="college-of-swords")],
        inventory=Inventory(items=(InventoryItem(name_en="Rapier", kind=ItemKind.WEAPON, equipped=True),)),
    )
    bard.set_class_choice("sub:college-of-swords:Fighting Style", ["Dueling"], ["Dueling", "Two-Weapon Fighting"])
    assert _attacks(bard, compendium)["Rapier"]["damage"].startswith("1d8+5")  # СПР +3 і Дуель +2


def test_samurai_takes_skill_or_language(rules) -> None:
    samurai = make_character(rules, classes=[CharacterClass("fighter", 3, subclass_key="samurai")])
    samurai.set_class_choice("sub:samurai:Skill or Language", ["giant"], ["giant", "Insight"])
    assert samurai.all_proficiencies().has(ProficiencyKind.LANGUAGE, "giant")
    samurai.set_class_choice("sub:samurai:Skill or Language", ["Insight"], ["giant", "Insight"])
    assert samurai.all_proficiencies().has(ProficiencyKind.SKILL, Skill.INSIGHT.value)


def test_pact_of_the_tome_cantrips_any_class(rules, compendium) -> None:
    from dndsheet.characters.api.class_choices import allowed_names

    warlock = make_character(rules, abilities=_scores(cha=16), classes=[CharacterClass("warlock", 3, subclass_key="the-fiend")])
    warlock.set_class_choice("warlock:Pact Boon", ["Pact of the Tome"], ["Pact of the Tome"])
    key = "boon:pact of the tome:Cantrips"
    options = allowed_names(key, compendium, warlock)
    assert {"Guidance", "Sacred Flame", "Fire Bolt"} <= set(options)
    warlock.set_class_choice(key, ["Guidance", "Sacred Flame", "Fire Bolt"], options)
    granted = {spell.name_en: spell for spell in _sheet(warlock).granted_spells}
    assert granted["Sacred Flame"].source == "pact-boon" and granted["Sacred Flame"].ability is Ability.CHA


# --- ресурси рис ---------------------------------------------------------------


def test_lucky_and_superiority_dice_resources(rules) -> None:
    lucky = make_character(rules, feats=("phb-2014/feat/lucky",))
    luck = {item.key: item for item in resources_for(lucky, _sheet(lucky).ability_modifiers)}["feat:luck-points"]
    assert luck.total == 3 and luck.recharge == "long"

    adept = make_character(rules, feats=("phb-2014/feat/martial-adept",))
    dice = {item.key: item for item in resources_for(adept, _sheet(adept).ability_modifiers)}
    assert dice["feat:superiority-dice"].total == 1 and dice["feat:superiority-dice"].recharge == "short"

    master = make_character(
        rules, classes=[CharacterClass("fighter", 3, subclass_key="battle-master")], feats=("phb-2014/feat/martial-adept",)
    )
    dice = {item.key: item for item in resources_for(master, _sheet(master).ability_modifiers)}
    assert dice["fighter:superiority-dice"].total == 4 + 1, "кістка риси додається до запасу майстра битви"
    assert "feat:superiority-dice" not in dice


# --- кенсей (XGtE, p. 34) ------------------------------------------------------


def test_kensei_weapons_are_monk_weapons(rules, compendium) -> None:
    longsword = InventoryItem(name_en="Longsword", kind=ItemKind.WEAPON, equipped=True)
    monk = make_character(
        rules,
        abilities=_scores(str=10, dex=16, wis=13),
        classes=[CharacterClass("monk", 3, subclass_key="way-of-the-kensei")],
        inventory=Inventory(items=(longsword, InventoryItem(name_en="Longbow", kind=ItemKind.WEAPON), InventoryItem(name_en="Greatsword", kind=ItemKind.WEAPON))),
    )
    assert monk.kensei_slots == 2
    assert _attacks(monk, compendium)["Longsword"]["attack_bonus"] == 0, "без позначки — без володіння, Сила 10"
    monk.update_item(0, {"kensei_weapon": True})
    monk.update_item(1, {"kensei_weapon": True})
    attacks = _attacks(monk, compendium)
    assert attacks["Longsword"]["ability"] == "dex" and attacks["Longsword"]["attack_bonus"] == 2 + 3
    assert "Kensei's Shot" in attacks["Longbow"]["notes"]
    with pytest.raises(ValidationError):
        monk.update_item(2, {"kensei_weapon": True})
    plain = make_character(rules, inventory=Inventory(items=(longsword,)))
    with pytest.raises(ValidationError):
        plain.update_item(0, {"kensei_weapon": True})


# --- книга виду (VGtM / MPMM) ----------------------------------------------------


def test_species_source_changes_natural_weapon_die(rules, compendium) -> None:
    tabaxi = make_character(rules, abilities=_scores(str=12), species_key="tabaxi")
    assert _attacks(tabaxi, compendium)["Cat's Claws"]["damage"].startswith("1d4")
    tabaxi.set_species_source("mpmm")
    assert tabaxi.species_source == "MPMM"
    assert _attacks(tabaxi, compendium)["Cat's Claws"]["damage"].startswith("1d6")
    with pytest.raises(ValidationError):
        tabaxi.set_species_source("PHB")


# --- магічні таємниці й Книга давніх таємниць ---------------------------------


def test_bard_magical_secrets_count_in_spells_known(rules, compendium) -> None:
    """Магічні таємниці: 2 закляття будь-якого класу на 10 рівні, у межах відомих (PHB, p. 54)."""
    from dndsheet.characters.api.class_choices import allowed_names, option_levels
    from dndsheet.characters.application.rows import spell_rows

    bard = rules.class_mechanics("bard")
    assert bard.spells_known_at(9) == 12 and bard.spells_known_at(10) == 12, "дві з 14 — таємниці"
    character = make_character(rules, abilities=_scores(cha=16), classes=[CharacterClass("bard", 10)])
    key = "feature:bard:Magical Secrets"
    assert character.class_choice_slots[key] == 2
    options = allowed_names(key, compendium, character)
    assert {"Fireball", "Counterspell", "Eldritch Blast"} <= set(options)
    assert "Wish" not in options, "лише рівні, які бард 10 уже чарує"
    character.set_class_choice(key, ["Fireball", "Eldritch Blast"], options, option_levels(key, compendium, character))
    rows = {row.name_en: row for row in spell_rows(character, _sheet(character))}
    assert rows["Fireball"].level == 3 and rows["Fireball"].source == "secrets"
    assert rows["Eldritch Blast"].level == 0 and "Харизма" in rows["Eldritch Blast"].note


def test_lore_additional_secrets_and_book_of_ancient_secrets(rules, compendium) -> None:
    from dndsheet.characters.api.class_choices import allowed_names

    lore = make_character(rules, abilities=_scores(cha=13), classes=[CharacterClass("bard", 6, subclass_key="college-of-lore")])
    assert lore.class_choice_slots["sub:college-of-lore:Additional Magical Secrets"] == 2
    warlock = make_character(rules, abilities=_scores(cha=16), classes=[CharacterClass("warlock", 3, subclass_key="the-fiend")])
    warlock.set_class_choice("warlock:Pact Boon", ["Pact of the Tome"], ["Pact of the Tome"])
    warlock.set_class_choice("warlock:Eldritch Invocations", ["Book of Ancient Secrets"], ["Book of Ancient Secrets"])
    key = "inv:book of ancient secrets:Rituals"
    options = allowed_names(key, compendium, warlock)
    assert {"Find Familiar", "Detect Magic"} <= set(options) and "Shield" not in options, "лише ритуали"
    warlock.set_class_choice(key, ["Find Familiar", "Detect Magic"], options)
    granted = {spell.name_en: spell for spell in _sheet(warlock).granted_spells}
    assert granted["Find Familiar"].usage == "ritual only"


def test_text_only_subclass_choices(rules, compendium) -> None:
    from dndsheet.characters.api.class_choices import allowed_names

    hunter = make_character(rules, abilities=_scores(dex=13, wis=13), classes=[CharacterClass("ranger", 7, subclass_key="hunter")])
    slots = hunter.class_choice_slots
    assert slots["sub:hunter:Hunter's Prey"] == 1 and slots["sub:hunter:Defensive Tactics"] == 1
    assert "sub:hunter:Multiattack" not in slots
    hunter.set_class_choice("sub:hunter:Hunter's Prey", ["Colossus Slayer"], allowed_names("sub:hunter:Hunter's Prey", compendium, hunter))
    monk = make_character(rules, classes=[CharacterClass("monk", 6, subclass_key="way-of-the-four-elements")])
    key = "sub:way-of-the-four-elements:Elemental Disciplines"
    assert monk.class_choice_slots[key] == 2
    assert "Fangs of the Fire Snake" in allowed_names(key, compendium, monk)


# --- переписані ритуали --------------------------------------------------------


def test_copied_rituals_are_open_ended_and_level_capped(rules, compendium) -> None:
    """Книга давніх таємниць: ритуали до половини рівня чаклуна, скільки знайдете (PHB, p. 110)."""
    from dndsheet.characters.api.class_choices import allowed_names, class_choices_payload, option_levels

    warlock = make_character(rules, abilities=_scores(cha=16), classes=[CharacterClass("warlock", 5, subclass_key="the-fiend")])
    warlock.set_class_choice("warlock:Pact Boon", ["Pact of the Tome"], ["Pact of the Tome"])
    warlock.set_class_choice("warlock:Eldritch Invocations", ["Book of Ancient Secrets"], ["Book of Ancient Secrets"])
    warlock.set_class_choice("inv:book of ancient secrets:Rituals", ["Find Familiar"], ["Find Familiar"])
    key = "inv:book of ancient secrets:Copied Rituals"
    options = allowed_names(key, compendium, warlock)
    levels = option_levels(key, compendium, warlock)
    assert "Leomund’s Tiny Hut" in options and levels["Leomund’s Tiny Hut"] == 3, "чаклун 5 — до 3 рівня"
    assert "Find Familiar" not in options, "уже в книзі як стартовий ритуал"
    assert all(level <= 3 for level in levels.values())
    warlock.set_class_choice(key, ["Leomund’s Tiny Hut", "Alarm"], options, levels)
    group = next(item for item in class_choices_payload(warlock, compendium) if item["key"] == key)
    assert group["open_ended"]
    granted = {spell.name_en: spell for spell in _sheet(warlock).granted_spells}
    assert granted["Leomund’s Tiny Hut"].spell_level == 3 and granted["Leomund’s Tiny Hut"].usage == "ritual only"


# --- числа з текстових виборів і класові примітки ------------------------------


def test_rage_bear_totem_and_aspect(rules, compendium) -> None:
    barbarian = make_character(
        rules,
        abilities=_scores(str=16),
        classes=[CharacterClass("barbarian", 6, subclass_key="path-of-the-totem-warrior")],
        inventory=Inventory(items=(InventoryItem(name_en="Greataxe", kind=ItemKind.WEAPON, equipped=True),)),
    )
    assert "у люті (Rage): +2 урону" in _attacks(barbarian, compendium)["Greataxe"]["notes"]
    assert "дробильному" in _sheet(barbarian).resistance_notes[0]
    capacity = _sheet(barbarian).carrying_capacity
    barbarian.set_class_choice("sub:path-of-the-totem-warrior:Totem Spirit", ["Bear"], ["Bear", "Wolf"])
    barbarian.set_class_choice("sub:path-of-the-totem-warrior:Aspect of the Beast", ["Bear"], ["Bear", "Wolf"])
    sheet = _sheet(barbarian)
    assert "крім психічного" in sheet.resistance_notes[0]
    assert sheet.carrying_capacity == 2 * capacity


def test_draconic_ancestor_language_and_affinity(rules) -> None:
    from dndsheet.characters.api.router import _elemental_affinity

    sorcerer = make_character(
        rules, abilities=_scores(cha=16), classes=[CharacterClass("sorcerer", 6, subclass_key="draconic-bloodline")]
    )
    assert sorcerer.all_proficiencies().has(ProficiencyKind.LANGUAGE, "draconic")
    sorcerer.set_class_choice("sub:draconic-bloodline:Dragon Ancestor", ["Red (fire)"], ["Red (fire)"])
    spells = [{"name_en": "Fireball", "damage": {"dice": "8d6", "type": "fire"}}, {"name_en": "Ray of Frost", "damage": {"dice": "1d8", "type": "cold"}}]
    _elemental_affinity(spells, sorcerer, _sheet(sorcerer))
    assert "+3" in spells[0]["note"] and "note" not in spells[1]
    assert any("fire" in note for note in _sheet(sorcerer).resistance_notes)


def test_class_attack_notes(rules, compendium) -> None:
    rapier = InventoryItem(name_en="Rapier", kind=ItemKind.WEAPON, equipped=True)
    rogue = make_character(rules, abilities=_scores(dex=16), classes=[CharacterClass("rogue", 5)], inventory=Inventory(items=(rapier,)))
    assert "+3d6" in _attacks(rogue, compendium)["Rapier"]["notes"]
    paladin = make_character(
        rules, abilities=_scores(str=16, cha=13), classes=[CharacterClass("paladin", 2)], inventory=Inventory(items=(rapier,))
    )
    assert "Divine Smite" in _attacks(paladin, compendium)["Rapier"]["notes"]
    hunter = make_character(
        rules, abilities=_scores(dex=13, wis=13), classes=[CharacterClass("ranger", 3, subclass_key="hunter")], inventory=Inventory(items=(rapier,))
    )
    hunter.set_class_choice("sub:hunter:Hunter's Prey", ["Colossus Slayer"], ["Colossus Slayer"])
    assert "Colossus Slayer" in _attacks(hunter, compendium)["Rapier"]["notes"]
