"""Порти контексту `compendium`.

Домен каже, *що* йому потрібно; звідки саме це береться (JSONL-корпус,
кеш у памʼяті, згодом — БД) вирішує інфраструктура. Порушення цього правила
легко помітити: `lint-imports` забороняє домену імпортувати інфраструктуру.
"""

from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable

from dndsheet.compendium.domain.entry import Category, CompendiumEntry
from dndsheet.compendium.domain.query import EntryQuery, Page
from dndsheet.shared.rules import (
    BackgroundMechanics,
    ClassMechanics,
    SpeciesMechanics,
)


@runtime_checkable
class CompendiumRepository(Protocol):
    """Джерело записів довідника (read-only)."""

    def get(self, entry_id: str) -> CompendiumEntry | None:
        """Запис за id (`<source_id>/<category>/<slug>`) або None."""

    def find(self, query: EntryQuery) -> Page:
        """Сторінка записів, що проходять фільтр."""

    def counts(self) -> Mapping[Category, int]:
        """Скільки записів у кожній категорії (лише непорожні)."""

    def warnings(self) -> tuple[str, ...]:
        """Що пішло не так під час завантаження (пропущені теки, биті файли)."""


@runtime_checkable
class SpellListRepository(Protocol):
    """Класові списки заклять.

    У самому корпусі закляття майже не несуть `data.classes`, тому
    «закляття класу» береться з окремого похідного індексу.
    """

    def spell_names_for(self, class_name: str) -> Mapping[int, tuple[str, ...]] | None:
        """Назви заклять за рівнями або None, якщо списку для класу немає."""

    def books(self) -> tuple[str, ...]:
        """Книги, з яких списки зібрані."""


@runtime_checkable
class MechanicsRepository(Protocol):
    """Механіки класів, видів і передісторій.

    Текст умінь живе в корпусі записів; тут — числа, без яких не порахувати
    лист: хіт-дайс, володіння, бонуси характеристик, таблиці слотів. Індекс
    похідний (`content/index/*-mechanics.json`), тому його може не бути —
    тоді `available()` каже `false`, а не кидає виняток.
    """

    def available(self) -> bool:
        """Чи є індекс механік на диску."""

    def warnings(self) -> tuple[str, ...]:
        """Що не так з індексом (немає, стара схема, битий JSON)."""

    def classes(self) -> Mapping[str, ClassMechanics]:
        """Усі класи 2014, ключ — назва в нижньому регістрі."""

    def class_mechanics(self, name: str) -> ClassMechanics | None:
        """Механіки класу за назвою (без регістру й пунктуації)."""

    def species(self) -> Mapping[str, SpeciesMechanics]:
        """Базові види (без підрас)."""

    def subspecies(self) -> Mapping[str, SpeciesMechanics]:
        """Підраси; `subrace_of` вказує на базовий вид."""

    def species_mechanics(self, name: str) -> SpeciesMechanics | None:
        """Вид або підраса за назвою."""

    def backgrounds(self) -> Mapping[str, BackgroundMechanics]:
        """Передісторії."""

    def background_mechanics(self, name: str) -> BackgroundMechanics | None:
        """Передісторія за назвою."""
