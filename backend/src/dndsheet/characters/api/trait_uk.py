"""Українські назви й тексти видів — із `content/translations/species`.

Корпус — це джерело правил: у ньому один `text_en`, у якому живуть і опис, і
вміння. Переклад тому не лежить у записах довідника, а поруч — файлами в
`content/translations/species/`:

    [{"id": "sha1(оригінал)[:10]", "name_uk": "Темний зір"}]
    [{"id": "sha1(оригінал)[:10]", "text_uk": "У вас темний зір..."}]

Ключ — хеш **оригіналу**, бо «Darkvision» у двадцяти видів — той самий рядок,
і перекладати його двадцять разів не потрібно. Немає перекладу — повертаємо
`None`, і екран показує текст книги (без вигадок).

Файли читаються один раз на процес; тексти книг не змінюються.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

#: Завантажений переклад: `{"names": {...}, "texts": {...}, "files": [...]}`.
_CACHE: dict[str, Any] | None = None


def ident(text: str) -> str:
    """Ключ перекладу — перші 10 hex sha1 оригіналу."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def _folder() -> Path:
    root = os.environ.get("DNDSHEET_CONTENT_DIR") or "content"
    return Path(root) / "translations" / "species"


def translations() -> dict[str, Any]:
    """Назви й тексти з усіх файлів каталогу (кеш на процес)."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    names: dict[str, str] = {}
    texts: dict[str, str] = {}
    files: list[str] = []
    folder = _folder()
    if folder.is_dir():
        for path in sorted(folder.glob("*.json")):
            try:
                rows = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(rows, list):
                continue
            files.append(path.name)
            for row in rows:
                if not isinstance(row, dict):
                    continue
                key = str(row.get("id") or "").strip()
                if not key:
                    continue
                if isinstance(row.get("name_uk"), str) and row["name_uk"].strip():
                    names[key] = row["name_uk"].strip()
                elif isinstance(row.get("text_uk"), str) and row["text_uk"].strip():
                    texts[key] = row["text_uk"].strip()
    _CACHE = {"names": names, "texts": texts, "files": files}
    return _CACHE


def name_uk(name_en: str) -> str | None:
    return translations()["names"].get(ident(name_en))


def text_uk(text_en: str) -> str | None:
    return translations()["texts"].get(ident(text_en))


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
