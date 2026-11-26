"""Що дає наступний рівень: план підвищення, без змін персонажа.

Питання «що буде, якщо я візьму рівень мага?» задається на екрані **до**
вибору, тому потрібна відповідь, яка нічого не змінює. Тут вона й
будується: копія персонажа підіймається на рівень, рахується обома
`DerivedStatsCalculator`, і план показує різницю — хіти, бонус майстерності,
слоти, ліміти заклять, нові вміння, нові ресурси.

Чому копія, а не окремі формули: правила вже живуть в обчислювачі. Друга
реалізація тих самих чисел обовʼязково розійшлася б із листом.

Вимоги мультикласу (PHB, p. 163) — єдине, що тут рахується окремо: це не
похідне число персонажа, а умова **допуску** до нового класу. Текст вимог
навмисно з кодами характеристик («STR 13») — українські назви живе екран.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.services.derived_stats import (
    ComputedSheet,
    DerivedStatsCalculator,
)
from dndsheet.characters.domain.services.feature_resources import resources_for
from dndsheet.characters.domain.services.hit_points import average_hit_points
from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import MAX_LEVEL, Ability
from dndsheet.shared.rules import ClassFeature, ClassMechanics


@dataclass(frozen=True, slots=True)
class SlotRow:
    """Слоти одного рівня: було → стало."""

    level: int
    before: int
    after: int


@dataclass(frozen=True, slots=True)
class LevelPlan:
    """Що зміниться, якщо взяти наступний рівень у цьому класі."""

    class_key: str
    class_name: str
    is_new_class: bool
    current_level: int
    new_level: int
    total_level_before: int
    total_level_after: int
    hit_die: int
    constitution_modifier: int
    #: Скільки хітів дає рівень у середньому (половина дайса + 1 + статура).
    hp_average: int
    #: Скільки дає найкращий кидок (максимум дайса + статура).
    hp_best_roll: int
    features: tuple[ClassFeature, ...]
    subclass_title: str | None
    subclass_level: int | None
    subclass_required: bool
    asi_slots: int
    asi_taken: int
    asi_pending: bool
    proficiency_bonus_before: int
    proficiency_bonus_after: int
    cantrips_before: int
    cantrips_after: int
    spells_known_before: int | None
    spells_known_after: int | None
    prepared_before: int | None
    prepared_after: int | None
    slots: tuple[SlotRow, ...]
    pact_before: tuple[int, int] | None
    pact_after: tuple[int, int] | None
    caster_level_before: int
    caster_level_after: int
    #: Найвищий рівень закляття, який персонаж має після підвищення.
    max_spell_level: int
    resources_before: tuple[str, ...]
    resources_after: tuple[str, ...]
    #: Чи можна взяти цей клас (для наявного — завжди True).
    allowed: bool = True
    #: Чому не можна (порожньо, коли можна).
    blocked_reason: str | None = None
    #: Вимоги мультикласу для показу (порожньо, якщо їх немає).
    requirements: tuple[str, ...] = ()


class LevelUpPlanner:
    """Будує плани підвищення рівня. Нічого не змінює й не зберігає."""

    def __init__(self, calculator: DerivedStatsCalculator | None = None) -> None:
        self._calculator = calculator or DerivedStatsCalculator()

    def plans(self, character: Character) -> tuple[LevelPlan, ...]:
        """План для кожного наявного класу і для кожного нового.

        На 20 сумарних рівнях рости нікуди: порожній список, а не помилка.
        """
        if character.total_level >= MAX_LEVEL:
            return ()
        keys = [
            entry.class_key for entry in character.classes if entry.level < MAX_LEVEL
        ]
        known = set(keys)
        for key in _known_class_keys(character):
            if key not in known:
                keys.append(key)
        return tuple(self.plan(character, key) for key in keys)

    def plan(self, character: Character, class_key: str) -> LevelPlan:
        key = class_key.strip().casefold()
        definition = character.class_definition(key)
        existing = character.has_class(key)
        current_level = character.class_level(key)
        if existing and current_level >= MAX_LEVEL:
            raise ValidationError(f"{definition.name_en}: 20 рівень у класі — це максимум")
        if not existing and character.total_level >= MAX_LEVEL:
            raise ValidationError(f"сумарний рівень не може бути більшим за {MAX_LEVEL}")

        candidate = self._with_next_level(character, key, existing)
        before = self._calculator.compute(character)
        after = self._calculator.compute(candidate)
        constitution = after.ability_modifiers[Ability.CON]

        allowed, reason = True, None
        requirements: tuple[str, ...] = ()
        if not existing:
            allowed, reason = self._check_multiclass(character, definition)
            requirements = _requirements_text(definition)

        return LevelPlan(
            class_key=key,
            class_name=definition.name_en,
            is_new_class=not existing,
            current_level=current_level,
            new_level=current_level + 1,
            total_level_before=character.total_level,
            total_level_after=candidate.total_level,
            hit_die=definition.hit_die,
            constitution_modifier=constitution,
            hp_average=max(1, average_hit_points(definition.hit_die) + constitution),
            hp_best_roll=max(1, definition.hit_die + constitution),
            features=self._new_features(definition, current_level, current_level + 1),
            subclass_title=definition.subclass_title,
            subclass_level=definition.subclass_level,
            subclass_required=self._needs_subclass(candidate, key, definition),
            asi_slots=candidate.asi_slots,
            asi_taken=candidate.asi_taken,
            asi_pending=candidate.asi_slots > candidate.asi_taken,
            proficiency_bonus_before=before.proficiency_bonus,
            proficiency_bonus_after=after.proficiency_bonus,
            cantrips_before=definition.cantrips_at(max(1, current_level)) if existing else 0,
            cantrips_after=definition.cantrips_at(current_level + 1),
            spells_known_before=definition.spells_known_at(current_level) if existing else 0,
            spells_known_after=definition.spells_known_at(current_level + 1),
            # Новий клас: до нього підготовлених заклять не було, тому
            # «було 0» — це 0, а не «ліміту немає».
            prepared_before=self._prepared(before, key) if existing else 0,
            prepared_after=self._prepared(after, key),
            slots=_slot_rows(before, after),
            pact_before=_pact(before),
            pact_after=_pact(after),
            caster_level_before=before.spellcasting.caster_level,
            caster_level_after=after.spellcasting.caster_level,
            max_spell_level=after.spellcasting.slots.highest_level,
            resources_before=tuple(
                resource.key for resource in resources_for(character, before.ability_modifiers)
            ),
            resources_after=tuple(
                resource.key for resource in resources_for(candidate, after.ability_modifiers)
            ),
            allowed=allowed,
            blocked_reason=reason,
            requirements=requirements,
        )

    # ------------------------------------------------------------------
    # внутрішнє
    # ------------------------------------------------------------------

    @staticmethod
    def _with_next_level(
        character: Character, class_key: str, existing: bool
    ) -> Character:
        """Копія персонажа з наступним рівнем — без спільного стану.

        `rules` навмисно спільний: це порт до правил, копіювати його не
        можна (за ним стоїть увесь довідник). Решта змінних частин копіюється.
        """
        candidate = copy.copy(character)
        candidate.classes = list(character.classes)
        candidate.abilities = dict(character.abilities)
        candidate.events = []
        if existing:
            candidate.raise_level(class_key)
        else:
            candidate.add_class(class_key, 1)
        return candidate

    @staticmethod
    def _new_features(
        definition: ClassMechanics, current_level: int, new_level: int
    ) -> tuple[ClassFeature, ...]:
        before = {feature.name_en for feature in definition.features_at(max(1, current_level))}
        return tuple(
            feature
            for feature in definition.features_at(new_level)
            if feature.name_en not in before
        )

    @staticmethod
    def _needs_subclass(
        candidate: Character, class_key: str, definition: ClassMechanics
    ) -> bool:
        if not definition.subclass_level:
            return False
        entry = next(item for item in candidate.classes if item.class_key == class_key)
        if entry.subclass_key is not None:
            return False
        return entry.level >= definition.subclass_level

    @staticmethod
    def _prepared(computed: ComputedSheet, class_key: str) -> int | None:
        casting = computed.spellcasting.for_class(class_key)
        return casting.prepared_limit if casting is not None else None

    @staticmethod
    def _check_multiclass(
        character: Character, definition: ClassMechanics
    ) -> tuple[bool, str | None]:
        """Вимоги мультикласу: і новий клас, і всі наявні (PHB, p. 163)."""
        scores = {
            ability: character.abilities[ability].value
            + character.ability_bonus_from_origin(ability)
            for ability in character.abilities
        }
        if not definition.satisfies_multiclass(scores):
            return False, (
                f"для мультикласу в {definition.name_en} треба "
                f"{' або '.join(_requirements_text(definition)) or '—'}"
            )
        for entry, current in character.class_entries():
            if not current.satisfies_multiclass(scores):
                return False, (
                    f"щоб узяти новий клас, треба також відповідати вимогам "
                    f"{current.name_en}: {' або '.join(_requirements_text(current)) or '—'}"
                )
        return True, None


#: Класи 2014 у порядку книги гравця (плюс артифіцер із TCE).
CLASS_KEYS: tuple[str, ...] = (
    "barbarian",
    "bard",
    "cleric",
    "druid",
    "fighter",
    "monk",
    "paladin",
    "ranger",
    "rogue",
    "sorcerer",
    "warlock",
    "wizard",
    "artificer",
)


def _known_class_keys(character: Character) -> tuple[str, ...]:
    """Класи, які справді є в джерелі правил (порт не дає «перелічити все»)."""
    return tuple(
        key for key in CLASS_KEYS if character.rules.class_mechanics(key) is not None
    )


def _slot_rows(before: ComputedSheet, after: ComputedSheet) -> tuple[SlotRow, ...]:
    rows: dict[int, SlotRow] = {}
    for level, count in before.spellcasting.slots.by_level:
        rows[level] = SlotRow(level=level, before=count, after=count)
    for level, count in after.spellcasting.slots.by_level:
        current = rows.get(level)
        rows[level] = SlotRow(
            level=level, before=current.before if current else 0, after=count
        )
    return tuple(rows[level] for level in sorted(rows))


def _pact(computed: ComputedSheet) -> tuple[int, int] | None:
    pact = computed.spellcasting.slots.pact
    return (pact.slots, pact.slot_level) if pact is not None else None


def _requirements_text(definition: ClassMechanics) -> tuple[str, ...]:
    """Вимоги одним рядком на альтернативу: «STR 13 або DEX 13»."""
    return tuple(
        " або ".join(f"{ability.value.upper()} {score}" for ability, score in alternative.items())
        for alternative in definition.multiclass_requirements
    )


__all__ = ["CLASS_KEYS", "LevelPlan", "LevelUpPlanner", "SlotRow"]
