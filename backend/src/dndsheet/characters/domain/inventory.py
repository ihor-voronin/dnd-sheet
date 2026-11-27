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

#: Скільком предметам можна настроїтися одночасно (PHB, p. 138).
MAX_ATTUNED = 3


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
    #: Для зброї: власний урон гравця (повний рядок, як «1d8+3 slashing»).
    #: Порожньо — урон рахується з довідника й модифікатора здібності.
    damage: str | None = None
    #: Зброя угоди (Pact of the Blade, PHB, p. 107): викликана чи звʼязана.
    pact_weapon: bool = False
    #: Зброя Хекс-воїна (Hex Warrior, XGtE, p. 55): обрана після тривалого відпочинку.
    hex_weapon: bool = False

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
        if (self.pact_weapon or self.hex_weapon) and self.kind is not ItemKind.WEAPON:
            raise ValidationError(f"{self.name_en}: зброєю угоди чи Хекс-воїна буває лише зброя")
        if self.damage is not None:
            if not str(self.damage).strip():
                raise ValidationError(f"{self.name_en}: порожній урон зброї")
            if self.kind is not ItemKind.WEAPON:
                raise ValidationError(
                    f"{self.name_en}: власний урон буває лише у зброї"
                )

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
        if self.attuned_count > MAX_ATTUNED:
            raise ValidationError(
                f"одночасно можна настроїтися не більше ніж на {MAX_ATTUNED} предмети"
            )
        if sum(1 for item in self.items if item.pact_weapon) > 1:
            raise ValidationError("зброя угоди буває лише одна (PHB, p. 107)")
        if sum(1 for item in self.items if item.hex_weapon) > 1:
            raise ValidationError("Хекс-воїн обирає лише одну зброю (XGtE, p. 55)")

    def __len__(self) -> int:
        return len(self.items)

    def add(self, *items: InventoryItem) -> "Inventory":
        """Додати предмети; споряджена броня (чи щит) знімає попередню.

        Так само, як `equip`: інакше «додати одягнуту броню» впиралося б у
        правило «одна броня одночасно», хоча гравець просто перевдягається.
        """
        current = list(self.items)
        for item in items:
            if item.equipped and (item.is_armor or item.is_shield):
                current = [
                    other.equipped_copy(False)
                    if other.equipped
                    and (
                        (item.is_armor and other.is_armor)
                        or (item.is_shield and other.is_shield)
                    )
                    else other
                    for other in current
                ]
            current = _release_bonds(current, item)
            current.append(item)
        return Inventory(items=tuple(current), money=self.money)

    def replace_at(self, index: int, item: InventoryItem) -> "Inventory":
        """Замінити предмет за порядком у списку (порядок — стабільний).

        Якщо предмет стає спорядженим, інша броня (чи щит) знімається: так
        само, як `equip`. Інакше редагування предмета вперлося б у правило
        «одна броня одночасно», яке стосується стану, а не самої правки.
        """
        self._check_index(index)
        items = list(self.items)
        if item.equipped and (item.is_armor or item.is_shield):
            for position, other in enumerate(items):
                if position == index or not other.equipped:
                    continue
                if (item.is_armor and other.is_armor) or (
                    item.is_shield and other.is_shield
                ):
                    items[position] = other.equipped_copy(False)
        items[index] = None  # type: ignore[call-overload] — місце звільняється для нової позначки
        items = _release_bonds(items, item)
        items[index] = item
        return Inventory(items=tuple(items), money=self.money)

    @property
    def pact_weapon(self) -> InventoryItem | None:
        return next((item for item in self.items if item.pact_weapon), None)

    @property
    def hex_weapon(self) -> InventoryItem | None:
        return next((item for item in self.items if item.hex_weapon), None)

    def remove_at(self, index: int) -> "Inventory":
        self._check_index(index)
        items = list(self.items)
        del items[index]
        return Inventory(items=tuple(items), money=self.money)

    def item_at(self, index: int) -> InventoryItem:
        self._check_index(index)
        return self.items[index]

    def _check_index(self, index: int) -> None:
        if isinstance(index, bool) or not isinstance(index, int):
            raise ValidationError("номер предмета має бути цілим числом")
        if not 0 <= index < len(self.items):
            raise ValidationError(f"у інвентарі немає предмета №{index + 1}")

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


def _release_bonds(items: list, item: InventoryItem) -> list:
    """Нова зброя угоди (чи Хекс-воїна) знімає позначку з попередньої — як споряджена броня."""
    return [
        other
        if other is None
        else _replace(
            other,
            pact_weapon=other.pact_weapon and not item.pact_weapon,
            hex_weapon=other.hex_weapon and not item.hex_weapon,
        )
        for other in items
    ]
