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
from typing import Any, Iterable, Mapping

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.inventory import Inventory, InventoryItem
from dndsheet.characters.domain.pick_rules import count_picks, validate_pick
from dndsheet.characters.domain.ports import RulesSource
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiencies,
    Proficiency,
    ProficiencyKind,
    SourceKind,
)
from dndsheet.characters.domain.spells import KnownSpell
from dndsheet.characters.domain.vitals import HitPointState
from dndsheet.shared.errors import NotFoundError, ValidationError
from dndsheet.shared.kernel import Ability, AbilityScore, Money, Skill
from dndsheet.shared.rules import (
    SPECIES_WITH_FEAT,
    BackgroundMechanics,
    ClassMechanics,
    SpeciesMechanics,
    ability_bonus_totals,
    requires_subspecies,
)
from dndsheet.shared.rules import (
    ability_spread as validate_ability_spread,
)


def ability_spread_values(values: object) -> dict[Ability, int]:
    """Розподіл із тіла запиту: перевірку форми робить `shared.rules`."""
    return validate_ability_spread(values if isinstance(values, Mapping) else None)


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


#: Ключ «власної передісторії»: правила вибору стандартні, текст — гравця.
CUSTOM_BACKGROUND_KEY = "custom"
CUSTOM_BACKGROUND_NAME = "Власна передісторія"


