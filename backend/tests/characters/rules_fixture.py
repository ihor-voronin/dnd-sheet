"""Мінімальний набір правил для юніт-тестів домену.

Навіщо не брати справжній індекс: тести домену мають працювати без корпусу
(свіжий клон репозиторію), і мають перевіряти саме логіку, а не вміст книг.
Числа тут — ті самі, що в PHB (SRD), тому золоті персонажі, зібрані на цьому
наборі, мусять дати ті самі відповіді, що й на реальному довіднику. Це й
перевіряє `test_golden.py`, проганяючи обидва джерела.
"""

from __future__ import annotations

from typing import Any

from dndsheet.shared.kernel import Ability, Skill
from dndsheet.shared.rules import (
    CASTER_SLOT_TABLE,
    PACT_SLOT_TABLE,
    AbilityBonus,
    AbilityChoice,
    BackgroundMechanics,
    CasterProgression,
    ClassFeature,
    ClassMechanics,
    Size,
    SkillChoice,
    SpeciesMechanics,
)

A = Ability


def _class(
    key: str,
    name: str,
    hit_die: int,
    saves: tuple[Ability, ...],
    *,
    skills: tuple[Skill, ...] = (),
    skill_count: int = 2,
    **extra: Any,
) -> ClassMechanics:
    return ClassMechanics(
        key=key,
        name_en=name,
        source_id="PHB",
        hit_die=hit_die,
        saving_throws=frozenset(saves),
        skill_choices=(SkillChoice(count=skill_count, options=skills),) if skills else (),
        armor_training=tuple(extra.pop("armor", ("light", "medium", "shield"))),
        weapon_training=tuple(extra.pop("weapons", ("simple",))),
        **extra,
    )


FIGHTER = _class(
    "fighter",
    "Fighter",
    10,
    (A.STR, A.CON),
    skills=(Skill.ACROBATICS, Skill.ANIMAL_HANDLING, Skill.ATHLETICS, Skill.HISTORY,
            Skill.INSIGHT, Skill.INTIMIDATION, Skill.PERCEPTION, Skill.SURVIVAL),
    armor=("light", "medium", "heavy", "shield"),
    weapons=("simple", "martial"),
    subclass_level=3,
    subclass_title="Martial Archetype",
    features=(ClassFeature("Second Wind", 1), ClassFeature("Action Surge", 2)),
)

WARLOCK = _class(
    "warlock",
    "Warlock",
    8,
    (A.WIS, A.CHA),
    skills=(Skill.ARCANA, Skill.DECEPTION, Skill.HISTORY, Skill.INTIMIDATION,
            Skill.INVESTIGATION, Skill.NATURE, Skill.RELIGION),
    spellcasting_ability=A.CHA,
    caster_progression=CasterProgression.PACT,
    subclass_level=1,
    subclass_title="Otherworldly Patron",
    cantrips_known=(2, 2, 2, 3),
    spells_known=(2, 3, 4, 5),
    pact_slots=PACT_SLOT_TABLE,
)

WIZARD = _class(
    "wizard",
    "Wizard",
    6,
    (A.INT, A.WIS),
    skills=(Skill.ARCANA, Skill.HISTORY, Skill.INSIGHT, Skill.INVESTIGATION,
            Skill.MEDICINE, Skill.RELIGION),
    spellcasting_ability=A.INT,
    caster_progression=CasterProgression.FULL,
    prepares_spells=True,
    subclass_level=2,
    subclass_title="Arcane Tradition",
    cantrips_known=(3, 3, 3, 4),
    spell_slots=CASTER_SLOT_TABLE,
)

ROGUE = _class(
    "rogue",
    "Rogue",
    8,
    (A.DEX, A.INT),
    skills=(Skill.ACROBATICS, Skill.ATHLETICS, Skill.DECEPTION, Skill.INSIGHT,
            Skill.INTIMIDATION, Skill.INVESTIGATION, Skill.PERCEPTION,
            Skill.PERFORMANCE, Skill.PERSUASION, Skill.SLEIGHT_OF_HAND, Skill.STEALTH),
    subclass_level=3,
    subclass_title="Roguish Archetype",
)

