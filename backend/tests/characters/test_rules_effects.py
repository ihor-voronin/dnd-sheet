"""Ефекти виборів: риси з вибором, містичні виклики, бойові стилі, атаки.

Кожен тест — одне правило з посиланням на книгу (PHB 2014, XGtE, TCoE).
"""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.inventory import Inventory, InventoryItem, ItemKind
from dndsheet.characters.domain.proficiencies import ProficiencyKind
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
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


def _weapon(name: str) -> InventoryItem:
    return InventoryItem(name_en=name, kind=ItemKind.WEAPON, equipped=True)


# --- риси з вибором (PHB, p. 165–170) ---------------------------------------


def test_skilled_feat_offers_three_choices_and_grants_them(rules, compendium) -> None:
    from dndsheet.characters.api.class_choices import allowed_names

    character = make_character(rules, feats=("phb-2014/feat/skilled",))
    key = "feat:skilled:Skills or Tools"
    assert character.class_choice_slots[key] == 3
    allowed = allowed_names(key, compendium, character)
    assert "Stealth" in allowed and "thieves' tools" in allowed
    with pytest.raises(ValidationError):
        character.set_class_choice(key, ["Stealth", "Arcana", "lute", "History"], allowed)
    character.set_class_choice(key, ["Stealth", "Arcana", "lute"], allowed)
    owned = character.all_proficiencies()
    assert owned.has(ProficiencyKind.SKILL, Skill.STEALTH.value)
    assert owned.has(ProficiencyKind.TOOL, "lute")
    assert _sheet(character).skill_proficiency[Skill.ARCANA]


def test_skill_expert_adds_expertise_slot(rules) -> None:
    character = make_character(rules, feats=("tcoe/feat/skill-expert",))
    assert character.expertise_slots == 1
    assert character.class_choice_slots["feat:skill-expert:Skill"] == 1


def test_armored_feats_grant_proficiency(rules) -> None:
    character = make_character(
        rules, classes=[CharacterClass("wizard", 4)], feats=("phb-2014/feat/moderately-armored",)
    )
    owned = character.all_proficiencies()
    assert owned.has(ProficiencyKind.ARMOR, "medium") and owned.has(ProficiencyKind.ARMOR, "shield")


def test_magic_initiate_spells_follow_chosen_class(rules, compendium) -> None:
    from dndsheet.characters.api.class_choices import allowed_names

    character = make_character(rules, feats=("phb-2014/feat/magic-initiate",))
    character.set_class_choice("feat:magic-initiate:Spell Class", ["wizard"], ["wizard", "cleric"])
    cantrips = allowed_names("feat:magic-initiate:Cantrips", compendium, character)
    assert "Fire Bolt" in cantrips and "Sacred Flame" not in cantrips
    character.set_class_choice("feat:magic-initiate:Cantrips", ["Fire Bolt", "Light"], cantrips)
    first = allowed_names("feat:magic-initiate:1st-level Spell", compendium, character)
    character.set_class_choice("feat:magic-initiate:1st-level Spell", ["Shield"], first)
    granted = {(spell.name_en, spell.source, spell.usage) for spell in _sheet(character).granted_spells}
    assert ("Fire Bolt", "feat", "") in granted
    assert ("Shield", "feat", "1/long rest") in granted
    from dndsheet.characters.application.rows import spell_rows

    shield = next(row for row in spell_rows(character, _sheet(character)) if row.name_en == "Shield")
    assert "Інтелект: КС 10, атака +2" in shield.note  # ІНТ 10, бонус майстерності +2
    # інший клас — обрані закляття скидаються
    character.set_class_choice("feat:magic-initiate:Spell Class", ["cleric"], ["wizard", "cleric"])
    assert "feat:magic-initiate:Cantrips" not in character.class_choices


def test_fey_touched_grants_misty_step_and_school_choice(rules, compendium) -> None:
    from dndsheet.characters.api.class_choices import allowed_names

    character = make_character(rules, feats=("tcoe/feat/fey-touched",))
    options = allowed_names("feat:fey-touched:1st-level Spell", compendium, character)
    assert "Shield" not in options  # огородження — не та школа
    assert "Bless" in options  # зачарування
    assert "Command" in options or "Hex" in options
    assert any(spell.name_en == "Misty Step" for spell in _sheet(character).granted_spells)


# --- риса виду (PHB, p. 31; TCoE, p. 8) -------------------------------------


def test_variant_human_takes_feat_at_first_level(rules) -> None:
    human = make_character(
        rules,
        species_key="human",
        subspecies_key="variant human",
        ability_bonus_choices=(Ability.STR, Ability.CON),
    )
    assert human.grants_species_feat
    human.set_species_feat("phb-2014/feat/alert")
    assert _sheet(human).initiative == 5
    human.set_species_feat("phb-2014/feat/skilled")
    assert human.feats == ("phb-2014/feat/skilled",)
    assert human.class_choice_slots["feat:skilled:Skills or Tools"] == 3
    plain = make_character(rules, species_key="human")
    with pytest.raises(ValidationError):
        plain.set_species_feat("phb-2014/feat/alert")


