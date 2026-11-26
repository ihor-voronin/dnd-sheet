"""Інвентар персонажа: предмети, вага, споряджене й гроші.

Броня й щит — теж предмети, а не окремі поля персонажа: на листі вони
в інвентарі, а КЗ залежить від того, чи предмет **споряджено**. Тому
`InventoryItem` несе числа броні лише тоді, коли це справді броня.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace as _replace
from enum import StrEnum

from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import Money

#: Скільки фунтів тягне одна одиниця Сила (PHB, p. 176).
CARRY_PER_STRENGTH = 15


class ItemKind(StrEnum):
    """Що це за предмет — від цього залежить, як він впливає на лист."""

    ARMOR = "armor"
    SHIELD = "shield"
    WEAPON = "weapon"
    GEAR = "gear"
    TOOL = "tool"
    PACK = "pack"
    MAGIC = "magic"


@dataclass(frozen=True, slots=True)
class InventoryItem:
    """Один предмет у інвентарі."""

    name_en: str
    kind: ItemKind = ItemKind.GEAR
    quantity: int = 1
    weight_lb: float = 0.0
    equipped: bool = False
    attuned: bool = False
    entry_id: str | None = None
    #: Для броні: базовий КЗ і межа бонусу Спритності (`None` — без межі).
    armor_base: int | None = None
    dex_cap: int | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.name_en.strip():
            raise ValidationError("предмет без назви")
        if isinstance(self.quantity, bool) or not isinstance(self.quantity, int):
            raise ValidationError(f"{self.name_en}: кількість має бути цілим числом")
        if self.quantity < 0:
            raise ValidationError(f"{self.name_en}: кількість не може бути відʼємною")
        if self.weight_lb < 0:
            raise ValidationError(f"{self.name_en}: вага не може бути відʼємною")
        if self.kind is ItemKind.ARMOR:
            if self.armor_base is None or self.armor_base < 10:
                raise ValidationError(
                    f"{self.name_en}: броня без базового КЗ (мінімум 10)"
                )
        elif self.armor_base is not None:
            raise ValidationError(
                f"{self.name_en}: базовий КЗ буває лише в броні"
            )
        if self.dex_cap is not None and self.dex_cap < 0:
            raise ValidationError(f"{self.name_en}: межа Спритності не може бути відʼємною")

    @property
    def total_weight(self) -> float:
        return round(self.weight_lb * self.quantity, 3)

    @property
    def is_armor(self) -> bool:
        return self.kind is ItemKind.ARMOR

    @property
    def is_shield(self) -> bool:
        return self.kind is ItemKind.SHIELD

    def equipped_copy(self, equipped: bool) -> "InventoryItem":
        return _replace(self, equipped=equipped)


@dataclass(frozen=True, slots=True)
class Inventory:
    """Предмети й гаманець. Незмінний: кожна зміна — новий інвентар."""

    items: tuple[InventoryItem, ...] = ()
    money: Money = field(default_factory=Money)

    def __post_init__(self) -> None:
        if sum(1 for item in self.items if item.is_armor and item.equipped) > 1:
            raise ValidationError("одночасно можна носити лише одну броню")
        if sum(1 for item in self.items if item.is_shield and item.equipped) > 1:
            raise ValidationError("одночасно можна тримати лише один щит")

    def __len__(self) -> int:
        return len(self.items)

    def add(self, *items: InventoryItem) -> "Inventory":
        return Inventory(items=self.items + tuple(items), money=self.money)

    def with_money(self, money: Money) -> "Inventory":
        return Inventory(items=self.items, money=money)

    def equip(self, name: str, equipped: bool = True) -> "Inventory":
        """Спорядити предмет за назвою. Броня й щит — взаємовиключні."""
        wanted = name.strip().casefold()
        found = False
        updated: list[InventoryItem] = []
        for item in self.items:
            if item.name_en.casefold() != wanted:
                updated.append(item)
                continue
            found = True
            if equipped and item.is_armor:
                updated = [
                    other.equipped_copy(False) if other.is_armor and other.equipped else other
                    for other in updated
                ]
            if equipped and item.is_shield:
                updated = [
                    other.equipped_copy(False) if other.is_shield and other.equipped else other
                    for other in updated
                ]
            updated.append(item.equipped_copy(equipped))
        if not found:
            raise ValidationError(f"у інвентарі немає предмета {name!r}")
        return Inventory(items=tuple(updated), money=self.money)

    @property
    def total_weight(self) -> float:
        return round(sum(item.total_weight for item in self.items), 3)

    @property
    def worn_armor(self) -> InventoryItem | None:
        return next((item for item in self.items if item.is_armor and item.equipped), None)

    @property
    def worn_shield(self) -> InventoryItem | None:
        return next((item for item in self.items if item.is_shield and item.equipped), None)

    @property
    def attuned_count(self) -> int:
        return sum(1 for item in self.items if item.attuned)
