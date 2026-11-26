"""Відпочинок і хіт-дайси: правила 2014, які змінюють стан листа.

Короткий відпочинок (PHB, p. 186) відновлює Pact Magic варлока й нічого
більше: звичайні слоти, хіти й хіт-дайси лишаються як були. Хіт-дайси
витрачають окремо — це і є лікування під час відпочинку.

Довгий відпочинок (PHB, p. 186) повертає все: поточні хіти до максимуму,
усі слоти (і Pact Magic), половину витрачених хіт-дайсів (мінімум один),
скидає тимчасові хіти, кидки смерті й зменшує втому на 1.

Максимуми не дублюються в агрегаті: їх рахує `DerivedStatsCalculator`, тому
сервіс спершу обчислює лист, а потім змінює стан.
"""

from __future__ import annotations

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import Ability


class RestService:
    """Відпочинок і витрата хіт-дайсів."""

    def __init__(self, calculator: DerivedStatsCalculator | None = None) -> None:
        self._calculator = calculator or DerivedStatsCalculator()

    def long_rest(self, character: Character) -> None:
        sheet = self._calculator.compute(character)
        maximum = sheet.hit_points.maximum
        state = character.state

        total_dice = sum(character.hit_dice_pool.values())
        quota = max(1, (total_dice + 1) // 2) if total_dice else 0
        restored: list[tuple[int, int]] = []
        for die in sorted(character.hit_dice_pool):
            if quota <= 0:
                break
            used = state.hit_die_used(die)
            give = min(used, quota)
            if give:
                restored.append((die, give))
                quota -= give

        character.set_hp(current=maximum, temporary=0)
        character.set_state(
            state.cleared_slots().restored_hit_dice(restored).healed_state()
        )

    def short_rest(self, character: Character) -> None:
        character.set_state(character.state.with_pact_used(0))

    def spend_hit_die(self, character: Character, die: int, roll: int) -> int:
        """Витратити хіт-дайс і полікуватися: кидок + Статура, не вище максимуму."""
        pool = character.hit_dice_pool
        if die not in pool:
            raise ValidationError(f"у персонажа немає хіт-дайсів d{die}")
        used = character.state.hit_die_used(die)
        if used >= pool[die]:
            raise ValidationError(f"усі хіт-дайси d{die} вже витрачені")
        if isinstance(roll, bool) or not isinstance(roll, int) or not 1 <= roll <= die:
            raise ValidationError(f"кидок d{die} має бути 1..{die}, отримано {roll}")

        sheet = self._calculator.compute(character)
        healed = max(0, roll + sheet.ability_modifiers[Ability.CON])
        maximum = sheet.hit_points.maximum
        current = min(maximum, character.hp.current + healed)

        character.set_state(character.state.with_hit_die_used(die, used + 1))
        character.set_hp(current=current)
        return healed
