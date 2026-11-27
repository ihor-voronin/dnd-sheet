"""Назви книг із реєстру джерел (`content/sources.yml`).

Реєстр веде конвеєр ingest (`scripts/ingest/sync_sources.py`), тому формат тут
стабільний і простий: `- id:` і `title:` під ним. Повноцінний YAML-парсер для
двох полів — зайва залежність, але й «перший рядок, що схожий на title» теж не
годиться: назву книги треба взяти саме з її блоку.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from dndsheet.compendium.infrastructure.jsonl_corpus import default_content_dir

_ID_RE = re.compile(r"^\s*-\s+id:\s*(?P<id>[A-Za-z0-9._-]+)\s*$")
_TITLE_RE = re.compile(r"^\s+title:\s*(?P<title>.+?)\s*$")
_DDB_RE = re.compile(r"^\s+ddb:\s*(?P<ddb>[A-Za-z0-9._-]+)\s*$")


def load_ddb_slugs(path: Path) -> dict[str, str]:
    """`id` книги → її адреса на D&D Beyond (`/sources/dnd/<slug>`), де вона є."""
    if not path.is_file():
        return {}
    slugs: dict[str, str] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _ID_RE.match(line)
        if match:
            current = match.group("id")
            continue
        match = _DDB_RE.match(line)
        if current is not None and match:
            slugs[current] = match.group("ddb")
    return slugs


def load_market(path: Path) -> dict[str, Any]:
    """Ціни й обкладинки книг (`content/books_market.json`); немає файлу — порожньо."""
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_titles(path: Path) -> dict[str, str]:
    """`id` книги → її оригінальна назва. Відсутній файл — порожня мапа."""
    if not path.is_file():
        return {}

    titles: dict[str, str] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _ID_RE.match(line)
        if match:
            current = match.group("id")
            continue
        if current is None:
            continue
        match = _TITLE_RE.match(line)
        if match:
            titles[current] = _unquote(match.group("title"))
            current = None
    return titles


def default_sources_file() -> Path:
    return default_content_dir() / "sources.yml"


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value
