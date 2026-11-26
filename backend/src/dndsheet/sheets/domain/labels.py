"""Демонстраційні підписи для каркасу.

УВАГА: це тимчасова заглушка до наповнення `compendium` + `glossary` (етап 2).
Після конвеєра контенту підписи приходитимуть із БД, а цей модуль буде видалено.
Українські назви тут — чернетка для перевірки верстки, не еталон перекладу.
"""

from __future__ import annotations

from dndsheet.shared.kernel import Ability, Skill
from dndsheet.sheets.domain.document import LocalizedText

DEMO_ABILITIES: dict[Ability, tuple[str, str]] = {
    Ability.STR: ("Сила", "Strength"),
    Ability.DEX: ("Спритність", "Dexterity"),
    Ability.CON: ("Статура", "Constitution"),
    Ability.INT: ("Інтелект", "Intelligence"),
    Ability.WIS: ("Мудрість", "Wisdom"),
    Ability.CHA: ("Харизма", "Charisma"),
}

DEMO_SKILLS: dict[Skill, tuple[str, str]] = {
    Skill.ATHLETICS: ("Атлетика", "Athletics"),
    Skill.ACROBATICS: ("Акробатика", "Acrobatics"),
    Skill.SLEIGHT_OF_HAND: ("Спритність рук", "Sleight of Hand"),
    Skill.STEALTH: ("Скритність", "Stealth"),
    Skill.ARCANA: ("Магія", "Arcana"),
    Skill.HISTORY: ("Історія", "History"),
    Skill.INVESTIGATION: ("Розслідування", "Investigation"),
    Skill.NATURE: ("Природа", "Nature"),
    Skill.RELIGION: ("Релігія", "Religion"),
    Skill.ANIMAL_HANDLING: ("Поводження з тваринами", "Animal Handling"),
    Skill.INSIGHT: ("Проникливість", "Insight"),
    Skill.MEDICINE: ("Медицина", "Medicine"),
    Skill.PERCEPTION: ("Спостережливість", "Perception"),
    Skill.SURVIVAL: ("Виживання", "Survival"),
    Skill.DECEPTION: ("Обман", "Deception"),
    Skill.INTIMIDATION: ("Залякування", "Intimidation"),
    Skill.PERFORMANCE: ("Виступ", "Performance"),
    Skill.PERSUASION: ("Переконання", "Persuasion"),
}

DEMO_HINTS: dict[str, tuple[str, str]] = {
    "ability.str": ("Значення Сили", "Strength score"),
    "ability.dex": ("Значення Спритності", "Dexterity score"),
    "ability.con": ("Значення Статури", "Constitution score"),
    "ability.int": ("Значення Інтелекту", "Intelligence score"),
    "ability.wis": ("Значення Мудрості", "Wisdom score"),
    "ability.cha": ("Значення Харизми", "Charisma score"),
    "combat.ac": ("10 + мод. Спритності + бонус броні", "10 + Dex modifier + armor bonus"),
    "combat.initiative": ("Модифікатор Спритності", "Dexterity modifier"),
    "combat.passive_perception": (
        "10 + модифікатор Спостережливості",
        "10 + Perception modifier",
    ),
    "rules.proficiency_bonus": (
        "Залежить від рівня персонажа",
        "Derived from character level",
    ),
    "combat.saving_throw": (
        "Модифікатор характеристики + бонус майстерності (якщо є володіння)",
        "Ability modifier + proficiency bonus (if proficient)",
    ),
    "skill.check": (
        "Модифікатор характеристики + бонус майстерності (якщо є володіння)",
        "Ability modifier + proficiency bonus (if proficient)",
    ),
}


def ability_label(ability: Ability) -> LocalizedText:
    uk, en = DEMO_ABILITIES[ability]
    return LocalizedText(uk=uk, en=en, glossary_id=f"ability.{ability.value}")


def ability_mod_label(ability: Ability) -> LocalizedText:
    uk, en = DEMO_ABILITIES[ability]
    return LocalizedText(uk=f"Мод. {uk}", en=f"{en} mod")


def save_label(ability: Ability) -> LocalizedText:
    uk, en = DEMO_ABILITIES[ability]
    return LocalizedText(uk=f"Рятівний кидок: {uk}", en=f"Saving Throw: {en}")


def skill_label(skill: Skill) -> LocalizedText:
    uk, en = DEMO_SKILLS[skill]
    return LocalizedText(uk=uk, en=en, glossary_id=f"skill.{skill.value}")


def hint(glossary_id: str) -> LocalizedText | None:
    pair = DEMO_HINTS.get(glossary_id)
    if pair is None:
        return None
    uk, en = pair
    return LocalizedText(uk=uk, en=en, glossary_id=glossary_id)
