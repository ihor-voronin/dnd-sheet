"""Атаки зброєю: бонус атаки й кубик урону з профілю предмета.

Правила (PHB, розділ «Зброя»):

* звичайна зброя ближнього бою — Сила;
* `finesse` — краща зі Сили й Спритності;
* `ammunition`/`range` — Спритність;
* бонус атаки = бонус майстерності + модифікатор обраної здібності;
* урон = кубик зброї + той самий модифікатор.

Профіль зброї (кубик, властивості) приходить із довідника: домен не читає
корпус, тому `WeaponProfile` — це просто значення, яке йому передали.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from dndsheet.shared.kernel import Ability
from dndsheet.shared.rules import die_size

#: Властивості, які змінюють вибір здібності (рядок із довідника, нижній регістр).
FINESSE = "finesse"
RANGED = "ammunition"


@dataclass(frozen=True, slots=True)
class WeaponProfile:
    """Що довідник знає про зброю; немає даних — немає й атаки."""

    name_en: str
    damage: str | None = None
    properties: str = ""
    #: Група з довідника: «Simple Melee Weapons», «Martial Ranged Weapons».
    group: str = ""


@dataclass(frozen=True, slots=True)
class AttackProfile:
    """Готовий рядок «Дій»: назва, бонус, урон, здібність."""

    name_en: str
    attack_bonus: int
    damage: str
    ability: Ability
    notes: str


def attack_profile(
    profile: WeaponProfile,
    *,
    strength_modifier: int,
    dexterity_modifier: int,
    proficiency: int,
    proficient: bool = True,
    alternatives: Mapping[Ability, int] | None = None,
    min_die: str | None = None,
) -> AttackProfile | None:
    """Порахувати атаку; `None`, якщо в довіднику немає кубика урону.

    `alternatives` — інші характеристики, якими вміння дозволяють бити
    (чернець — Спритність, хексблейд — Харизма, Shillelagh — Мудрість):
    береться краща. `min_die` — кістка, яку вміння ставить замість меншої
    (бойові мистецтва ченця, Shillelagh d8).
    """
    if not profile.damage:
        return None
    dice, _, damage_type = profile.damage.partition(" ")
    dice = dice.strip()
    damage_type = damage_type.strip()
    if not dice:
        return None
    properties = profile.properties.casefold()
    # Метальна зброя ближнього бою (кинджал, ручна сокира) кидається тією ж
    # характеристикою, що й б'є: Сила, або краща для finesse (PHB, p. 147).
    if FINESSE in properties:
        ability = Ability.STR if strength_modifier >= dexterity_modifier else Ability.DEX
    elif RANGED in properties:
        ability = Ability.DEX
    else:
        ability = Ability.STR
    modifier = strength_modifier if ability is Ability.STR else dexterity_modifier
    for other, value in (alternatives or {}).items():
        if value > modifier:
            ability, modifier = other, value
    if min_die and die_size(min_die) > die_size(dice):
        dice = min_die
    damage = dice + (f"{modifier:+d}" if modifier else "")
    if damage_type:
        damage = f"{damage} {damage_type}"
    return AttackProfile(
        name_en=profile.name_en,
        # Бонус майстерності — лише до зброї, якою персонаж володіє (PHB, p. 146).
        attack_bonus=(proficiency if proficient else 0) + modifier,
        damage=damage,
        ability=ability,
        notes=profile.properties,
    )
