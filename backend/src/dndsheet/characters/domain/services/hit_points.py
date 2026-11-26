"""Максимум хітів і пул хіт-дайсів (правила 2014).

Правило просте, але його легко зіпсувати, тому воно тут одне:

* 1-й рівень персонажа — **максимум** хіт-дайса першого класу + модифікатор
  Статури;
* кожен наступний рівень — кидок (якщо гравець його записав) або середнє
  (половина дайса + 1) + модифікатор Статури;
* кожен рівень додає щонайменше 1 хіт (PHB, p. 12);
* мультиклас: перший рівень дає максимум, решта — за своїм хіт-дайсом.

`rolls` — фактичні кидки на рівнях **після першого**, у порядку класів
(спершу рівні 2..N першого класу, далі рівні 1..M другого). Такий порядок
обрано тому, що іншого джерело не дає: гравець записує кидки, коли бере
рівень, а порядок класів у агрегаті — це і є порядок узяття.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.proficiencies import GrantSource, SourceKind
from dndsheet.characters.domain.vitals import HitPointState
from dndsheet.shared.rules import ClassMechanics

ClassesAndDefinitions = Sequence[tuple[CharacterClass, ClassMechanics]]


@dataclass(frozen=True, slots=True)
class HitPointPart:
    """Складова максимуму: «1 рівень Воїна d10», «Статура», «кидки»."""

    label: str
    value: int
    source: GrantSource | None = None


@dataclass(frozen=True, slots=True)
class HitPointsView:
    """Максимум, поточні, тимчасові й складники — усе для листа."""

    maximum: int
    current: int
    temporary: int
    parts: tuple[HitPointPart, ...]

    @property
    def is_bloodied(self) -> bool:
        return self.maximum > 0 and self.current * 2 <= self.maximum

    @property
    def overflow(self) -> int:
        """Наскільки поточні хіти перевищують максимум (для warning-а)."""
        return max(0, self.current - self.maximum)


def average_hit_points(hit_die: int) -> int:
    """Середнє за правилом «половина дайса + 1» (PHB, p. 12)."""
    return hit_die // 2 + 1


def hit_point_maximum(
    classes: ClassesAndDefinitions,
    constitution_modifier: int,
    state: HitPointState | None = None,
) -> tuple[int, tuple[HitPointPart, ...]]:
    """Порахувати максимум хітів і пояснити його складниками."""
    state = state or HitPointState()
    if state.override_max is not None:
        return state.override_max, (
            HitPointPart(label="manual-override", value=state.override_max),
        )

    parts: list[HitPointPart] = []
    total = 0
    roll_index = 0
    rolls = state.rolls
    first = True
    for entry, definition in classes:
        if entry.level <= 0:
            continue
        source = GrantSource.of(SourceKind.CLASS, entry.class_key)
        for level in range(1, entry.level + 1):
            if first:
                value = definition.hit_die + constitution_modifier
                label = f"level-1-max: d{definition.hit_die}"
                first = False
            elif roll_index < len(rolls):
                value = rolls[roll_index] + constitution_modifier
                label = f"level-{level}-roll: d{definition.hit_die}"
                roll_index += 1
            else:
                value = average_hit_points(definition.hit_die) + constitution_modifier
                label = f"level-{level}-average: d{definition.hit_die}"
            value = max(1, value)
            total += value
            parts.append(HitPointPart(label=label, value=value, source=source))

    if state.bonus:
        total += state.bonus
        parts.append(HitPointPart(label="bonus", value=state.bonus))
    return total, tuple(parts)


def hit_dice_pool(classes: ClassesAndDefinitions) -> dict[int, int]:
    """Скільки хіт-дайсів якого розміру зараз має персонаж."""
    pool: dict[int, int] = {}
    for entry, definition in classes:
        if entry.level <= 0:
            continue
        pool[definition.hit_die] = pool.get(definition.hit_die, 0) + entry.level
    return pool
