"""Корпус довідника на диску: `content/compendium/<book>/<category>.jsonl`.

Один файл — одна категорія однієї книги (так його пише конвеєр ingest і так
його перевіряє `scripts/normalize`). Читач навмисно простий: ніякого кешу на
диску, ніякої БД — 3818 записів завантажуються в памʼять за один прохід, а
індекси будуються один раз на старті застосунку.

Битий запис — це помилка завантаження, а не «пропустимо й поїдемо далі»:
довідник, у якому тихо зникло закляття, гірший за довідник, який не піднявся.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from dndsheet.compendium.domain.entry import (
    CATEGORY_ORDER,
    Category,
    CompendiumEntry,
    search_key,
)
from dndsheet.compendium.domain.query import EntryQuery, Page
from dndsheet.shared.errors import ValidationError


class CorpusError(Exception):
    """Корпус на диску неможливо прочитати."""


def repo_root() -> Path:
    """Корінь репозиторію: тека, у якій є і `content`, і `contract`."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "contract").is_dir() and (parent / "content").is_dir():
            return parent
    return Path.cwd()


def default_content_dir() -> Path:
    """Тека корпусів. Перекривається змінною `DNDSHEET_CONTENT_DIR`."""
    override = os.environ.get("DNDSHEET_CONTENT_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return repo_root() / "content"


def default_compendium_dir() -> Path:
    return default_content_dir() / "compendium"


@dataclass(slots=True)
class LoadedCorpus:
    """Результат одного прочитання корпусу: записи, індекси й зауваження."""

    entries: tuple[CompendiumEntry, ...]
    by_id: dict[str, CompendiumEntry]
    by_category: dict[Category, tuple[CompendiumEntry, ...]]
    by_book: dict[str, tuple[CompendiumEntry, ...]]
    books: dict[str, int]
    warnings: tuple[str, ...] = ()

    @classmethod
    def empty(cls) -> "LoadedCorpus":
        return cls(entries=(), by_id={}, by_category={}, by_book={}, books={})


def load_corpus(directory: Path) -> LoadedCorpus:
    """Прочитати теку корпусу. Відсутня тека — порожній корпус, не помилка."""
    directory = Path(directory)
    if not directory.is_dir():
        return LoadedCorpus.empty()

    entries: list[CompendiumEntry] = []
    seen: dict[str, str] = {}
    warnings: list[str] = []

    for book_dir in sorted(path for path in directory.iterdir() if path.is_dir()):
        if book_dir.name.startswith("_"):
            continue
        for file in sorted(book_dir.glob("*.jsonl")):
            try:
                category = Category.parse(file.stem)
            except ValidationError:
                warnings.append(f"{book_dir.name}/{file.name}: невідома категорія, файл пропущено")
                continue
            entries.extend(_read_file(file, category, book_dir.name, seen, warnings))

    ordered = tuple(sorted(entries, key=lambda entry: (entry.name_en.casefold(), entry.id)))

    by_category: dict[Category, list[CompendiumEntry]] = {}
    by_book: dict[str, list[CompendiumEntry]] = {}
    books: dict[str, int] = {}
    for entry in ordered:
        by_category.setdefault(entry.category, []).append(entry)
        by_book.setdefault(entry.source_id, []).append(entry)
        books[entry.source_id] = books.get(entry.source_id, 0) + 1

    return LoadedCorpus(
        entries=ordered,
        by_id={entry.id: entry for entry in ordered},
        by_category={key: tuple(value) for key, value in by_category.items()},
        by_book={key: tuple(value) for key, value in by_book.items()},
        books=dict(sorted(books.items())),
        warnings=tuple(warnings),
    )


def _read_file(
    file: Path,
    category: Category,
    book: str,
    seen: dict[str, str],
    warnings: list[str],
) -> list[CompendiumEntry]:
    result: list[CompendiumEntry] = []
    with file.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            where = f"{book}/{file.name}:{number}"
            try:
                record: Mapping[str, Any] = json.loads(text)
            except json.JSONDecodeError as exc:
                raise CorpusError(f"{where}: невірний JSON ({exc.msg})") from exc
            try:
                entry = CompendiumEntry.from_record(record)
            except ValidationError as exc:
                raise CorpusError(f"{where}: {exc}") from exc
            if entry.category is not category:
                raise CorpusError(f"{where}: категорія {entry.category.value} у файлі {category.value}.jsonl")
            if entry.id in seen:
                warnings.append(f"{where}: повторний id {entry.id} (уже в {seen[entry.id]}), лишено перший")
                continue
            seen[entry.id] = where
            result.append(entry)
    return result


@dataclass(slots=True)
class JsonlCompendiumRepository:
    """Read-only репозиторій над текою корпусу (завантаження — при першому запиті)."""

    directory: Path | None = None
    _loaded: LoadedCorpus | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.directory is None:
            self.directory = default_compendium_dir()
        self.directory = Path(self.directory)

    # --- порт ---------------------------------------------------------------

    def get(self, entry_id: str) -> CompendiumEntry | None:
        return self._ensure_loaded().by_id.get(entry_id)

    def find(self, query: EntryQuery) -> Page:
        corpus = self._ensure_loaded()
        if query.category is not None:
            candidates = corpus.by_category.get(query.category, ())
        elif query.source_id is not None:
            candidates = corpus.by_book.get(query.source_id, ())
        else:
            candidates = corpus.entries

        matched = [entry for entry in candidates if query.matches(entry)]
        if query.q:
            # Спершу точна назва, далі назви, що з запиту починаються: на «Shield»
            # звичайний щит не має губитися за «Animated Shield» за абеткою.
            wanted = search_key(query.q)
            matched.sort(key=lambda entry: _rank(search_key(entry.name_en), wanted))
        window = matched[query.offset : query.offset + query.limit]
        return Page(
            items=tuple(window),
            total=len(matched),
            limit=query.limit,
            offset=query.offset,
        )

    def counts(self) -> Mapping[Category, int]:
        corpus = self._ensure_loaded()
        return {
            category: len(corpus.by_category[category])
            for category in CATEGORY_ORDER
            if category in corpus.by_category
        }

    def warnings(self) -> tuple[str, ...]:
        return self._ensure_loaded().warnings

    # --- додаткове (для зведення й діагностики) ------------------------------

    @property
    def directory_path(self) -> Path:
        assert self.directory is not None
        return self.directory

    def entries_count(self) -> int:
        return len(self._ensure_loaded().entries)

    def books(self) -> Mapping[str, int]:
        return self._ensure_loaded().books

    def all_entries(self) -> tuple[CompendiumEntry, ...]:
        return self._ensure_loaded().entries

    def _ensure_loaded(self) -> LoadedCorpus:
        if self._loaded is None:
            self._loaded = load_corpus(self.directory_path)
        return self._loaded


def _rank(name: str, wanted: str) -> int:
    """0 — точна назва, 1 — назва починається з запиту, 2 — решта (порядок стабільний)."""
    if name == wanted:
        return 0
    return 1 if name.startswith(wanted) else 2
