"""Шар українського перекладу: назви й тексти за хешем оригіналу.

Корпус — джерело правил англійською; переклад лежить поруч, у
`content/translations/<шар>/*.json`:

    [{"id": "sha1(оригінал)[:10]", "name_uk": "Темний зір"}]
    [{"id": "sha1(оригінал)[:10]", "text_uk": "У вас темний зір..."}]

Модуль спільний: ним користуються і лист (`characters.api.uk_text`), і
довідник (`compendium.api`). Немає перекладу — `None`, екран показує оригінал.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
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


def reset() -> None:
    """Забути все завантажене (тести й перегенерація перекладу)."""
    _CACHE.clear()


#: Перший рядок опису закляття — «2nd-level abjuration» або «Evocation cantrip»:
#: рівень і школу лист показує окремо, тож у тексті (і в ключі перекладу) його немає.
SPELL_HEADER = re.compile(
    r"^(?:\d+(?:st|nd|rd|th)-level\s+[a-z]+(?:\s*\(ritual\))?|[A-Z][a-z]+\s+cantrip)$",
    re.IGNORECASE,
)


def spell_body(text: str) -> str:
    """Опис закляття без першого рядка «2nd-level abjuration»."""
    lines = text.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and SPELL_HEADER.match(lines[0].strip()):
        lines.pop(0)
    return "\n".join(lines).strip()


#: Категорія довідника → шар перекладу.
LAYERS = {"spell": "spells", "feat": "feats", "optionalfeature": "optional-features"}


def entry_name_uk(category: str, name_en: str) -> str | None:
    layer = LAYERS.get(category)
    return name_uk(layer, name_en) if layer else None


def entry_text_uk(category: str, text_en: str) -> str | None:
    """Переклад тексту запису довідника; закляття — без рядка рівня й школи."""
    layer = LAYERS.get(category)
    if not layer or not text_en:
        return None
    return text_uk(layer, spell_body(text_en) if category == "spell" else text_en)
