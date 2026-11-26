"""Стан листа: те, що гравець змінює за столом, а не правила.

Домен відрізняє **правила** (КЗ, максимум хітів, слоти — похідні, їх не
зберігають) від **стану** (скільки хітів зараз, скільки слотів витрачено,
кидки смерті, натхнення, втома, ручні виправлення чисел, нотатки). Цей
модуль — друга половина.

`overrides` — свідомий компроміс з правилами: гравець може вписати своє
число (КЗ від магічного предмета, якого немає в довіднику), і тоді лист
позначає поле як «вручну». Ключі — стабільні id полів (`armor_class`,
`skill:athletics`, `save:str`), а не індекси: інакше після зміни порядку
виправлення поїхали б на інше поле.

Максимумів тут немає: скільки слотів і хіт-дайсів має персонаж, знає
`DerivedStatsCalculator`. Тому `SheetState` перевіряє лише абсолютні межі
(слоти 1..9, кидки смерті 0..3, втома 0..6), а «не більше максимуму» —
справа застосунку, який бачить обчислений лист.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Iterable, Mapping

from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import Ability, Skill

#: Поля, які можна виправити вручну. Решта — ні: не варто давати вписувати
#: «рівень» чи «бонус майстерності», бо це руйнує похідні.
OVERRIDABLE = frozenset(
    {
        "armor_class",
        "hit_points_max",
        "initiative",
        "speed",
        "passive_perception",
        "inspiration",
    }
)

#: Нотатки листа — вільний текст, але з фіксованими розділами.
NOTE_KEYS = ("appearance", "allies", "enemies", "backstory", "notes")


def _check_count(value: int, what: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{what} має бути цілим числом")
    if value < 0:
        raise ValidationError(f"{what} не може бути відʼємним")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{what} не може бути більшим за {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class DeathSaves:
    """Кидки проти смерті: три успіхи — стабілізувався, три провали — смерть."""

    successes: int = 0
    failures: int = 0

    def __post_init__(self) -> None:
        _check_count(self.successes, "успіхи кидків смерті", 3)
        _check_count(self.failures, "провали кидків смерті", 3)

    @property
    def dead(self) -> bool:
        return self.failures >= 3

    @property
    def stable(self) -> bool:
        return self.successes >= 3

    def with_successes(self, value: int) -> "DeathSaves":
        return DeathSaves(successes=value, failures=self.failures)

    def with_failures(self, value: int) -> "DeathSaves":
        return DeathSaves(successes=self.successes, failures=value)


def _valid_override_key(key: str) -> str:
    cleaned = key.strip()
    if cleaned in OVERRIDABLE:
        return cleaned
    if cleaned.startswith("skill:"):
        try:
            Skill(cleaned.split(":", 1)[1])
        except ValueError as exc:
            raise ValidationError(f"невідома навичка у виправленні: {cleaned!r}") from exc
        return cleaned
    if cleaned.startswith("save:"):
        try:
            Ability(cleaned.split(":", 1)[1])
        except ValueError as exc:
            raise ValidationError(f"невідомий порятунок у виправленні: {cleaned!r}") from exc
        return cleaned
    raise ValidationError(f"поле {key!r} не можна виправити вручну")


@dataclass(frozen=True, slots=True)
class SheetState:
    """Усе, що лист памʼятає про похід: лічильники, виправлення, нотатки."""

    slots_used: Mapping[int, int] = field(default_factory=lambda: MappingProxyType({}))
    pact_used: int = 0
    hit_dice_used: Mapping[int, int] = field(default_factory=lambda: MappingProxyType({}))
    #: Витрачені класові ресурси: ключ ресурсу -> скільки разів використано.
    feature_used: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))
    death_saves: DeathSaves = field(default_factory=DeathSaves)
    inspiration: bool = False
    exhaustion: int = 0
    overrides: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))
    notes: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        _check_count(self.pact_used, "витрачені слоти Pact Magic")
        _check_count(self.exhaustion, "рівень втоми", 6)
        cleaned_slots: dict[int, int] = {}
        for level, count in self.slots_used.items():
            try:
                level = int(level)
            except (TypeError, ValueError) as exc:
                raise ValidationError(f"рівень слотів {level!r} має бути числом") from exc
            if not 1 <= level <= 9:
                raise ValidationError(f"рівень слотів має бути 1..9, отримано {level}")
            cleaned_slots[level] = _check_count(int(count), f"слоти {level} рівня")
        cleaned_dice: dict[int, int] = {}
        for die, count in self.hit_dice_used.items():
            try:
                die = int(die)
            except (TypeError, ValueError) as exc:
                raise ValidationError(f"хіт-дайс {die!r} має бути числом") from exc
            if not 4 <= die <= 20:
                raise ValidationError(f"хіт-дайс має бути d4..d20, отримано d{die}")
            cleaned_dice[die] = _check_count(int(count), f"витрачені d{die}")
        cleaned_features: dict[str, int] = {}
        for key, count in self.feature_used.items():
            cleaned_key = str(key).strip()
            if not cleaned_key:
                raise ValidationError("порожній ключ класового ресурсу")
            cleaned_features[cleaned_key] = _check_count(
                int(count), f"витрачено ресурсу {cleaned_key!r}"
            )
        cleaned_overrides: dict[str, int] = {}
        for key, value in self.overrides.items():
            cleaned_overrides[_valid_override_key(str(key))] = _check_count(
                int(value), f"виправлення {key!r}"
            )
        cleaned_notes: dict[str, str] = {}
        for key, value in self.notes.items():
            if key not in NOTE_KEYS:
                raise ValidationError(f"невідомий розділ нотаток {key!r}")
            cleaned_notes[key] = str(value)
        object.__setattr__(self, "slots_used", MappingProxyType(cleaned_slots))
        object.__setattr__(self, "hit_dice_used", MappingProxyType(cleaned_dice))
        object.__setattr__(self, "feature_used", MappingProxyType(cleaned_features))
        object.__setattr__(self, "overrides", MappingProxyType(cleaned_overrides))
        object.__setattr__(self, "notes", MappingProxyType(cleaned_notes))

    # --- слоти -------------------------------------------------------------

    def slot_used(self, level: int) -> int:
        return int(self.slots_used.get(level, 0))

    def with_slots_used(self, used: Mapping[int, int]) -> "SheetState":
        return replace(self, slots_used=MappingProxyType(dict(used)))

    def with_slot_used(self, level: int, used: int) -> "SheetState":
        values = dict(self.slots_used)
        if used <= 0:
            values.pop(level, None)
        else:
            values[level] = used
        return self.with_slots_used(values)

    def with_pact_used(self, used: int) -> "SheetState":
        return replace(self, pact_used=used)

    # --- хіт-дайси ---------------------------------------------------------

    def hit_die_used(self, die: int) -> int:
        return int(self.hit_dice_used.get(die, 0))

    def with_hit_dice_used(self, used: Mapping[int, int]) -> "SheetState":
        return replace(self, hit_dice_used=MappingProxyType(dict(used)))

    def with_hit_die_used(self, die: int, used: int) -> "SheetState":
        values = dict(self.hit_dice_used)
        if used <= 0:
            values.pop(die, None)
        else:
            values[die] = used
        return self.with_hit_dice_used(values)

    # --- класові ресурси ---------------------------------------------------

    def feature_used_count(self, key: str) -> int:
        return int(self.feature_used.get(key, 0))

    def with_feature_used(self, values: Mapping[str, int]) -> "SheetState":
        return replace(self, feature_used=MappingProxyType(dict(values)))

    def with_feature_use(self, key: str, used: int) -> "SheetState":
        values = dict(self.feature_used)
        if used <= 0:
            values.pop(key, None)
        else:
            values[key] = used
        return self.with_feature_used(values)

    def reset_features(self, ready: Iterable[str] | None = None) -> "SheetState":
        """Повернути ресурси: `None` — усі, інакше лише перелічені ключі."""
        if ready is None:
            return self.with_feature_used({})
        keys = set(ready)
        return self.with_feature_used(
            {key: value for key, value in self.feature_used.items() if key not in keys}
        )

    # --- інше --------------------------------------------------------------

    def with_death_saves(self, saves: DeathSaves) -> "SheetState":
        return replace(self, death_saves=saves)

    def with_inspiration(self, value: bool) -> "SheetState":
        return replace(self, inspiration=value)

    def with_exhaustion(self, value: int) -> "SheetState":
        return replace(self, exhaustion=value)

    def with_override(self, key: str, value: int) -> "SheetState":
        values = dict(self.overrides)
        values[_valid_override_key(key)] = value
        return replace(self, overrides=MappingProxyType(values))

    def without_override(self, key: str) -> "SheetState":
        values = dict(self.overrides)
        values.pop(key, None)
        return replace(self, overrides=MappingProxyType(values))

    def with_notes(self, notes: Mapping[str, str]) -> "SheetState":
        values = dict(self.notes)
        for key, value in notes.items():
            if key not in NOTE_KEYS:
                raise ValidationError(f"невідомий розділ нотаток {key!r}")
            values[key] = "" if value is None else str(value)
        return replace(self, notes=MappingProxyType(values))

    # --- масове скидання ---------------------------------------------------

    def cleared_slots(self) -> "SheetState":
        return replace(
            self,
            slots_used=MappingProxyType({}),
            pact_used=0,
        )

    def restored_hit_dice(self, restored: Iterable[tuple[int, int]]) -> "SheetState":
        """Повернути частину витрачених хіт-дайсів: [(die, count_to_return)]."""
        values = dict(self.hit_dice_used)
        for die, count in restored:
            left = max(0, values.get(die, 0) - count)
            if left:
                values[die] = left
            else:
                values.pop(die, None)
        return self.with_hit_dice_used(values)

    def healed_state(self) -> "SheetState":
        """Після довгого відпочинку: смерть і натхнення скидаються, втома -1."""
        return replace(
            self,
            death_saves=DeathSaves(),
            exhaustion=max(0, self.exhaustion - 1),
        )
