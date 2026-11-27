"""Похідний індекс класових списків заклять (`content/index/spell-lists.json`).

Навіщо окремий індекс: у корпусі закляття майже не мають `data.classes`
(заповнено лише там, де джерело дало список), а візарду потрібно «які закляття
доступні цьому класу з рівня 1». Списки збирає `scripts/ingest/spell_lists.py`
з таблиць «Spell Lists» у книгах; читач тут лише віддає їх.

Індекс похідний і не обовʼязковий: якщо його немає (свіжий клон), сервіс
чесно скаже, що списку немає, а не вдасть, що заклять у класа нуль.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from dndsheet.compendium.domain.entry import search_key
from dndsheet.compendium.infrastructure.jsonl_corpus import default_content_dir

SCHEMA = "spell-lists/1"


class SpellListsError(Exception):
    """Індекс класових списків пошкоджено."""


def default_spell_lists_file() -> Path:
    return default_content_dir() / "index" / "spell-lists.json"


@dataclass(slots=True)
class JsonSpellListRepository:
    """Класові списки заклять з одного JSON-файлу."""

    path: Path | None = None
    _cache: dict[str, dict[int, tuple[str, ...]]] | None = field(default=None, init=False, repr=False)
    _books: tuple[str, ...] = field(default=(), init=False, repr=False)

    def __post_init__(self) -> None:
        if self.path is None:
            self.path = default_spell_lists_file()
        self.path = Path(self.path)

    def spell_names_for(self, class_name: str) -> Mapping[int, tuple[str, ...]] | None:
        lists = self._ensure_loaded()
        return lists.get(search_key(class_name))

    def books(self) -> tuple[str, ...]:
        self._ensure_loaded()
        return self._books

    def available(self) -> bool:
        """Чи є індекс на диску (для зведення й діагностики)."""
        assert self.path is not None
        return self.path.is_file()

    def _ensure_loaded(self) -> dict[str, dict[int, tuple[str, ...]]]:
        if self._cache is not None:
            return self._cache

        assert self.path is not None
        if not self.path.is_file():
            self._cache = {}
            self._books = ()
            return self._cache

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SpellListsError(f"{self.path.name}: невірний JSON ({exc.msg})") from exc

        if payload.get("schema") != SCHEMA:
            raise SpellListsError(f"{self.path.name}: схема {payload.get('schema')!r}, очікується {SCHEMA!r}")

        merged: dict[str, dict[int, set[str]]] = {}
        books: list[str] = []
        for book, per_class in (payload.get("lists") or {}).items():
            if not per_class:
                continue
            books.append(book)
            for class_name, per_level in per_class.items():
                bucket = merged.setdefault(search_key(class_name), {})
                for level, names in per_level.items():
                    bucket.setdefault(int(level), set()).update(names)

        self._cache = {
            class_name: {level: tuple(sorted(names, key=str.casefold)) for level, names in sorted(per_level.items())}
            for class_name, per_level in merged.items()
        }
        self._books = tuple(sorted(books))
        return self._cache
