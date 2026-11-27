"""Правила як дані: те, що однаково розуміють довідник і персонаж.

Тут живуть не «записи довідника» й не «стан персонажа», а **ознаки правил**:
кість хітів класу, бонуси виду, вимоги мультикласу, таблиця комірок заклять.
Їх розуміють обидва контексти, тому вони в спільному ядрі:

* `compendium` віддає їх через API (візард питає «що дає Воїн на 1 рівні?»);
* `characters` рахує з них лист (`DerivedStatsCalculator`).

Модуль чистий: жодного I/O, лише значення, розбір уже готового JSON і таблиці
правил. Таблиці комірок тут, а не в корпусі, бо це SRD-контент: 20 рядків, які
не змінюються від книги до книги, і без них домен не порахує нічого.

Джерела чисел: PHB (2014) — «Multiclassing: Spellcasting» (p. 165), Warlock
(Pact Magic, p. 107), і механіки класів з дзеркала 5e.tools
(`content/index/class-mechanics.json`, складає `scripts/ingest/mechanics.py`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
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
    {"T": Size.TINY, "S": Size.SMALL, "M": Size.MEDIUM, "L": Size.LARGE, "H": Size.HUGE, "G": Size.GARGANTUAN}
)

ARMOR_TRAININGS = ("light", "medium", "heavy", "shield")
WEAPON_TRAININGS = ("simple", "martial")

# ---------------------------------------------------------------------------
# таблиці правил (SRD)
# ---------------------------------------------------------------------------

#: Комірки за рівнями заклять для рівня заклинателя 1..20 (PHB, p. 165).
#: Рядок 1 — 1 рівень: два комірки 1 рівня. Це ж таблиця дає комірки
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

#: Pact Magic warlock-а: (кількість комірок, рівень комірок) на рівень 1..20.
#: Окрема таблиця, бо комірки відпочивають на короткому відпочинку й не
#: додаються до мультикласових (PHB, p. 107 і 164).
PACT_SLOT_TABLE: tuple[tuple[int, int], ...] = (
    (1, 1),
    (2, 1),
    (2, 2),
    (2, 2),
    (2, 3),
    (2, 3),
    (2, 4),
    (2, 4),
    (2, 5),
    (2, 5),
    (3, 5),
    (3, 5),
    (3, 5),
    (3, 5),
    (3, 5),
    (3, 5),
    (4, 5),
    (4, 5),
    (4, 5),
    (4, 5),
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
    """Комірки за рівнем заклинателя 1..20: 9 чисел, індекс 0 — 1 рівень."""
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
#: дворф, ельф, гном, напіврослик; EEPC — genasi; ERLW — shifter; EGtW —
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
    #: Завжди підготовлені за рівнем класу: {1: (bless, cure wounds), 3: (…)}.
    by_level: Mapping[int, tuple[str, ...]] = field(default_factory=lambda: MappingProxyType({}))
    #: Круг Землі: місцевість → таблиця за рівнями (обирається в `class_choices`).
    by_terrain: Mapping[str, Mapping[int, tuple[str, ...]]] = field(default_factory=lambda: MappingProxyType({}))


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
    optional_features: Mapping[str, tuple[tuple[int, int], ...]] = field(default_factory=lambda: MappingProxyType({}))
    #: Закляття підкласів на 1 рівні, ключ — slug id підкласу (life-domain).
    subclass_spells: Mapping[str, SubclassSpells] = field(default_factory=lambda: MappingProxyType({}))
    variants: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValidationError("клас без ключа")
        if not 4 <= self.hit_die <= 20:
            raise ValidationError(f"{self.key}: неприпустимий кість хітів d{self.hit_die}")
        if not self.saving_throws:
            raise ValidationError(f"{self.key}: без володінь рятівними кидками")
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
        """Ліміт відомих заклять зі списку класу; `None` — клас не має такого ліміту.

        Магічні таємниці барда входять у колонку відомих (PHB, p. 54), але
        обираються окремо й з будь-якого класу — тому зі списку барда їх менше.
        """
        if not self.spells_known:
            return None
        _check_level(level)
        if len(self.spells_known) < level:
            return None
        known = self.spells_known[level - 1]
        return known - magical_secrets_count(level) if self.key == "bard" else known

    def slots_at(self, level: int) -> tuple[int, ...]:
        _check_level(level)
        if len(self.spell_slots) < level:
            return (0,) * MAX_SPELL_LEVEL
        return self.spell_slots[level - 1]

    def pact_at(self, level: int) -> tuple[int, int]:
        """(комірки, рівень комірок) для Pact Magic; (0, 0), якщо його немає."""
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
        pact = tuple((int(row[0]), int(row[1])) for row in record.get("pact_slots") or () if len(row) >= 2)
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
            armor_training=tuple(str(item) for item in record.get("armor_training") or () if str(item) in ARMOR_KINDS),
            weapon_training=tuple(str(item) for item in record.get("weapon_training") or ()),
            tool_training=tuple(str(item) for item in record.get("tool_training") or ()),
            spellcasting_ability=_optional_ability(record.get("spellcasting_ability")),
            caster_progression=CasterProgression.parse(record.get("caster_progression")),
            prepares_spells=bool(record.get("prepares_spells")),
            cantrips_known=tuple(int(value) for value in record.get("cantrips_known") or ()),
            spells_known=(
                tuple(int(value) for value in record["spells_known"]) if record.get("spells_known") else None
            ),
            spell_slots=slots,
            pact_slots=pact,
            subclass_title=_optional_str(record.get("subclass_title")),
            subclass_level=(int(record["subclass_level"]) if record.get("subclass_level") else None),
            multiclass_requirements=MULTICLASS_REQUIREMENT_FIXES.get(key, requirements),
            multiclass_armor=tuple(str(item) for item in gained.get("armor") or () if str(item) in ARMOR_KINDS),
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
            skill_proficiencies=frozenset(_skill(name) for name in record.get("skill_proficiencies") or ()),
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
            cantrip_choice_class=_optional_str((record.get("cantrip_choice") or {}).get("from_class")),
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
            skill_proficiencies=frozenset(_skill(name) for name in record.get("skill_proficiencies") or ()),
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
        raise ValidationError("ability_spread має бути обʼєктом «характеристика: +»")
    spread: dict[Ability, int] = {}
    for name, amount in raw.items():
        try:
            ability = Ability(str(name).strip().casefold())
        except ValueError as exc:
            raise ValidationError(f"невідома характеристика {name!r}") from exc
        if isinstance(amount, bool) or not isinstance(amount, int):
            raise ValidationError(f"{name}: бонус має бути цілим числом")
        if amount < 1 or amount > 2:
            raise ValidationError(f"{name}: бонус вільного розподілу — +1 або +2, надіслано {amount}")
        if ability in spread:
            raise ValidationError(f"характеристика {ability.value!r} повторюється")
        spread[ability] = amount
    if sum(spread.values()) != 3:
        raise ValidationError(f"вільний розподіл дає рівно +3 (два бонуси або три), надіслано {sum(spread.values())}")
    shape = sorted(spread.values(), reverse=True)
    if shape not in ([2, 1], [1, 1, 1]):
        raise ValidationError("вільний розподіл: або +2 і +1 до двох характеристик, або +1, +1 і +1 до трьох")
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


# ---------------------------------------------------------------------------
# заклинателі-третинки: чарують через підклас (PHB, p. 74 і 97)
# ---------------------------------------------------------------------------

#: Відомі закляття містичного лицаря й таємного пройдисвіта за рівнем класу.
_THIRD_CASTER_KNOWN = (0, 0, 3, 4, 4, 4, 5, 6, 6, 7, 8, 8, 9, 10, 10, 11, 11, 11, 12, 13)

#: Підклас → заговори (3–9 рівень, 10+). Пройдисвіт має ще Mage Hand.
THIRD_CASTER_SUBCLASSES: Mapping[str, tuple[int, int]] = {
    "eldritch-knight": (2, 3),
    "arcane-trickster": (3, 4),
}


def with_subclass_casting(definition: ClassMechanics, subclass_key: str | None) -> ClassMechanics:
    """Воїн чи плут з магічним підкласом чарує як третинний заклинатель.

    Інтелект, список мага, комірки власної таблиці = таблиця за рівнем
    заклинателя ⌈рівень / 3⌉ (з 3 рівня класу).

    shortcut: обмеження шкіл (огородження й втілення / чари й ілюзія) не
    перевіряється — додати, коли закляття в агрегаті матимуть школу.
    """
    slug = (subclass_key or "").strip().casefold().rsplit("/", 1)[-1]
    cantrips = THIRD_CASTER_SUBCLASSES.get(slug)
    if cantrips is None or definition.casts_spells:
        return definition
    levels = range(1, MAX_LEVEL + 1)
    return replace(
        definition,
        spellcasting_ability=Ability.INT,
        caster_progression=CasterProgression.THIRD,
        cantrips_known=tuple(0 if lvl < 3 else cantrips[lvl >= 10] for lvl in levels),
        spells_known=_THIRD_CASTER_KNOWN,
        spell_slots=tuple(spell_slots(-(-lvl // 3)) if lvl >= 3 else spell_slots(0) for lvl in levels),
    )


# ---------------------------------------------------------------------------
# риси з +1 до характеристики (PHB, p. 165–170)
# ---------------------------------------------------------------------------

_FEAT_INCREASE = re.compile(r"Increase (?:your|the chosen) (.*?)(?: score)? by 1", re.I)


def feat_ability_options(text: str) -> tuple[Ability, ...]:
    """Які характеристики риса дає підвищити на 1; порожньо — риса без +1.

    «Increase your Strength or Dexterity score by 1» → (STR, DEX);
    «Increase the chosen ability score by 1» (Resilient) → усі шість.
    """
    match = _FEAT_INCREASE.search(text or "")
    if match is None:
        return ()
    phrase = match.group(1).casefold()
    if "chosen" in match.group(0).casefold() or "ability" in phrase:
        return tuple(Ability)
    names = {
        "strength": Ability.STR,
        "dexterity": Ability.DEX,
        "constitution": Ability.CON,
        "intelligence": Ability.INT,
        "wisdom": Ability.WIS,
        "charisma": Ability.CHA,
    }
    return tuple(ability for name, ability in names.items() if name in phrase)


#: Навичка, яку клас дає при мультикласі (PHB, p. 164): бард — будь-яку,
#: слідопит і плут — зі свого списку. Решта класів навичок не дає.
MULTICLASS_SKILLS: Mapping[str, int] = {"bard": 1, "ranger": 1, "rogue": 1}


# ---------------------------------------------------------------------------
# вибори класу: бойовий стиль, втаємничення, метамагія, прийоми… (PHB 2014)
# ---------------------------------------------------------------------------

#: Група → тип запису `optionalfeature` у довіднику ({cls} — ключ класу).
CHOICE_FEATURE_TYPES: Mapping[str, str] = {
    "Fighting Style": "fighting style ({cls})",
    "Eldritch Invocations": "eldritch invocation",
    "Metamagic": "metamagic",
    "Pact Boon": "pact boon",
    "Maneuvers": "maneuver (battle master)",
    "Infusions": "artificer infusion",
}

#: Місцевості слідопита й Круга Землі (PHB, p. 68, 91), у порядку книги.
TERRAINS = ("arctic", "coast", "desert", "forest", "grassland", "mountain", "swamp", "underdark")

#: Групи, варіанти яких — не записи довідника, а перелік із книги (PHB, p. 91).
CHOICE_FIXED_OPTIONS: Mapping[str, tuple[str, ...]] = {
    "Favored Enemy": (
        "aberrations",
        "beasts",
        "celestials",
        "constructs",
        "dragons",
        "elementals",
        "fey",
        "fiends",
        "giants",
        "monstrosities",
        "oozes",
        "plants",
        "undead",
        "humanoids (two races)",
    ),
    "Natural Explorer": TERRAINS,
    "Circle Terrain": TERRAINS,
}

#: Вибори, яких індекс механік не має: (клас, підклас або None, група) → [(рівень, скільки)].
_EXTRA_CHOICES: Mapping[tuple[str, str | None, str], tuple[tuple[int, int], ...]] = {
    ("fighter", "battle-master", "Maneuvers"): ((3, 3), (7, 5), (10, 7), (15, 9)),
    ("fighter", "champion", "Fighting Style"): ((10, 1),),  # Additional Fighting Style
    ("ranger", None, "Favored Enemy"): ((1, 1), (6, 2), (14, 3)),
    ("ranger", None, "Natural Explorer"): ((1, 1), (6, 2), (10, 3)),
    ("druid", "circle-of-the-land", "Circle Terrain"): ((2, 1),),
}


def class_choice_slots(entries: Iterable[tuple[Any, ClassMechanics]]) -> dict[str, int]:
    """Скільки варіантів кожної групи дали рівні: {"fighter:Fighting Style": 1}."""
    slots: dict[str, int] = {}
    for entry, definition in entries:
        subclass = (entry.subclass_key or "").casefold().rsplit("/", 1)[-1] or None
        groups = {name: definition.optional_feature_count(name, entry.level) for name in definition.optional_features}
        for (klass, needs, group), steps in _EXTRA_CHOICES.items():
            if klass == entry.class_key and needs in (None, subclass):
                groups[group] = groups.get(group, 0) + max(
                    (count for level, count in steps if level <= entry.level), default=0
                )
        for group, count in groups.items():
            if count > 0 and (group in CHOICE_FEATURE_TYPES or group in CHOICE_FIXED_OPTIONS):
                slots[f"{entry.class_key}:{group}"] = count
    return slots


#: Броня із завадою на Скритність (PHB, p. 145).
_NOISY_ARMOR = frozenset({"padded", "scale mail", "half plate", "ring mail", "chain mail", "splint", "plate"})


def stealth_disadvantage(armor: Any) -> bool:
    """Чи дає вдягнена броня заваду на Скритність (`armor` — предмет або None)."""
    if armor is None:
        return False
    name = armor.name_en.strip().casefold().removesuffix(" armor")
    return name in _NOISY_ARMOR


#: Категорія броні за назвою (PHB, p. 145); магічні («Plate Armor +1», «Elven
#: Chain») — за базовою назвою всередині. Довше — раніше: «studded leather»
#: перш ніж «leather».
_ARMOR_CATEGORY: tuple[tuple[str, str], ...] = (
    ("studded leather", "light"),
    ("padded", "light"),
    ("leather", "light"),
    ("chain shirt", "medium"),
    ("elven chain", "medium"),
    ("scale mail", "medium"),
    ("half plate", "medium"),
    ("breastplate", "medium"),
    ("spiked armor", "medium"),
    ("hide", "medium"),
    ("ring mail", "heavy"),
    ("chain mail", "heavy"),
    ("splint", "heavy"),
    ("plate", "heavy"),
)


def armor_category(armor: Any) -> str | None:
    """«light» / «medium» / «heavy» для вдягненої броні; без назви в таблиці — з межі Спритності."""
    if armor is None:
        return None
    name = armor.name_en.strip().casefold()
    for base, category in _ARMOR_CATEGORY:
        if base in name:
            return category
    return {None: "light", 2: "medium", 0: "heavy"}.get(armor.dex_cap, "medium")


def armor_dex_cap(armor: Any) -> int | None:
    """Межа Спритності за категорією: легка — без межі, середня — 2, важка — 0."""
    return {"light": None, "medium": 2, "heavy": 0}[armor_category(armor) or "light"]


#: Музичні інструменти (PHB, p. 154): бард при мультикласі обирає один (p. 164).
MUSICAL_INSTRUMENTS = (
    "bagpipes",
    "drum",
    "dulcimer",
    "flute",
    "horn",
    "lute",
    "lyre",
    "pan flute",
    "shawm",
    "viol",
)


# ---------------------------------------------------------------------------
# вибори рис і бойових стилів (PHB, p. 165–170; TCoE, p. 22, 41, 79; XGtE, p. 73)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DerivedChoice:
    """Що треба обрати, коли взято рису чи стиль: «3 навички або інструменти».

    `kind` каже, з чого обирати: skill, tool, skill_or_tool, language, weapon,
    expertise, spell, fixed (готовий перелік `options`) або optional (записи
    `optionalfeature` типу `feature_type`).
    """

    group: str
    count: int
    kind: str
    spell_level: int = 0
    schools: tuple[str, ...] = ()
    #: Клас списку заклять; `None` — клас із вибору «Spell Class» тієї ж риси,
    #: «*» — будь-який клас.
    spell_class: str | None = None
    ritual: bool = False
    options: tuple[str, ...] = ()
    feature_type: str = ""
    #: Будь-який рівень від заговорів до найвищого, який має цей клас (Магічні таємниці).
    max_level_of: str = ""
    #: Рівень закляття — до половини рівня (вгору): «warlock» — рівня чаклуна,
    #: «total» — рівня персонажа (переписані ритуали).
    max_level_half: str = ""
    #: Без ліміту: гравець дописує, скільки знайшов (ритуали в книзі); `count` — стеля.
    open_ended: bool = False


#: Класи, з яких Magic Initiate і Ritual Caster беруть закляття.
FEAT_SPELL_CLASSES = ("bard", "cleric", "druid", "sorcerer", "warlock", "wizard")

#: Інструменти ремісника (PHB, p. 154) — Artificer Initiate обирає один.
ARTISAN_TOOLS = (
    "alchemist's supplies",
    "brewer's supplies",
    "calligrapher's supplies",
    "carpenter's tools",
    "cartographer's tools",
    "cobbler's tools",
    "cook's utensils",
    "glassblower's tools",
    "jeweler's tools",
    "leatherworker's tools",
    "mason's tools",
    "painter's supplies",
    "potter's tools",
    "smith's tools",
    "tinker's tools",
    "weaver's tools",
    "woodcarver's tools",
)

#: Усі інструменти, якими можна володіти (PHB, p. 154–155).
ALL_TOOLS = (
    ARTISAN_TOOLS
    + (
        "disguise kit",
        "forgery kit",
        "herbalism kit",
        "navigator's tools",
        "poisoner's kit",
        "thieves' tools",
        "vehicles (land)",
        "vehicles (water)",
        "dice set",
        "dragonchess set",
        "playing card set",
        "three-dragon ante set",
    )
    + MUSICAL_INSTRUMENTS
)

#: Стандартні й екзотичні мови (PHB, p. 123).
LANGUAGES = (
    "common",
    "dwarvish",
    "elvish",
    "giant",
    "gnomish",
    "goblin",
    "halfling",
    "orc",
    "abyssal",
    "celestial",
    "draconic",
    "deep speech",
    "infernal",
    "primordial",
    "sylvan",
    "undercommon",
)

#: Проста й воєнна зброя (PHB, p. 149) — Weapon Master обирає чотири.
WEAPONS = (
    "club",
    "dagger",
    "greatclub",
    "handaxe",
    "javelin",
    "light hammer",
    "mace",
    "quarterstaff",
    "sickle",
    "spear",
    "light crossbow",
    "dart",
    "shortbow",
    "sling",
    "battleaxe",
    "flail",
    "glaive",
    "greataxe",
    "greatsword",
    "halberd",
    "lance",
    "longsword",
    "maul",
    "morningstar",
    "pike",
    "rapier",
    "scimitar",
    "shortsword",
    "trident",
    "war pick",
    "warhammer",
    "whip",
    "blowgun",
    "hand crossbow",
    "heavy crossbow",
    "longbow",
    "net",
)

_SPELL_CLASS = DerivedChoice("Spell Class", 1, "fixed", options=FEAT_SPELL_CLASSES)

#: Риса (останній сегмент ключа) → вибори, які вона дає.
FEAT_CHOICES: Mapping[str, tuple[DerivedChoice, ...]] = {
    "skilled": (DerivedChoice("Skills or Tools", 3, "skill_or_tool"),),
    "skill-expert": (DerivedChoice("Skill", 1, "skill"), DerivedChoice("Expertise", 1, "expertise")),
    "prodigy": (
        DerivedChoice("Skill", 1, "skill"),
        DerivedChoice("Tool", 1, "tool"),
        DerivedChoice("Language", 1, "language"),
        DerivedChoice("Expertise", 1, "expertise"),
    ),
    "linguist": (DerivedChoice("Languages", 3, "language"),),
    "weapon-master": (DerivedChoice("Weapons", 4, "weapon"),),
    "magic-initiate": (
        _SPELL_CLASS,
        DerivedChoice("Cantrips", 2, "spell", spell_level=0),
        DerivedChoice("1st-level Spell", 1, "spell", spell_level=1),
    ),
    "ritual-caster": (
        _SPELL_CLASS,
        DerivedChoice("Rituals", 2, "spell", spell_level=1, ritual=True),
        # Знайдені пізніше ритуали класу — до половини рівня персонажа (PHB, p. 169).
        DerivedChoice("Copied Rituals", 40, "spell", ritual=True, open_ended=True, max_level_half="total"),
    ),
    "elemental-adept": (
        DerivedChoice("Damage Type", 1, "fixed", options=("acid", "cold", "fire", "lightning", "thunder")),
    ),
    "martial-adept": (DerivedChoice("Maneuvers", 2, "optional", feature_type="maneuver (battle master)"),),
    "eldritch-adept": (DerivedChoice("Eldritch Invocations", 1, "optional", feature_type="eldritch invocation"),),
    "metamagic-adept": (DerivedChoice("Metamagic", 2, "optional", feature_type="metamagic"),),
    "fighting-initiate": (DerivedChoice("Fighting Style", 1, "optional", feature_type="fighting style (fighter)"),),
    "fey-touched": (
        DerivedChoice(
            "1st-level Spell", 1, "spell", spell_level=1, schools=("divination", "enchantment"), spell_class="*"
        ),
    ),
    "shadow-touched": (
        DerivedChoice(
            "1st-level Spell", 1, "spell", spell_level=1, schools=("illusion", "necromancy"), spell_class="*"
        ),
    ),
    "artificer-initiate": (
        DerivedChoice("Cantrip", 1, "spell", spell_level=0, spell_class="artificer"),
        DerivedChoice("1st-level Spell", 1, "spell", spell_level=1, spell_class="artificer"),
        DerivedChoice("Tool", 1, "fixed", options=ARTISAN_TOOLS),
    ),
    "wood-elf-magic": (DerivedChoice("Cantrip", 1, "spell", spell_level=0, spell_class="druid"),),
}

#: Бойовий стиль → вибори (TCoE, p. 41): заговори жерця чи друїда, маневр.
STYLE_CHOICES: Mapping[str, tuple[DerivedChoice, ...]] = {
    "blessed warrior": (DerivedChoice("Cantrips", 2, "spell", spell_level=0, spell_class="cleric"),),
    "druidic warrior": (DerivedChoice("Cantrips", 2, "spell", spell_level=0, spell_class="druid"),),
    "superior technique": (DerivedChoice("Maneuvers", 1, "optional", feature_type="maneuver (battle master)"),),
}

#: Підклас (останній сегмент ключа) → (рівень класу, вибори). Ефект — той самий
#: механізм, що й у рис: володіння, експертиза, заговори, бойовий стиль.
#: Варіанти Мисливця, тотемів і драконячого предка (PHB, p. 50, 93, 102).
HUNTER_PREY = ("Colossus Slayer", "Giant Killer", "Horde Breaker")
TOTEMS = ("Bear", "Eagle", "Elk", "Tiger", "Wolf")
DRAGON_ANCESTORS = (
    "Black (acid)",
    "Blue (lightning)",
    "Brass (fire)",
    "Bronze (lightning)",
    "Copper (acid)",
    "Gold (fire)",
    "Green (poison)",
    "Red (fire)",
    "Silver (cold)",
    "White (cold)",
)


def _steps(
    group: str, kind: str, steps: tuple[tuple[int, int], ...], **extra: object
) -> tuple[tuple[int, DerivedChoice], ...]:
    """Вибір, кількість якого росте з рівнем: ((3, 2), (7, 3)) — 2 на 3 рівні, 3 на 7."""
    return tuple((level, DerivedChoice(group, count, kind, **extra)) for level, count in steps)  # type: ignore[arg-type]


#: Підклас (останній сегмент ключа) → ((рівень класу, вибір), …). Однакова група на
#: вищому рівні замінює нижчу (кількість росте). Ефект — той самий механізм, що й у
#: рис: володіння, експертиза, закляття, бойовий стиль; решта — вибір для листа,
#: текст уміння вже у «Вміннях».
SUBCLASS_CHOICES: Mapping[str, tuple[tuple[int, DerivedChoice], ...]] = {
    # Blessings of Knowledge: 2 мови й 2 навички з подвоєним бонусом (PHB, p. 59).
    "knowledge-domain": (
        (1, DerivedChoice("Languages", 2, "language")),
        (1, DerivedChoice("Skills", 2, "skill", options=("Arcana", "History", "Nature", "Religion"))),
    ),
    # Acolyte of Nature: заговір друїда й навичка (PHB, p. 62).
    "nature-domain": (
        (1, DerivedChoice("Cantrip", 1, "spell", spell_level=0, spell_class="druid")),
        (1, DerivedChoice("Skill", 1, "skill", options=("Animal Handling", "Nature", "Survival"))),
    ),
    # Bonus Proficiencies: три навички; Additional Magical Secrets — 2 закляття
    # будь-якого класу, що не рахуються у відомих (PHB, p. 54–55).
    "college-of-lore": (
        (3, DerivedChoice("Skills", 3, "skill")),
        (6, DerivedChoice("Additional Magical Secrets", 2, "spell", spell_class="*", max_level_of="bard")),
    ),
    # Fighting Style: Дуель або Бій двома зброями (XGtE, p. 15).
    "college-of-swords": (
        (3, DerivedChoice("Fighting Style", 1, "fixed", options=("Dueling", "Two-Weapon Fighting"))),
    ),
    # Bonus Proficiency: навичка зі списку або мова (XGtE, p. 31).
    "samurai": (
        (
            3,
            DerivedChoice(
                "Skill or Language",
                1,
                "skill_or_language",
                options=("History", "Insight", "Performance", "Persuasion"),
            ),
        ),
    ),
    # Мисливець: по одному вибору на 3, 7, 11 і 15 рівнях (PHB, p. 93).
    "hunter": (
        (3, DerivedChoice("Hunter's Prey", 1, "fixed", options=HUNTER_PREY)),
        (
            7,
            DerivedChoice(
                "Defensive Tactics", 1, "fixed", options=("Escape the Horde", "Multiattack Defense", "Steel Will")
            ),
        ),
        (11, DerivedChoice("Multiattack", 1, "fixed", options=("Volley", "Whirlwind Attack"))),
        (
            15,
            DerivedChoice(
                "Superior Hunter's Defense", 1, "fixed", options=("Evasion", "Stand Against the Tide", "Uncanny Dodge")
            ),
        ),
    ),
    # Тотемний воїн: дух на 3, аспект на 6, налаштування на 14 (PHB, p. 50; SCAG — лось і тигр).
    "path-of-the-totem-warrior": (
        (3, DerivedChoice("Totem Spirit", 1, "fixed", options=TOTEMS)),
        (6, DerivedChoice("Aspect of the Beast", 1, "fixed", options=TOTEMS)),
        (14, DerivedChoice("Totemic Attunement", 1, "fixed", options=TOTEMS)),
    ),
    # Драконячий предок: тип дракона задає тип урону (PHB, p. 102).
    "draconic-bloodline": ((1, DerivedChoice("Dragon Ancestor", 1, "fixed", options=DRAGON_ANCESTORS)),),
    # Аура бурі: пустеля, море чи тундра (XGtE, p. 10).
    "path-of-the-storm-herald": ((3, DerivedChoice("Storm Aura", 1, "fixed", options=("Desert", "Sea", "Tundra"))),),
    # Учень стихій: дисципліни на 3, 6, 11, 17 рівнях (PHB, p. 80).
    "way-of-the-four-elements": _steps(
        "Elemental Disciplines", "optional", ((3, 1), (6, 2), (11, 3), (17, 4)), feature_type="elemental discipline"
    ),
    # Арканний постріл: 2 на 3 рівні, далі +1 на 7, 10, 15, 18 (XGtE, p. 28).
    "arcane-archer": _steps(
        "Arcane Shot", "optional", ((3, 2), (7, 3), (10, 4), (15, 5), (18, 6)), feature_type="arcane shot"
    ),
    # Різьбяр рун: 2 руни на 3 рівні, далі +1 на 7, 10, 15 (TCoE, p. 44).
    "rune-knight": _steps("Runes", "optional", ((3, 2), (7, 3), (10, 4), (15, 5)), feature_type="rune"),
}

#: Магічні таємниці барда: 2 закляття будь-якого класу на 10, 14 і 18 рівнях; вони
#: входять у кількість відомих (PHB, p. 54) — тому ліміт зі списку барда менший.
MAGICAL_SECRETS: tuple[tuple[int, int], ...] = ((10, 2), (14, 4), (18, 6))


#: Бонус урону люті варвара за рівнем (PHB, p. 48).
RAGE_DAMAGE = ((16, 4), (9, 3), (1, 2))


def rage_damage(level: int) -> int:
    return next((bonus for threshold, bonus in RAGE_DAMAGE if level >= threshold), 0) if level else 0


def dragon_damage_type(ancestor: str) -> str | None:
    """«Red (fire)» → «fire»: тип урону драконячого предка (PHB, p. 102)."""
    if "(" not in ancestor:
        return None
    return ancestor.rsplit("(", 1)[1].rstrip(")").strip().casefold() or None


def magical_secrets_count(level: int) -> int:
    return max((count for threshold, count in MAGICAL_SECRETS if level >= threshold), default=0)


#: Вміння класу з вибором поза таблицею виборів: клас → ((рівень, вибір), …).
CLASS_FEATURE_CHOICES: Mapping[str, tuple[tuple[int, DerivedChoice], ...]] = {
    "bard": tuple(
        (level, DerivedChoice("Magical Secrets", count, "spell", spell_class="*", max_level_of="bard"))
        for level, count in MAGICAL_SECRETS
    ),
    # Містичний арканум: по закляттю 6–9 рівнів, раз на тривалий відпочинок (PHB, p. 108).
    "warlock": tuple(
        (
            level,
            DerivedChoice(
                f"Mystic Arcanum ({spell_level}th level)", 1, "spell", spell_level=spell_level, spell_class="warlock"
            ),
        )
        for level, spell_level in ((11, 6), (13, 7), (15, 8), (17, 9))
    ),
    # Майстерність заклять (18) і фірмові закляття (20) мага (PHB, p. 115).
    "wizard": (
        (18, DerivedChoice("Spell Mastery (1st level)", 1, "spell", spell_level=1, spell_class="wizard")),
        (18, DerivedChoice("Spell Mastery (2nd level)", 1, "spell", spell_level=2, spell_class="wizard")),
        (20, DerivedChoice("Signature Spells", 2, "spell", spell_level=3, spell_class="wizard")),
    ),
}

#: Як чаруються закляття вмінь класу (група → примітка).
CLASS_FEATURE_SPELL_USAGE: Mapping[str, str] = {
    "Mystic Arcanum": "1/long rest",
    "Spell Mastery": "at will",
    "Signature Spells": "1/short rest",
}

#: Рятівні кидки від умінь класу: (клас, рівень) → характеристики (PHB, p. 79, 96).
CLASS_FEATURE_SAVES: Mapping[tuple[str, int], tuple[str, ...]] = {
    ("monk", 14): ("str", "dex", "con", "int", "wis", "cha"),  # Diamond Soul
    ("rogue", 15): ("wis",),  # Slippery Mind
}

#: Скільки предметів може настроїти артифіцер (TCoE, p. 12–13); решта — 3.
ARTIFICER_ATTUNEMENT = ((18, 6), (14, 5), (10, 4))

#: Виклик → вибори: Книга давніх таємниць — 2 ритуали 1 рівня будь-якого класу (PHB, p. 110).
INVOCATION_CHOICES: Mapping[str, tuple[DerivedChoice, ...]] = {
    "book of ancient secrets": (
        DerivedChoice("Rituals", 2, "spell", spell_level=1, spell_class="*", ritual=True),
        # Переписані пізніше ритуали будь-якого класу — до половини рівня чаклуна (PHB, p. 110).
        DerivedChoice(
            "Copied Rituals", 40, "spell", spell_class="*", ritual=True, open_ended=True, max_level_half="warlock"
        ),
    ),
}

#: Підкласи, чиї обрані навички мають подвоєний бонус (Blessings of Knowledge).
SUBCLASS_EXPERTISE = frozenset({"knowledge-domain"})

#: Дар угоди → вибори: Угода фоліанта — три заговори будь-якого класу (PHB, p. 108).
BOON_CHOICES: Mapping[str, tuple[DerivedChoice, ...]] = {
    "pact of the tome": (DerivedChoice("Cantrips", 3, "spell", spell_level=0, spell_class="*"),),
}

#: Закляття, які риса дає без вибору: (назва, рівень, як чарується).
FEAT_SPELLS: Mapping[str, tuple[tuple[str, int, str], ...]] = {
    "fey-touched": (("Misty Step", 2, "1/long rest"),),
    "shadow-touched": (("Invisibility", 2, "1/long rest"),),
    "telekinetic": (("Mage Hand", 0, "invisible"),),
    "telepathic": (("Detect Thoughts", 2, "1/long rest"),),
    "drow-high-magic": (
        ("Detect Magic", 1, "at will"),
        ("Levitate", 2, "1/long rest"),
        ("Dispel Magic", 3, "1/long rest"),
    ),
    "wood-elf-magic": (("Longstrider", 1, "1/long rest"), ("Pass without Trace", 2, "1/long rest")),
    "fey-teleportation": (("Misty Step", 2, "1/short rest"),),
}

#: Як чаруються закляття 1+ рівня з вибору риси (Magic Initiate: 1/тривалий відпочинок).
FEAT_CHOICE_SPELL_NOTE: Mapping[str, str] = {
    "magic-initiate": "1/long rest",
    "fey-touched": "1/long rest",
    "shadow-touched": "1/long rest",
    "artificer-initiate": "1/long rest",
    "ritual-caster": "ritual only",
}

#: Володіння, які риса дає без вибору: (вид, значення).
FEAT_PROFICIENCIES: Mapping[str, tuple[tuple[str, str], ...]] = {
    "lightly-armored": (("armor", "light"),),
    "moderately-armored": (("armor", "medium"), ("armor", "shield")),
    "heavily-armored": (("armor", "heavy"),),
    "tavern-brawler": (("weapon", "improvised weapons"),),
    "chef": (("tool", "cook's utensils"),),
    "poisoner": (("tool", "poisoner's kit"),),
    "gunner": (("weapon", "firearms"),),
    "fey-teleportation": (("language", "sylvan"),),
}

#: Володіння від підкласу (останній сегмент ключа) без вибору: (вид, значення).
#: Хексблейд — Hex Warrior (XGtE, p. 55); домени — Bonus Proficiency (PHB, p. 60–63).
SUBCLASS_PROFICIENCIES: Mapping[str, tuple[tuple[str, str], ...]] = {
    "the-hexblade": (("armor", "medium"), ("armor", "shield"), ("weapon", "martial")),
    "life-domain": (("armor", "heavy"),),
    "nature-domain": (("armor", "heavy"),),
    "tempest-domain": (("armor", "heavy"), ("weapon", "martial")),
    "war-domain": (("armor", "heavy"), ("weapon", "martial")),
    "death-domain": (("weapon", "martial"),),
    "forge-domain": (("armor", "heavy"), ("tool", "smith's tools")),
    "order-domain": (("armor", "heavy"),),
    "twilight-domain": (("armor", "heavy"), ("weapon", "martial")),
    "college-of-valor": (("armor", "medium"), ("armor", "shield"), ("weapon", "martial")),
    "college-of-swords": (("armor", "medium"), ("weapon", "scimitar")),
    "battle-smith": (("weapon", "martial"), ("tool", "smith's tools")),
    "armorer": (("armor", "heavy"), ("tool", "smith's tools")),
    "bladesinging": (("armor", "light"), ("skill", "performance")),
    "assassin": (("tool", "disguise kit"), ("tool", "poisoner's kit")),
    # Драконячий родовід: читаєте й говорите драконячою (PHB, p. 102).
    "draconic-bloodline": (("language", "draconic"),),
}

#: Види, що дають рису на 1 рівні (PHB, p. 31; TCoE, p. 8).
SPECIES_WITH_FEAT = frozenset({"variant human", "custom lineage"})


# ---------------------------------------------------------------------------
# містичні виклики (PHB, p. 110; XGtE, p. 56; TCoE, p. 70)
# ---------------------------------------------------------------------------

#: Виклик → закляття, яке він дає: (назва, рівень, як чарується).
INVOCATION_SPELLS: Mapping[str, tuple[str, int, str]] = {
    "armor of shadows": ("Mage Armor", 1, "at will"),
    "ascendant step": ("Levitate", 2, "at will"),
    "beast speech": ("Speak with Animals", 1, "at will"),
    "bewitching whispers": ("Compulsion", 4, "1/long rest"),
    "chains of carceri": ("Hold Monster", 5, "at will"),
    "dreadful word": ("Confusion", 4, "1/long rest"),
    "eldritch sight": ("Detect Magic", 1, "at will"),
    "fiendish vigor": ("False Life", 1, "at will"),
    "mask of many faces": ("Disguise Self", 1, "at will"),
    "master of myriad forms": ("Alter Self", 2, "at will"),
    "minions of chaos": ("Conjure Elemental", 5, "1/long rest"),
    "mire the mind": ("Slow", 3, "1/long rest"),
    "misty visions": ("Silent Image", 1, "at will"),
    "otherworldly leap": ("Jump", 1, "at will"),
    "sculptor of flesh": ("Polymorph", 4, "1/long rest"),
    "sign of ill omen": ("Bestow Curse", 3, "1/long rest"),
    "thief of five fates": ("Bane", 1, "1/long rest"),
    "visions of distant realms": ("Arcane Eye", 4, "at will"),
    "whispers of the grave": ("Speak with Dead", 3, "at will"),
    "shroud of shadow": ("Invisibility", 2, "at will"),
    "trickster's escape": ("Freedom of Movement", 4, "1/long rest"),
    "gift of the depths": ("Water Breathing", 3, "1/long rest"),
    "far scribe": ("Sending", 3, "no slot"),
    "undying servitude": ("Animate Dead", 3, "1/long rest"),
}

#: Виклики, що змінюють Містичний розряд (Eldritch Blast): назва → примітка.
ELDRITCH_BLAST_INVOCATIONS: Mapping[str, str] = {
    "agonizing blast": "agonizing",
    "eldritch spear": "range 300 feet",
    "repelling blast": "push 10 feet",
    "grasp of hadar": "pull 10 feet (1/turn)",
    "lance of lethargy": "speed −10 feet (1/turn)",
}


# ---------------------------------------------------------------------------
# природна зброя видів і удар без зброї (PHB, p. 195; VGtM; MPMM; MOoT; VRGR)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NaturalWeapon:
    """Природна зброя виду: нею б'ють як ударом без зброї, але з кубиком."""

    name_en: str
    die: str
    damage_type: str
    #: Кубик у Monsters of the Multiverse, якщо вид звідти.
    die_mpmm: str | None = None
    ability: Ability = Ability.STR
    note: str = ""