def _custom_background(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    """Нормалізувати текст власної передісторії з форми."""
    data = dict(raw or {})
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValidationError("вкажіть назву власної передісторії")
    if len(name) > 80:
        raise ValidationError("назва власної передісторії — до 80 символів")
    try:
        money = max(0, int(data.get("money_gp") or 0))
    except (TypeError, ValueError) as exc:
        raise ValidationError("гроші власної передісторії — ціле число") from exc
    items: list[dict[str, Any]] = []
    for raw_item in data.get("items") or []:
        if not isinstance(raw_item, Mapping):
            raise ValidationError("предмет власної передісторії — обʼєкт")
        item_name = str(raw_item.get("name_en") or "").strip()
        if not item_name:
            continue
        try:
            quantity = max(1, min(99, int(raw_item.get("quantity") or 1)))
        except (TypeError, ValueError) as exc:
            raise ValidationError("кількість предмета — ціле число") from exc
        items.append({"name_en": item_name[:120], "quantity": quantity})
    return {
        "name": name,
        "description": str(data.get("description") or "").strip(),
        "feature_name": str(data.get("feature_name") or "").strip(),
        "feature_text": str(data.get("feature_text") or "").strip(),
        "equipment": str(data.get("equipment") or "").strip(),
        "items": items,
        "money_gp": money,
    }


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
    #: Вільний розподіл бонусів виду (правила 2022): +2/+1 або три +1.
    ability_spread: dict[Ability, int] = field(default_factory=dict)
    class_key: str | None = None
    subclass_key: str | None = None
    ability_method: AbilityMethod | None = None
    ability_scores: dict[Ability, int] = field(default_factory=dict)
    roll_set: tuple[int, ...] = ()
    background_key: str | None = None
    #: Власна передісторія: назва, опис, риса й спорядження, які гравець
    #: написав сам. Правила вибору (2 навички / 1 інструмент / 1 мова) —
    #: стандартні, їх дає `RulesSource` для ключа `custom`.
    custom_background: dict[str, Any] | None = None
    alignment: str | None = None
    picks: tuple[Proficiency, ...] = ()
    items: tuple[InventoryItem, ...] = ()
    money: Money = field(default_factory=Money)
    equipment_submitted: bool = False
    spells: tuple[KnownSpell, ...] = ()
    #: Обрані заговори виду (високий ельф): імена, не id.
    spell_choices: tuple[str, ...] = ()
    #: Риса виду на 1 рівні (варіантна людина, власна лінія): ключ риси.
    species_feat: str | None = None
    #: Характеристика, яку риса підвищила на 1 (Resilient, Actor…).
    species_feat_ability: Ability | None = None
    #: Книга виду («MPMM»), якщо вид є в кількох.
    species_source: str | None = None
    #: Вибори риси виду: «feat:skilled:Skills or Tools» → назви (як `class_choices`).
    species_feat_choices: dict[str, tuple[str, ...]] = field(default_factory=dict)

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
        return self.rules.background_mechanics(self.background_key) if self.background_key else None

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
        totals = ability_bonus_totals(self.species, self.ability_choices)
        for ability, amount in self.ability_spread.items():
            totals[ability] += amount
        if self.species_feat and self.species_feat_ability is not None:
            totals[self.species_feat_ability] += 1
        return totals

    @property
    def grants_species_feat(self) -> bool:
        """Варіантна людина й власна лінія беруть рису на 1 рівні (PHB, p. 31; TCoE, p. 8)."""
        return any((key or "").casefold() in SPECIES_WITH_FEAT for key in (self.species_key, self.subspecies_key))

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
        ability_spread: Mapping[Any, Any] | None = None,
        species_feat: str | None = None,
        species_feat_ability: Ability | None = None,
        species_source: str | None = None,
        species_feat_choices: Mapping[str, Iterable[str]] | None = None,
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
                raise ValidationError(f"{subspecies.name_en!r} не належить виду {species.name_en!r}")
        effective = subspecies or species
        choices = () if effective.ability_choice is None else tuple(ability_choices)
        candidate = replace(self)
        candidate.name = name.strip()
        candidate.species_key = species.key
        candidate.subspecies_key = subspecies.key if subspecies else None
        candidate.ability_choices = choices
        # Вільний розподіл (правила 2022) є лише у видів без фіксованих
        # бонусів; для решти навіть надісланий розподіл — помилка.
        candidate.ability_spread = ability_spread_values(ability_spread)
        candidate.spell_choices = tuple(name.strip() for name in spell_choices if str(name).strip())
        candidate.species_feat = (species_feat or "").strip().casefold() or None
        candidate.species_feat_ability = species_feat_ability if candidate.species_feat else None
        candidate.species_source = (species_source or "").strip().upper() or None
        # Лише вибори обраної риси: інша риса — інші групи.
        prefix = f"feat:{(candidate.species_feat or '').rsplit('/', 1)[-1]}:"
        candidate.species_feat_choices = {
            str(key): tuple(str(value) for value in values)
            for key, values in (species_feat_choices or {}).items()
            if candidate.species_feat and str(key).startswith(prefix) and values
        }
        if candidate.species_source and candidate.species_source not in {item.upper() for item in species.variants}:
            raise ValidationError(f"{species.name_en} не має версії з книги {species_source!r}")
        if (self.species_key, self.subspecies_key) != (
            candidate.species_key,
            candidate.subspecies_key,
        ):
            candidate.picks = tuple(pick for pick in candidate.picks if pick.source.kind is not SourceKind.SPECIES)
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
            raise ValidationError(f"{definition.name_en!r} обирає {definition.subclass_title!r} вже на 1 рівні")
        candidate = replace(self)
        changed = self.class_key is not None and self.class_key != definition.key
        candidate.class_key = definition.key
        candidate.subclass_key = subclass
        if changed:
            candidate.picks = tuple(pick for pick in candidate.picks if pick.source.kind is not SourceKind.CLASS)
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
        custom: Mapping[str, Any] | None = None,
    ) -> None:
        background = self.rules.background_mechanics(background_key)
        if background is None:
            raise NotFoundError(f"немає правил передісторії {background_key!r}")
        candidate = replace(self)
        candidate.background_key = background.key
        candidate.alignment = alignment.strip() if alignment else None
        candidate.picks = tuple(picks)
        candidate.custom_background = _custom_background(custom) if background.key == CUSTOM_BACKGROUND_KEY else None
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
            abilities={ability: AbilityScore(score) for ability, score in self.ability_scores.items()},
            rules=self.rules,
            classes=[
                CharacterClass(
                    class_key=self.class_key,
                    level=1,
                    subclass_key=self.subclass_key,
                )
            ],
            ability_bonus_choices=self.ability_choices,
            ability_spread=dict(self.ability_spread),
            species_key=self.species_key,
            subspecies_key=self.subspecies_key,
            background_key=self.background_key,
            custom_background=dict(self.custom_background) if self.custom_background else None,
            alignment=self.alignment,
            chosen=Proficiencies(items=self.picks),
            inventory=Inventory(items=self.items, money=self.money),
            spells=self.spells,
            spell_choices=self.spell_choices,
            feats=(self.species_feat,) if self.species_feat else (),
            feat_abilities=(
                {self.species_feat: self.species_feat_ability}
                if self.species_feat and self.species_feat_ability is not None
                else {}
            ),
            species_feat=self.species_feat,
            species_source=self.species_source,
            class_choices=dict(self.species_feat_choices),
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
        # Підраса обовʼязкова там, де вона визначає числа: ельф без підраси —
        # це не «ельф без уточнень», а незакінчений вибір.
        if requires_subspecies(species.key) and not self.subspecies_key:
            raise ValidationError(f"{species.name_en}: оберіть підрасу — вона дає свої бонуси й особливості")
        if self.subspecies_key:
            subspecies = self.rules.species_mechanics(self.subspecies_key)
            if subspecies is None:
                raise NotFoundError(f"немає правил підраси {self.subspecies_key!r}")
            if not subspecies.is_subspecies:
                raise ValidationError(f"{subspecies.name_en!r} не є підрасою")
            if subspecies.subrace_of and subspecies.subrace_of != species.key:
                raise ValidationError(f"{subspecies.name_en!r} не належить виду {species.name_en!r}")
        effective = self.species
        if effective is not None and effective.ability_unresolved:
            if not self.ability_spread:
                raise ValidationError(
                    f"{effective.name_en}: оберіть бонуси характеристик — +2 і +1 до "
                    f"двох різних або +1, +1 і +1 до трьох (правила 2022)"
                )
        elif self.ability_spread:
            raise ValidationError(
                f"{effective.name_en if effective is not None else 'вид'} має фіксовані "
                f"бонуси — вільний розподіл (правила 2022) для нього не діє"
            )
        if self.grants_species_feat and not self.species_feat:
            raise ValidationError("варіантна людина й власна лінія беруть рису на 1 рівні — оберіть рису")
        if self.species_feat and not self.grants_species_feat:
            raise ValidationError("вид не дає риси на 1 рівні")
        allowed = effective.cantrip_choice_count if effective is not None and effective.cantrip_choice_class else 0
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
            raise ValidationError(f"треба обрати {choice.count} здібності, обрано {len(self.ability_choices)}")
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
                    f"{definition.name_en!r} обирає {definition.subclass_title!r} на 1 рівні — зробіть вибір"
                )
            return
        if definition.subclass_level is None:
            raise ValidationError(f"{definition.name_en!r} не має підкласів")
        if definition.subclass_level > 1:
            raise ValidationError(f"{definition.subclass_title!r} обирається з {definition.subclass_level} рівня")

    def _validate_abilities(self) -> None:
        if self.ability_method is None:
            raise ValidationError("оберіть спосіб розподілу характеристик")
        if self.class_key is None:
            raise ValidationError("спершу оберіть клас")
        if set(self.ability_scores) != set(Ability):
            missing = ", ".join(sorted(ability.value for ability in Ability if ability not in self.ability_scores))
            raise ValidationError(f"не заповнено характеристики: {missing}")
        values = list(self.ability_scores.values())
        if self.ability_method is AbilityMethod.STANDARD_ARRAY:
            if sorted(values) != sorted(STANDARD_ARRAY):
                raise ValidationError("стандартний набір — це 15, 14, 13, 12, 10, 8, кожне число рівно раз")
        elif self.ability_method is AbilityMethod.POINT_BUY:
            for ability, score in self.ability_scores.items():
                if score not in POINT_BUY_COSTS:
                    raise ValidationError(f"{ability.value}: point buy дозволяє 8..15, отримано {score}")
            spent = sum(POINT_BUY_COSTS[score] for score in values)
            if spent > POINT_BUY_BUDGET:
                raise ValidationError(f"point buy: витрачено {spent} з {POINT_BUY_BUDGET} очок")
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
                    f"{ability.value}: {score} + {bonuses.get(ability, 0)} (вид) = {total}, а межа — {ABILITY_MAX}"
                )

    def _validate_background(self) -> None:
        if not self.background_key:
            raise ValidationError("оберіть передісторію")
        if self.background is None:
            raise NotFoundError(f"немає правил передісторії {self.background_key!r}")
        if self.class_key is None:
            raise ValidationError("спершу оберіть клас")
        if self.background_key == CUSTOM_BACKGROUND_KEY:
            if not self.custom_background:
                raise ValidationError("власна передісторія без назви й опису")
            for pick in self.picks:
                if pick.kind is ProficiencyKind.SKILL:
                    try:
                        Skill(pick.value.strip().casefold().replace(" ", "_"))
                    except ValueError as exc:
                        raise ValidationError(f"невідома навичка {pick.value!r}") from exc
                elif not pick.value.strip():
                    raise ValidationError("володіння без значення")
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
                raise ValidationError(f"{definition.name_en!r} дає {needed} навичок — обрано {used}")
        effective = self.species
        if effective is not None and effective.skill_any:
            source = GrantSource.of(SourceKind.SPECIES, effective.key)
            used = count_picks(accepted, ProficiencyKind.SKILL, source)
            if used != effective.skill_any:
                raise ValidationError(
                    f"{effective.name_en!r} дає {effective.skill_any} навичок на вибір — обрано {used}"
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
                    f"{spell.name_en!r}: закляття класу {spell.class_key!r}, а персонаж — {definition.name_en!r}"
                )
        cantrips = sum(1 for spell in self.spells if spell.is_cantrip)
        limit = definition.cantrips_at(1)
        if cantrips > limit:
            raise ValidationError(f"{definition.name_en}: заговорів не більше {limit}, обрано {cantrips}")
        known = tuple(spell for spell in self.spells if not spell.is_cantrip)
        known_limit = definition.spells_known_at(1)
        if known_limit is not None and len(known) > known_limit:
            raise ValidationError(
                f"{definition.name_en}: відомих заклять не більше {known_limit}, обрано {len(known)}"
            )
        max_level = self._max_spell_level(definition)
        for spell in known:
            if spell.level > max_level:
                raise ValidationError(f"{definition.name_en}: на 1 рівні немає заклять {spell.level} рівня")
        if definition.prepares_spells:
            ability = definition.spellcasting_ability
            prepared_limit = max(1, self.ability_modifier(ability) + 1) if ability else 1
            prepared = sum(1 for spell in known if spell.prepared or spell.always_prepared)
            if prepared > prepared_limit:
                raise ValidationError(
                    f"{definition.name_en}: підготовлених не більше {prepared_limit}, підготовлено {prepared}"
                )

    def _max_spell_level(self, definition: ClassMechanics) -> int:
        if definition.is_pact_magic:
            slots, level = definition.pact_at(1)
            return level if slots else 0
        table = definition.slots_at(1)
        levels = [index for index, count in enumerate(table, start=1) if count]
        return max(levels, default=0)
