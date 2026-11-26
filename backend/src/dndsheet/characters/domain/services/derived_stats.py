"""Обчислення похідних характеристик (правила 2014, v2).

Чистий доменний сервіс: жодного репозиторію, жодного I/O. Усе, що йому
потрібно, він бере з агрегату `Character` (разом із портом правил) і з
`ModifierResolver`, який каже, **звідки** взялася кожна цифра.

Що тут рахується: характеристики (база + бонуси), модифікатори, бонус
майстерності, кидки порятунку, навички, ініціатива, швидкість, пасивна
уважність, КЗ (броня/щит/безбронний захист), максимум хітів, хіт-дайси,
слоти заклять і DC, вантажопідйомність.

Чого тут немає: атак зброєю (потрібні дані предметів — етап 4) і рис із
числовими бонусами (етап 7). Обидва місця позначені в коді.
"""

from __future__ import annotations

from dataclasses import dataclass

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.inventory import CARRY_PER_STRENGTH
from dndsheet.characters.domain.proficiencies import ProficiencyKind, Proficiencies
from dndsheet.characters.domain.services.hit_points import (
    HitPointsView,
    hit_dice_pool,
    hit_point_maximum,
)
from dndsheet.characters.domain.services.modifier_resolver import (
    ModifierKind,
    ModifierResolver,
    ModifierSet,
)
from dndsheet.characters.domain.services.spell_slots import (
    ClassCasting,
    Spellcasting,
    SpellSlotService,
)
from dndsheet.shared.kernel import (
    SKILL_ABILITY,
    Ability,
    Skill,
    proficiency_bonus,
)
from dndsheet.shared.rules import ClassMechanics

SHIELD_AC_BONUS = 2
UNARMORED_BASE = 10
PASSIVE_BASE = 10

#: Безбронний захист: клас → друга характеристика до КЗ (PHB, 2014).
#: Це правило, а не дані книги, тому воно тут, а не в корпусі.
UNARMORED_DEFENSE: dict[str, Ability] = {
    "barbarian": Ability.CON,
    "monk": Ability.WIS,
}


@dataclass(frozen=True, slots=True)
class AbilityView:
    """Характеристика очима листа: база, бонус, підсумок, модифікатор."""

    base: int
    bonus: int
    total: int
    modifier: int


@dataclass(frozen=True, slots=True)
class GrantedSpellView:
    """Закляття не з класу: вид (thaumaturgy) або підклас (домен жреця)."""

    name_en: str
    spell_level: int
    source: str  # "species" | "subclass"
    prepared: bool = False


@dataclass(frozen=True, slots=True)
class ArmorClassPart:
    """Доданок КЗ: назва (ключ, не текст) і число."""

    label: str
    value: int


@dataclass(frozen=True, slots=True)
class ComputedSheet:
    """Обчислений зріз персонажа. Не зберігається, будується щоразу."""

    total_level: int
    proficiency_bonus: int
    abilities: dict[Ability, AbilityView]
    ability_modifiers: dict[Ability, int]
    saving_throws: dict[Ability, int]
    saving_throw_proficiency: dict[Ability, bool]
    skills: dict[Skill, int]
    skill_proficiency: dict[Skill, bool]
    initiative: int
    speed: int
    armor_class: int
    armor_class_parts: tuple[ArmorClassPart, ...]
    passive_perception: int
    hit_points: HitPointsView
    hit_dice: dict[int, int]
    spellcasting: Spellcasting
    granted_spells: tuple[GrantedSpellView, ...]
    proficiencies: Proficiencies
    darkvision: int
    resistances: tuple[str, ...]
    carrying_capacity: int
    carried_weight: float
    modifiers: ModifierSet
    feats: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    # --- зручні похідні для рендерів --------------------------------------

    @property
    def casting_classes(self) -> tuple[ClassCasting, ...]:
        return self.spellcasting.classes

    def ability(self, ability: Ability) -> AbilityView:
        return self.abilities[ability]

    def skill_bonus(self, skill: Skill) -> int:
        return self.skills[skill]


