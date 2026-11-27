"""Вибори класу для листа: бойовий стиль, втаємничення, метамагія, прийоми…

Варіанти — записи `optionalfeature` довідника (або перелік із книги для
улюбленого ворога й природного дослідника). Домен довідника не читає, тому
список дозволених назв збирається тут і передається у сценарій.
"""

from __future__ import annotations

import re
from typing import Any

from dndsheet.characters.api import uk_text
from dndsheet.characters.domain import derived_choices
from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.proficiencies import ProficiencyKind
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import Skill
from dndsheet.shared.rules import (
    ALL_TOOLS,
    CHOICE_FEATURE_TYPES,
    CHOICE_FIXED_OPTIONS,
    LANGUAGES,
    WEAPONS,
    DerivedChoice,
)
from dndsheet.sheets.domain.labels import DEMO_SKILLS, LANGUAGE_LABELS

#: Класи, з яких риси беруть закляття (назви — як у глосарії).
CLASS_UK = {
    "paladin": "Паладин",
    "ranger": "Слідопит",
    "artificer": "Артифіцер",
    "bard": "Бард",
    "cleric": "Жрець",
    "druid": "Друїд",
    "sorcerer": "Чародій",
    "warlock": "Чаклун",
    "wizard": "Маг",
}


#: Шар перекладу в `content/translations/` (назви й тексти за хешем оригіналу).
LAYER = "optional-features"


def missing_prerequisite(prerequisite: str | None, character: Character, class_key: str) -> str | None:
    """Чого бракує для втаємничення: «Level 5 Warlock», «Pact of the Blade», «Spell: hex/curse»."""
    if not prerequisite:
        return None
    for part in (piece.strip() for piece in prerequisite.split(",")):
        level = re.fullmatch(r"Level (\d+) \w+", part)
        if level and character.class_level(class_key) < int(level.group(1)):
            return f"потрібен {level.group(1)} рівень"
        if part.startswith("Pact of") and part not in character.class_choices.get(f"{class_key}:Pact Boon", ()):
            return f"потрібна {uk_text.with_english(part, uk_text.name_uk(LAYER, part))}"
        if part.startswith("Spell:"):
            # «hex/curse»: закляття hex або прокляття (Hexblade's Curse) підкласу.
            names = re.sub(r"\bcantrip\b", "", part[6:]).strip().casefold().split("/")
            known = {spell.name_en.casefold() for spell in character.spells}
            subclass = next((e.subclass_key or "" for e in character.classes if e.class_key == class_key), "")
            curse = "curse" in names and "hexblade" in subclass
            if not curse and not known & {name.strip() for name in names}:
                spell = names[0].strip().title()
                return f"потрібне закляття {uk_text.with_english(spell, uk_text.name_uk('spells', spell))}"
    return None


def _plain(name_en: str, name_uk: str | None = None, locked: str | None = None) -> dict[str, Any]:
    return {"name_en": name_en, "name_uk": name_uk, "text_en": "", "prerequisite": None, "locked": locked}


def _derived_options(
    group_key: str, choice: DerivedChoice, compendium: CompendiumService, character: Character | None
) -> list[dict[str, Any]]:
    """Варіанти вибору риси чи стилю: навички, інструменти, мови, зброя, закляття."""
    owned = character.all_proficiencies() if character is not None else None
    chosen = set(character.class_choices.get(group_key, ())) if character is not None else set()

    def lock(kind: ProficiencyKind, value: str, shown: str) -> str | None:
        if owned is None or shown in chosen or not owned.has(kind, value):
            return None
        return "уже є володіння"

    rows: list[dict[str, Any]] = []
    if choice.kind in ("skill", "skill_or_tool", "skill_or_language"):
        # Список навичок може бути обмежений правилом (Домен знань: 4 навички).
        allowed_skills = {name.casefold() for name in choice.options}
        for skill in Skill:
            uk, en = DEMO_SKILLS[skill]
            if allowed_skills and en.casefold() not in allowed_skills:
                continue
            rows.append(_plain(en, uk, lock(ProficiencyKind.SKILL, skill.value, en)))
    if choice.kind == "skill_or_language":
        rows.extend(
            _plain(name, LANGUAGE_LABELS.get(name, (None,))[0], lock(ProficiencyKind.LANGUAGE, name, name))
            for name in LANGUAGES
        )
    if choice.kind in ("tool", "skill_or_tool"):
        rows.extend(_plain(tool, None, lock(ProficiencyKind.TOOL, tool, tool)) for tool in ALL_TOOLS)
    if choice.kind == "language":
        rows.extend(
            _plain(name, LANGUAGE_LABELS.get(name, (None,))[0], lock(ProficiencyKind.LANGUAGE, name, name))
            for name in LANGUAGES
        )
    if choice.kind == "weapon":
        rows.extend(_plain(name, None, lock(ProficiencyKind.WEAPON, name, name)) for name in WEAPONS)
    if choice.kind == "fixed":
        rows.extend(
            _plain(name, CLASS_UK.get(name) or uk_text.name_uk("subclasses", name) or uk_text.name_uk("classes", name))
            for name in choice.options
        )
    if choice.kind == "optional":
        seen: dict[str, dict[str, Any]] = {}
        for entry in compendium.optional_features(choice.feature_type):
            prerequisite = (entry.data or {}).get("prerequisite")
            seen.setdefault(
                entry.name_en.casefold(),
                {
                    "name_en": entry.name_en,
                    "name_uk": uk_text.name_uk(LAYER, entry.name_en),
                    "text_en": entry.text_en or "",
                    "text_uk": uk_text.text_uk(LAYER, entry.text_en or ""),
                    "prerequisite": prerequisite,
                    "source": entry.source_id,
                    # Містичний адепт (Eldritch Adept) бере лише виклики без передумов.
                    "locked": "потрібна передумова чаклуна"
                    if prerequisite and "invocation" in choice.feature_type
                    else None,
                },
            )
        rows = sorted(seen.values(), key=lambda item: item["name_en"])
    if choice.kind == "spell":
        rows = _spell_options(group_key, choice, compendium, character)
    return rows


