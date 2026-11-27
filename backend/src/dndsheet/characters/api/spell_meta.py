"""Дані заклять для листа: час, дистанція, компоненти, урон, опис.

У вкладці «Дії» потрібні короткі дані (дія, дистанція, чим бʼє), а у
«Відомих закляттях» — ще й компоненти та текст правила. Тому з довідника
береться `data` (час, дистанція, тривалість, школа, компоненти, текст вищих
рівнів) і `text_en` (опис); з тексту ж вичитуються перший кубик урону, тип
рятівного кидка та згадка атаки закляттям. Це **підказка**, а не розрахунок ефекту:
лист не застосовує закляття.

Рятівний кидок шукається лише тоді, коли він не є «saving throw to avoid the
spell» (так у `Light`: предмет можна врятувати, але ефекту на ціль немає).

Результат кешується на застосунку: імена й тексти заклять не змінюються.
"""

from __future__ import annotations

import re
from typing import Any

from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.domain.entry import Category
from dndsheet.compendium.domain.query import EntryQuery
from dndsheet.shared.errors import NotFoundError

#: Кубик урону разом із типом: «1d6 acid», «2d8 + 3 fire».
DAMAGE = re.compile(
    r"(\d+d\d+(?:\s*[+−-]\s*\d+)?)\s+"
    r"(acid|bludgeoning|cold|fire|force|lightning|necrotic|piercing|poison|"
    r"psychic|radiant|slashing|thunder)",
    re.IGNORECASE,
)

SAVE = re.compile(
    r"(strength|dexterity|constitution|intelligence|wisdom|charisma)"
    r"\s+saving\s+throw(?!\s+to\s+avoid)",
    re.IGNORECASE,
)

SAVE_CODES = {
    "strength": "str",
    "dexterity": "dex",
    "constitution": "con",
    "intelligence": "int",
    "wisdom": "wis",
    "charisma": "cha",
}

SPELL_ATTACK = re.compile(r"spell\s+attack", re.IGNORECASE)

#: Перший рядок опису — «2nd-level abjuration» або «Evocation cantrip»:
#: рівень і школу лист уже показує окремо, у тексті він зайвий.
HEADER = re.compile(
    r"^(?:\d+(?:st|nd|rd|th)-level\s+[a-z]+(?:\s*\(ritual\))?|[A-Z][a-z]+\s+cantrip)$",
    re.IGNORECASE,
)


def enrich_spells(
    spells: list[dict[str, Any]],
    service: CompendiumService,
    cache: dict[str, dict[str, Any] | None] | None = None,
) -> None:
    """Дописати кожному рядку закляття його короткі дані (на місці)."""
    store = cache if cache is not None else {}
    for spell in spells:
        # Власне закляття довідник не знає: його текст дав гравець, і
        # підміняти його книжковим (навіть якщо назва збіглася) не можна.
        if spell.get("custom"):
            continue
        key = spell.get("entry_id") or str(spell.get("name_en") or "").strip().casefold()
        if not key:
            continue
        if key not in store:
            store[key] = _meta_for(service, spell)
        meta = store[key]
        if meta:
            spell.update(meta)


def _meta_for(
    service: CompendiumService, spell: dict[str, Any]
) -> dict[str, Any] | None:
    entry = _entry(service, spell)
    if entry is None:
        return None
    data = dict(entry.data or {})
    text = str(entry.text_en or "")
    damage = DAMAGE.search(text)
    save = SAVE.search(text)
    return {
        "casting_time": _text(data.get("casting_time")),
        "range": _text(data.get("range")),
        "duration": _text(data.get("duration")),
        "components": _text(data.get("components")),
        "concentration": bool(data.get("concentration")),
        "ritual": bool(data.get("ritual")),
        "school": _text(data.get("school")),
        "description": _body(text),
        "at_higher_levels": _text(data.get("at_higher_levels")),
        "damage": (
            {
                "dice": damage.group(1).replace(" ", "").replace("−", "-"),
                "type": damage.group(2).lower(),
            }
            if damage
            else None
        ),
        "save": SAVE_CODES[save.group(1).lower()] if save else None,
        "attack_roll": bool(SPELL_ATTACK.search(text)),
    }


def _entry(service: CompendiumService, spell: dict[str, Any]):  # noqa: ANN202
    entry_id = spell.get("entry_id")
    if entry_id:
        try:
            return service.entry(str(entry_id))
        except NotFoundError:
            pass
    name = str(spell.get("name_en") or "").strip()
    if not name:
        return None
    # Надані видом чи підкласом закляття не мають entry_id у персонажа —
    # шукаємо за точною назвою в довіднику. Пошук підрядковий, тому беремо
    # із запасом: коротка назва («Light») трапляється в багатьох закляттях.
    page = service.entries(EntryQuery(category=Category.SPELL, q=name, limit=100))
    wanted = name.casefold()
    for candidate in page.items:
        if candidate.name_en.strip().casefold() == wanted:
            return candidate
    return None


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _body(text: str) -> str:
    """Опис без першого рядка «2nd-level abjuration» — він уже є в підписах."""
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and HEADER.match(lines[0].strip()):
        lines.pop(0)
    return "\n".join(lines).strip()
