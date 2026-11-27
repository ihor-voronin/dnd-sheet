"""Стан здоровʼя персонажа: поточні хіти, тимчасові, кидки кісток хітів.

Максимум не зберігається: він залежить від класів, статури й рис, тому його
рахує `DerivedStatsCalculator`. Тут — те, що є **станом**, а не правилом:
скільки зараз, скільки тимчасових, які кидки були на рівнях і чи гравець
вписав власний максимум вручну.

`current = None` означає «гравець ще не чіпав хіти» — лист показує максимум.
Це не те саме, що `0`: нуль хітів — це непритомний персонаж із кидками
смерті, і плутати ці два стани не можна (лист показував би повні хіти замість
нуля).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from dndsheet.shared.errors import ValidationError

#: Кість хітів у 5e не буває більшим за d20 (і меншим за d4 у звичайних класів).
MIN_HIT_DIE = 4
MAX_HIT_DIE = 20


@dataclass(frozen=True, slots=True)
class HitPointState:
    """Поточні хіти й те, з чого рахується максимум."""

    #: `None` — «не задано»: показуємо максимум. `0` — непритомний.
    current: int | None = None
    temporary: int = 0
    #: Кидки на рівнях **після першого**, у порядку класів. `None` на місці
    #: кидка — «на цьому рівні взято середнє»; це потрібно, коли рівень
    #: узято в класі, який стоїть у списку не останнім, і кидок доводиться
    #: вставляти в середину.
    rolls: tuple[int | None, ...] = ()
    bonus: int = 0
    override_max: int | None = None

    def __post_init__(self) -> None:
        if self.current is not None:
            if isinstance(self.current, bool) or not isinstance(self.current, int):
                raise ValidationError("current хітів має бути цілим числом")
            if self.current < 0:
                raise ValidationError("current хітів не може бути відʼємним")
        if isinstance(self.temporary, bool) or not isinstance(self.temporary, int):
            raise ValidationError("temporary хітів має бути цілим числом")
        if self.temporary < 0:
            raise ValidationError("temporary хітів не може бути відʼємним")
        for roll in self.rolls:
            if roll is None:
                continue
            if MIN_HIT_DIE <= roll <= MAX_HIT_DIE:
                continue
            raise ValidationError(
                f"кидок кості хітів має бути в межах d{MIN_HIT_DIE}..d{MAX_HIT_DIE}, отримано {roll}"
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

    def with_rolls(self, rolls: tuple[int | None, ...]) -> "HitPointState":
        return replace(self, rolls=rolls)

    def with_roll_at(self, index: int, roll: int | None) -> "HitPointState":
        """Вставити кидок на місце рівня, зсунувши пізніші кидки.

        Кидки впорядковані за рівнями, тому кидок у класі, який стоїть не
        останнім у списку, **вставляється**, а не дописується: інакше чужі
        рівні отримали б не свої числа. Місця, яких ще не було в кортежі,
        стають `None` — «середнє».
        """
        if index < 0:
            raise ValidationError("місце кидка не може бути відʼємним")
        values: list[int | None] = list(self.rolls)
        while len(values) < index:
            values.append(None)
        values.insert(index, roll)
        return replace(self, rolls=tuple(values))

    def with_bonus(self, bonus: int) -> "HitPointState":
        return replace(self, bonus=bonus)

    def with_override_max(self, override_max: int | None) -> "HitPointState":
        return replace(self, override_max=override_max)

    def apply_damage(self, amount: int) -> "HitPointState":
        """Урон спершу знімає тимчасові хіти (PHB, p. 197)."""
        if amount < 0:
            raise ValidationError("урон не може бути відʼємним")
        current = self._known_current("урон")
        absorbed = min(self.temporary, amount)
        return replace(
            self,
            temporary=self.temporary - absorbed,
            current=max(0, current - (amount - absorbed)),
        )

    def apply_healing(self, amount: int) -> "HitPointState":
        if amount < 0:
            raise ValidationError("лікування не може бути відʼємним")
        return replace(self, current=self._known_current("лікування") + amount)

    def _known_current(self, action: str) -> int:
        """Хіти «як є». Незадані хіти — помилка виклику, а не мовчазний нуль.

        Хто знає максимум — той і має спершу його підставити
        (`RestService` читає максимум із обчисленого листа).
        """
        if self.current is None:
            raise ValidationError(
                f"{action} на невідомих поточних хітах: спершу задайте current"
            )
        return self.current
