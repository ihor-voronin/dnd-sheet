"""Закляття персонажа й слоти Pact Magic.

Закляття належить **класу**, а не персонажу: у мультикласі «Пекельний
договір» іде окремо від слотів волшебника, і ліміт відомих заклять у кожного
класу свій. Тому `KnownSpell.class_key` обовʼязковий.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from dndsheet.shared.errors import ValidationError
from dndsheet.shared.rules import MAX_SPELL_LEVEL


@dataclass(frozen=True, slots=True)
class KnownSpell:
    """Відоме (або підготовлене) закляття персонажа."""

    name_en: str
    level: int
    class_key: str
    entry_id: str | None = None
    prepared: bool = False
    always_prepared: bool = False

    def __post_init__(self) -> None:
        if not self.name_en.strip():
            raise ValidationError("закляття без назви")
        if not self.class_key.strip():
            raise ValidationError(f"{self.name_en}: закляття без класу")
        if isinstance(self.level, bool) or not isinstance(self.level, int):
            raise ValidationError(f"{self.name_en}: рівень закляття має бути числом")
        if not 0 <= self.level <= MAX_SPELL_LEVEL:
            raise ValidationError(
                f"{self.name_en}: рівень закляття має бути 0..{MAX_SPELL_LEVEL}"
            )

    @property
    def is_cantrip(self) -> bool:
        return self.level == 0

    def prepare(self, prepared: bool = True) -> "KnownSpell":
        return replace(self, prepared=prepared)


@dataclass(frozen=True, slots=True)
class PactMagic:
    """Слоти Pact Magic: усі одного рівня, відновлюються на короткому відпочинку."""

    slots: int
    slot_level: int

    def __post_init__(self) -> None:
        if self.slots < 0 or not 0 <= self.slot_level <= MAX_SPELL_LEVEL:
            raise ValidationError("неприпустимі слоти Pact Magic")

    @property
    def empty(self) -> bool:
        return self.slots == 0


@dataclass(frozen=True, slots=True)
class SpellSlots:
    """Слоти заклять: звичайні за рівнями й (окремо) Pact Magic."""

    by_level: tuple[tuple[int, int], ...] = ()
    pact: PactMagic | None = None

    @classmethod
    def from_table(
        cls, table: tuple[int, ...], pact: PactMagic | None = None
    ) -> "SpellSlots":
        return cls(
            by_level=tuple(
                (level, count) for level, count in enumerate(table, start=1) if count
            ),
            pact=pact,
        )

    def count(self, spell_level: int) -> int:
        return dict(self.by_level).get(spell_level, 0)

    @property
    def total(self) -> int:
        return sum(count for _, count in self.by_level) + (self.pact.slots if self.pact else 0)

    @property
    def highest_level(self) -> int:
        levels = [level for level, _ in self.by_level if level]
        if self.pact and self.pact.slots:
            levels.append(self.pact.slot_level)
        return max(levels, default=0)