class DerivedStatsCalculator:
    """Рахує лист. Нічого не змінює й нічого не зберігає."""

    def __init__(self, resolver: ModifierResolver | None = None) -> None:
        self._resolver = resolver or ModifierResolver()

    def compute(self, character: Character) -> ComputedSheet:
        modifiers = self._resolver.resolve(character)
        abilities = self._abilities(character, modifiers)
        modifiers_map = {ability: view.modifier for ability, view in abilities.items()}
        total_level = max(1, character.total_level)
        proficiency = proficiency_bonus(total_level)
        proficiencies = character.all_proficiencies()
        warnings: list[str] = []

        saving_proficiency = {
            ability: proficiencies.has(ProficiencyKind.SAVING_THROW, ability.value)
            for ability in Ability
        }
        saving_throws = {
            ability: modifiers_map[ability] + (proficiency if saving_proficiency[ability] else 0)
            for ability in Ability
        }

        skill_proficiency = {
            skill: proficiencies.has(ProficiencyKind.SKILL, skill.value) for skill in Skill
        }
        skills = {
            skill: modifiers_map[SKILL_ABILITY[skill]]
            + (proficiency if skill_proficiency[skill] else 0)
            for skill in Skill
        }

        armor_class, ac_parts = self._armor_class(character, modifiers_map, modifiers)
        hit_points = self._hit_points(character, modifiers_map, warnings)
        spellcasting = SpellSlotService().compute(
            character.class_entries(),
            {ability: view.total for ability, view in abilities.items()},
            proficiency,
        )
        self._check_prepared(character, spellcasting, warnings)

        species = character.species
        speed = species.speed if species is not None else 30
        speed += modifiers.total(ModifierKind.SPEED)

        strength = abilities[Ability.STR].total
        return ComputedSheet(
            total_level=character.total_level,
            proficiency_bonus=proficiency,
            abilities=abilities,
            ability_modifiers=modifiers_map,
            saving_throws=saving_throws,
            saving_throw_proficiency=saving_proficiency,
            skills=skills,
            skill_proficiency=skill_proficiency,
            initiative=modifiers_map[Ability.DEX] + modifiers.total(ModifierKind.INITIATIVE),
            speed=speed,
            armor_class=armor_class,
            armor_class_parts=ac_parts,
            passive_perception=PASSIVE_BASE + skills[Skill.PERCEPTION],
            hit_points=hit_points,
            hit_dice=hit_dice_pool(character.class_entries()),
            spellcasting=spellcasting,
            granted_spells=self._granted_spells(character),
            proficiencies=proficiencies,
            darkvision=species.darkvision if species is not None else 0,
            resistances=species.resistances if species is not None else (),
            carrying_capacity=strength * CARRY_PER_STRENGTH,
            carried_weight=character.inventory.total_weight,
            modifiers=modifiers,
            feats=character.feats,
            warnings=tuple(warnings),
        )

    # --- частини ------------------------------------------------------------

    @staticmethod
    def _abilities(
        character: Character, modifiers: ModifierSet
    ) -> dict[Ability, AbilityView]:
        views: dict[Ability, AbilityView] = {}
        for ability in Ability:
            base = character.ability(ability).value
            bonus = modifiers.ability_bonus(ability.value)
            total = min(30, base + bonus)  # межа 5e: 30 — максимум (PHB, p. 173)
            views[ability] = AbilityView(
                base=base, bonus=bonus, total=total, modifier=(total - 10) // 2
            )
        return views

    @staticmethod
    def _armor_class(
        character: Character,
        modifiers: dict[Ability, int],
        collected: ModifierSet,
    ) -> tuple[int, tuple[ArmorClassPart, ...]]:
        parts: list[ArmorClassPart] = []
        armor = character.inventory.worn_armor
        dexterity = modifiers[Ability.DEX]
        if armor is not None and armor.armor_base is not None:
            parts.append(ArmorClassPart(label=f"armor:{armor.name_en}", value=armor.armor_base))
            capped = dexterity if armor.dex_cap is None else min(dexterity, armor.dex_cap)
            if capped:
                parts.append(ArmorClassPart(label="dexterity", value=capped))
        else:
            parts.append(ArmorClassPart(label="unarmored", value=UNARMORED_BASE))
            second = next(
                (
                    UNARMORED_DEFENSE[entry.class_key]
                    for entry in character.classes
                    if entry.class_key in UNARMORED_DEFENSE and entry.level > 0
                ),
                None,
            )
            parts.append(ArmorClassPart(label="dexterity", value=dexterity))
            if second is not None:
                parts.append(
                    ArmorClassPart(
                        label=f"unarmored-defense:{second.value}", value=modifiers[second]
                    )
                )
        if character.inventory.worn_shield is not None:
            parts.append(ArmorClassPart(label="shield", value=SHIELD_AC_BONUS))
        bonus = collected.total(ModifierKind.ARMOR_CLASS)
        if bonus:
            parts.append(ArmorClassPart(label="bonus", value=bonus))
        return sum(part.value for part in parts), tuple(parts)

    @staticmethod
    def _hit_points(
        character: Character,
        modifiers: dict[Ability, int],
        warnings: list[str],
    ) -> HitPointsView:
        maximum, parts = hit_point_maximum(
            character.class_entries(), modifiers[Ability.CON], character.hp
        )
        per_level = 0  # риси на кшталт Tough — етап 7; поле лишається для них
        if per_level:
            maximum += per_level * max(1, character.total_level)
        state = character.hp
        current = state.current if state.current else maximum
        if current > maximum:
            warnings.append(
                f"поточні хіти ({current}) більші за максимум ({maximum})"
            )
        return HitPointsView(
            maximum=maximum,
            current=current,
            temporary=state.temporary,
            parts=parts,
        )

    @staticmethod
    def _granted_spells(character: Character) -> tuple[GrantedSpellView, ...]:
        """Що персонаж отримав від виду й підкласу — без класових лімітів.

        `expanded` патрона сюди не входить: це лише розширений список, з якого
        гравець обирає, а не готові закляття.
        """
        views: list[GrantedSpellView] = []
        species = character.species
        if species is not None:
            level = max(1, character.total_level)
            for name in species.shared_cantrips:
                views.append(GrantedSpellView(name_en=name, spell_level=0, source="species"))
            for spell in species.granted_spells:
                if spell.min_level <= level:
                    views.append(
                        GrantedSpellView(
                            name_en=spell.name_en,
                            spell_level=spell.spell_level,
                            source="species",
                        )
                    )
            for name in character.spell_choices:
                views.append(GrantedSpellView(name_en=name, spell_level=0, source="species"))
        for entry, definition in character.class_entries():
            spells = definition.subclass_spells_for(entry.subclass_key)
            if spells is None:
                continue
            for name in spells.prepared:
                views.append(
                    GrantedSpellView(
                        name_en=name, spell_level=1, source="subclass", prepared=True
                    )
                )
        return tuple(views)

    @staticmethod
    def _check_prepared(
        character: Character, spellcasting: Spellcasting, warnings: list[str]
    ) -> None:
        for casting in spellcasting.classes:
            if casting.prepared_limit is None:
                continue
            prepared = sum(
                1
                for spell in character.spells_of(casting.class_key)
                if not spell.is_cantrip and (spell.prepared or spell.always_prepared)
            )
            if prepared > casting.prepared_limit:
                warnings.append(
                    f"{casting.name_en}: підготовлено {prepared} заклять, "
                    f"ліміт {casting.prepared_limit}"
                )

    # --- для сумісності з рендерами ---------------------------------------

    @staticmethod
    def class_mechanics_of(character: Character, class_key: str) -> ClassMechanics:
        return character.class_definition(class_key)
