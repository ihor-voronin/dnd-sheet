"""Шар українського перекладу правил: назви й тексти за хешем оригіналу.

Корпус — це джерело правил, і в ньому один `text_en`. Переклад тому не лежить
у записах довідника, а поруч — файлами в `content/translations/<шар>/`:

    [{"id": "sha1(оригінал)[:10]", "name_uk": "Темний зір"}]
    [{"id": "sha1(оригінал)[:10]", "text_uk": "У вас темний зір..."}]

Ключ — хеш **оригіналу**, бо «Darkvision» у двадцяти видів — той самий рядок,
і перекладати його двадцять разів не потрібно. Немає перекладу — повертаємо
`None`, і екран показує текст книги (без вигадок).

Кеш — на процес і на **повний шлях** каталогу: тести підміняють
`DNDSHEET_CONTENT_DIR`, і кеш не має перетікати з одного корпусу в інший.
"""

from __future__ import annotations

from typing import Any

from dndsheet.shared.translations import (  # noqa: F401 — публічне API шару
    EMPTY,
    folder,
    ident,
    name_uk,
    read,
    reset,
    text_uk,
)


def with_english(name_en: str, uk: str | None) -> str:
    """Правило перекладу проєкту: «Українська (English)»; немає перекладу — оригінал."""
    if not uk or uk.strip().casefold() == name_en.strip().casefold():
        return name_en
    return f"{uk} ({name_en})"


def enrich_item(payload: dict[str, Any], layer: str, *, text_field: str | None = None) -> dict[str, Any]:
    """Додати `name_uk` і `text_uk` до запису вміння чи риси.

    Поле тексту шукаємо за назвою (`text` у главі класу, `description` у
    підкласі) або явно — коли воно одне.
    """
    title = str(payload.get("name_en") or "")
    if title:
        translated = name_uk(layer, title)
        if translated:
            payload["name_uk"] = translated
    if text_field:
        body = str(payload.get(text_field) or "")
    else:
        body = str(payload.get("text") or payload.get("description") or "")
    if body:
        translated_text = text_uk(layer, body)
        if translated_text:
            payload["text_uk"] = translated_text
    return payload


__all__ = [
    "EMPTY",
    "enrich_item",
    "folder",
    "ident",
    "name_uk",
    "read",
    "reset",
    "text_uk",
    "with_english",
]
