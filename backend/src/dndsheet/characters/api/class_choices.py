"""Вибори класу для листа: бойовий стиль, втаємничення, метамагія, прийоми…

Варіанти — записи `optionalfeature` довідника (або перелік із книги для
улюбленого ворога й природного дослідника). Домен довідника не читає, тому
список дозволених назв збирається тут і передається у сценарій.
"""

from __future__ import annotations

import re
from typing import Any

from dndsheet.characters.api import uk_text
from dndsheet.characters.domain.character import Character
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.shared.rules import CHOICE_FEATURE_TYPES, CHOICE_FIXED_OPTIONS


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
            return f"потрібен дар {part}"
        if part.startswith("Spell:"):
            # «hex/curse»: закляття hex або прокляття (Hexblade's Curse) підкласу.
            names = re.sub(r"\bcantrip\b", "", part[6:]).strip().casefold().split("/")
            known = {spell.name_en.casefold() for spell in character.spells}
            subclass = next((e.subclass_key or "" for e in character.classes if e.class_key == class_key), "")
            curse = "curse" in names and "hexblade" in subclass
            if not curse and not known & {name.strip() for name in names}:
                return f"потрібне закляття {'/'.join(names)}"
    return None


def _options(group_key: str, compendium: CompendiumService, character: Character | None = None) -> list[dict[str, Any]]:
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
        seen.setdefault(entry.name_en.casefold(), {
            "name_en": entry.name_en,
            "name_uk": uk_text.name_uk(LAYER, entry.name_en),
            "text_en": entry.text_en or "",
            "text_uk": uk_text.text_uk(LAYER, entry.text_en or ""),
            "prerequisite": (entry.data or {}).get("prerequisite"),
            "source": entry.source_id,
            "locked": missing_prerequisite((entry.data or {}).get("prerequisite"), character, class_key)
            if character is not None
            else None,
        })
    return sorted(seen.values(), key=lambda item: item["name_en"])


def allowed_names(group_key: str, compendium: CompendiumService, character: Character) -> list[str]:
    """Варіанти, передумови яких персонаж уже має."""
    return [item["name_en"] for item in _options(group_key, compendium, character) if not item.get("locked")]


def class_choices_payload(character: Character, compendium: CompendiumService) -> list[dict[str, Any]]:
    """Групи, які дали рівні: скільки можна, що обрано і з чого обирати."""
    return [
        {
            "key": key,
            "class_key": key.partition(":")[0],
            "group": key.partition(":")[2],
            "slots": slots,
            "chosen": list(character.class_choices.get(key, ())),
            "options": _options(key, compendium, character),
        }
        for key, slots in sorted(character.class_choice_slots.items())
    ]
