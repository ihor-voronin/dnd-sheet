"""Агрегат Character (контекст `characters`).

Мінімальна, але справжня версія: інваріанти, характеристики, володіння, броня.
Розширення (класи, рівні, інвентар, закляття) — етапи 1 і 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import (
    MAX_LEVEL,
    MIN_LEVEL,
    Ability,
    AbilityScore,
    Armor,
    Skill,
)


@dataclass(slots=True)
class Character:
    """Корінь агрегату. Змінюється лише через власні методи."""

    id: str
    name: str
    level: int
    abilities: dict[Ability, AbilityScore]
    skill_proficiencies: set[Skill] = field(default_factory=set)
    save_proficiencies: set[Ability] = field(default_factory=set)
    armor: Armor | None = None
    shield: bool = False
    version: int = 1

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValidationError("Імʼя персонажа не може бути порожнім")
        if isinstance(self.level, bool) or not isinstance(self.level, int):
            raise ValidationError("Рівень має бути цілим числом")
        if not MIN_LEVEL <= self.level <= MAX_LEVEL:
            raise ValidationError(f"Рівень має бути в межах {MIN_LEVEL}..{MAX_LEVEL}")
        missing = set(Ability) - set(self.abilities)
        if missing:
            names = ", ".join(sorted(a.value for a in missing))
            raise ValidationError(f"Не задано характеристики: {names}")
        if self.version < 1:
            raise ValidationError("Версія агрегату має бути >= 1")
        self.name = self.name.strip()

    def ability(self, ability: Ability) -> AbilityScore:
        return self.abilities[ability]

    def set_ability(self, ability: Ability, score: int) -> None:
        new_score = AbilityScore(score)
        if self.abilities.get(ability) == new_score:
            return
        self.abilities[ability] = new_score
        self.bump_version()

    def set_level(self, level: int) -> None:
        if not MIN_LEVEL <= level <= MAX_LEVEL:
            raise ValidationError(f"Рівень має бути в межах {MIN_LEVEL}..{MAX_LEVEL}")
        if level == self.level:
            return
        self.level = level
        self.bump_version()

    def bump_version(self) -> None:
        self.version += 1
