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
from dndsheet.characters.domain.proficiencies import Proficiencies, ProficiencyKind
from dndsheet.characters.domain.services.derived_stats import ComputedSheet

#: Звідки взялося закляття: від класу (вибір гравця), виду або підкласу.
SpellSource = Literal[
    "class", "species", "subclass", "feat", "fighting-style", "invocation", "pact-boon", "secrets", "feature"
]

#: Як чарується закляття поза класом — українською для листа й PDF.
USAGE_UK = {
    "at will": "за бажанням, без комірки",
    "1/long rest": "раз на тривалий відпочинок без комірки",
    "1/short rest": "раз на короткий відпочинок без комірки",
    "ritual only": "лише як ритуал",
    "no slot": "без комірки",
    "invisible": "рука невидима",
}


@dataclass(frozen=True, slots=True)
class SpellRow:
    name_en: str
    level: int
    class_key: str | None
    prepared: bool
    always_prepared: bool
    source: SpellSource
    #: Власне закляття: довідник його не знає, тому й опис — від гравця.
    custom: bool = False
    description: str | None = None
    #: Короткі дані власного закляття (книжковим їх дописує довідник).
    school: str | None = None
    casting_time: str | None = None
    range: str | None = None
    duration: str | None = None
    components: str | None = None
    concentration: bool = False
    ritual: bool = False
    #: Примітка: як чарується (від виклику, риси) або що змінює (Болісний розряд).
    note: str = ""

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
class CustomFeatureRow:
    """Власне вміння для екрана й експорту: текст гравця, без чисел."""

    id: str
    name: str
    text: str
    origin: str | None
    level: int | None
    uses: int | None
    recharge: str | None
    used: int
    resource_key: str | None


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


def custom_feature_rows(character: Character) -> tuple[CustomFeatureRow, ...]:
    """Власні вміння в порядку, у якому їх додав гравець."""
    return tuple(
        CustomFeatureRow(
            id=feature.id,
            name=feature.name,
            text=feature.text,
            origin=feature.origin,
            level=feature.level,
            uses=feature.uses,
            recharge=feature.recharge,
            used=(
                min(character.state.feature_used.get(feature.resource_key, 0), feature.uses)
                if feature.resource_key is not None and feature.uses is not None
                else 0
            ),
            resource_key=feature.resource_key,
        )
        for feature in character.custom_features
    )


#: Характеристика чарування в примітці до закляття поза класом.
_ABILITY_UK = {
    "str": "Сила",
    "dex": "Спритність",
    "con": "Статура",
    "int": "Інтелект",
    "wis": "Мудрість",
    "cha": "Харизма",
}


def _casting_note(ability, computed: ComputedSheet) -> str:  # noqa: ANN001 — Ability | None
    """«Інтелект: КС 11, атака +3» — для заклять від рис, стилів і викликів."""
    if ability is None:
        return ""
    modifier = computed.ability_modifiers[ability]
    dc = 8 + computed.proficiency_bonus + modifier
    return f"{_ABILITY_UK[ability.value]}: КС {dc}, атака {computed.proficiency_bonus + modifier:+d}"


_GRANTED_SOURCES = ("species", "subclass", "feat", "fighting-style", "invocation", "pact-boon", "secrets", "feature")


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
            custom=spell.custom,
            description=spell.description,
            school=spell.school,
            casting_time=spell.casting_time,
            range=spell.range,
            duration=spell.duration,
            components=spell.components,
            concentration=spell.concentration,
            ritual=spell.ritual,
            note=computed.spell_notes.get(spell.name_en.casefold(), ""),
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
                class_key=granted.class_key,
                prepared=granted.prepared,
                always_prepared=granted.prepared,
                source=granted.source if granted.source in _GRANTED_SOURCES else "subclass",
                note="; ".join(
                    filter(
                        None,
                        [
                            USAGE_UK.get(granted.usage, granted.usage),
                            _casting_note(granted.ability, computed),
                            computed.spell_notes.get(granted.name_en.casefold()),
                        ],
                    )
                ),
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
