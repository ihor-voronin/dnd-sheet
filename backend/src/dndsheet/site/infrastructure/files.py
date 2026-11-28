"""Файли, з яких читають відкриті сторінки: словники SPA й глосарій термінів."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)


def load_json(path: Path) -> dict[str, Any]:
    """Словники SPA (`kb-labels.json`); немає файлу чи він битий — порожньо, сторінки англійською."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.info("немає %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def glossary_path() -> Path:
    return Path(os.environ.get("DNDSHEET_CONTENT_DIR") or "content") / "glossary.uk.yml"


@lru_cache(maxsize=4)
def _terminology(path: str) -> tuple[tuple[str, str, str], ...]:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        log.info("немає глосарію %s: %s", path, exc)
        return ()
    rows = []
    for term in data.get("terms") or ():
        if isinstance(term, dict) and term.get("uk") and term.get("en"):
            group = str(term.get("id") or "").split(".")[0]
            rows.append((str(term["uk"]), str(term["en"]), group))
    return tuple(sorted(rows, key=lambda row: row[0].casefold()))


def load_terminology() -> tuple[tuple[str, str, str], ...]:
    """Пари «українською — English» з `content/glossary.uk.yml` (єдине джерело термінології)."""
    return _terminology(str(glossary_path()))
