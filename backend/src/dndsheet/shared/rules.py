"""Правила як дані: те, що однаково розуміють довідник і персонаж.

Тут живуть не «записи довідника» й не «стан персонажа», а **ознаки правил**:
хіт-дайс класу, бонуси виду, вимоги мультикласу, таблиця слотів заклять.
Їх розуміють обидва контексти, тому вони в спільному ядрі:

* `compendium` віддає їх через API (візард питає «що дає Воїн на 1 рівні?»);
* `characters` рахує з них лист (`DerivedStatsCalculator`).

Модуль чистий: жодного I/O, лише значення, розбір уже готового JSON і таблиці
правил. Таблиці слотів тут, а не в корпусі, бо це SRD-контент: 20 рядків, які
не змінюються від книги до книги, і без них домен не порахує нічого.

Джерела чисел: PHB (2014) — «Multiclassing: Spellcasting» (p. 165), Warlock
(Pact Magic, p. 107), і механіки класів з дзеркала 5e.tools
(`content/index/class-mechanics.json`, складає `scripts/ingest/mechanics.py`).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import MAX_LEVEL, MIN_LEVEL, Ability, Skill

# ---------------------------------------------------------------------------
# переліки
# ---------------------------------------------------------------------------


class CasterProgression(StrEnum):
    """Як рівні класу складаються в рівень заклинателя (мультиклас)."""

    FULL = "full"
    HALF = "1/2"
    THIRD = "1/3"
    ARTIFICER = "artificer"
    PACT = "pact"

    @property
    def divisor(self) -> int | None:
        """На скільки ділити рівні класу; `None` — не заклинатель/Pact Magic."""
        return {
            CasterProgression.FULL: 1,
            CasterProgression.HALF: 2,
            CasterProgression.THIRD: 3,
            CasterProgression.ARTIFICER: 2,
        }.get(self)

    @property
    def rounds_up(self) -> bool:
        """Виноска PHB: рівні артифіцера (TCE) округлюються вгору."""
        return self is CasterProgression.ARTIFICER

    @classmethod
    def parse(cls, value: str | None) -> "CasterProgression | None":
        if value is None or not str(value).strip():
            return None
        text = str(value).strip().casefold()
        aliases = {"half": cls.HALF, "third": cls.THIRD, "1/2": cls.HALF, "1/3": cls.THIRD}
        if text in aliases:
            return aliases[text]
        try:
            return cls(text)
        except ValueError as exc:
            raise ValidationError(f"невідомий прогрес заклять {value!r}") from exc


class Size(StrEnum):
    TINY = "tiny"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    HUGE = "huge"
    GARGANTUAN = "gargantuan"

    @classmethod
    def parse(cls, value: str) -> "Size":
        try:
            return cls(str(value).strip().casefold())
        except ValueError as exc:
            raise ValidationError(f"невідомий розмір {value!r}") from exc


SIZE_FROM_CODE: Mapping[str, Size] = MappingProxyType(
    {"T": Size.TINY, "S": Size.SMALL, "M": Size.MEDIUM,
     "L": Size.LARGE, "H": Size.HUGE, "G": Size.GARGANTUAN}
)

ARMOR_TRAININGS = ("light", "medium", "heavy", "shield")
WEAPON_TRAININGS = ("simple", "martial")

# ---------------------------------------------------------------------------
# таблиці правил (SRD)
# ---------------------------------------------------------------------------

#: Слоти за рівнями заклять для рівня заклинателя 1..20 (PHB, p. 165).
#: Рядок 1 — 1 рівень: два слоти 1 рівня. Це ж таблиця дає слоти
#: мультикласовому персонажу за сумарним рівнем заклинателя.
CASTER_SLOT_TABLE: tuple[tuple[int, ...], ...] = (
    (2, 0, 0, 0, 0, 0, 0, 0, 0),
    (3, 0, 0, 0, 0, 0, 0, 0, 0),
    (4, 2, 0, 0, 0, 0, 0, 0, 0),
    (4, 3, 0, 0, 0, 0, 0, 0, 0),
    (4, 3, 2, 0, 0, 0, 0, 0, 0),
    (4, 3, 3, 0, 0, 0, 0, 0, 0),
    (4, 3, 3, 1, 0, 0, 0, 0, 0),
    (4, 3, 3, 2, 0, 0, 0, 0, 0),
    (4, 3, 3, 3, 1, 0, 0, 0, 0),
    (4, 3, 3, 3, 2, 0, 0, 0, 0),
    (4, 3, 3, 3, 2, 1, 0, 0, 0),
    (4, 3, 3, 3, 2, 1, 0, 0, 0),
    (4, 3, 3, 3, 2, 1, 1, 0, 0),
    (4, 3, 3, 3, 2, 1, 1, 0, 0),
    (4, 3, 3, 3, 2, 1, 1, 1, 0),
    (4, 3, 3, 3, 2, 1, 1, 1, 0),
    (4, 3, 3, 3, 2, 1, 1, 1, 1),
    (4, 3, 3, 3, 3, 1, 1, 1, 1),
    (4, 3, 3, 3, 3, 2, 1, 1, 1),
    (4, 3, 3, 3, 3, 2, 2, 1, 1),
)

#: Pact Magic warlock-а: (кількість слотів, рівень слотів) на рівень 1..20.
#: Окрема таблиця, бо слоти відпочивають на короткому відпочинку й не
#: додаються до мультикласових (PHB, p. 107 і 164).
PACT_SLOT_TABLE: tuple[tuple[int, int], ...] = (
    (1, 1), (2, 1), (2, 2), (2, 2), (2, 3), (2, 3), (2, 4), (2, 4),
    (2, 5), (2, 5), (3, 5), (3, 5), (3, 5), (3, 5), (3, 5), (3, 5),
    (4, 5), (4, 5), (4, 5), (4, 5),
)

MAX_SPELL_LEVEL = 9


def _check_level(level: int, what: str = "рівень") -> int:
    if isinstance(level, bool) or not isinstance(level, int):
        raise ValidationError(f"{what} має бути цілим числом")
    if not MIN_LEVEL <= level <= MAX_LEVEL:
        raise ValidationError(f"{what} має бути в межах {MIN_LEVEL}..{MAX_LEVEL}")
    return level


def caster_level(levels: Iterable[tuple[CasterProgression | None, int]]) -> int:
    """Сумарний рівень заклинателя для мультикласу (без Pact Magic).

    Повні заклинателі додають рівень цілком, напівзаклинателі — половину,
    третинні — третину. Артифіцер (TCE) ділить навпіл, але округлює вгору.
    Pact Magic warlock-а в цю суму не входить зовсім.
    """
    total = 0
    for progression, level in levels:
        if progression is None or progression is CasterProgression.PACT:
            continue
        divisor = progression.divisor
        if not divisor:
            continue
        if progression.rounds_up:
            total += (level + divisor - 1) // divisor
        else:
            total += level // divisor
    return min(total, MAX_LEVEL)


def spell_slots(level: int) -> tuple[int, ...]:
    """Слоти за рівнем заклинателя 1..20: 9 чисел, індекс 0 — 1 рівень."""
    if level <= 0:
        return (0,) * MAX_SPELL_LEVEL
    return CASTER_SLOT_TABLE[_check_level(level) - 1]


def prepared_spell_limit(
    modifier: int,
    class_level: int,
    progression: "CasterProgression | None" = None,
) -> int:
    """Скільки заклять клас готує на день, мінімум 1.

    * жрець, друїд, маг — модифікатор + рівень класу (PHB, p. 58, 66, 114);
    * паладин — модифікатор + **половина** рівня паладина, вниз (PHB, p. 84);
    * артифіцер — модифікатор + половина рівня, вниз (TCE, p. 10).

    Формула одна на обчислювач листа й на щоденну підготовку: якщо їх дві,
    екран і перевірка рано чи пізно розійдуться.
    """
    if progression in (CasterProgression.HALF, CasterProgression.ARTIFICER):
        return max(1, modifier + class_level // 2)
    return max(1, modifier + class_level)


#: Вимоги мультикласу (PHB, p. 163), де індекс механік помиляється: таблицю
#: книги «Strength 13 or Dexterity 13» розбір склеїв в одну умову «і».
MULTICLASS_REQUIREMENT_FIXES: Mapping[str, tuple[Mapping[Ability, int], ...]] = {
    "fighter": ({Ability.STR: 13}, {Ability.DEX: 13}),
}

#: Що з книги може бути бронею; решта рядка («druids will not wear armor
#: made of metal») — не володіння, а шум розбору.
ARMOR_KINDS = frozenset({"light", "medium", "heavy", "shield"})


#: Види, де підраса **обовʼязкова**: вона визначає числа (PHB p. 20–24 —
#: дворф, ельф, гном, піврослик; EEPC — genasi; ERLW — shifter; EGtW —
#: aasimar; gith поділяється на githyanki/githzerai).
#:
#: Корпус не позначає «обовʼязковість» окремим полем, а «є підраси» — не те
#: саме: у людини є *Variant Human*, і він необовʼязковий. Тому список
#: явний — інакше довелося б або заборонити звичайну людину, або дозволити
#: ельфа без підраси.
SUBRACE_REQUIRED: frozenset[str] = frozenset(
    {"dwarf", "elf", "gnome", "halfling", "genasi", "shifter", "aasimar", "gith"}
)


def requires_subspecies(species_key: str | None) -> bool:
    return (species_key or "").strip().casefold() in SUBRACE_REQUIRED


# ---------------------------------------------------------------------------
# дрібні ознаки правил
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AbilityBonus:
    """Фіксований бонус до характеристики від виду (або іншого джерела)."""

    ability: Ability
    amount: int

    def __post_init__(self) -> None:
        if isinstance(self.amount, bool) or not isinstance(self.amount, int):
            raise ValidationError("бонус до характеристики має бути цілим числом")


@dataclass(frozen=True, slots=True)
class AbilityChoice:
    """«Дві здібності на вибір по +1» — те, що не можна порахувати без вибору."""

    count: int
    amount: int
    options: tuple[Ability, ...]

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValidationError("вибір характеристики має давати хоча б один бонус")
        if not self.options:
            raise ValidationError("вибір характеристики без варіантів")


@dataclass(frozen=True, slots=True)
class SkillChoice:
    """«Дві навички зі списку» у володіннях класу."""

    count: int
    options: tuple[Skill, ...]

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValidationError("вибір навички має давати хоча б одну навичку")
        if not self.options:
            raise ValidationError("вибір навички без варіантів")


@dataclass(frozen=True, slots=True)
class GrantedSpell:
    """Закляття, яке дає не клас, а вид: «ви знаєте thaumaturgy».

    `min_level` — рівень персонажа, з якого воно доступне (тифлінг отримує
    `hellish rebuke` на 3-му). Для 1 рівня беремо лише `min_level == 1`.
    """

    name_en: str
    spell_level: int
    min_level: int = 1

    def __post_init__(self) -> None:
        if not self.name_en.strip():
            raise ValidationError("закляття виду без назви")
        if not 0 <= self.spell_level <= MAX_SPELL_LEVEL:
            raise ValidationError(f"{self.name_en}: рівень закляття 0..{MAX_SPELL_LEVEL}")
        _check_level(self.min_level, "рівень появи закляття")


@dataclass(frozen=True, slots=True)
class SubclassSpells:
    """Закляття підкласу на 1 рівні.

    `prepared` — завжди підготовлені (домен жреця), `expanded` — додані до
    списку класу, з якого гравець обирає (патрон варлока).
    """

    prepared: tuple[str, ...] = ()
    expanded: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ClassFeature:
    """Риса класу: назва й рівень, на якому вона зʼявляється."""

    name_en: str
    level: int

    def __post_init__(self) -> None:
        if not self.name_en.strip():
            raise ValidationError("риса класу без назви")
        _check_level(self.level)


# ---------------------------------------------------------------------------
# клас
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClassMechanics:
    """Що клас дає механічно. Текст рис живе в довіднику, тут — числа."""

    key: str
    name_en: str
    source_id: str
    hit_die: int
    saving_throws: frozenset[Ability]
    skill_choices: tuple[SkillChoice, ...] = ()
    skill_any: int = 0
    armor_training: tuple[str, ...] = ()
    weapon_training: tuple[str, ...] = ()
    tool_training: tuple[str, ...] = ()
    spellcasting_ability: Ability | None = None
    caster_progression: CasterProgression | None = None
    prepares_spells: bool = False
    cantrips_known: tuple[int, ...] = ()
    spells_known: tuple[int, ...] | None = None
    spell_slots: tuple[tuple[int, ...], ...] = ()
    pact_slots: tuple[tuple[int, int], ...] = ()
    subclass_title: str | None = None
    subclass_level: int | None = None
    multiclass_requirements: tuple[Mapping[Ability, int], ...] = ()
    multiclass_armor: tuple[str, ...] = ()
    multiclass_weapons: tuple[str, ...] = ()
    multiclass_tools: tuple[str, ...] = ()
    features: tuple[ClassFeature, ...] = ()
    optional_features: Mapping[str, tuple[tuple[int, int], ...]] = field(
        default_factory=lambda: MappingProxyType({})
    )
    #: Закляття підкласів на 1 рівні, ключ — slug id підкласу (life-domain).
    subclass_spells: Mapping[str, SubclassSpells] = field(
        default_factory=lambda: MappingProxyType({})
    )
    variants: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValidationError("клас без ключа")
        if not 4 <= self.hit_die <= 20:
            raise ValidationError(f"{self.key}: неприпустимий хіт-дайс d{self.hit_die}")
        if not self.saving_throws:
            raise ValidationError(f"{self.key}: без володінь кидками порятунку")
        if self.subclass_level is not None:
            _check_level(self.subclass_level, "рівень підкласу")

    # --- похідне -----------------------------------------------------------

    @property
    def casts_spells(self) -> bool:
        return self.spellcasting_ability is not None

    @property
    def is_pact_magic(self) -> bool:
        return self.caster_progression is CasterProgression.PACT

    @property
    def skill_limit(self) -> int:
        """Скільки навичок клас дає обрати на 1 рівні."""
        return sum(choice.count for choice in self.skill_choices) + self.skill_any

    def skill_options(self) -> tuple[Skill, ...]:
        seen: list[Skill] = []
        for choice in self.skill_choices:
            for skill in choice.options:
                if skill not in seen:
                    seen.append(skill)
        return tuple(seen)

    def cantrips_at(self, level: int) -> int:
        _check_level(level)
        return self.cantrips_known[level - 1] if len(self.cantrips_known) >= level else 0

    def spells_known_at(self, level: int) -> int | None:
        """Ліміт відомих заклять; `None` — клас не має такого ліміту."""
        if not self.spells_known:
            return None
        _check_level(level)
        return self.spells_known[level - 1] if len(self.spells_known) >= level else None

    def slots_at(self, level: int) -> tuple[int, ...]:
        _check_level(level)
        if len(self.spell_slots) < level:
            return (0,) * MAX_SPELL_LEVEL
        return self.spell_slots[level - 1]

    def pact_at(self, level: int) -> tuple[int, int]:
        """(слоти, рівень слотів) для Pact Magic; (0, 0), якщо його немає."""
        _check_level(level)
        if len(self.pact_slots) < level:
            return (0, 0)
        return self.pact_slots[level - 1]

    def max_spell_level(self, level: int) -> int:
        """Найвищий рівень закляття, який клас має на цьому рівні.

        Формула одна на лист, підготовку й підвищення рівня: інакше екран
        пропонував би закляття, яких клас ще не дає.
        """
        if self.is_pact_magic:
            slots, slot_level = self.pact_at(level)
            return slot_level if slots else 0
        return max(
            (index for index, count in enumerate(self.slots_at(level), start=1) if count),
            default=0,
        )

    def features_at(self, level: int) -> tuple[ClassFeature, ...]:
        _check_level(level)
        return tuple(feature for feature in self.features if feature.level <= level)

    def optional_feature_count(self, name: str, level: int) -> int:
        """Скільки опційних умінь («Eldritch Invocations») клас дає на рівні."""
        _check_level(level)
        steps = self.optional_features.get(name) or ()
        count = 0
        for step_level, step_count in steps:
            if step_level <= level:
                count = step_count
        return count

    def subclass_spells_for(self, subclass_key: str | None) -> SubclassSpells | None:
        """Закляття підкласу за ключем: id корпусу або slug («life-domain»)."""
        if not subclass_key:
            return None
        slug = subclass_key.strip().casefold().rsplit("/", 1)[-1]
        return self.subclass_spells.get(slug)

    def satisfies_multiclass(self, scores: Mapping[Ability, int]) -> bool:
        """Чи проходить персонаж за вимогами мультикласу (PHB, p. 163).

        Вимога — «АБО»: Воїну досить 13 STR **або** 13 DEX. Порожній список
        вимог означає «без обмежень».
        """
        if not self.multiclass_requirements:
            return True
        for alternative in self.multiclass_requirements:
            if all(scores.get(ability, 0) >= score for ability, score in alternative.items()):
                return True
        return False

    # --- розбір ------------------------------------------------------------

    @classmethod
    def from_index(cls, key: str, record: Mapping[str, Any]) -> "ClassMechanics":
        """Розібрати запис `content/index/class-mechanics.json`."""
        slots = tuple(tuple(int(value) for value in row) for row in record.get("spell_slots") or ())
        pact = tuple(
            (int(row[0]), int(row[1])) for row in record.get("pact_slots") or () if len(row) >= 2
        )
        optional = {
            str(name): tuple((int(level), int(count)) for level, count in steps)
            for name, steps in (record.get("optional_features") or {}).items()
        }
        requirements = tuple(
            {
                _ability(name): int(score)
                for name, score in alternative.items()
                if name in {ability.value for ability in Ability}
            }
            for alternative in record.get("multiclass_requirements") or ()
        )
        gained = record.get("multiclass_gained") or {}
        return cls(
            key=key,
            name_en=str(record.get("name_en") or key),
            source_id=str(record.get("source_id") or ""),
            hit_die=int(record.get("hit_die") or 0),
            saving_throws=frozenset(_ability(name) for name in record.get("saving_throws") or ()),
            skill_choices=tuple(
                SkillChoice(
                    count=int(choice.get("count") or 1),
                    options=tuple(_skill(name) for name in choice.get("from") or ()),
                )
                for choice in record.get("skill_choices") or ()
            ),
            skill_any=int(record.get("skill_any") or 0),
            armor_training=tuple(
                str(item) for item in record.get("armor_training") or () if str(item) in ARMOR_KINDS
            ),
            weapon_training=tuple(str(item) for item in record.get("weapon_training") or ()),
            tool_training=tuple(str(item) for item in record.get("tool_training") or ()),
            spellcasting_ability=_optional_ability(record.get("spellcasting_ability")),
            caster_progression=CasterProgression.parse(record.get("caster_progression")),
            prepares_spells=bool(record.get("prepares_spells")),
            cantrips_known=tuple(int(value) for value in record.get("cantrips_known") or ()),
            spells_known=(
                tuple(int(value) for value in record["spells_known"])
                if record.get("spells_known")
                else None
            ),
            spell_slots=slots,
            pact_slots=pact,
            subclass_title=_optional_str(record.get("subclass_title")),
            subclass_level=(
                int(record["subclass_level"]) if record.get("subclass_level") else None
            ),
            multiclass_requirements=MULTICLASS_REQUIREMENT_FIXES.get(key, requirements),
            multiclass_armor=tuple(
                str(item) for item in gained.get("armor") or () if str(item) in ARMOR_KINDS
            ),
            multiclass_weapons=tuple(str(item) for item in gained.get("weapons") or ()),
            multiclass_tools=tuple(str(item) for item in gained.get("tools") or ()),
            features=tuple(
                ClassFeature(name_en=str(feature.get("name") or ""), level=int(feature.get("level") or 0))
                for feature in record.get("features") or ()
                if feature.get("name") and feature.get("level")
            ),
            optional_features=MappingProxyType(optional),
            subclass_spells=MappingProxyType(
                {
                    str(key): SubclassSpells(
                        prepared=tuple(str(name) for name in value.get("prepared") or ()),
                        expanded=tuple(str(name) for name in value.get("expanded") or ()),
                    )
                    for key, value in (record.get("subclass_spells") or {}).items()
                    if isinstance(value, dict)
                }
            ),
            variants=tuple(str(item) for item in record.get("variants") or ()),
        )


# ---------------------------------------------------------------------------
# вид і передісторія
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SpeciesMechanics:
    """Вид (раса) або підраса. Підраса вже несе успадковані числа батька."""

    key: str
    name_en: str
    source_id: str
    size: Size
    speed: int
    subrace_of: str | None = None
    ability_bonuses: tuple[AbilityBonus, ...] = ()
    ability_choice: AbilityChoice | None = None
    skill_proficiencies: frozenset[Skill] = frozenset()
    skill_any: int = 0
    weapon_proficiencies: tuple[str, ...] = ()
    tool_proficiencies: tuple[str, ...] = ()
    tools_any: int = 0
    languages: tuple[str, ...] = ()
    languages_any_standard: int = 0
    darkvision: int = 0
    resistances: tuple[str, ...] = ()
    standard_variant: bool = False
    #: Бонуси характеристик не закодовані в дзеркалі (вільний розподіл 2022):
    #: вибір робить гравець, а не таблиця.
    ability_unresolved: bool = False
    #: Заговори, які вид дає одразу («ви знаєте thaumaturgy»).
    shared_cantrips: tuple[str, ...] = ()
    #: Вибір заговору зі списку класу («один заговір візарда» у високого ельфа).
    cantrip_choice_class: str | None = None
    cantrip_choice_count: int = 0
    #: Інші закляття виду на 1 рівні (уроджені, раз на відпочинок).
    granted_spells: tuple[GrantedSpell, ...] = ()
    variants: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValidationError("вид без ключа")
        if not 0 <= self.speed <= 120:
            raise ValidationError(f"{self.key}: неприпустима швидкість {self.speed}")
        if self.darkvision < 0:
            raise ValidationError(f"{self.key}: темний зір не може бути відʼємним")

    @property
    def is_subspecies(self) -> bool:
        return bool(self.subrace_of)

    @classmethod
    def from_index(cls, key: str, record: Mapping[str, Any]) -> "SpeciesMechanics":
        sizes = record.get("size") or ("medium",)
        fixed = record.get("ability_fixed") or {}
        choice = record.get("ability_choice")
        return cls(
            key=key,
            name_en=str(record.get("name_en") or key),
            source_id=str(record.get("source_id") or ""),
            size=Size.parse(sizes[0]),
            speed=int(record.get("speed") or 30),
            subrace_of=_optional_str(record.get("subrace_of")),
            ability_bonuses=tuple(
                AbilityBonus(ability=_ability(name), amount=int(amount))
                for name, amount in fixed.items()
                if name in {ability.value for ability in Ability}
            ),
            ability_choice=(
                AbilityChoice(
                    count=int(choice.get("count") or 1),
                    amount=int(choice.get("amount") or 1),
                    options=tuple(_ability(name) for name in choice.get("from") or ()),
                )
                if choice
                else None
            ),
            skill_proficiencies=frozenset(
                _skill(name) for name in record.get("skill_proficiencies") or ()
            ),
            skill_any=int(record.get("skill_any") or 0),
            weapon_proficiencies=tuple(str(item) for item in record.get("weapon_proficiencies") or ()),
            tool_proficiencies=tuple(str(item) for item in record.get("tool_proficiencies") or ()),
            tools_any=int(record.get("tools_any") or 0),
            languages=tuple(str(item) for item in record.get("languages") or ()),
            languages_any_standard=int(record.get("languages_any_standard") or 0),
            darkvision=int(record.get("darkvision") or 0),
            resistances=tuple(str(item) for item in record.get("resistances") or ()),
            standard_variant=bool(record.get("standard_variant")),
            ability_unresolved=bool(record.get("ability_unresolved")),
            shared_cantrips=tuple(str(item) for item in record.get("shared_cantrips") or ()),
            cantrip_choice_class=_optional_str(
                (record.get("cantrip_choice") or {}).get("from_class")
            ),
            cantrip_choice_count=int((record.get("cantrip_choice") or {}).get("count") or 0),
            granted_spells=tuple(
                GrantedSpell(
                    name_en=str(item.get("name") or ""),
                    spell_level=int(item.get("level") or 1),
                    min_level=int(item.get("min_level") or 1),
                )
                for item in record.get("granted_spells") or ()
                if isinstance(item, dict) and item.get("name")
            ),
            variants=tuple(str(item) for item in record.get("variants") or ()),
        )


@dataclass(frozen=True, slots=True)
class BackgroundMechanics:
    """Передісторія: навички, інструменти, мови й риса."""

    key: str
    name_en: str
    source_id: str
    skill_proficiencies: frozenset[Skill] = frozenset()
    skill_any: int = 0
    tool_proficiencies: tuple[str, ...] = ()
    tools_any: int = 0
    languages_any_standard: int = 0
    feature_en: str | None = None
    variants: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValidationError("передісторія без ключа")

    @classmethod
    def from_index(cls, key: str, record: Mapping[str, Any]) -> "BackgroundMechanics":
        return cls(
            key=key,
            name_en=str(record.get("name_en") or key),
            source_id=str(record.get("source_id") or ""),
            skill_proficiencies=frozenset(
                _skill(name) for name in record.get("skill_proficiencies") or ()
            ),
            skill_any=int(record.get("skill_any") or 0),
            tool_proficiencies=tuple(str(item) for item in record.get("tool_proficiencies") or ()),
            tools_any=int(record.get("tools_any") or 0),
            languages_any_standard=int(record.get("languages_any_standard") or 0),
            feature_en=_optional_str(record.get("feature")),
            variants=tuple(str(item) for item in record.get("variants") or ()),
        )


# ---------------------------------------------------------------------------
# допоміжне
# ---------------------------------------------------------------------------


def ability_spread(
    raw: Mapping[Any, Any] | None = None,
) -> dict[Ability, int]:
    """Розподіл характеристик за правилами 2022 (MotM, p. 7; TCoE «Custom Lineage»).

    Два дозволені види: **+2 і +1** до двох різних характеристик або **+1,
    +1 і +1** до трьох. Старе правило видів давало фіксовані бонуси, тому тут
    їх немає — гравець розставляє сам, а сервер перевіряє форму.

    Повертає `{Ability: бонус}`; порожній вхід — порожній результат.
    """
    if not raw:
        return {}
    if not isinstance(raw, Mapping):
        raise ValidationError(
            "ability_spread має бути обʼєктом «характеристика: +»"
        )
    spread: dict[Ability, int] = {}
    for name, amount in raw.items():
        try:
            ability = Ability(str(name).strip().casefold())
        except ValueError as exc:
            raise ValidationError(f"невідома характеристика {name!r}") from exc
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise ValidationError(f"{name}: бонус має бути цілим числом")
        if amount < 1 or amount > 2:
            raise ValidationError(
                f"{name}: бонус вільного розподілу — +1 або +2, надіслано {amount}"
            )
        if ability in spread:
            raise ValidationError(f"характеристика {ability.value!r} повторюється")
        spread[ability] = amount
    if sum(spread.values()) != 3:
        raise ValidationError(
            f"вільний розподіл дає рівно +3 (два бонуси або три), надіслано "
            f"{sum(spread.values())}"
        )
    shape = sorted(spread.values(), reverse=True)
    if shape not in ([2, 1], [1, 1, 1]):
        raise ValidationError(
            "вільний розподіл: або +2 і +1 до двох характеристик, або +1, +1 і +1 до трьох"
        )
    return spread


def ability_bonus_totals(
    species: SpeciesMechanics | None,
    choices: Iterable[Ability] = (),
) -> dict[Ability, int]:
    """Бонуси характеристик від виду: фіксовані плюс зроблений вибір.

    Той самий розрахунок потрібен і `ModifierResolver` (де він ще й несе
    джерело), і візарду, який перевіряє, що після бонусів жодна
    характеристика не перевищила 20 (PHB, p. 173).
    """
    totals = dict.fromkeys(Ability, 0)
    if species is None:
        return totals
    for bonus in species.ability_bonuses:
        totals[bonus.ability] += bonus.amount
    if species.ability_choice is not None:
        for ability in choices:
            totals[ability] += species.ability_choice.amount
    return totals


def _ability(value: Any) -> Ability:
    try:
        return Ability(str(value).strip().casefold())
    except ValueError as exc:
        raise ValidationError(f"невідома характеристика {value!r}") from exc


def _optional_ability(value: Any) -> Ability | None:
    return None if value is None or not str(value).strip() else _ability(value)


def _skill(value: Any) -> Skill:
    text = str(value).strip().casefold().replace(" ", "_").replace("-", "_")
    try:
        return Skill(text)
    except ValueError as exc:
        raise ValidationError(f"невідома навичка {value!r}") from exc


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