# --- містичні виклики (PHB, p. 110) ------------------------------------------


def _warlock(rules, level: int = 5, **extra):
    return make_character(rules, abilities=_scores(cha=16, dex=14), classes=[CharacterClass("warlock", level, **extra)])


def test_invocations_grant_spells_and_senses(rules) -> None:
    warlock = _warlock(rules)
    warlock.set_class_choice(
        "warlock:Eldritch Invocations",
        ["Devil's Sight", "Mask of Many Faces", "Beguiling Influence"],
        ["Devil's Sight", "Mask of Many Faces", "Beguiling Influence"],
    )
    sheet = _sheet(warlock)
    assert sheet.darkvision == 120
    assert any(s.name_en == "Disguise Self" and s.source == "invocation" for s in sheet.granted_spells)
    assert sheet.skill_proficiency[Skill.DECEPTION] and sheet.skill_proficiency[Skill.PERSUASION]


def test_armor_of_shadows_is_unarmored_option(rules) -> None:
    warlock = _warlock(rules)
    before = _sheet(warlock).armor_class
    warlock.set_class_choice("warlock:Eldritch Invocations", ["Armor of Shadows"], ["Armor of Shadows"])
    assert _sheet(warlock).armor_class == before + 3  # 13 + СПР замість 10 + СПР


def test_agonizing_blast_note_on_eldritch_blast(rules) -> None:
    from dndsheet.characters.application.rows import spell_rows
    from dndsheet.characters.domain.spells import KnownSpell

    warlock = _warlock(rules)
    warlock.learn_spell(KnownSpell(name_en="Eldritch Blast", level=0, class_key="warlock"))
    warlock.set_class_choice("warlock:Eldritch Invocations", ["Agonizing Blast"], ["Agonizing Blast"])
    row = next(row for row in spell_rows(warlock, _sheet(warlock)) if row.name_en == "Eldritch Blast")
    assert "+3" in row.note and "Agonizing Blast" in row.note


def test_stale_choices_do_not_apply(rules) -> None:
    warlock = _warlock(rules, level=2)
    warlock.set_class_choice("warlock:Eldritch Invocations", ["Devil's Sight"], ["Devil's Sight"])
    warlock.class_choices = {**warlock.class_choices, "feat:skilled:Skills or Tools": ("Stealth",)}
    assert not warlock.all_proficiencies().has(ProficiencyKind.SKILL, "stealth"), "риси Skilled немає"


# --- бойові стилі (TCoE, p. 41) ----------------------------------------------


def test_blessed_warrior_gives_cleric_cantrips(rules, compendium) -> None:
    from dndsheet.characters.api.class_choices import allowed_names

    paladin = make_character(rules, abilities=_scores(cha=14), classes=[CharacterClass("paladin", 2)])
    paladin.set_class_choice("paladin:Fighting Style", ["Blessed Warrior"], ["Blessed Warrior"])
    key = "style:blessed warrior:Cantrips"
    options = allowed_names(key, compendium, paladin)
    assert "Sacred Flame" in options
    paladin.set_class_choice(key, ["Sacred Flame", "Guidance"], options)
    assert {"Sacred Flame", "Guidance"} <= {s.name_en for s in _sheet(paladin).granted_spells}


def test_blind_fighting_gives_blindsight(rules) -> None:
    fighter = make_character(rules)
    fighter.set_class_choice("fighter:Fighting Style", ["Blind Fighting"], ["Blind Fighting"])
    assert _sheet(fighter).blindsight == 10


# --- атаки: ченець, природна зброя, хексблейд, Shillelagh ---------------------


def test_monk_unarmed_strike_uses_martial_arts(rules, compendium) -> None:
    monk = make_character(rules, abilities=_scores(str=10, dex=16, wis=14), classes=[CharacterClass("monk", 5)])
    unarmed = _attacks(monk, compendium)["Unarmed Strike"]
    assert unarmed["ability"] == "dex"
    assert unarmed["damage"].startswith("1d6+3")
    assert unarmed["attack_bonus"] == 3 + 3


def test_monk_weapon_uses_dexterity_and_martial_arts_die(rules, compendium) -> None:
    monk = make_character(
        rules,
        abilities=_scores(str=10, dex=16),
        classes=[CharacterClass("monk", 11)],
        inventory=Inventory(items=(_weapon("Club"), _weapon("Greatclub"))),
    )
    attacks = _attacks(monk, compendium)
    assert attacks["Club"]["ability"] == "dex" and attacks["Club"]["damage"].startswith("1d8+3")
    assert attacks["Greatclub"]["ability"] == "str", "дворучна — не зброя ченця"


