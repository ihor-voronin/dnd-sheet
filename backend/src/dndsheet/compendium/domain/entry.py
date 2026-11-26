"""Запис довідника — read-only сутність контексту `compendium`.

Довідник не редагується під час роботи: записи приходять з корпусу
(`content/compendium/<book>/<category>.jsonl`) і перевіряються контрактом
`contract/compendium-entry.schema.json`. Тому тут немає сетерів і немає
історії змін — тільки розбір, валідація й зручні похідні властивості.

Ключів у записі рівно 16 (`contract/compendium-format.json`), але домен не
зобовʼязаний знати їх усі: невідомі поля лишаються в `data`, а не губляться.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from dndsheet.shared.errors import ValidationError

SCHEMA = "compendium-entry/1"

REQUIRED_KEYS: tuple[str, ...] = (
    "id",
    "schema",
    "source_id",
    "category",
    "name_en",
    "edition",
    "license",
    "text_en",
    "status",
)

_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)


class Category(StrEnum):
    """Категорії довідника. Значення збігаються з назвами файлів корпусу."""

    CLASS = "class"
    SUBCLASS = "subclass"
    SPECIES = "species"
    BACKGROUND = "background"
    FEAT = "feat"
    OPTIONAL_FEATURE = "optionalfeature"
    SPELL = "spell"
    ITEM = "item"
    MONSTER = "monster"
    RULE = "rule"

    @classmethod
    def parse(cls, value: str) -> "Category":
        try:
            return cls(value)
        except ValueError as exc:
            known = ", ".join(category.value for category in cls)
            raise ValidationError(
                f"невідома категорія {value!r}; відомі: {known}"
            ) from exc


#: Порядок показу категорій: від «з чого збирається персонаж» до «довідкового».
CATEGORY_ORDER: tuple[Category, ...] = (
    Category.CLASS,
    Category.SUBCLASS,
    Category.SPECIES,
    Category.BACKGROUND,
    Category.FEAT,
    Category.OPTIONAL_FEATURE,
    Category.SPELL,
    Category.ITEM,
    Category.RULE,
    Category.MONSTER,
)


def search_key(text: str) -> str:
    """Ключ пошуку: регістр, пунктуація й подвійні пробіли не мають значення.

    Дужки та тире в назвах («Crossbow, Light», «Thieves’ Tools») заважають
    пошуку більше, ніж допомагають, тому зіставляємо саме «слова».
    """
    return " ".join(_PUNCTUATION_RE.sub(" ", text.casefold()).split())


@dataclass(frozen=True, slots=True)
class CompendiumEntry:
    """Один запис довідника. Незмінний після створення."""

    id: str
    source_id: str
    category: Category
    name_en: str
    edition: str
    license: str
    text_en: str
    status: str
    schema: str = SCHEMA
    name_uk: str | None = None
    url: str | None = None
    page: int | None = None
    text_uk: str | None = None
    data: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    fetched_at: str | None = None
    notes: tuple[str, ...] = ()

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "CompendiumEntry":
        """Розібрати рядок корпусу. Битий запис — помилка, а не «пропустимо»."""
        for key in REQUIRED_KEYS:
            if key not in record:
                where = record.get("id") or record.get("source_id") or "?"
                raise ValidationError(f"запис {where}: немає обовʼязкового поля {key}")

        entry_id = str(record["id"])
        category = Category.parse(str(record["category"]))
        if entry_id.split("/")[1:2] != [category.value]:
            raise ValidationError(
                f"запис {entry_id}: id не збігається з категорією {category.value}"
            )
        if record["schema"] != SCHEMA:
            raise ValidationError(
                f"запис {entry_id}: схема {record['schema']!r}, очікується {SCHEMA!r}"
            )

        data = record.get("data") or {}
        if not isinstance(data, Mapping):
            raise ValidationError(f"запис {entry_id}: data має бути обʼєктом")

        page = record.get("page")
        if isinstance(page, bool) or not isinstance(page, (int, type(None))):
            raise ValidationError(f"запис {entry_id}: page має бути числом або null")

        notes = record.get("notes") or ()
        if not isinstance(notes, (list, tuple)):
            raise ValidationError(f"запис {entry_id}: notes має бути списком")

        return cls(
            id=entry_id,
            source_id=str(record["source_id"]),
            category=category,
            name_en=str(record["name_en"]),
            edition=str(record["edition"]),
            license=str(record["license"]),
            text_en=str(record["text_en"]),
            status=str(record["status"]),
            schema=str(record["schema"]),
            name_uk=_optional_str(record.get("name_uk")),
            url=_optional_str(record.get("url")),
            page=page,
            text_uk=_optional_str(record.get("text_uk")),
            data=MappingProxyType(dict(data)),
            fetched_at=_optional_str(record.get("fetched_at")),
            notes=tuple(str(note) for note in notes),
        )

    # --- похідні властивості -------------------------------------------------

    @property
    def display_name(self) -> str:
        """Що показуємо: українська назва, а якщо її ще немає — англійська."""
        return self.name_uk or self.name_en

    @property
    def is_translated(self) -> bool:
        return bool(self.name_uk and self.text_uk)

    @property
    def search_text(self) -> str:
        """Текст, за яким шукаємо назву: обидві мови, без пунктуації."""
        names = " ".join(part for part in (self.name_en, self.name_uk) if part)
        return search_key(names)

    @property
    def spell_level(self) -> int | None:
        if self.category is not Category.SPELL:
            return None
        level = self.data.get("level")
        if isinstance(level, bool) or not isinstance(level, int):
            return None
        return level

    @property
    def spell_school(self) -> str | None:
        if self.category is not Category.SPELL:
            return None
        return _lower_str(self.data.get("school"))

    @property
    def subclass_of(self) -> str | None:
        """Клас, до якого належить підклас (`data.class`, напр. `rogue`)."""
        if self.category is not Category.SUBCLASS:
            return None
        return _lower_str(self.data.get("class"))

    @property
    def subclass_level(self) -> int | None:
        level = self.data.get("level")
        if self.category is not Category.SUBCLASS:
            return None
        if isinstance(level, bool) or not isinstance(level, int):
            return None
        return level

    @property
    def feature_types(self) -> tuple[str, ...]:
        """Групи опційного вміння: invocation, maneuver, fighting style…"""
        if self.category is not Category.OPTIONAL_FEATURE:
            return ()
        raw = self.data.get("feature_type") or ()
        if isinstance(raw, str):
            raw = (raw,)
        return tuple(str(item).casefold() for item in raw if item)

    @property
    def prerequisite(self) -> str | None:
        return _optional_str(self.data.get("prerequisite"))

    @property
    def item_type(self) -> str | None:
        if self.category is not Category.ITEM:
            return None
        return _lower_str(self.data.get("item_type"))

    @property
    def item_group(self) -> str | None:
        return _optional_str(self.data.get("group"))

    @property
    def rarity(self) -> str | None:
        return _lower_str(self.data.get("rarity"))

    @property
    def is_magical(self) -> bool:
        return bool(self.data.get("magical"))

    @property
    def spell_classes(self) -> tuple[str, ...]:
        """Класи, у яких закляття є за `data.classes` (заповнено не в усіх книгах)."""
        if self.category is not Category.SPELL:
            return ()
        raw = self.data.get("classes") or ()
        if isinstance(raw, str):
            raw = (raw,)
        return tuple(str(item).casefold() for item in raw if item)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _lower_str(value: Any) -> str | None:
    text = _optional_str(value)
    return text.casefold() if text else None