#: Ключ виду або підвиду → природна зброя.
NATURAL_WEAPONS: Mapping[str, NaturalWeapon] = {
    "tabaxi": NaturalWeapon("Cat's Claws", "1d4", "slashing", die_mpmm="1d6"),
    "aarakocra": NaturalWeapon("Talons", "1d4", "slashing", die_mpmm="1d6"),
    "lizardfolk": NaturalWeapon("Bite", "1d6", "piercing"),
    "minotaur": NaturalWeapon("Horns", "1d6", "piercing"),
    "leonin": NaturalWeapon("Claws", "1d4", "slashing"),
    "tortle": NaturalWeapon("Claws", "1d4", "slashing", die_mpmm="1d6"),
    "centaur": NaturalWeapon("Hooves", "1d4", "bludgeoning", die_mpmm="1d6"),
    "satyr": NaturalWeapon("Ram", "1d4", "bludgeoning", die_mpmm="1d6"),
    "dhampir": NaturalWeapon("Vampiric Bite", "1d4", "piercing", ability=Ability.CON),
    "longtooth shifter": NaturalWeapon("Fangs", "1d6", "piercing", note="shifted only"),
}


def natural_weapon_for(species_key: str | None, subspecies_key: str | None) -> NaturalWeapon | None:
    """Природна зброя виду чи підвиду (підвид важливіший: ікласті шифтери)."""
    for key in (subspecies_key, species_key):
        slug = (key or "").strip().casefold().rsplit("/", 1)[-1]
        if slug in NATURAL_WEAPONS:
            return NATURAL_WEAPONS[slug]
    return None


