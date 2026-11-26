"""Підписи листа: українське слово + оригінал англійською.

Кожен підпис — `LocalizedText` (uk для показу, en для тултіпа й англійського
рендера). Тут лише **слова інтерфейсу**: назви книг, класів, заклять і
предметів приходять із довідника англійською, і їх переклад — окремий
конвеєр (`localization`), а не цей модуль.

Значення мають збігатися з `frontend/src/labels.ts`: якщо екран і PDF
називають те саме по-різному, це помилка, а не стиль.
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


# ---------------------------------------------------------------------------
# слова листа: інвентар, володіння, нотатки, закляття
# ---------------------------------------------------------------------------

ITEM_KIND_LABELS: dict[str, tuple[str, str]] = {
    "armor": ("броня", "armor"),
    "shield": ("щит", "shield"),
    "weapon": ("зброя", "weapon"),
    "gear": ("речі", "gear"),
    "tool": ("інструмент", "tool"),
    "pack": ("набір", "pack"),
    "magic": ("магічне", "magic"),
}

PROFICIENCY_KIND_LABELS: dict[str, tuple[str, str]] = {
    "skill": ("навички", "skills"),
    "saving_throw": ("кидки порятунку", "saving throws"),
    "armor": ("броня", "armor"),
    "weapon": ("зброя", "weapons"),
    "tool": ("інструменти", "tools"),
    "language": ("мови", "languages"),
}

SOURCE_KIND_LABELS: dict[str, tuple[str, str]] = {
    "class": ("клас", "class"),
    "species": ("вид", "species"),
    "background": ("передісторія", "background"),
    "manual": ("вручну", "manual"),
}

LANGUAGE_LABELS: dict[str, tuple[str, str]] = {
    "common": ("спільна", "Common"),
    "elvish": ("ельфійська", "Elvish"),
    "dwarvish": ("дворфська", "Dwarvish"),
    "infernal": ("пекельна", "Infernal"),
    "celestial": ("небесна", "Celestial"),
    "draconic": ("драконяча", "Draconic"),
    "gnomish": ("гномівська", "Gnomish"),
    "goblin": ("гоблінська", "Goblin"),
    "halfling": ("півросликів", "Halfling"),
    "orc": ("ороча", "Orc"),
    "abyssal": ("безодні", "Abyssal"),
    "sylvan": ("лісова", "Sylvan"),
    "undercommon": ("підземна", "Undercommon"),
    "primordial": ("первісна", "Primordial"),
    "giant": ("велетнів", "Giant"),
    "deep speech": ("глибока мова", "Deep Speech"),
}

ALIGNMENT_LABELS: dict[str, tuple[str, str]] = {
    "lawful good": ("законно-добрий", "Lawful Good"),
    "neutral good": ("нейтрально-добрий", "Neutral Good"),
    "chaotic good": ("хаотично-добрий", "Chaotic Good"),
    "lawful neutral": ("законно-нейтральний", "Lawful Neutral"),
    "neutral": ("нейтральний", "Neutral"),
    "chaotic neutral": ("хаотично-нейтральний", "Chaotic Neutral"),
    "lawful evil": ("законно-злий", "Lawful Evil"),
    "neutral evil": ("нейтрально-злий", "Neutral Evil"),
    "chaotic evil": ("хаотично-злий", "Chaotic Evil"),
}

NOTE_LABELS: dict[str, tuple[str, str]] = {
    "appearance": ("Зовнішність", "Appearance"),
    "allies": ("Союзники", "Allies"),
    "enemies": ("Вороги", "Enemies"),
    "backstory": ("Передісторія", "Backstory"),
    "notes": ("Нотатки", "Notes"),
}

SPELL_SOURCE_LABELS: dict[str, tuple[str, str]] = {
    "class": ("від класу", "class"),
    "species": ("від виду", "species"),
    "subclass": ("від підкласу", "subclass"),
}


def item_kind_label(kind: str) -> LocalizedText:
    return _pair(ITEM_KIND_LABELS, kind, kind)


def proficiency_kind_label(kind: str) -> LocalizedText:
    return _pair(PROFICIENCY_KIND_LABELS, kind, kind)


def source_kind_label(kind: str) -> LocalizedText:
    return _pair(SOURCE_KIND_LABELS, kind, kind)


def language_label(value: str) -> LocalizedText:
    return _pair(LANGUAGE_LABELS, value, value)


def alignment_label(value: str) -> LocalizedText:
    return _pair(ALIGNMENT_LABELS, value, value)


def note_label(key: str) -> LocalizedText:
    return _pair(NOTE_LABELS, key, key)


def spell_source_label(source: str) -> LocalizedText:
    return _pair(SPELL_SOURCE_LABELS, source, source)


def spell_level_label(level: int) -> LocalizedText:
    if level == 0:
        return LocalizedText(uk="заговір", en="cantrip")
    return LocalizedText(uk=f"{level} рівня", en=f"level {level}")


def english_name(name: str) -> LocalizedText:
    """Назва з довідника: перекладу немає, тому uk = en (чесно, без вигадок)."""
    return LocalizedText(uk=name, en=name)


def _pair(table: dict[str, tuple[str, str]], key: str, fallback: str) -> LocalizedText:
    pair = table.get(key.strip().casefold())
    if pair is None:
        return LocalizedText(uk=fallback, en=fallback)
    uk, en = pair
    return LocalizedText(uk=uk, en=en)
