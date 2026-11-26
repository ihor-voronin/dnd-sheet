"""Сценарії довідника: зведення, пошук, класи, підкласи, класові закляття.

Тут живе єдина логіка «як з корпусу дістати те, що просить візард і лист».
API — тонка обгортка над цим сервісом, тому кожен сценарій можна перевірити
без HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from dndsheet.compendium.domain.entry import (
    CATEGORY_ORDER,
    Category,
    CompendiumEntry,
    search_key,
)
from dndsheet.compendium.domain.query import EntryQuery, Page
from dndsheet.compendium.domain.repository import (
    CompendiumRepository,
    MechanicsRepository,
    SpellListRepository,
)
from dndsheet.shared.errors import NotFoundError
from dndsheet.shared.rules import (
    BackgroundMechanics,
    ClassMechanics,
    SpeciesMechanics,
)

MAX_SPELL_LEVEL = 9
PAGE_SIZE = 200


@dataclass(frozen=True, slots=True)
class BookSummary:
    source_id: str
    title: str
    entries: int


@dataclass(frozen=True, slots=True)
class ClassSummary:
    """Клас і те, що про нього треба знати на екрані вибору."""

    entry: CompendiumEntry
    subclasses: int


@dataclass(frozen=True, slots=True)
class ClassSpells:
    """Закляття класу й чесне джерело цих даних.

    `source`:
    * `spell-lists` — зі списків «Spell Lists» у книгах (повний набір);
    * `entry-data` — з поля `data.classes` заклять (неповний, лише там, де є);
    * `none` — списку немає; порожній результат означає «не знаю», а не «нуль».
    """

    class_name: str
    spells: tuple[CompendiumEntry, ...]
    source: str


@dataclass(frozen=True, slots=True)
class CorpusSummary:
    entries: int
    categories: tuple[tuple[Category, int], ...]
    books: tuple[BookSummary, ...]
    spell_lists: bool
    warnings: tuple[str, ...]
    mechanics: bool = False


class CompendiumService:
    """Сценарії читання довідника."""

    def __init__(
        self,
        repository: CompendiumRepository,
        spell_lists: SpellListRepository | None = None,
        titles: Mapping[str, str] | None = None,
        mechanics: MechanicsRepository | None = None,
    ) -> None:
        self._repository = repository
        self._spell_lists = spell_lists
        self._titles = dict(titles or {})
        self._mechanics = mechanics
        self._spells_by_name: dict[str, CompendiumEntry] | None = None
        self._books_by_source: dict[str, int] | None = None

    # --- зведення -----------------------------------------------------------

    def summary(self) -> CorpusSummary:
        counts = self._repository.counts()
        warnings = list(self._repository.warnings())
        if self._mechanics is not None and not self._mechanics.available():
            warnings.extend(self._mechanics.warnings())
        total = sum(counts.values())
        if total == 0:
            warnings.append(
                "корпус не знайдено або він порожній: перевірте DNDSHEET_CONTENT_DIR"
            )

        books = tuple(
            BookSummary(
                source_id=source_id,
                title=self._titles.get(source_id, source_id),
                entries=count,
            )
            for source_id, count in sorted(self._book_counts().items())
        )
        categories = tuple(
            (category, counts[category])
            for category in CATEGORY_ORDER
            if counts.get(category)
        )
        return CorpusSummary(
            entries=total,
            categories=categories,
            books=books,
            spell_lists=bool(self._spell_lists and self._spell_lists.books()),
            warnings=tuple(warnings),
            mechanics=self.mechanics_available(),
        )

    # --- пошук --------------------------------------------------------------

    def entries(self, query: EntryQuery) -> Page:
        return self._repository.find(query)

    def entry(self, entry_id: str) -> CompendiumEntry:
        found = self._repository.get(entry_id)
        if found is None:
            raise NotFoundError(f"запису {entry_id} немає в довіднику")
        return found

    # --- класи --------------------------------------------------------------

    def classes(self) -> tuple[ClassSummary, ...]:
        classes = self._all(Category.CLASS)
        subclasses = self._all(Category.SUBCLASS)
        per_class: dict[str, int] = {}
        for subclass in subclasses:
            if subclass.subclass_of:
                key = subclass.subclass_of
                per_class[key] = per_class.get(key, 0) + 1
        return tuple(
            ClassSummary(
                entry=entry,
                subclasses=per_class.get(search_key(entry.name_en), 0),
            )
            for entry in classes
        )

    def subclasses(self, class_name: str) -> tuple[CompendiumEntry, ...]:
        return self._all(Category.SUBCLASS, subclass_of=class_name)

    # --- механіки -----------------------------------------------------------

    def mechanics_available(self) -> bool:
        """Чи є похідні індекси механік (без них не зібрати персонажа)."""
        return bool(self._mechanics and self._mechanics.available())

    def mechanics_warnings(self) -> tuple[str, ...]:
        return tuple(self._mechanics.warnings()) if self._mechanics else (
            "механіки класів не підключені",
        )

    def class_definitions(self) -> tuple[ClassMechanics, ...]:
        """Усі класи 2014 з механіками, за назвою."""
        if self._mechanics is None:
            return ()
        return tuple(sorted(self._mechanics.classes().values(), key=lambda item: item.name_en))

    def class_mechanics(self, class_name: str) -> ClassMechanics:
        if self._mechanics is None:
            raise NotFoundError("механіки класів не підключені")
        found = self._mechanics.class_mechanics(class_name)
        if found is None:
            raise NotFoundError(f"немає механік класу {class_name!r}")
        return found

    def species_list(self) -> tuple[SpeciesMechanics, ...]:
        """Базові види (без підрас), за назвою."""
        if self._mechanics is None:
            return ()
        return tuple(sorted(self._mechanics.species().values(), key=lambda item: item.name_en))

    def subspecies_of(self, species_name: str) -> tuple[SpeciesMechanics, ...]:
        """Підраси виду («Dwarf» → «Hill Dwarf», «Mountain Dwarf»)."""
        if self._mechanics is None:
            return ()
        wanted = species_name.strip().casefold()
        return tuple(
            sorted(
                (
                    item
                    for item in self._mechanics.subspecies().values()
                    if (item.subrace_of or "").casefold() == wanted
                ),
                key=lambda item: item.name_en,
            )
        )

    def species_mechanics(self, name: str) -> SpeciesMechanics:
        if self._mechanics is None:
            raise NotFoundError("механіки видів не підключені")
        found = self._mechanics.species_mechanics(name)
        if found is None:
            raise NotFoundError(f"немає механік виду {name!r}")
        return found

    def backgrounds(self) -> tuple[BackgroundMechanics, ...]:
        if self._mechanics is None:
            return ()
        return tuple(
            sorted(self._mechanics.backgrounds().values(), key=lambda item: item.name_en)
        )

    def background_mechanics(self, name: str) -> BackgroundMechanics:
        if self._mechanics is None:
            raise NotFoundError("механіки передісторій не підключені")
        found = self._mechanics.background_mechanics(name)
        if found is None:
            raise NotFoundError(f"немає механік передісторії {name!r}")
        return found

    # --- закляття -----------------------------------------------------------

    def class_spells(
        self, class_name: str, max_level: int = MAX_SPELL_LEVEL
    ) -> ClassSpells:
        """Закляття класу до `max_level` включно."""
        if not 0 <= max_level <= MAX_SPELL_LEVEL:
            max_level = MAX_SPELL_LEVEL

        if self._spell_lists is not None:
            names = self._spell_lists.spell_names_for(class_name)
            if names:
                spells = self._resolve_spell_names(names, max_level)
                if spells:
                    return ClassSpells(
                        class_name=class_name, spells=spells, source="spell-lists"
                    )

        by_data = self._spells_from_entry_data(class_name, max_level)
        if by_data:
            return ClassSpells(class_name=class_name, spells=by_data, source="entry-data")
        return ClassSpells(class_name=class_name, spells=(), source="none")

    # --- інше ---------------------------------------------------------------

    def optional_features(
        self, feature_type: str | None = None
    ) -> tuple[CompendiumEntry, ...]:
        return self._all(Category.OPTIONAL_FEATURE, feature_type=feature_type)

    def feats(self) -> tuple[CompendiumEntry, ...]:
        """Усі риси корпусу, за назвою (для вибору на підвищенні рівня)."""
        return tuple(sorted(self._all(Category.FEAT), key=lambda entry: entry.name_en))

    def spells(
        self,
        level: int | None = None,
        school: str | None = None,
        class_name: str | None = None,
        query: str | None = None,
    ) -> Page:
        if class_name is not None:
            known = self.class_spells(class_name)
            if known.source == "none":
                return Page(items=(), total=0, limit=PAGE_SIZE, offset=0)
            found = tuple(
                entry
                for entry in known.spells
                if (level is None or entry.spell_level == level)
                and (school is None or entry.spell_school == school.casefold())
                and (not query or search_key(query) in entry.search_text)
            )
            return Page(items=found, total=len(found), limit=PAGE_SIZE, offset=0)
        return self._repository.find(
            EntryQuery(
                category=Category.SPELL,
                level=level,
                school=school,
                q=query,
                limit=PAGE_SIZE,
            )
        )

    # --- внутрішнє ----------------------------------------------------------

    def _all(self, category: Category, **filters: object) -> tuple[CompendiumEntry, ...]:
        """Усі записи категорії (з пагінацією всередині, щоб не знати ліміт)."""
        collected: list[CompendiumEntry] = []
        offset = 0
        while True:
            page = self._repository.find(
                EntryQuery(category=category, limit=PAGE_SIZE, offset=offset, **filters)  # type: ignore[arg-type]
            )
            collected.extend(page.items)
            offset += PAGE_SIZE
            if offset >= page.total:
                return tuple(collected)

    def _resolve_spell_names(
        self, names: Mapping[int, tuple[str, ...]], max_level: int
    ) -> tuple[CompendiumEntry, ...]:
        index = self._spell_index()
        seen: set[str] = set()
        result: list[CompendiumEntry] = []
        for level in sorted(names):
            if level > max_level:
                continue
            for name in names[level]:
                key = search_key(name)
                if key in seen:
                    continue
                entry = index.get(key)
                if entry is None:
                    continue
                seen.add(key)
                result.append(entry)
        return tuple(result)

    def _spells_from_entry_data(
        self, class_name: str, max_level: int
    ) -> tuple[CompendiumEntry, ...]:
        wanted = search_key(class_name)
        found: list[CompendiumEntry] = []
        for entry in self._all(Category.SPELL):
            if entry.spell_level is not None and entry.spell_level > max_level:
                continue
            if wanted in {search_key(name) for name in entry.spell_classes}:
                found.append(entry)
        return tuple(found)

    def _spell_index(self) -> dict[str, CompendiumEntry]:
        """Назва закляття → запис. Перевага: SRD, потім найменший id."""
        if self._spells_by_name is not None:
            return self._spells_by_name

        index: dict[str, CompendiumEntry] = {}
        for entry in self._all(Category.SPELL):
            key = search_key(entry.name_en)
            current = index.get(key)
            if current is None or _preferred(entry, current):
                index[key] = entry
        self._spells_by_name = index
        return index

    def _book_counts(self) -> dict[str, int]:
        if self._books_by_source is not None:
            return self._books_by_source

        books = getattr(self._repository, "books", None)
        if callable(books):
            self._books_by_source = dict(books())
            return self._books_by_source

        counts: dict[str, int] = {}
        for category in Category:
            for entry in self._all(category):
                counts[entry.source_id] = counts.get(entry.source_id, 0) + 1
        self._books_by_source = counts
        return counts


def _preferred(candidate: CompendiumEntry, current: CompendiumEntry) -> bool:
    """SRD-запис кращий за пропрієтарний: його текст можна показувати будь-де."""
    if candidate.license == "srd" and current.license != "srd":
        return True
    if candidate.license != "srd" and current.license == "srd":
        return False
    return candidate.id < current.id