HUMAN = SpeciesMechanics(
    key="human",
    name_en="Human",
    source_id="PHB",
    size=Size.MEDIUM,
    speed=30,
    ability_bonuses=(
        AbilityBonus(A.STR, 1), AbilityBonus(A.DEX, 1), AbilityBonus(A.CON, 1),
        AbilityBonus(A.INT, 1), AbilityBonus(A.WIS, 1), AbilityBonus(A.CHA, 1),
    ),
    languages=("common",),
    standard_variant=True,
)

TIEFLING = SpeciesMechanics(
    key="tiefling",
    name_en="Tiefling",
    source_id="PHB",
    size=Size.MEDIUM,
    speed=30,
    ability_bonuses=(AbilityBonus(A.INT, 1), AbilityBonus(A.CHA, 2)),
    languages=("common", "infernal"),
    darkvision=60,
    resistances=("fire",),
)

ELF = SpeciesMechanics(
    key="elf",
    name_en="Elf",
    source_id="PHB",
    size=Size.MEDIUM,
    speed=30,
    ability_bonuses=(AbilityBonus(A.DEX, 2),),
    skill_proficiencies=frozenset({Skill.PERCEPTION}),
    languages=("common", "elvish"),
    darkvision=60,
)

WOOD_ELF = SpeciesMechanics(
    key="wood elf",
    name_en="Wood Elf",
    source_id="PHB",
    size=Size.MEDIUM,
    speed=35,
    subrace_of="elf",
    ability_bonuses=(AbilityBonus(A.DEX, 2), AbilityBonus(A.WIS, 1)),
    skill_proficiencies=frozenset({Skill.PERCEPTION}),
    languages=("common", "elvish"),
    darkvision=60,
)

HALF_ELF = SpeciesMechanics(
    key="half-elf",
    name_en="Half-Elf",
    source_id="PHB",
    size=Size.MEDIUM,
    speed=30,
    ability_bonuses=(AbilityBonus(A.CHA, 2),),
    ability_choice=AbilityChoice(count=2, amount=1, options=(A.STR, A.DEX, A.CON, A.INT, A.WIS)),
    skill_any=2,
    languages=("common", "elvish"),
    languages_any_standard=1,
    darkvision=60,
)

SOLDIER = BackgroundMechanics(
    key="soldier",
    name_en="Soldier",
    source_id="PHB",
    skill_proficiencies=frozenset({Skill.ATHLETICS, Skill.INTIMIDATION}),
    tool_proficiencies=("dice set", "vehicles (land)"),
    feature_en="Military Rank",
)

ACOLYTE = BackgroundMechanics(
    key="acolyte",
    name_en="Acolyte",
    source_id="PHB",
    skill_proficiencies=frozenset({Skill.INSIGHT, Skill.RELIGION}),
    languages_any_standard=2,
    feature_en="Shelter of the Faithful",
)

CRIMINAL = BackgroundMechanics(
    key="criminal",
    name_en="Criminal",
    source_id="PHB",
    skill_proficiencies=frozenset({Skill.DECEPTION, Skill.STEALTH}),
    tool_proficiencies=("thieves' tools",),
    feature_en="Criminal Contact",
)


class FixtureRules:
    """`RulesSource` над константами вище."""

    def __init__(self) -> None:
        self._classes = {item.key: item for item in (FIGHTER, WARLOCK, WIZARD, ROGUE)}
        self._species = {
            item.key: item for item in (HUMAN, TIEFLING, ELF, WOOD_ELF, HALF_ELF)
        }
        self._backgrounds = {
            item.key: item for item in (SOLDIER, ACOLYTE, CRIMINAL)
        }

    def class_mechanics(self, key: str) -> ClassMechanics | None:
        return self._classes.get((key or "").strip().casefold())

    def species_mechanics(self, key: str) -> SpeciesMechanics | None:
        return self._species.get((key or "").strip().casefold())

    def background_mechanics(self, key: str) -> BackgroundMechanics | None:
        return self._backgrounds.get((key or "").strip().casefold())
