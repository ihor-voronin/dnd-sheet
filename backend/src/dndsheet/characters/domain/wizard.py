"""Чернетка персонажа: шість кроків візарда, кожен перевіряється окремо.

Чернетка — не «напівперсонаж». `Character` вимагає, щоб усе вже було
узгоджено (вид, клас, характеристики, володіння, закляття), а під час
створення гравець ходить кроками туди й назад. Тому чернетка тримає відповіді
кожного кроку й перевіряє їх **окремо**, а `to_character()` збирає з них
агрегат — і той перевіряє все разом, як завжди.

Крок відкривається лише тоді, коли завершені всі попередні: інакше можна
дійти до заклять, не маючи класу. Назад можна завжди, і тоді зміна класу чи
виду прибирає залежні відповіді (володіння, закляття), а не лишає їх
«висіти» — інакше лист отримав би навичку класу, якого в персонажа немає.

Рівень тут — перший: створення персонажа 1 рівня. Підвищення рівня й
мультиклас — окремий потік (етап 7), тому в чернетці рівно один клас.

Валідація кроку не читає корпус довідника: усе, що їй потрібно, — це
`RulesSource` (механіки класу, виду, передісторії). Список підкласів і текст
заклять — це вже довідник, тому їх перевіряє application-шар.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Iterable, Mapping

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.inventory import Inventory, InventoryItem
from dndsheet.characters.domain.pick_rules import count_picks, validate_pick
from dndsheet.characters.domain.ports import RulesSource
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiency,
    ProficiencyKind,
    Proficiencies,
    SourceKind,
)
from dndsheet.characters.domain.spells import KnownSpell
from dndsheet.characters.domain.vitals import HitPointState
from dndsheet.shared.errors import NotFoundError, ValidationError
from dndsheet.shared.kernel import Ability, AbilityScore, Money
from dndsheet.shared.rules import (
    BackgroundMechanics,
    ClassMechanics,
    SpeciesMechanics,
    ability_bonus_totals,
)

#: Стандартний набір характеристик (PHB, p. 13).
STANDARD_ARRAY: tuple[int, ...] = (15, 14, 13, 12, 10, 8)

#: Вартість point buy від 8 до 15 (PHB, p. 13). Бюджет — 27 очок.
POINT_BUY_COSTS: Mapping[int, int] = {
    8: 0,
    9: 1,
    10: 2,
    11: 3,
    12: 4,
    13: 5,
    14: 7,
    15: 9,
}
POINT_BUY_BUDGET = 27

#: Межа характеристики для персонажа (PHB, p. 173).
ABILITY_MAX = 20


class WizardStep(StrEnum):
    """Кроки створення — саме в тому порядку, у якому їх проходять."""

    SPECIES = "species"
    CLASS = "class"
    ABILITIES = "abilities"
    BACKGROUND = "background"
    EQUIPMENT = "equipment"
    SPELLS = "spells"


STEP_ORDER: tuple[WizardStep, ...] = tuple(WizardStep)

#: Кроки, без яких персонажа не зібрати. Спорядження — не обовʼязкове:
#: гравець може прийти зі своїм, і це не привід блокувати створення.
REQUIRED_STEPS: tuple[WizardStep, ...] = (
    WizardStep.SPECIES,
    WizardStep.CLASS,
    WizardStep.ABILITIES,
    WizardStep.BACKGROUND,
)


class AbilityMethod(StrEnum):
    """Як гравець отримав характеристики."""

    STANDARD_ARRAY = "standard_array"
    POINT_BUY = "point_buy"
    ROLLS = "rolls"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class StepStatus:
    """Стан кроку для навігації: чи завершений і чи можна його відкрити."""

    step: WizardStep
    complete: bool
    unlocked: bool
    optional: bool


@dataclass(slots=True)
class Draft:
    """Відповіді кроків одного створення персонажа.

    Поля навмисно плоскі (а не «словник відповідей»): так кожне з них має тип,
    а не «щось із JSON», і `to_character()` не вгадує, що там лежить.
    """

    id: str
    rules: RulesSource = field(repr=False, compare=False)
    revision: int = 0
    name: str = ""
    species_key: str | None = None
    subspecies_key: str | None = None
    ability_choices: tuple[Ability, ...] = ()
    class_key: str | None = None
    subclass_key: str | None = None
    ability_method: AbilityMethod | None = None
    ability_scores: dict[Ability, int] = field(default_factory=dict)
    roll_set: tuple[int, ...] = ()
    background_key: str | None = None
    alignment: str | None = None
    picks: tuple[Proficiency, ...] = ()
    items: tuple[InventoryItem, ...] = ()
    money: Money = field(default_factory=Money)
    equipment_submitted: bool = False
    spells: tuple[KnownSpell, ...] = ()
    #: Обрані заговори виду (високий ельф): імена, не id.
    spell_choices: tuple[str, ...] = ()

    # ------------------------------------------------------------------
    # похідні
    # ------------------------------------------------------------------

    @property
    def species(self) -> SpeciesMechanics | None:
        """Діючий вид: підраса вже несе успадковані числа батька."""
        key = self.subspecies_key or self.species_key
        return self.rules.species_mechanics(key) if key else None

    @property
    def base_species(self) -> SpeciesMechanics | None:
        return self.rules.species_mechanics(self.species_key) if self.species_key else None

    @property
    def background(self) -> BackgroundMechanics | None:
        return (
            self.rules.background_mechanics(self.background_key)
            if self.background_key
            else None
        )

    @property
    def class_definition(self) -> ClassMechanics:
        if not self.class_key:
            raise ValidationError("клас ще не обрано")
        definition = self.rules.class_mechanics(self.class_key)
        if definition is None:
            raise NotFoundError(f"немає правил класу {self.class_key!r}")
        return definition

    @property
    def chosen(self) -> Proficiencies:
        return Proficiencies(items=self.picks)

    @property
    def ability_bonuses(self) -> dict[Ability, int]:
        return ability_bonus_totals(self.species, self.ability_choices)

    def ability_modifier(self, ability: Ability) -> int:
        """Модифікатор уже з бонусами виду — потрібен для ліміту підготовлених."""
        base = self.ability_scores.get(ability, 10)
        total = min(ABILITY_MAX, base + self.ability_bonuses.get(ability, 0))
        return (total - 10) // 2

    # ------------------------------------------------------------------
    # кроки: застосування відповідей
    # ------------------------------------------------------------------

    def apply_species(
        self,
        *,
        name: str,
        species_key: str,
        subspecies_key: str | None = None,
        ability_choices: Iterable[Ability] = (),
        spell_choices: Iterable[str] = (),
    ) -> None:
        species = self.rules.species_mechanics(species_key)
        if species is None:
            raise NotFoundError(f"немає правил виду {species_key!r}")
        if species.is_subspecies:
            raise ValidationError(f"{species.name_en!r} — підраса; вкажіть базовий вид")
        subspecies = None
        if subspecies_key:
            subspecies = self.rules.species_mechanics(subspecies_key)
            if subspecies is None:
                raise NotFoundError(f"немає правил підраси {subspecies_key!r}")
            if not subspecies.is_subspecies:
                raise ValidationError(f"{subspecies.name_en!r} не є підрасою")
            if subspecies.subrace_of not in (None, species.key):
                raise ValidationError(
                    f"{subspecies.name_en!r} не належить виду {species.name_en!r}"
                )
        effective = subspecies or species
        choices = () if effective.ability_choice is None else tuple(ability_choices)
        candidate = replace(self)
        candidate.name = name.strip()
        candidate.species_key = species.key
        candidate.subspecies_key = subspecies.key if subspecies else None
        candidate.ability_choices = choices
        candidate.spell_choices = tuple(
            name.strip() for name in spell_choices if str(name).strip()
        )
        if (self.species_key, self.subspecies_key) != (
            candidate.species_key,
            candidate.subspecies_key,
        ):
            candidate.picks = tuple(
                pick for pick in candidate.picks if pick.source.kind is not SourceKind.SPECIES
            )
        candidate._validate_species()
        candidate.revision += 1
        self._commit(candidate)

    def apply_class(self, *, class_key: str, subclass_key: str | None = None) -> None:
        definition = self.rules.class_mechanics(class_key)
        if definition is None:
            raise NotFoundError(f"немає правил класу {class_key!r}")
        subclass = subclass_key.strip().casefold() if subclass_key else None
        if definition.subclass_level is None:
            if subclass:
                raise ValidationError(f"{definition.name_en!r} не має підкласів")
        elif definition.subclass_level > 1:
            if subclass:
                raise ValidationError(
                    f"{definition.subclass_title!r} обирається з "
                    f"{definition.subclass_level} рівня — на 1-му його ще немає"
                )
            subclass = None
        elif not subclass:
            raise ValidationError(
                f"{definition.name_en!r} обирає {definition.subclass_title!r} "
                f"вже на 1 рівні"
            )
        candidate = replace(self)
        changed = self.class_key is not None and self.class_key != definition.key
        candidate.class_key = definition.key
        candidate.subclass_key = subclass
        if changed:
            candidate.picks = tuple(
                pick for pick in candidate.picks if pick.source.kind is not SourceKind.CLASS
            )
            candidate.spells = ()
        candidate._validate_class()
        candidate.revision += 1
        self._commit(candidate)

    def apply_abilities(
        self,
        *,
        method: AbilityMethod | str,
        scores: Mapping[Ability | str, int],
        rolls: Iterable[int] = (),
    ) -> None:
        parsed_method = AbilityMethod(method)
        parsed_scores: dict[Ability, int] = {}
        for key, value in scores.items():
            ability = key if isinstance(key, Ability) else Ability(str(key).strip().casefold())
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValidationError(f"{ability.value}: характеристика має бути цілим числом")
            parsed_scores[ability] = value
        candidate = replace(self)
        candidate.ability_method = parsed_method
        candidate.ability_scores = parsed_scores
        candidate.roll_set = tuple(int(value) for value in rolls)
        candidate._validate_abilities()
        candidate.revision += 1
        self._commit(candidate)

    def apply_background(
        self,
        *,
        background_key: str,
        picks: Iterable[Proficiency] = (),
        alignment: str | None = None,
    ) -> None:
        background = self.rules.background_mechanics(background_key)
        if background is None:
            raise NotFoundError(f"немає правил передісторії {background_key!r}")
        candidate = replace(self)
        candidate.background_key = background.key
        candidate.alignment = alignment.strip() if alignment else None
        candidate.picks = tuple(picks)
        candidate._validate_background()
        candidate.revision += 1
        self._commit(candidate)

    def apply_equipment(
        self,
        *,
        items: Iterable[InventoryItem] = (),
        money: Money | None = None,
    ) -> None:
        candidate = replace(self)
        candidate.items = tuple(items)
        candidate.money = money or Money()
        candidate.equipment_submitted = True
        candidate._validate_equipment()
        candidate.revision += 1
        self._commit(candidate)

    def apply_spells(self, *, spells: Iterable[KnownSpell] = ()) -> None:
        candidate = replace(self)
        candidate.spells = tuple(spells)
        candidate._validate_spells()
        candidate.revision += 1
        self._commit(candidate)

    def _commit(self, candidate: "Draft") -> None:
        """Перенести перевірений стан у себе. Невдалий крок не змінює чернетку."""
        for name in self.__slots__:
            setattr(self, name, getattr(candidate, name))

    # ------------------------------------------------------------------
    # валідація кроків
    # ------------------------------------------------------------------

    def validate_step(self, step: WizardStep) -> None:
        """Перевірити крок; інакше — `ValidationError` з причиною."""
        validators = {
            WizardStep.SPECIES: self._validate_species,
            WizardStep.CLASS: self._validate_class,
            WizardStep.ABILITIES: self._validate_abilities,
            WizardStep.BACKGROUND: self._validate_background,
            WizardStep.EQUIPMENT: self._validate_equipment,
            WizardStep.SPELLS: self._validate_spells,
        }
        validators[step]()

    def is_complete(self, step: WizardStep) -> bool:
        if step is WizardStep.EQUIPMENT and not self.equipment_submitted:
            return False
        try:
            self.validate_step(step)
        except ValidationError:
            return False
        return True

    def statuses(self) -> tuple[StepStatus, ...]:
        """Стан кроків: завершеність і доступність для навігації."""
        first_open = len(STEP_ORDER)
        for index, step in enumerate(STEP_ORDER):
            if not self.is_complete(step):
                first_open = index
                break
        return tuple(
            StepStatus(
                step=step,
                complete=self.is_complete(step),
                unlocked=index <= first_open,
                optional=step not in REQUIRED_STEPS,
            )
            for index, step in enumerate(STEP_ORDER)
        )

    def next_step(self) -> WizardStep | None:
        for step in STEP_ORDER:
            if not self.is_complete(step):
                return step
        return None

    def validate_for_finish(self) -> None:
        """Усе, без чого персонаж не народжується."""
        for step in REQUIRED_STEPS:
            self.validate_step(step)
        self.validate_step(WizardStep.SPELLS)
        self.validate_step(WizardStep.EQUIPMENT)

    # ------------------------------------------------------------------
    # готовий персонаж
    # ------------------------------------------------------------------

    def to_character(self, character_id: str) -> Character:
        """Зібрати агрегат. Повна перевірка — уже в `Character`."""
        self.validate_for_finish()
        assert self.class_key is not None
        return Character(
            id=character_id,
            name=self.name,
            abilities={
                ability: AbilityScore(score) for ability, score in self.ability_scores.items()
            },
            rules=self.rules,
            classes=[
                CharacterClass(
                    class_key=self.class_key,
                    level=1,
                    subclass_key=self.subclass_key,
                )
            ],
            ability_bonus_choices=self.ability_choices,
            species_key=self.species_key,
            subspecies_key=self.subspecies_key,
            background_key=self.background_key,
            alignment=self.alignment,
            chosen=Proficiencies(items=self.picks),
            inventory=Inventory(items=self.items, money=self.money),
            spells=self.spells,
            spell_choices=self.spell_choices,
            hp=HitPointState(),
        )

    # ------------------------------------------------------------------
    # перевірки
    # ------------------------------------------------------------------

    def _validate_species(self) -> None:
        if not self.name.strip():
            raise ValidationError("вкажіть імʼя персонажа")
        if not self.species_key:
            raise ValidationError("оберіть вид")
        species = self.base_species
        if species is None:
            raise NotFoundError(f"немає правил виду {self.species_key!r}")
        if species.is_subspecies:
            raise ValidationError(f"{species.name_en!r} — підраса, а не базовий вид")
        if self.subspecies_key:
            subspecies = self.rules.species_mechanics(self.subspecies_key)
            if subspecies is None:
                raise NotFoundError(f"немає правил підраси {self.subspecies_key!r}")
            if not subspecies.is_subspecies:
                raise ValidationError(f"{subspecies.name_en!r} не є підрасою")
            if subspecies.subrace_of and subspecies.subrace_of != species.key:
                raise ValidationError(
                    f"{subspecies.name_en!r} не належить виду {species.name_en!r}"
                )
        effective = self.species
        if effective is not None and effective.ability_unresolved:
            raise ValidationError(
                f"{effective.name_en}: вільний розподіл характеристик (правила 2022) "
                f"поки що не підтримується — оберіть вид із фіксованими бонусами"
            )
        allowed = (
            effective.cantrip_choice_count
            if effective is not None and effective.cantrip_choice_class
            else 0
        )
        if len(set(self.spell_choices)) != len(self.spell_choices):
            raise ValidationError("заговори виду не можуть повторюватися")
        if len(self.spell_choices) != allowed:
            raise ValidationError(
                f"вид дає {allowed} заговорів на вибір, обрано {len(self.spell_choices)}"
                if allowed
                else "вид не дає вибору заговорів"
            )
        choice = effective.ability_choice if effective else None
        if choice is None:
            if self.ability_choices:
                raise ValidationError("вид не дає вибору бонусів характеристик")
            return
        if len(set(self.ability_choices)) != len(self.ability_choices):
            raise ValidationError("здібності на вибір не можуть повторюватися")
        if len(self.ability_choices) != choice.count:
            raise ValidationError(
                f"треба обрати {choice.count} здібності, обрано {len(self.ability_choices)}"
            )
        for ability in self.ability_choices:
            if ability not in choice.options:
                raise ValidationError(f"{ability.value} не входить у вибір виду")

    def _validate_class(self) -> None:
        if not self.class_key:
            raise ValidationError("оберіть клас")
        definition = self.class_definition
        if self.subclass_key is None:
            if definition.subclass_level == 1:
                raise ValidationError(
                    f"{definition.name_en!r} обирає {definition.subclass_title!r} "
                    f"на 1 рівні — зробіть вибір"
                )
            return
        if definition.subclass_level is None:
            raise ValidationError(f"{definition.name_en!r} не має підкласів")
        if definition.subclass_level > 1:
            raise ValidationError(
                f"{definition.subclass_title!r} обирається з {definition.subclass_level} рівня"
            )

    def _validate_abilities(self) -> None:
        if self.ability_method is None:
            raise ValidationError("оберіть спосіб розподілу характеристик")
        if self.class_key is None:
            raise ValidationError("спершу оберіть клас")
        if set(self.ability_scores) != set(Ability):
            missing = ", ".join(
                sorted(ability.value for ability in Ability if ability not in self.ability_scores)
            )
            raise ValidationError(f"не заповнено характеристики: {missing}")
        values = list(self.ability_scores.values())
        if self.ability_method is AbilityMethod.STANDARD_ARRAY:
            if sorted(values) != sorted(STANDARD_ARRAY):
                raise ValidationError(
                    "стандартний набір — це 15, 14, 13, 12, 10, 8, кожне число рівно раз"
                )
        elif self.ability_method is AbilityMethod.POINT_BUY:
            for ability, score in self.ability_scores.items():
                if score not in POINT_BUY_COSTS:
                    raise ValidationError(
                        f"{ability.value}: point buy дозволяє 8..15, отримано {score}"
                    )
            spent = sum(POINT_BUY_COSTS[score] for score in values)
            if spent > POINT_BUY_BUDGET:
                raise ValidationError(
                    f"point buy: витрачено {spent} з {POINT_BUY_BUDGET} очок"
                )
        elif self.ability_method is AbilityMethod.ROLLS:
            if len(self.roll_set) != 6:
                raise ValidationError("для кидків треба шість результатів 4d6 без найменшого")
            if any(not 3 <= roll <= 18 for roll in self.roll_set):
                raise ValidationError("кидок 4d6 без найменшого дає 3..18")
            if sorted(values) != sorted(self.roll_set):
                raise ValidationError("розподіл має використати кожен кидок рівно раз")
        else:
            for ability, score in self.ability_scores.items():
                if not 3 <= score <= ABILITY_MAX:
                    raise ValidationError(f"{ability.value}: ручне значення 3..{ABILITY_MAX}")
        bonuses = self.ability_bonuses
        for ability, score in self.ability_scores.items():
            total = score + bonuses.get(ability, 0)
            if total > ABILITY_MAX:
                raise ValidationError(
                    f"{ability.value}: {score} + {bonuses.get(ability, 0)} (вид) = {total}, "
                    f"а межа — {ABILITY_MAX}"
                )

    def _validate_background(self) -> None:
        if not self.background_key:
            raise ValidationError("оберіть передісторію")
        if self.background is None:
            raise NotFoundError(f"немає правил передісторії {self.background_key!r}")
        if self.class_key is None:
            raise ValidationError("спершу оберіть клас")
        accepted = Proficiencies()
        for pick in self.picks:
            validate_pick(self.rules, pick, existing=accepted)
            accepted = accepted.add(pick)
        definition = self.class_definition
        needed = definition.skill_limit
        if needed:
            source = GrantSource.of(SourceKind.CLASS, definition.key)
            used = count_picks(accepted, ProficiencyKind.SKILL, source)
            if used != needed:
                raise ValidationError(
                    f"{definition.name_en!r} дає {needed} навичок — обрано {used}"
                )
        effective = self.species
        if effective is not None and effective.skill_any:
            source = GrantSource.of(SourceKind.SPECIES, effective.key)
            used = count_picks(accepted, ProficiencyKind.SKILL, source)
            if used != effective.skill_any:
                raise ValidationError(
                    f"{effective.name_en!r} дає {effective.skill_any} навичок на вибір — "
                    f"обрано {used}"
                )

    def _validate_equipment(self) -> None:
        """Інвентар перевіряє себе сам: одна броня, один щит, вага, гроші."""
        Inventory(items=self.items, money=self.money)

    def _validate_spells(self) -> None:
        if self.class_key is None:
            raise ValidationError("спершу оберіть клас")
        definition = self.class_definition
        if not definition.casts_spells:
            if self.spells:
                raise ValidationError(f"{definition.name_en!r} не чарує — заклять бути не може")
            return
        for spell in self.spells:
            if spell.class_key != definition.key:
                raise ValidationError(
                    f"{spell.name_en!r}: закляття класу {spell.class_key!r}, "
                    f"а персонаж — {definition.name_en!r}"
                )
        cantrips = sum(1 for spell in self.spells if spell.is_cantrip)
        limit = definition.cantrips_at(1)
        if cantrips > limit:
            raise ValidationError(
                f"{definition.name_en}: заговорів не більше {limit}, обрано {cantrips}"
            )
        known = tuple(spell for spell in self.spells if not spell.is_cantrip)
        known_limit = definition.spells_known_at(1)
        if known_limit is not None and len(known) > known_limit:
            raise ValidationError(
                f"{definition.name_en}: відомих заклять не більше {known_limit}, "
                f"обрано {len(known)}"
            )
        max_level = self._max_spell_level(definition)
        for spell in known:
            if spell.level > max_level:
                raise ValidationError(
                    f"{definition.name_en}: на 1 рівні немає заклять {spell.level} рівня"
                )
        if definition.prepares_spells:
            ability = definition.spellcasting_ability
            prepared_limit = max(1, self.ability_modifier(ability) + 1) if ability else 1
            prepared = sum(
                1 for spell in known if spell.prepared or spell.always_prepared
            )
            if prepared > prepared_limit:
                raise ValidationError(
                    f"{definition.name_en}: підготовлених не більше {prepared_limit}, "
                    f"підготовлено {prepared}"
                )

    def _max_spell_level(self, definition: ClassMechanics) -> int:
        if definition.is_pact_magic:
            slots, level = definition.pact_at(1)
            return level if slots else 0
        table = definition.slots_at(1)
        levels = [index for index, count in enumerate(table, start=1) if count]
        return max(levels, default=0)
