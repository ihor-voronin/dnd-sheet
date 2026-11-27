"""Демонстраційний персонаж для розробки рендерів і фронтенду.

Це НЕ контент із книг: лише числа й предмети, які можна перевірити очима
(Елара — лісова ельфійка-плут 3 рівня). Механіки приходять із того ж
довідника, що й у справжнього персонажа, тому демо не бреше про правила.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.inventory import Inventory, InventoryItem, ItemKind
from dndsheet.characters.domain.ports import RulesSource
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiencies,
    Proficiency,
    ProficiencyKind,
    SourceKind,
)
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.domain.vitals import HitPointState
from dndsheet.shared.kernel import Ability, AbilityScore, Money, Skill
from dndsheet.sheets.application.build_document import build_sheet_document
from dndsheet.sheets.domain.document import SheetDocument


def build_demo_character(rules: RulesSource) -> Character:
    """Елара Світлотінь — лісова ельфійка, плут 3 рівня."""
    return Character(
        id="demo-elara",
        name="Елара Світлотінь",
        abilities={
            Ability.STR: AbilityScore(10),
            Ability.DEX: AbilityScore(15),
            Ability.CON: AbilityScore(13),
            Ability.INT: AbilityScore(12),
            Ability.WIS: AbilityScore(14),
            Ability.CHA: AbilityScore(8),
        },
        rules=rules,
        species_key="elf",
        subspecies_key="wood elf",
        background_key="criminal",
        classes=[CharacterClass(class_key="rogue", level=3)],
        chosen=Proficiencies(
            items=(
                Proficiency(
                    kind=ProficiencyKind.SKILL,
                    value=Skill.PERCEPTION.value,
                    source=GrantSource.of(SourceKind.CLASS, "rogue"),
                ),
                Proficiency(
                    kind=ProficiencyKind.SKILL,
                    value=Skill.ACROBATICS.value,
                    source=GrantSource.of(SourceKind.CLASS, "rogue"),
                ),
            )
        ),
        inventory=Inventory(
            items=(
                InventoryItem(
                    name_en="leather armor",
                    kind=ItemKind.ARMOR,
                    weight_lb=10,
                    equipped=True,
                    armor_base=11,
                ),
                InventoryItem(name_en="shortsword", kind=ItemKind.WEAPON, weight_lb=2),
                InventoryItem(name_en="thieves' tools", kind=ItemKind.TOOL, weight_lb=1),
                InventoryItem(name_en="burglar's pack", kind=ItemKind.PACK),
            ),
            money=Money(gp=15, sp=5),
        ),
        hp=HitPointState(current=19),
    )


def build_demo_document(rules: RulesSource, attacks: Iterable[Mapping[str, Any]] | None = None) -> SheetDocument:
    """Демо-лист. `attacks` — з довідника (без нього розділу «Атаки» немає).

    Атаки не рахуються тут: для них потрібен довідник, а `sheets` знає лише
    порт правил. Композиційний корінь додає їх, коли довідник є.
    """
    character = build_demo_character(rules)
    computed = DerivedStatsCalculator().compute(character)
    return build_sheet_document(character, computed, attacks)
