"""Комірки заклять і числа заклинателя, включно з мультикласом.

Правила, які тут зашиті (PHB, 2014):

* рівень заклинателя = повні класи цілком + половина напівзаклинателів
  (з округленням вниз) + третина третинних; Pact Magic warlock-а окремо;
* **один заклинательський клас** читає власну таблицю класу, **два й більше** —
  таблицю мультикласу за рівнем заклинателя. Це не дрібниця: для paladin-а 5
  таблиця мультикласу дає 3 комірки 1 рівня, а власна — 4 + 2 другого, бо
  напівзаклинатель отримує новий рівень комірок на непарних рівнях;
* опір закляттям = 8 + бонус майстерності + модифікатор характеристики
  заклинань; бонус атаки = бонус майстерності + модифікатор;
* «підготовлених» у підготовлюючого класу не більше ніж модифікатор + рівень
  класу (мінімум 1), у відомого — ліміт із таблиці класу.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.spells import PactMagic, SpellSlots
from dndsheet.shared.kernel import Ability
from dndsheet.shared.rules import (
    PACT_SLOT_TABLE,
    ClassMechanics,
    caster_level,
    prepared_spell_limit,
    spell_slots,
)

ClassesAndDefinitions = Sequence[tuple[CharacterClass, ClassMechanics]]


@dataclass(frozen=True, slots=True)
class ClassCasting:
    """Числа заклинателя для одного класу персонажа."""

    class_key: str
    name_en: str
    ability: Ability
    level: int
    modifier: int
    save_dc: int
    attack_bonus: int
    cantrips_limit: int
    spells_known_limit: int | None
    prepared_limit: int | None
    prepares: bool
    #: Найвищий рівень закляття цього класу на його рівні (для вибору).
    max_spell_level: int = 0


@dataclass(frozen=True, slots=True)
class Spellcasting:
    """Усе про закляття персонажа, що обчислюється: комірки, DC, ліміти."""

    caster_level: int
    slots: SpellSlots
    classes: tuple[ClassCasting, ...]
    #: Звідки взялися звичайні комірки: `class` — таблиця єдиного класу,
    #: `multiclass` — таблиця за рівнем заклинателя, `none` — закляттів немає.
    slots_from: str = "none"

    @property
    def casts_spells(self) -> bool:
        return bool(self.classes)

    def for_class(self, class_key: str) -> ClassCasting | None:
        wanted = class_key.strip().casefold()
        return next((item for item in self.classes if item.class_key == wanted), None)


def pact_magic_for(level: int) -> PactMagic | None:
    """Pact Magic за рівнем warlock-а; `None`, якщо рівня немає."""
    if not 1 <= level <= len(PACT_SLOT_TABLE):
        return None
    slots, slot_level = PACT_SLOT_TABLE[level - 1]
    return PactMagic(slots=slots, slot_level=slot_level) if slots else None


class SpellSlotService:
    """Обчислювач комірок і характеристик заклинань."""

    def compute(
        self,
        classes: ClassesAndDefinitions,
        abilities: Mapping[Ability, int],
        proficiency_bonus: int,
    ) -> Spellcasting:
        # Паладин і слідопит отримують «Spellcasting» лише на 2 рівні (PHB, p. 84,
        # 91): на 1 рівні в них ні комірок, ні заговорів — і заклинателем для
        # таблиці мультикласу такий клас ще не є.
        casters = [
            (entry, definition)
            for entry, definition in classes
            if definition.casts_spells
            and entry.level > 0
            and (definition.max_spell_level(entry.level) > 0 or definition.cantrips_at(entry.level) > 0)
        ]
        if not casters:
            return Spellcasting(caster_level=0, slots=SpellSlots(), classes=())
        combined = caster_level((definition.caster_progression, entry.level) for entry, definition in casters)
        # Таблиця мультикласу — лише коли «Spellcasting» мають два класи й
        # більше; Pact Magic чаклуна сюди не рахується (PHB, p. 164–165):
        # паладин 5 + чаклун 1 бере комірки з таблиці паладина.
        standard_casters = [(entry, definition) for entry, definition in casters if not definition.is_pact_magic]
        if len(standard_casters) > 1:
            standard = spell_slots(combined) if combined else ()
            slots_from = "multiclass"
        elif standard_casters:
            entry, definition = standard_casters[0]
            standard = definition.slots_at(entry.level)
            slots_from = "class"
        else:
            standard = ()
            slots_from = "class"
        pact: PactMagic | None = None
        for entry, definition in casters:
            if not definition.is_pact_magic:
                continue
            from_data = definition.pact_at(entry.level)
            pact = (
                PactMagic(slots=from_data[0], slot_level=from_data[1]) if from_data[0] else pact_magic_for(entry.level)
            )

        details: list[ClassCasting] = []
        for entry, definition in casters:
            ability = definition.spellcasting_ability
            if ability is None:
                continue
            score = abilities.get(ability, 10)
            modifier = (score - 10) // 2
            known = definition.spells_known_at(entry.level)
            prepared = (
                prepared_spell_limit(modifier, entry.level, definition.caster_progression)
                if definition.prepares_spells
                else None
            )
            details.append(
                ClassCasting(
                    class_key=entry.class_key,
                    name_en=definition.name_en,
                    ability=ability,
                    level=entry.level,
                    modifier=modifier,
                    save_dc=8 + proficiency_bonus + modifier,
                    attack_bonus=proficiency_bonus + modifier,
                    cantrips_limit=definition.cantrips_at(entry.level),
                    spells_known_limit=known,
                    prepared_limit=prepared,
                    prepares=definition.prepares_spells,
                    max_spell_level=definition.max_spell_level(entry.level),
                )
            )

        return Spellcasting(
            caster_level=combined,
            slots=SpellSlots.from_table(standard, pact=pact),
            classes=tuple(details),
            slots_from=slots_from,
        )


def spellcasting_for_classes(
    classes: ClassesAndDefinitions,
    abilities: Mapping[Ability, int] | None = None,
    proficiency_bonus: int = 2,
) -> Spellcasting:
    """Зручна обгортка: лише за класами (без бонусів виду)."""
    return SpellSlotService().compute(classes, abilities or {}, proficiency_bonus)
