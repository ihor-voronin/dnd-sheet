"""Слоти заклять і числа заклинателя, включно з мультикласом.

Правила, які тут зашиті (PHB, 2014):

* рівень заклинателя = повні класи цілком + половина напівзаклинателів
  (з округленням вниз) + третина третинних; Pact Magic warlock-а окремо;
* слоти беруться з однієї таблиці за рівнем заклинателя — для одного класу
  вона дає те саме, що й рядок класу, тому окремого шляху не треба;
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


@dataclass(frozen=True, slots=True)
class Spellcasting:
    """Усе про закляття персонажа, що обчислюється: слоти, DC, ліміти."""

    caster_level: int
    slots: SpellSlots
    classes: tuple[ClassCasting, ...]

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
    """Обчислювач слотів і характеристик заклинань."""

    def compute(
        self,
        classes: ClassesAndDefinitions,
        abilities: Mapping[Ability, int],
        proficiency_bonus: int,
    ) -> Spellcasting:
        casters = [
            (entry, definition)
            for entry, definition in classes
            if definition.casts_spells and entry.level > 0
        ]
        if not casters:
            return Spellcasting(caster_level=0, slots=SpellSlots(), classes=())

        combined = caster_level(
            (definition.caster_progression, entry.level) for entry, definition in casters
        )
        standard = spell_slots(combined) if combined else ()
        pact: PactMagic | None = None
        for entry, definition in casters:
            if not definition.is_pact_magic:
                continue
            from_data = definition.pact_at(entry.level)
            pact = (
                PactMagic(slots=from_data[0], slot_level=from_data[1])
                if from_data[0]
                else pact_magic_for(entry.level)
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
                max(1, modifier + entry.level) if definition.prepares_spells else None
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
                )
            )

        return Spellcasting(
            caster_level=combined,
            slots=SpellSlots.from_table(standard, pact=pact),
            classes=tuple(details),
        )


def spellcasting_for_classes(
    classes: ClassesAndDefinitions,
    abilities: Mapping[Ability, int] | None = None,
    proficiency_bonus: int = 2,
) -> Spellcasting:
    """Зручна обгортка: лише за класами (без бонусів виду)."""
    return SpellSlotService().compute(classes, abilities or {}, proficiency_bonus)
