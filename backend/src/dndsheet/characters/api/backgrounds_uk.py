"""Українські назви, описи й спорядження передісторій.

Переклад лежить у `content/translations/backgrounds/` і приєднується за хешем
оригіналу: назва передісторії й риси, опис, текст риси та кожна фраза
спорядження. Немає перекладу — поля не зʼявляється, і екран показує
англійський текст книги без вигадок.

Кеш і читання файлів — спільні, у `uk_text`.
"""

from __future__ import annotations

from typing import Any

from dndsheet.characters.api import uk_text

#: Назва шару в `content/translations/`.
LAYER = "backgrounds"


def name_uk(name_en: str) -> str | None:
    return uk_text.name_uk(LAYER, name_en)


def text_uk(text_en: str) -> str | None:
    return uk_text.text_uk(LAYER, text_en)


def _feature_name(feature_en: str | None) -> str | None:
    return name_uk(feature_en) if feature_en else None


def equipment_row_uk(text: str) -> str | None:
    """Одна фраза спорядження: «uniform» → «однострій»."""
    return text_uk(text)


def enrich_details(payload: dict[str, Any]) -> dict[str, Any]:
    """Крок візарда: опис, риса й спорядження передісторії українською."""
    description = payload.get("description")
    if isinstance(description, str) and description:
        translated = text_uk(description)
        if translated:
            payload["description_uk"] = translated
    title = _feature_name(payload.get("feature_en"))
    if title:
        payload["feature_uk"] = title
    body = payload.get("feature_text")
    if isinstance(body, str) and body:
        translated = text_uk(body)
        if translated:
            payload["feature_text_uk"] = translated
    for row in payload.get("equipment") or []:
        enrich_equipment_row(row)
    return payload


def enrich_equipment_row(row: dict[str, Any]) -> dict[str, Any]:
    """Предмет із рядка `Equipment:` — з варіантами вибору."""
    text = str(row.get("text") or "")
    translated = text_uk(text) if text else None
    if translated:
        row["text_uk"] = translated
    choices = list(row.get("choices") or [])
    translated_choices = [text_uk(choice) or choice for choice in choices]
    if choices and translated_choices != choices:
        row["choices_uk"] = translated_choices
    return row


def enrich_sheet(payload: dict[str, Any]) -> dict[str, Any]:
    """Вкладка «Передісторія» на листі.

    Тут спорядження — один рядок (як у книзі). Українською його збираємо з
    перекладених фраз, а не перекладаємо рядок цілком: так «pouch containing
    10 gp» звучить однаково у всіх передісторіях.
    """
    title = str(payload.get("name_en") or "")
    if title:
        translated = name_uk(title)
        if translated:
            payload["name_uk"] = translated
    feature = str(payload.get("feature_en") or "")
    if feature:
        translated = name_uk(feature)
        if translated:
            payload["feature_uk"] = translated
    description = payload.get("description")
    if isinstance(description, str) and description:
        translated = text_uk(description)
        if translated:
            payload["description_uk"] = translated
    body = payload.get("feature_text")
    if isinstance(body, str) and body:
        translated = text_uk(body)
        if translated:
            payload["feature_text_uk"] = translated
    equipment = payload.get("equipment")
    if isinstance(equipment, str) and equipment:
        # Рядок книги розібраний на предмети ще в `background_info` — збираємо
        # український список із тих самих фраз, що й крок візарда.
        rows = payload.get("equipment_rows") or []
        parts: list[str] = []
        for row in rows:
            enrich_equipment_row(row)
            translated = row.get("text_uk")
            if translated:
                parts.append(str(translated))
            elif row.get("text"):
                parts.append(str(row["text"]))
        if parts:
            payload["equipment_uk"] = ", ".join(parts)
    return payload


__all__ = [
    "LAYER",
    "enrich_details",
    "enrich_equipment_row",
    "enrich_sheet",
    "equipment_row_uk",
    "name_uk",
    "text_uk",
]
