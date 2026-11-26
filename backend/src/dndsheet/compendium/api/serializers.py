"""Перетворення доменних записів у JSON для API.

Список і один запис віддаються по-різному: у списку текст книги не потрібен
(він важить більше за всі інші поля разом), а в картці запису — потрібен.
Тому `brief` і `full` — різні контракти, і це видно з коду, а не з нагоди.
"""

from __future__ import annotations

from typing import Any

from dndsheet.compendium.domain.entry import CompendiumEntry


def entry_brief(entry: CompendiumEntry) -> dict[str, Any]:
    """Запис для списків і вибору: без тексту, але з усіма полями `data`."""
    return {
        "id": entry.id,
        "source_id": entry.source_id,
        "category": entry.category.value,
        "name_en": entry.name_en,
        "name_uk": entry.name_uk,
        "display_name": entry.display_name,
        "edition": entry.edition,
        "license": entry.license,
        "page": entry.page,
        "url": entry.url,
        "status": entry.status,
        "translated": entry.is_translated,
        "data": dict(entry.data),
    }


def entry_full(entry: CompendiumEntry) -> dict[str, Any]:
    """Повний запис: додає текст книги й походження."""
    payload = entry_brief(entry)
    payload.update(
        {
            "schema": entry.schema,
            "text_en": entry.text_en,
            "text_uk": entry.text_uk,
            "fetched_at": entry.fetched_at,
            "notes": list(entry.notes),
        }
    )
    return payload
