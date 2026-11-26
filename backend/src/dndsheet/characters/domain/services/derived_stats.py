"""Обчислення похідних характеристик (правила 2014).

Чистий доменний сервіс: жодних репозиторіїв, жодного I/O.
Поки що не враховує риси/предмети — це `ModifierResolver` на етапі 3.
"""

from __future__ import annotations

from dataclasses import dataclass

from dndsheet.characters.domain.character import Character
from dndsheet.shared.kernel import (
    SKILL_ABILITY,
    Ability,
    Skill,
    proficiency_bonus,
)

SHIELD_BONUS = 2
PASSIVE_BASE = 10


@dataclass(frozen=True, slots=True)
class ComputedSheet:
    """Обчислений зріз персонажа. Не зберігається, будується щоразу."""

    ability_modifiers: dict[Ability, int]
    proficiency_bonus: int
    saving_throws: dict[Ability, int]
    skills: dict[Skill, int]
    armor_class: int
    initiative: int
    passive_perception: int


class DerivedStatsCalculator:
    def compute(self, character: Character) -> ComputedSheet:
        modifiers = {ability: character.ability(ability).modifier for ability in Ability}
        proficiency = proficiency_bonus(character.level)

        saving_throws = {
            ability: modifiers[ability] + (proficiency if ability in character.save_proficiencies else 0)
            for ability in Ability
        }

        skills = {
            skill: modifiers[SKILL_ABILITY[skill]] + (proficiency if skill in character.skill_proficiencies else 0)
            for skill in Skill
        }

        perception = skills[Skill.PERCEPTION]

        return ComputedSheet(
            ability_modifiers=modifiers,
            proficiency_bonus=proficiency,
            saving_throws=saving_throws,
            skills=skills,
            armor_class=self._armor_class(character),
            initiative=modifiers[Ability.DEX],
            passive_perception=PASSIVE_BASE + perception,
        )

    @staticmethod
    def _armor_class(character: Character) -> int:
        dexterity = character.ability(Ability.DEX).modifier
        if character.armor is None:
            armor_class = 10 + dexterity
        else:
            capped = dexterity if character.armor.dex_cap is None else min(dexterity, character.armor.dex_cap)
            armor_class = character.armor.base + capped
        return armor_class + (SHIELD_BONUS if character.shield else 0)
