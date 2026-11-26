"""Рядки листа, які показують і екран, і експорт.

Спокуса продублювати «як зібрати список заклять» у серіалізаторі й у
побудові документа велика, але тоді PDF і екран розійшлися б тихо: додав
закляття від підкласу в одному місці — у другому його немає. Тому збирання
рядків живе тут, а рендери лише форматують.

Рядки — прості значення (frozen dataclass), без логіки листа: жодних
обчислень, лише вибір і сортування того, що вже порахував домен.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.inventory import InventoryItem
from dndsheet.characters.domain.proficiencies import ProficiencyKind, Proficiencies
from dndsheet.characters.domain.services.derived_stats import ComputedSheet

#: Звідки взялося закляття: від класу (вибір гравця), виду або підкласу.
SpellSource = Literal["class", "species", "subclass"]


@dataclass(frozen=True, slots=True)
class SpellRow:
    name_en: str
    level: int
    class_key: str | None
    prepared: bool
    always_prepared: bool
    source: SpellSource

    @property
    def is_cantrip(self) -> bool:
        return self.level == 0


@dataclass(frozen=True, slots=True)
class FeatureRow:
    name_en: str
    level: int
    class_key: str
    class_name: str


@dataclass(frozen=True, slots=True)
class ProficiencyRow:
    kind: ProficiencyKind
    value: str
    source_kind: str
    source_key: str


@dataclass(frozen=True, slots=True)
class ItemRow:
    name_en: str
    kind: str
    quantity: int
    weight_lb: float
    equipped: bool
    attuned: bool
    armor_base: int | None
    dex_cap: int | None


def feature_rows(character: Character) -> tuple[FeatureRow, ...]:
    """Уміння класів на поточному рівні — назви й рівень, без тексту."""
    items: list[FeatureRow] = []
    for entry, definition in character.class_entries():
        for feature in definition.features_at(entry.level):
            items.append(
                FeatureRow(
                    name_en=feature.name_en,
                    level=feature.level,
                    class_key=entry.class_key,
                    class_name=definition.name_en,
                )
            )
    items.sort(key=lambda item: (item.level, item.name_en))
    return tuple(items)


def spell_rows(character: Character, computed: ComputedSheet) -> tuple[SpellRow, ...]:
    """Закляття персонажа: класові (вибір гравця) + надані видом і підкласом."""
    rows: list[SpellRow] = [
        SpellRow(
            name_en=spell.name_en,
            level=spell.level,
            class_key=spell.class_key,
            prepared=spell.prepared or spell.always_prepared,
            always_prepared=spell.always_prepared,
            source="class",
        )
        for spell in character.spells
    ]
    known = {row.name_en.casefold() for row in rows}
    for granted in computed.granted_spells:
        # Домен жреця може дати закляття, яке гравець і сам узяв класом —
        # показуємо один рядок, а не два.
        if granted.name_en.casefold() in known:
            continue
        known.add(granted.name_en.casefold())
        rows.append(
            SpellRow(
                name_en=granted.name_en,
                level=granted.spell_level,
                class_key=None,
                prepared=granted.prepared,
                always_prepared=granted.prepared,
                source="species" if granted.source == "species" else "subclass",
            )
        )
    return tuple(rows)


def proficiency_rows(collected: Proficiencies) -> tuple[ProficiencyRow, ...]:
    """Володіння для екрана й експорту, без буквальних повторів.

    Домен навмисно зберігає те саме володіння з різних джерел: «Атлетика» від
    класу й від передісторії — два факти. Але коли збігається ще й джерело,
    це вже один факт, записаний двічі (повторний вибір, перенесена чернетка),
    і на аркуші він не має друкуватися двічі.
    """
    rows: list[ProficiencyRow] = []
    seen: set[tuple[ProficiencyKind, str, str, str]] = set()
    for item in collected.items:
        key = (item.kind, item.value.casefold(), item.source.kind.value, item.source.key)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            ProficiencyRow(
                kind=item.kind,
                value=item.value,
                source_kind=item.source.kind.value,
                source_key=item.source.key,
            )
        )
    return tuple(rows)


def item_rows(character: Character) -> tuple[ItemRow, ...]:
    return tuple(_item_row(item) for item in character.inventory.items)


def _item_row(item: InventoryItem) -> ItemRow:
    return ItemRow(
        name_en=item.name_en,
        kind=item.kind.value,
        quantity=item.quantity,
        weight_lb=item.weight_lb,
        equipped=item.equipped,
        attuned=item.attuned,
        armor_base=item.armor_base,
        dex_cap=item.dex_cap,
    )


def spell_sort_key(row: SpellRow) -> tuple[int, str]:
    return (row.level, row.name_en.casefold())


__all__ = [
    "FeatureRow",
    "ItemRow",
    "ProficiencyRow",
    "SpellRow",
    "feature_rows",
    "item_rows",
    "proficiency_rows",
    "spell_rows",
    "spell_sort_key",
]
