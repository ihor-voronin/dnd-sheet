"""Закляття персонажа й комірки Pact Magic.

Закляття належить **класу**, а не персонажу: у мультикласі «Пекельний
договір» іде окремо від комірок волшебника, і ліміт відомих заклять у кожного
класу свій. Тому `KnownSpell.class_key` обовʼязковий.

Виняток — власне закляття поза класом (`OTHER_CLASS`): дар майстра, сила
предмета, домашнє правило. Воно не належить жодному класу й не займає місця в
лімітах — правила про нього нічого не кажуть.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from dndsheet.shared.errors import ValidationError
from dndsheet.shared.rules import MAX_SPELL_LEVEL

#: «Клас» власного закляття, яке не належить жодному класу персонажа.
OTHER_CLASS = "other"

#: Межі тексту власного закляття: лист — не книга, а запис не має рости без меж.
MAX_NAME = 120
MAX_TEXT = 4000
MAX_META = 120

#: Короткі дані власного закляття, які гравець може вписати сам.
CUSTOM_META = ("school", "casting_time", "range", "duration", "components")


@dataclass(frozen=True, slots=True)
class KnownSpell:
    """Відоме (або підготовлене) закляття персонажа."""

    name_en: str
    level: int
    class_key: str
    entry_id: str | None = None
    prepared: bool = False
    always_prepared: bool = False
    #: Власне (домашнє) закляття: у довіднику його немає, назву й текст дав
    #: гравець. Лист і експорт кажуть «власне», щоб його не плутали з
    #: книжковим — жодних чисел правила з нього не виводяться.
    custom: bool = False
    #: Текст власного закляття (для книжкових він приходить із довідника).
    description: str | None = None
    #: Короткі дані власного закляття (книжковим їх дописує довідник):
    #: школа, час, дистанція, тривалість, компоненти — вільним текстом.
    school: str | None = None
    casting_time: str | None = None
    range: str | None = None
    duration: str | None = None
    components: str | None = None
    concentration: bool = False
    ritual: bool = False

    def __post_init__(self) -> None:
        name = self.name_en.strip()
        if not name:
            raise ValidationError("закляття без назви")
        if len(name) > MAX_NAME:
            raise ValidationError(f"назва закляття довша за {MAX_NAME} символів")
        object.__setattr__(self, "name_en", name)
        if not self.class_key.strip():
            raise ValidationError(f"{self.name_en}: закляття без класу")
        object.__setattr__(self, "class_key", self.class_key.strip().casefold())
        if isinstance(self.level, bool) or not isinstance(self.level, int):
            raise ValidationError(f"{self.name_en}: рівень закляття має бути числом")
        if not 0 <= self.level <= MAX_SPELL_LEVEL:
            raise ValidationError(f"{self.name_en}: рівень закляття має бути 0..{MAX_SPELL_LEVEL}")
        if self.custom and self.entry_id:
            raise ValidationError(f"{self.name_en}: власне закляття не має запису в довіднику")
        if self.class_key == OTHER_CLASS and not self.custom:
            raise ValidationError(f"{self.name_en}: поза класом буває лише власне закляття")
        text = (self.description or "").strip()
        object.__setattr__(self, "description", text or None)
        if text and not self.custom:
            raise ValidationError(f"{self.name_en}: власний текст буває лише у власного закляття")
        if len(text) > MAX_TEXT:
            raise ValidationError(f"{self.name_en}: текст закляття довший за {MAX_TEXT} символів")
        for key in CUSTOM_META:
            value = (getattr(self, key) or "").strip()
            if value and not self.custom:
                raise ValidationError(f"{self.name_en}: власні дані бувають лише у власного закляття")
            if len(value) > MAX_META:
                raise ValidationError(f"{self.name_en}: поле {key} довше за {MAX_META} символів")
            object.__setattr__(self, key, value or None)
        if (self.concentration or self.ritual) and not self.custom:
            raise ValidationError(f"{self.name_en}: концентрацію й ритуал книжковому дає довідник")

    @property
    def outside_class(self) -> bool:
        """Власне закляття поза класом: без КС класу й без місця в лімітах."""
        return self.class_key == OTHER_CLASS

    @property
    def is_cantrip(self) -> bool:
        return self.level == 0

    def prepare(self, prepared: bool = True) -> "KnownSpell":
        return replace(self, prepared=prepared)


@dataclass(frozen=True, slots=True)
class PactMagic:
    """Комірки Pact Magic: усі одного рівня, відновлюються на короткому відпочинку."""

    slots: int
    slot_level: int

    def __post_init__(self) -> None:
        if self.slots < 0 or not 0 <= self.slot_level <= MAX_SPELL_LEVEL:
            raise ValidationError("неприпустимі комірки Pact Magic")

    @property
    def empty(self) -> bool:
        return self.slots == 0


@dataclass(frozen=True, slots=True)
class SpellSlots:
    """Комірки заклять: звичайні за рівнями й (окремо) Pact Magic."""

    by_level: tuple[tuple[int, int], ...] = ()
    pact: PactMagic | None = None

    @classmethod
    def from_table(cls, table: tuple[int, ...], pact: PactMagic | None = None) -> "SpellSlots":
        return cls(
            by_level=tuple((level, count) for level, count in enumerate(table, start=1) if count),
            pact=pact,
        )

    def count(self, spell_level: int) -> int:
        return dict(self.by_level).get(spell_level, 0)

    @property
    def total(self) -> int:
        return sum(count for _, count in self.by_level) + (self.pact.slots if self.pact else 0)

    @property
    def highest_level(self) -> int:
        levels = [level for level, _ in self.by_level if level]
        if self.pact and self.pact.slots:
            levels.append(self.pact.slot_level)
        return max(levels, default=0)
