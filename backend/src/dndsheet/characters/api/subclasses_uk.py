"""Українські назви й тексти особливостей підкласів.

Переклад лежить у `content/translations/subclasses/` і приєднується за хешем
оригіналу: `name_uk` — до назви особливості (`Channel Divinity: Preserve
Life`), `text_uk` — до її тексту. Немає перекладу — поля не зʼявляється, і
екран показує англійський текст книги без вигадок.

Кеш і читання файлів — спільні, у `uk_text`.
"""

from __future__ import annotations

from typing import Any

from dndsheet.characters.api import uk_text

#: Назва шару в `content/translations/`.
LAYER = "subclasses"


def name_uk(name_en: str) -> str | None:
    return uk_text.name_uk(LAYER, name_en)


def text_uk(text_en: str) -> str | None:
    return uk_text.text_uk(LAYER, text_en)


def enrich_feature(feature: dict[str, Any]) -> dict[str, Any]:
    """Назва й текст однієї особливості підкласу."""
    return uk_text.enrich_item(feature, LAYER)


def enrich_many(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in items:
        enrich_feature(item)
    return items


__all__ = ["LAYER", "enrich_feature", "enrich_many", "name_uk", "text_uk"]
