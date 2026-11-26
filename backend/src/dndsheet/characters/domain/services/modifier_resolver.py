"""Збирач бонусів: хто саме дав цифру й на що вона впливає.

`DerivedStatsCalculator` не лазить по правилах сам: спершу `ModifierResolver`
збирає **модифікатори** з джерелами (вид, передісторія, клас, риси, предмети,
ручні оверрайди), а обчислювач лише складає їх. З цього виходить те, що
потрібно на листі: «16 = 15 + 1 (людина)», а не голе 16.

Стекування: бонуси до характеристик і КЗ додаються; володіння не стекуються
(володієш або ні), тому вони живуть у `Proficiencies`, а не тут.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from dndsheet.characters.domain.proficiencies import GrantSource, SourceKind


class ModifierKind(StrEnum):
    """До чого застосовується число."""

    ABILITY = "ability"
    ARMOR_CLASS = "armor_class"
    SPEED = "speed"
    MAX_HIT_POINTS_PER_LEVEL = "max_hit_points_per_level"
    INITIATIVE = "initiative"
    SAVING_THROW = "saving_throw"
    SKILL = "skill"
    SPELL_DC = "spell_dc"
    ATTACK = "attack"


@dataclass(frozen=True, slots=True)
class Modifier:
    """Один доданок правила: скільки, до чого й хто дав."""

    kind: ModifierKind
    value: int
    source: GrantSource
    key: str | None = None
    note_en: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise ValueError("модифікатор має бути цілим числом")


@dataclass(frozen=True, slots=True)
class ModifierSet:
    """Усі зібрані модифікатори разом із запитами до них."""

    items: tuple[Modifier, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.items)

    def of(self, kind: ModifierKind, key: str | None = None) -> tuple[Modifier, ...]:
        wanted = key.casefold() if key else None
        return tuple(
            item
            for item in self.items
            if item.kind is kind and (wanted is None or (item.key or "").casefold() == wanted)
        )

    def total(self, kind: ModifierKind, key: str | None = None) -> int:
        return sum(item.value for item in self.of(kind, key))

    def ability_bonus(self, ability: str) -> int:
        return self.total(ModifierKind.ABILITY, ability)

    def by_source(self) -> dict[GrantSource, tuple[Modifier, ...]]:
        grouped: dict[GrantSource, list[Modifier]] = {}
        for item in self.items:
            grouped.setdefault(item.source, []).append(item)
        return {source: tuple(values) for source, values in grouped.items()}

    def add(self, *items: Modifier) -> "ModifierSet":
        return ModifierSet(items=self.items + tuple(items))


class ModifierResolver:
    """Збирає модифікатори з правил персонажа.

    Поки що джерела: вид (фіксовані бонуси й обраний вибір) і вручну вписані
    бонуси. Риси з числовими бонусами (ASI) і предмети — етапи 7 і 4; коли
    вони зʼявляться, додається ще один блок тут, а не в обчислювачі.
    """

    def resolve(self, character) -> ModifierSet:  # noqa: ANN001 — Character, щоб не було циклу
        collected: list[Modifier] = []

        species = character.species
        if species is not None:
            source = GrantSource.of(SourceKind.SPECIES, species.key)
            for bonus in species.ability_bonuses:
                collected.append(
                    Modifier(
                        kind=ModifierKind.ABILITY,
                        value=bonus.amount,
                        source=source,
                        key=bonus.ability.value,
                        note_en="species",
                    )
                )
            choice = species.ability_choice
            if choice is not None:
                for ability in character.ability_bonus_choices:
                    collected.append(
                        Modifier(
                            kind=ModifierKind.ABILITY,
                            value=choice.amount,
                            source=source,
                            key=ability.value,
                            note_en="species-choice",
                        )
                    )

        for item in character.chosen.items:
            continue

        return ModifierSet(items=tuple(collected))
