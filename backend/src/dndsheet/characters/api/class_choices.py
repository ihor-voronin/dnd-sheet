"""Вибори класу для листа: бойовий стиль, втаємничення, метамагія, прийоми…

Варіанти — записи `optionalfeature` довідника (або перелік із книги для
улюбленого ворога й природного дослідника). Домен довідника не читає, тому
список дозволених назв збирається тут і передається у сценарій.
"""

from __future__ import annotations

from typing import Any

from dndsheet.characters.domain.character import Character
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.shared.rules import CHOICE_FEATURE_TYPES, CHOICE_FIXED_OPTIONS


def _options(group_key: str, compendium: CompendiumService) -> list[dict[str, Any]]:
    class_key, _, group = group_key.partition(":")
    if group in CHOICE_FIXED_OPTIONS:
        return [{"name_en": name, "text_en": "", "prerequisite": None} for name in CHOICE_FIXED_OPTIONS[group]]
    feature_type = CHOICE_FEATURE_TYPES[group].format(cls=class_key)
    seen: dict[str, dict[str, Any]] = {}
    for entry in compendium.optional_features(feature_type):
        # shortcut: однойменні записи з різних книг зливаються в перший; передумови не перевіряються.
        seen.setdefault(entry.name_en.casefold(), {
            "name_en": entry.name_en,
            "text_en": entry.text_en or "",
            "prerequisite": (entry.data or {}).get("prerequisite"),
        })
    return sorted(seen.values(), key=lambda item: item["name_en"])


def allowed_names(group_key: str, compendium: CompendiumService) -> list[str]:
    return [item["name_en"] for item in _options(group_key, compendium)]


def class_choices_payload(character: Character, compendium: CompendiumService) -> list[dict[str, Any]]:
    """Групи, які дали рівні: скільки можна, що обрано і з чого обирати."""
    return [
        {
            "key": key,
            "class_key": key.partition(":")[0],
            "group": key.partition(":")[2],
            "slots": slots,
            "chosen": list(character.class_choices.get(key, ())),
            "options": _options(key, compendium),
        }
        for key, slots in sorted(character.class_choice_slots.items())
    ]