def test_tabaxi_claws_and_monk_take_larger_die(rules, compendium) -> None:
    tabaxi = make_character(rules, abilities=_scores(str=12, dex=16), species_key="tabaxi")
    claws = _attacks(tabaxi, compendium)["Cat's Claws"]
    assert claws["ability"] == "str" and claws["damage"] == "1d4+1 slashing"
    monk = make_character(
        rules, abilities=_scores(str=12, dex=16), species_key="tabaxi", classes=[CharacterClass("monk", 5)]
    )
    claws = _attacks(monk, compendium)["Cat's Claws"]
    assert claws["ability"] == "dex" and claws["damage"] == "1d6+4 slashing"  # СПР 16 + 2 табаксі
    monk_one = make_character(
        rules, abilities=_scores(str=12, dex=16), species_key="lizardfolk", classes=[CharacterClass("monk", 1)]
    )
    bite = _attacks(monk_one, compendium)["Bite"]
    assert bite["damage"] == "1d6+3 piercing", "укус d6 більший за d4 бойових мистецтв"


def test_martial_arts_lost_in_armor(rules, compendium) -> None:
    leather = InventoryItem(name_en="Leather", kind=ItemKind.ARMOR, equipped=True, armor_base=11)
    monk = make_character(
        rules,
        abilities=_scores(str=10, dex=16),
        classes=[CharacterClass("monk", 5)],
        inventory=Inventory(items=(leather,)),
    )
    assert _attacks(monk, compendium)["Unarmed Strike"]["damage"].startswith("1 ")


def test_hexblade_charisma_only_for_marked_weapons(rules, compendium) -> None:
    """Хекс-воїн — одна обрана зброя; угода — позначена зброя (XGtE, p. 55; PHB, p. 107)."""
    warlock = make_character(
        rules,
        abilities=_scores(str=10, cha=18),
        classes=[CharacterClass("warlock", 5, subclass_key="the-hexblade")],
        inventory=Inventory(items=(_weapon("Longsword"), _weapon("Greatsword"), _weapon("Rapier"))),
    )
    attacks = _attacks(warlock, compendium)
    assert attacks["Longsword"]["ability"] == "str", "не обрана для Хекс-воїна — Сила"
    warlock.update_item(0, {"hex_weapon": True})
    attacks = _attacks(warlock, compendium)
    assert attacks["Longsword"]["ability"] == "cha"
    # Позначка переходить: друга обрана зброя знімає першу.
    warlock.update_item(2, {"hex_weapon": True})
    assert not warlock.inventory.items[0].hex_weapon
    assert _attacks(warlock, compendium)["Rapier"]["ability"] == "cha"
    # Дворучна — лише як зброя угоди.
    warlock.update_item(1, {"hex_weapon": True})
    assert _attacks(warlock, compendium)["Greatsword"]["ability"] == "str"
    warlock.set_class_choice("warlock:Pact Boon", ["Pact of the Blade"], ["Pact of the Blade"])
    warlock.update_item(1, {"pact_weapon": True})
    greatsword = _attacks(warlock, compendium)["Greatsword"]
    assert greatsword["ability"] == "cha" and greatsword["attack_bonus"] == 3 + 4
    assert "зброя угоди" in greatsword["notes"]


def test_pact_weapon_gives_proficiency_only_when_marked(rules, compendium) -> None:
    warlock = make_character(
        rules,
        abilities=_scores(str=16, cha=16),
        classes=[CharacterClass("warlock", 3, subclass_key="the-fiend")],
        inventory=Inventory(items=(_weapon("Greataxe"), _weapon("Longbow"))),
    )
    warlock.set_class_choice("warlock:Pact Boon", ["Pact of the Blade"], ["Pact of the Blade"])
    assert _attacks(warlock, compendium)["Greataxe"]["attack_bonus"] == 3, "не позначена — без володіння"
    warlock.update_item(0, {"pact_weapon": True})
    assert _attacks(warlock, compendium)["Greataxe"]["attack_bonus"] == 3 + 2
    # Лук — лише з Improved Pact Weapon.
    warlock.update_item(1, {"pact_weapon": True})
    assert not warlock.inventory.items[0].pact_weapon, "зброя угоди лише одна"
    bow = _attacks(warlock, compendium)["Longbow"]
    assert "Improved Pact Weapon" in bow["notes"] and bow["attack_bonus"] == 0
    with pytest.raises(ValidationError):
        InventoryItem(name_en="Rope", pact_weapon=True)


def test_shillelagh_uses_wisdom_and_d8(rules, compendium) -> None:
    from dndsheet.characters.domain.spells import KnownSpell

    druid = make_character(
        rules,
        abilities=_scores(str=8, wis=16),
        classes=[CharacterClass("druid", 1)],
        inventory=Inventory(items=(_weapon("Quarterstaff"),)),
    )
    druid.learn_spell(KnownSpell(name_en="Shillelagh", level=0, class_key="druid"))
    row = _attacks(druid, compendium)["Quarterstaff (Shillelagh)"]
    assert row["ability"] == "wis" and row["damage"].startswith("1d8+3")
