"""Відпочинок і хіт-дайси: правила 2014, які змінюють стан листа.

Короткий відпочинок (PHB, p. 186): персонаж може витрачати хіт-дайси (це
окрема дія листа), відновлюються Pact Magic і ті класові ресурси, що
оновлюються на короткому відпочинку (Друге дихання, Дія-сплеск, Кі…).
Звичайні слоти, хіти й хіт-дайси самі не відновлюються.

Довгий відпочинок (PHB, p. 186) повертає поточні хіти до максимуму, усі слоти
(і Pact Magic), половину **загальної** кількості хіт-дайсів (округлення вниз,
мінімум один), усі класові ресурси, скидає кидки смерті й зменшує втому на 1.
Тимчасові хіти за правилами не зникають відпочинком: вони тривають, доки їх
не знімуть або не замінять новими, тому довгий відпочинок їх не чіпає.

Максимуми не дублюються в агрегаті: їх рахує `DerivedStatsCalculator`, тому
сервіс спершу обчислює лист, а потім змінює стан.
"""

from __future__ import annotations

from dataclasses import dataclass

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.domain.services.feature_resources import SHORT, resources_for
from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import Ability


@dataclass(frozen=True, slots=True)
class RestReport:
    """Що саме змінив відпочинок — для честного повідомлення на екрані."""

    kind: str
    hp_before: int
    hp_after: int
    temporary: int
    hit_dice_before: int
    hit_dice_after: int
    slots_before: int
    slots_after: int
    features_reset: tuple[str, ...]
    exhaustion_before: int
    exhaustion_after: int


class RestService:
    """Відпочинок і витрата хіт-дайсів."""

    def __init__(self, calculator: DerivedStatsCalculator | None = None) -> None:
        self._calculator = calculator or DerivedStatsCalculator()

    def long_rest(self, character: Character) -> RestReport:
        sheet = self._calculator.compute(character)
        state = character.state
        hp_before = sheet.hit_points.current
        temporary = sheet.hit_points.temporary
        dice_before = sum(state.hit_dice_used.values())
        slots_before = self._spent_slots(state)
        exhaustion_before = state.exhaustion
        resources = resources_for(character, sheet.ability_modifiers)
        reset_names = tuple(item.name_en for item in resources if item.used > 0)

        # Половина загальної кількості кісток, не половина витрачених:
        # (d10 ×2 + d6 ×3) → 5 кісток → 2 повертаються за ніч.
        total_dice = sum(character.hit_dice_pool.values())
        quota = max(1, total_dice // 2) if total_dice else 0
        restored: list[tuple[int, int]] = []
        for die in sorted(character.hit_dice_pool):
            if quota <= 0:
                break
            used = state.hit_die_used(die)
            give = min(used, quota)
            if give:
                restored.append((die, give))
                quota -= give

        # Тимчасові хіти не чіпаємо: за правилами вони живуть до зняття.
        character.set_hp(current=sheet.hit_points.maximum)
        character.set_state(
            state.cleared_slots()
            .restored_hit_dice(restored)
            .healed_state()
            .reset_features()
        )
        after = character.state
        return RestReport(
            kind="long",
            hp_before=hp_before,
            hp_after=sheet.hit_points.maximum,
            temporary=temporary,
            hit_dice_before=dice_before,
            hit_dice_after=sum(after.hit_dice_used.values()),
            slots_before=slots_before,
            slots_after=self._spent_slots(after),
            features_reset=reset_names,
            exhaustion_before=exhaustion_before,
            exhaustion_after=after.exhaustion,
        )

    def short_rest(self, character: Character) -> RestReport:
        sheet = self._calculator.compute(character)
        state = character.state
        hp = sheet.hit_points.current
        temporary = sheet.hit_points.temporary
        dice = sum(state.hit_dice_used.values())
        slots_before = self._spent_slots(state)
        exhaustion = state.exhaustion
        resources = resources_for(character, sheet.ability_modifiers)
        ready = [resource.key for resource in resources if resource.recharge == SHORT]
        reset_names = tuple(
            resource.name_en for resource in resources if resource.recharge == SHORT and resource.used
        )
        character.set_state(
            character.state.with_pact_used(0).reset_features(ready)
        )
        after = character.state
        return RestReport(
            kind="short",
            hp_before=hp,
            hp_after=hp,
            temporary=temporary,
            hit_dice_before=dice,
            hit_dice_after=dice,
            slots_before=slots_before,
            slots_after=self._spent_slots(after),
            features_reset=reset_names,
            exhaustion_before=exhaustion,
            exhaustion_after=exhaustion,
        )

    @staticmethod
    def _spent_slots(state) -> int:  # noqa: ANN001 — SheetState
        return sum(state.slots_used.values()) + state.pact_used

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
        # Беремо хіти з обчисленого листа: незадані вже замінені максимумом.
        current = min(maximum, sheet.hit_points.current + healed)

        character.set_state(character.state.with_hit_die_used(die, used + 1))
        character.set_hp(current=current)
        return healed
