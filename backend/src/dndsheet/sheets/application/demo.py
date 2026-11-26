"""Демонстраційний персонаж для розробки рендерів і фронтенду.

Це НЕ контент із книг: лише числа й підписи-заглушки, щоб можна було
перевірити документ, Markdown і PDF до появи конвеєра контенту.
"""

from __future__ import annotations

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.shared.kernel import Ability, AbilityScore, Armor, Skill
from dndsheet.sheets.application.build_document import build_sheet_document
from dndsheet.sheets.domain.document import SheetDocument


def build_demo_character() -> Character:
    return Character(
        id="demo-elara",
        name="Елара Світлотінь",
        level=3,
        abilities={
            Ability.STR: AbilityScore(16),
            Ability.DEX: AbilityScore(14),
            Ability.CON: AbilityScore(12),
            Ability.INT: AbilityScore(10),
            Ability.WIS: AbilityScore(13),
            Ability.CHA: AbilityScore(8),
        },
        skill_proficiencies={Skill.ATHLETICS, Skill.PERCEPTION, Skill.SURVIVAL},
        save_proficiencies={Ability.STR, Ability.CON},
        armor=Armor(name="Шкіряна броня", base=11),
    )


def build_demo_document() -> SheetDocument:
    character = build_demo_character()
    computed = DerivedStatsCalculator().compute(character)
    return build_sheet_document(character, computed)
