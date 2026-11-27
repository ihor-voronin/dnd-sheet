"""Школи заклять містичного лицаря й таємного пройдисвіта (PHB, p. 75, 98).

Відомі закляття 1+ рівня — лише з двох шкіл (огородження й вивернення у
лицаря, зачарування й ілюзія у пройдисвіта); виняток — по одному закляттю
будь-якої школи на 3, 8, 14 і 20 рівнях класу. Школу знає лише довідник,
тож перевірка тут, перед сценарієм, а не в домені.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from dndsheet.characters.api.spell_meta import _entry
from dndsheet.characters.domain.character import Character
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.shared.errors import ValidationError

SCHOOLS = {
    "eldritch-knight": ("fighter", frozenset({"abjuration", "evocation"}), "огородження чи вивернення"),
    "arcane-trickster": ("rogue", frozenset({"enchantment", "illusion"}), "зачарування чи ілюзії"),
}
FREE_AT = (3, 8, 14, 20)


def check_schools(
    character: Character,
    compendium: CompendiumService,
    class_key: str,
    adding: Iterable[Mapping[str, Any]],
    *,
    removing: str | None = None,
    level: int | None = None,
    subclass_key: str | None = None,
) -> None:
    """Відмовити, якщо закляття поза школами підкласу більше, ніж дозволяють рівні."""
    entry = next((item for item in character.classes if item.class_key == class_key), None)
    subclass = (subclass_key or (entry.subclass_key if entry else "") or "").casefold().rsplit("/", 1)[-1]
    rule = SCHOOLS.get(subclass)
    if rule is None or rule[0] != class_key:
        return
    _, allowed, label = rule
    class_level = level if level is not None else (entry.level if entry else 0)
    free = sum(1 for mark in FREE_AT if class_level >= mark)
    spells = [
        {"name_en": spell.name_en, "entry_id": spell.entry_id, "level": spell.level}
        for spell in character.spells_of(class_key)
        if not spell.is_cantrip and not spell.always_prepared and spell.name_en != removing
    ]
    spells += [dict(item) for item in adding if int(item.get("level") or 0) > 0]
    off = []
    for spell in spells:
        found = _entry(compendium, spell)
        school = str((found.data or {}).get("school") or "").casefold() if found else ""
        if school and school not in allowed:
            off.append(spell["name_en"])
    if len(off) > free:
        raise ValidationError(
            f"закляття поза школами {label}: {', '.join(off)} — на {class_level} рівні дозволено {free}"
        )
