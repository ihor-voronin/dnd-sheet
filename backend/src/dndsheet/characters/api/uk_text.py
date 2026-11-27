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

import hashlib
import json
import os
from pathlib import Path
from typing import Any

#: Завантажений переклад за шляхом каталогу: `{"names", "texts", "files"}`.
_CACHE: dict[str, dict[str, Any]] = {}

EMPTY: dict[str, Any] = {"names": {}, "texts": {}, "files": []}


def ident(text: str) -> str:
    """Ключ перекладу — перші 10 hex sha1 оригіналу."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def folder(layer: str) -> Path:
    """Каталог шару: `content/translations/<layer>`."""
    root = os.environ.get("DNDSHEET_CONTENT_DIR") or "content"
    return Path(root) / "translations" / layer


def read(layer: str) -> dict[str, Any]:
    """Назви й тексти з усіх файлів шару (кеш на процес і на шлях)."""
    path = folder(layer)
    key = str(path.resolve()) if path.exists() else str(path)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    names: dict[str, str] = {}
    texts: dict[str, str] = {}
    files: list[str] = []
    if path.is_dir():
        for file in sorted(path.glob("*.json")):
            try:
                rows = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(rows, dict):  # предмети: {"items": [{"id": "<id запису>", ...}]}
                rows = next((value for value in rows.values() if isinstance(value, list)), None)
            if not isinstance(rows, list):
                continue
            files.append(file.name)
            for row in rows:
                if not isinstance(row, dict):
                    continue
                ident_key = str(row.get("id") or "").strip()
                if not ident_key:
                    continue
                if isinstance(row.get("name_uk"), str) and row["name_uk"].strip():
                    names[ident_key] = row["name_uk"].strip()
                if isinstance(row.get("text_uk"), str) and row["text_uk"].strip():
                    texts[ident_key] = row["text_uk"].strip()

    loaded = {"names": names, "texts": texts, "files": files}
    _CACHE[key] = loaded
    return loaded


def name_uk(layer: str, name_en: str) -> str | None:
    names = read(layer)["names"]
    # Корпус пише апостроф по-різному («Dark One's» і «Dark One’s») — пробуємо обидва.
    return names.get(ident(name_en)) or names.get(ident(name_en.replace("'", "’"))) or names.get(
        ident(name_en.replace("’", "'"))
    )


def text_uk(layer: str, text_en: str) -> str | None:
    return read(layer)["texts"].get(ident(text_en))


def with_english(name_en: str, uk: str | None) -> str:
    """Правило перекладу проєкту: «Українська (English)»; немає перекладу — оригінал."""
    if not uk or uk.strip().casefold() == name_en.strip().casefold():
        return name_en
    return f"{uk} ({name_en})"


def reset() -> None:
    """Забути все завантажене (тести й перегенерація перекладу)."""
    _CACHE.clear()


def enrich_item(
    payload: dict[str, Any], layer: str, *, text_field: str | None = None
) -> dict[str, Any]:
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
    "with_english",
    "EMPTY",
    "enrich_item",
    "folder",
    "ident",
    "name_uk",
    "read",
    "reset",
    "text_uk",
]