def natural_weapon_die(weapon: NaturalWeapon, source: str | None) -> str:
    """Кістка природної зброї за книгою виду: у MPMM вона більша (табаксі 1d6)."""
    return weapon.die_mpmm if weapon.die_mpmm and (source or "").upper() == "MPMM" else weapon.die


#: Кістка бойових мистецтв ченця за рівнем (PHB, p. 76).
MARTIAL_ARTS_DIE = ((17, "1d10"), (11, "1d8"), (5, "1d6"), (1, "1d4"))


def martial_arts_die(monk_level: int) -> str | None:
    """Кістка бойових мистецтв або `None`, якщо ченця немає."""
    if monk_level <= 0:
        return None
    return next(die for level, die in MARTIAL_ARTS_DIE if monk_level >= level)


def die_size(dice: str) -> int:
    """Подвоєне середнє кидка, щоб порівнювати «1d6» і «2d4»; «1» → 2."""
    match = re.fullmatch(r"(\d+)d(\d+)", dice.strip())
    if match is None:
        return int(dice) * 2 if dice.strip().isdigit() else 0
    return int(match.group(1)) * (int(match.group(2)) + 1)


def is_monk_weapon(name_en: str, properties: str, group: str) -> bool:
    """Зброя ченця (PHB, p. 76): короткий меч і проста ближня без two-handed/heavy."""
    folded = properties.casefold()
    name = name_en.strip().casefold()
    if "shortsword" in name:
        return True
    if "two-handed" in folded or "heavy" in folded:
        return False
    if group:
        return group.casefold().startswith("simple melee")
    # Без групи (власний предмет, запис іншої книги) — за назвою.
    return "greatclub" not in name and any(base in name for base in _SIMPLE_MELEE_ONE_HANDED)


#: Проста зброя ближнього бою без two-handed і heavy (PHB, p. 149).
_SIMPLE_MELEE_ONE_HANDED = (
    "club",
    "dagger",
    "handaxe",
    "javelin",
    "light hammer",
    "mace",
    "quarterstaff",
    "sickle",
    "spear",
)
