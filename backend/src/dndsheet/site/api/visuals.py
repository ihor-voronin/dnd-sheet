"""Зображення на сторінках довідника: емблеми записів і кілька портретів.

Емблема — за розділом: закляття — школа магії, клас і підклас — клас, решта —
емблема розділу. Портрети (власні малюнки сайту) — на сторінках виду й класу:
«як може виглядати герой», чотири штуки, ліниво й з розміром у атрибутах.
"""

from __future__ import annotations

from typing import Any

from dndsheet.site.application.catalog import Record
from dndsheet.visuals.application import avatars, emblems
from dndsheet.visuals.domain import catalog as portraits

#: Різні класи й стать — щоб чотири портрети одного виду не були схожі.
_SPECIES_LOOKS = (("f", "fighter"), ("m", "wizard"), ("f", "cleric"), ("m", "rogue"))
_CLASS_LOOKS = (("human", "f"), ("elf", "m"), ("dwarf", "f"), ("tiefling", "m"))


def record_emblem(record: Record) -> str | None:
    if record.section == "spells":
        return emblems.school_emblem(record.entry.spell_school if record.entry is not None else None)
    if record.section == "classes":
        return emblems.class_emblem(record.parent or str(record.data.get("key") or record.slug))
    return f"section-{record.section}"


def entry_portraits(record: Record) -> list[dict[str, Any]]:
    if record.section == "species":
        group = portraits.species_group(f"{record.data.get('key') or ''} {record.name_en}")
        info = portraits.GROUP_BY_KEY.get(group or "")
        if info is None:
            return []
        looks = (
            _SPECIES_LOOKS if info.gendered else (("x", "fighter"), ("x", "wizard"), ("x", "cleric"), ("x", "rogue"))
        )
        ids = [f"{info.key}-{gender}-{klass}-1" for gender, klass in looks]
    elif record.section == "classes":
        klass = record.parent or str(record.data.get("key") or record.slug)
        if klass not in portraits.CLASSES:
            return []
        ids = [f"{group}-{gender}-{klass}-1" for group, gender in _CLASS_LOOKS]
    else:
        return []
    return [avatars.card(found) for value in ids if (found := portraits.portrait(value)) is not None]
