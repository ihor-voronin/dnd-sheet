"""Володіння персонажа разом із джерелом кожного володіння.

Навіщо окремий тип, а не `set[Skill]`: на листі й у суперечках треба знати
**звідки** володіння. Те саме володіння може прийти з класу, виду,
передісторії або вручну — і коли персонаж міняє клас, важливо, що саме
зникне. Тому кожен запис несе `GrantSource`, а не просто `True`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable


class ProficiencyKind(StrEnum):
    """Що саме є володінням."""

    SKILL = "skill"
    SAVING_THROW = "saving_throw"
    ARMOR = "armor"
    WEAPON = "weapon"
    TOOL = "tool"
    LANGUAGE = "language"


class SourceKind(StrEnum):
    """Звідки прийшло володіння."""

    CLASS = "class"
    SPECIES = "species"
    BACKGROUND = "background"
    FEAT = "feat"
    ITEM = "item"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class GrantSource:
    """Джерело правила: «клас fighter», «вид hill dwarf», «вручну».

    `key` — це стабільний ключ, а не підпис: переклад живе в контексті
    `localization`, домен не має знати, як це звучить українською.
    """

    kind: SourceKind
    key: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("джерело володіння без ключа")

    @classmethod
    def of(cls, kind: SourceKind, key: str) -> "GrantSource":
        return cls(kind=kind, key=key.strip().casefold())

    @classmethod
    def manual(cls, key: str = "manually-added") -> "GrantSource":
        return cls(kind=SourceKind.MANUAL, key=key)

    def __str__(self) -> str:
        return f"{self.kind.value}:{self.key}"


@dataclass(frozen=True, slots=True)
class Proficiency:
    """Одне володіння: вид, значення й джерело."""

    kind: ProficiencyKind
    value: str
    source: GrantSource

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("володіння без значення")

    @property
    def key(self) -> tuple[ProficiencyKind, str]:
        return (self.kind, self.value.casefold())

    def __str__(self) -> str:
        return f"{self.kind.value}:{self.value} ({self.source})"


@dataclass(frozen=True, slots=True)
class Proficiencies:
    """Набір володінь. Дублікати з різних джерел зберігаються — це не шум:
    саме так видно, що навичка прийшла і з класу, і з передісторії."""

    items: tuple[Proficiency, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    @classmethod
    def of(cls, *items: Proficiency) -> "Proficiencies":
        return cls(items=tuple(items))

    def add(self, *items: Proficiency) -> "Proficiencies":
        added = [item for item in items if item not in self.items]
        return Proficiencies(items=self.items + tuple(added))

    def merge(self, other: "Proficiencies") -> "Proficiencies":
        return self.add(*other.items)

    def has(self, kind: ProficiencyKind, value: str) -> bool:
        wanted = value.casefold()
        return any(item.kind is kind and item.value.casefold() == wanted for item in self.items)

    def sources(self, kind: ProficiencyKind, value: str) -> tuple[GrantSource, ...]:
        wanted = value.casefold()
        return tuple(
            item.source
            for item in self.items
            if item.kind is kind and item.value.casefold() == wanted
        )

    def values(self, kind: ProficiencyKind) -> tuple[str, ...]:
        seen: list[str] = []
        for item in self.items:
            if item.kind is kind and item.value not in seen:
                seen.append(item.value)
        return tuple(seen)

    def of_kind(self, kind: ProficiencyKind) -> tuple[Proficiency, ...]:
        return tuple(item for item in self.items if item.kind is kind)

    def without_source(self, kind: SourceKind, key: str) -> "Proficiencies":
        """Прибрати все, що дало конкретне джерело (зміна класу, виду…)."""
        wanted = key.strip().casefold()
        return Proficiencies(
            items=tuple(
                item
                for item in self.items
                if not (item.source.kind is kind and item.source.key == wanted)
            )
        )

    def extend(self, items: Iterable[Proficiency]) -> "Proficiencies":
        return self.add(*items)
