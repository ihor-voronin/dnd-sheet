"""Українські назви й тексти видів — із `content/translations/species`.

Корпус — це джерело правил: у ньому один `text_en`, у якому живуть і опис, і
вміння. Переклад тому не лежить у записах довідника, а поруч — файлами в
`content/translations/species/`, ключ — `sha1(оригінал)[:10]`. Немає
перекладу — повертаємо `None`, і екран показує текст книги (без вигадок).

Читання файлів і кеш — спільні для всіх шарів, у `uk_text`.
"""

from __future__ import annotations

from typing import Any

from dndsheet.characters.api import uk_text

#: Назва шару в `content/translations/`.
LAYER = "species"

#: Сумісність: раніше кеш жив тут, і тести скидали його саме так.
_CACHE: dict[str, Any] | None = None


def ident(text: str) -> str:
    return uk_text.ident(text)


def translations() -> dict[str, Any]:
    """Назви й тексти з усіх файлів каталогу (кеш на процес)."""
    return uk_text.read(LAYER)


def name_uk(name_en: str) -> str | None:
    return uk_text.name_uk(LAYER, name_en)


def text_uk(text_en: str) -> str | None:
    return uk_text.text_uk(LAYER, text_en)


def enrich(payload: dict[str, Any]) -> dict[str, Any]:
    """Додати `description_uk`, `name_uk`, `text_uk` до результату розбору.

    Нічого не змінює, якщо перекладу немає: поле просто не зʼявляється, і
    екран бере оригінал.
    """
    description = payload.get("description")
    if isinstance(description, str) and description:
        translated = text_uk(description)
        if translated:
            payload["description_uk"] = translated
    for trait in payload.get("traits") or []:
        title = str(trait.get("name_en") or "")
        if title:
            translated_name = name_uk(title)
            if translated_name:
                trait["name_uk"] = translated_name
        body = str(trait.get("text") or "")
        if body:
            translated_text = text_uk(body)
            if translated_text:
                trait["text_uk"] = translated_text
    return payload


__all__ = ["enrich", "ident", "name_uk", "text_uk", "translations"]
