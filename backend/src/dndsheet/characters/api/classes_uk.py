"""Українські назви й тексти особливостей класів.

Переклад лежить у `content/translations/classes/` і приєднується за хешем
оригіналу: `name_uk` — до назви вміння, `text_uk` — до тексту правила, а опис
класу (проза на початку глави) — теж `text_uk`. Немає перекладу — поля не
зʼявляється, і екран показує англійський текст книги без вигадок.

Кеш і читання файлів — спільні, у `uk_text`.
"""

from __future__ import annotations

from typing import Any

from dndsheet.characters.api import uk_text

#: Назва шару в `content/translations/`.
LAYER = "classes"


def name_uk(name_en: str) -> str | None:
    return uk_text.name_uk(LAYER, name_en)


def text_uk(text_en: str) -> str | None:
    return uk_text.text_uk(LAYER, text_en)


def enrich_details(payload: dict[str, Any]) -> dict[str, Any]:
    """Додати `description_uk` і `name_uk`/`text_uk` кожному вмінню."""
    description = payload.get("description")
    if isinstance(description, str) and description:
        translated = text_uk(description)
        if translated:
            payload["description_uk"] = translated
    for feature in payload.get("features") or []:
        enrich_feature(feature)
    return payload


def enrich_feature(feature: dict[str, Any]) -> dict[str, Any]:
    """Одне вміння: `name_uk` для назви, `text_uk` для тексту правила."""
    title = str(feature.get("name_en") or "")
    if title:
        translated_name = name_uk(title)
        if translated_name:
            feature["name_uk"] = translated_name
    body = str(feature.get("text") or feature.get("description") or "")
    if body:
        translated_text = text_uk(body)
        if translated_text:
            feature["text_uk"] = translated_text
    return feature


__all__ = ["LAYER", "enrich_details", "enrich_feature", "name_uk", "text_uk"]
