"""Спільне ядро (shared kernel): поняття, які поділяють `characters` і `sheets`.

Тут лише чисті value objects без інфраструктури. Підписи (українською) не живуть
у цьому модулі: вони належать контексту `localization` (глосарій → лейбли).
"""

from __future__ import annotations

import random
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from dndsheet.shared.errors import ValidationError


class Ability(StrEnum):
    STR = "str"
    DEX = "dex"
    CON = "con"
    INT = "int"
    WIS = "wis"
    CHA = "cha"


class Skill(StrEnum):
    ATHLETICS = "athletics"
    ACROBATICS = "acrobatics"
    SLEIGHT_OF_HAND = "sleight_of_hand"
    STEALTH = "stealth"
    ARCANA = "arcana"
    HISTORY = "history"
    INVESTIGATION = "investigation"
    NATURE = "nature"
    RELIGION = "religion"
    ANIMAL_HANDLING = "animal_handling"
    INSIGHT = "insight"
    MEDICINE = "medicine"
    PERCEPTION = "perception"
    SURVIVAL = "survival"
    DECEPTION = "deception"
    INTIMIDATION = "intimidation"
    PERFORMANCE = "performance"
    PERSUASION = "persuasion"


#: Якій характеристиці підпорядкована кожна навичка (правила 2014).
SKILL_ABILITY: Mapping[Skill, Ability] = {
    Skill.ATHLETICS: Ability.STR,
    Skill.ACROBATICS: Ability.DEX,
    Skill.SLEIGHT_OF_HAND: Ability.DEX,
    Skill.STEALTH: Ability.DEX,
    Skill.ARCANA: Ability.INT,
    Skill.HISTORY: Ability.INT,
    Skill.INVESTIGATION: Ability.INT,
    Skill.NATURE: Ability.INT,
    Skill.RELIGION: Ability.INT,
    Skill.ANIMAL_HANDLING: Ability.WIS,
    Skill.INSIGHT: Ability.WIS,
    Skill.MEDICINE: Ability.WIS,
    Skill.PERCEPTION: Ability.WIS,
    Skill.SURVIVAL: Ability.WIS,
    Skill.DECEPTION: Ability.CHA,
    Skill.INTIMIDATION: Ability.CHA,
    Skill.PERFORMANCE: Ability.CHA,
    Skill.PERSUASION: Ability.CHA,
}

MIN_ABILITY_SCORE = 1
MAX_ABILITY_SCORE = 30
MIN_LEVEL = 1
MAX_LEVEL = 20


@dataclass(frozen=True, slots=True)
class AbilityScore:
    """Значення характеристики 1..30 з похідним модифікатором."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise ValidationError("Значення характеристики має бути цілим числом")
        if not MIN_ABILITY_SCORE <= self.value <= MAX_ABILITY_SCORE:
            raise ValidationError(
                f"Значення характеристики має бути в межах "
                f"{MIN_ABILITY_SCORE}..{MAX_ABILITY_SCORE}, отримано {self.value}"
            )

    @property
    def modifier(self) -> int:
        """Модифікатор за 5e: floor((score - 10) / 2)."""
        return (self.value - 10) // 2


def proficiency_bonus(level: int) -> int:
    """Бонус майстерності за рівнем 1..20."""
    if isinstance(level, bool) or not isinstance(level, int):
        raise ValidationError("Рівень має бути цілим числом")
    if not MIN_LEVEL <= level <= MAX_LEVEL:
        raise ValidationError(f"Рівень має бути в межах {MIN_LEVEL}..{MAX_LEVEL}")
    return 2 + (level - 1) // 4


@dataclass(frozen=True, slots=True)
class Armor:
    """Броня: базовий КЗ і (опційно) межа бонусу від Спритності."""

    name: str
    base: int
    dex_cap: int | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValidationError("Назва броні не може бути порожньою")
        if self.base < 10:
            raise ValidationError("Базовий КЗ броні не може бути меншим за 10")
        if self.dex_cap is not None and self.dex_cap < 0:
            raise ValidationError("Межа бонусу Спритності не може бути відʼємною")


_DICE_RE = re.compile(
    r"^\s*(?P<count>\d{1,3})?d(?P<sides>\d{1,4})(?P<mod>[+-]\d{1,3})?\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class DiceExpression:
    """Кидок у нотації NdM±K. Без переваг/перешкод — вони властивість кидка, не кубика."""

    count: int
    sides: int
    modifier: int = 0

    def __post_init__(self) -> None:
        if not 1 <= self.count <= 100:
            raise ValidationError("Кількість кубиків має бути в межах 1..100")
        if self.sides < 2:
            raise ValidationError("Кубик має мати щонайменше 2 грані")

    @classmethod
    def parse(cls, expression: str) -> "DiceExpression":
        match = _DICE_RE.match(expression or "")
        if not match:
            raise ValidationError(f"Некоректний запис кидка: {expression!r}")
        count = int(match.group("count") or 1)
        sides = int(match.group("sides"))
        modifier = int(match.group("mod") or 0)
        return cls(count=count, sides=sides, modifier=modifier)

    @property
    def minimum(self) -> int:
        return self.count + self.modifier

    @property
    def maximum(self) -> int:
        return self.count * self.sides + self.modifier

    @property
    def average(self) -> float:
        return self.count * (self.sides + 1) / 2 + self.modifier

    def roll(self, rng: random.Random | None = None) -> int:
        generator = rng or random
        return sum(generator.randint(1, self.sides) for _ in range(self.count)) + self.modifier

    def __str__(self) -> str:
        mod = f"{self.modifier:+d}" if self.modifier else ""
        return f"{self.count}d{self.sides}{mod}"


#: Скільки срібла (у золоті) коштує одна монета кожного номіналу (PHB, p. 143).
COIN_IN_GP: Mapping[str, float] = {
    "pp": 10.0,
    "gp": 1.0,
    "ep": 0.5,
    "sp": 0.1,
    "cp": 0.01,
}


@dataclass(frozen=True, slots=True)
class Money:
    """Гаманець: п'ять номіналів, як на листі (pp, gp, ep, sp, cp)."""

    pp: int = 0
    gp: int = 0
    ep: int = 0
    sp: int = 0
    cp: int = 0

    def __post_init__(self) -> None:
        for name in COIN_IN_GP:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValidationError(f"кількість {name} має бути цілим числом")
            if value < 0:
                raise ValidationError(f"кількість {name} не може бути відʼємною")

    @property
    def total_gp(self) -> float:
        """Уся сума в золотих — для вантажу й порівняння цін."""
        return round(sum(getattr(self, coin) * rate for coin, rate in COIN_IN_GP.items()), 2)

    def plus(self, other: "Money") -> "Money":
        return Money(
            pp=self.pp + other.pp,
            gp=self.gp + other.gp,
            ep=self.ep + other.ep,
            sp=self.sp + other.sp,
            cp=self.cp + other.cp,
        )

    def to_dict(self) -> dict[str, int]:
        return {"pp": self.pp, "gp": self.gp, "ep": self.ep, "sp": self.sp, "cp": self.cp}
