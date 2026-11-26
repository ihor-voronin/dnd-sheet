"""Порти контексту `compendium`.

Домен каже, *що* йому потрібно; звідки саме це береться (JSONL-корпус,
кеш у памʼяті, згодом — БД) вирішує інфраструктура. Порушення цього правила
легко помітити: `lint-imports` забороняє домену імпортувати інфраструктуру.
"""

from __future__ import annotations

from typing import Mapping, Protocol, runtime_checkable

from dndsheet.compendium.domain.entry import Category, CompendiumEntry
from dndsheet.compendium.domain.query import EntryQuery, Page


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
