"""Стан здоровʼя персонажа: поточні хіти, тимчасові, кидки хіт-дайсів.

Максимум не зберігається: він залежить від класів, статури й рис, тому його
рахує `DerivedStatsCalculator`. Тут — те, що є **станом**, а не правилом:
скільки зараз, скільки тимчасових, які кидки були на рівнях і чи гравець
вписав власний максимум вручну.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from dndsheet.shared.errors import ValidationError

#: Хіт-дайс у 5e не буває більшим за d20 (і меншим за d4 у звичайних класів).
MIN_HIT_DIE = 4
MAX_HIT_DIE = 20


@dataclass(frozen=True, slots=True)
class HitPointState:
    """Поточні хіти й те, з чого рахується максимум."""

    current: int = 0
    temporary: int = 0
    rolls: tuple[int, ...] = ()
    bonus: int = 0
    override_max: int | None = None

    def __post_init__(self) -> None:
        for name, value in (("current", self.current), ("temporary", self.temporary)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValidationError(f"{name} хітів має бути цілим числом")
            if value < 0:
                raise ValidationError(f"{name} хітів не може бути відʼємним")
        for roll in self.rolls:
            if not MIN_HIT_DIE <= roll <= MAX_HIT_DIE:
                raise ValidationError(
                    f"кидок хіт-дайса має бути в межах d{MIN_HIT_DIE}..d{MAX_HIT_DIE}, отримано {roll}"
                )
        if self.override_max is not None:
            if isinstance(self.override_max, bool) or not isinstance(self.override_max, int):
                raise ValidationError("власний максимум хітів має бути цілим числом")
            if self.override_max < 0:
                raise ValidationError("власний максимум хітів не може бути відʼємним")

    def with_current(self, current: int) -> "HitPointState":
        return replace(self, current=current)

    def with_temporary(self, temporary: int) -> "HitPointState":
        return replace(self, temporary=temporary)

    def with_rolls(self, rolls: tuple[int, ...]) -> "HitPointState":
        return replace(self, rolls=rolls)

    def with_bonus(self, bonus: int) -> "HitPointState":
        return replace(self, bonus=bonus)

    def with_override_max(self, override_max: int | None) -> "HitPointState":
        return replace(self, override_max=override_max)

    def apply_damage(self, amount: int) -> "HitPointState":
        """Урон спершу знімає тимчасові хіти (PHB, p. 197)."""
        if amount < 0:
            raise ValidationError("урон не може бути відʼємним")
        absorbed = min(self.temporary, amount)
        return replace(
            self,
            temporary=self.temporary - absorbed,
            current=max(0, self.current - (amount - absorbed)),
        )

    def apply_healing(self, amount: int) -> "HitPointState":
        if amount < 0:
            raise ValidationError("лікування не може бути відʼємним")
        return replace(self, current=self.current + amount)