def _spell_options(
    group_key: str, choice: DerivedChoice, compendium: CompendiumService, character: Character | None
) -> list[dict[str, Any]]:
    """Закляття для риси: зі списку класу (або будь-якого), потрібного рівня й школи."""
    spell_class = derived_choices.spell_class_for(
        group_key, choice, character.class_choices if character is not None else {}
    )
    if spell_class is None:
        return []
    classes = (*CLASS_UK, "paladin", "ranger") if spell_class == "*" else (spell_class,)
    # Магічні таємниці: від заговорів до найвищого рівня, який має клас (PHB, p. 54).
    top = choice.spell_level
    bottom = choice.spell_level
    if choice.max_level_of and character is not None and character.has_class(choice.max_level_of):
        definition = character.class_definition(choice.max_level_of)
        top = definition.max_spell_level(character.class_level(choice.max_level_of))
        bottom = 0
    if choice.max_level_half and character is not None:
        # Переписані ритуали: рівень закляття — до половини рівня, вгору (PHB, p. 110, 169).
        base = (
            character.total_level if choice.max_level_half == "total" else character.class_level(choice.max_level_half)
        )
        top, bottom = max(1, -(-base // 2)), 1
    found: dict[str, Any] = {}
    for name in classes:
        for entry in compendium.class_spells(name, max_level=top).spells:
            data = entry.data or {}
            level = entry.spell_level if entry.spell_level is not None else -1
            if not bottom <= level <= top:
                continue
            if choice.schools and (entry.spell_school or "") not in choice.schools:
                continue
            if choice.ritual and not data.get("ritual"):
                continue
            found.setdefault(entry.name_en.casefold(), entry)
    # Те саме закляття в іншій групі цього ж джерела (ритуали книги й переписані) — не вдруге.
    prefix = group_key.rsplit(":", 1)[0] + ":"
    elsewhere = {
        name.casefold()
        for key, values in (character.class_choices.items() if character is not None else ())
        if key != group_key and key.startswith(prefix)
        for name in values
    }
    return [
        {
            "name_en": entry.name_en,
            "name_uk": uk_text.name_uk("spells", entry.name_en),
            "text_en": entry.text_en or "",
            "prerequisite": None,
            "locked": "уже обрано в іншій групі" if entry.name_en.casefold() in elsewhere else None,
            "school": entry.spell_school,
            "level": entry.spell_level,
        }
        for entry in sorted(found.values(), key=lambda item: item.name_en)
    ]


def _options(
    group_key: str, compendium: CompendiumService, character: Character | None = None
) -> list[dict[str, Any]]:
    derived = character.derived_choice_groups.get(group_key) if character is not None else None
    if derived is not None:
        return _derived_options(group_key, derived, compendium, character)
    class_key, _, group = group_key.partition(":")
    if group in CHOICE_FIXED_OPTIONS:
        return [
            {"name_en": name, "name_uk": uk_text.name_uk(LAYER, name), "text_en": "", "prerequisite": None}
            for name in CHOICE_FIXED_OPTIONS[group]
        ]
    feature_type = CHOICE_FEATURE_TYPES[group].format(cls=class_key)
    seen: dict[str, dict[str, Any]] = {}
    for entry in compendium.optional_features(feature_type):
        # однойменні записи з різних книг зливаються в перший (PHB раніше за TCoE).
        seen.setdefault(
            entry.name_en.casefold(),
            {
                "name_en": entry.name_en,
                "name_uk": uk_text.name_uk(LAYER, entry.name_en),
                "text_en": entry.text_en or "",
                "text_uk": uk_text.text_uk(LAYER, entry.text_en or ""),
                "prerequisite": (entry.data or {}).get("prerequisite"),
                "source": entry.source_id,
                "locked": missing_prerequisite((entry.data or {}).get("prerequisite"), character, class_key)
                if character is not None
                else None,
            },
        )
    return sorted(seen.values(), key=lambda item: item["name_en"])


def option_levels(group_key: str, compendium: CompendiumService, character: Character) -> dict[str, int]:
    """Рівні заклять серед варіантів групи — щоб домен знав рівень обраного."""
    return {
        item["name_en"]: int(item["level"])
        for item in _options(group_key, compendium, character)
        if isinstance(item.get("level"), int)
    }


def allowed_names(group_key: str, compendium: CompendiumService, character: Character) -> list[str]:
    """Варіанти, передумови яких персонаж уже має."""
    return [item["name_en"] for item in _options(group_key, compendium, character) if not item.get("locked")]


def class_choices_payload(character: Character, compendium: CompendiumService) -> list[dict[str, Any]]:
    """Групи, які дали рівні: скільки можна, що обрано і з чого обирати."""
    rows = []
    # Спершу вибори класу (за ключем), далі риси й стилі — у порядку правил:
    # «Клас заклять» Учня магії раніше за його заговори.
    derived_order = list(character.derived_choice_groups)
    slots_by_key = character.class_choice_slots
    ordered = sorted(
        slots_by_key.items(),
        key=lambda pair: (1, derived_order.index(pair[0]), "") if pair[0] in derived_order else (0, 0, pair[0]),
    )
    for key, slots in ordered:
        kind, owner, group = derived_choices.split_key(key)
        derived = kind in ("feat", "style", "sub", "boon", "feature", "inv")
        rows.append(
            {
                "key": key,
                "class_key": key.partition(":")[0],
                "group": group if derived else key.partition(":")[2],
                # Хто дав вибір: риса чи бойовий стиль (для підпису на листі).
                "origin": {"kind": kind, "key": owner, "name_uk": _owner_uk(kind, owner)} if derived else None,
                "slots": slots,
                "chosen": list(character.active_class_choices.get(key, ())),
                # Без ліміту (переписані ритуали): лист не нагадує «ще N на вибір».
                "open_ended": bool(derived and character.derived_choice_groups[key].open_ended),
                "options": _options(key, compendium, character),
            }
        )
    return rows


def duplicate_picks(character: Character) -> list[str]:
    """Обране в рисі чи підкласі, що вже є з іншого джерела: «Умілий (Skilled): Athletics»."""
    owned = character.all_proficiencies()
    problems: list[str] = []
    for key, choice in character.derived_choice_groups.items():
        source = derived_choices.source_of(character, key)
        kind, owner, _ = derived_choices.split_key(key)
        for value in character.active_class_choices.get(key, ()):
            proficiency = derived_choices.proficiency_of(choice.kind, value, source)
            if proficiency is None:
                continue
            if any(other != source for other in owned.sources(proficiency.kind, proficiency.value)):
                problems.append(f"{_owner_uk(kind, owner)}: {value}")
    return problems


def feat_probe_groups(character: Character, compendium: CompendiumService) -> list[dict[str, Any]]:
    """Групи виборів рис (для візарда): ті самі, що на листі."""
    return [group for group in class_choices_payload(character, compendium) if group["key"].startswith("feat:")]


def apply_choices(character: Character, compendium: CompendiumService, choices: dict[str, Any]) -> None:
    """Застосувати вибори в порядку правил («Клас заклять» раніше за заговори)."""
    order = list(character.derived_choice_groups)
    for key in sorted(choices, key=lambda item: order.index(item) if item in order else len(order)):
        if key not in character.class_choice_slots:
            raise ValidationError(f"риса не дає вибору {key!r}")
        character.set_class_choice(
            key, choices[key], allowed_names(key, compendium, character), option_levels(key, compendium, character)
        )


def _owner_uk(kind: str, owner: str) -> str:
    """Підпис джерела вибору: «Умілий (Skilled)», «Благословенний воїн (Blessed Warrior)»."""
    name_en = owner.replace("-", " ").title()
    if kind == "sub":
        name_en = name_en.replace(" Of The ", " of the ").replace(" Of ", " of ")
    if kind == "feature":
        return uk_text.with_english(owner.title(), CLASS_UK.get(owner))
    layer = {"feat": "feats", "sub": "subclasses"}.get(kind, LAYER)
    return uk_text.with_english(name_en, uk_text.name_uk(layer, name_en))
