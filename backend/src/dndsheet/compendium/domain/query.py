"""Запит до довідника й сторінка результатів.

Фільтр — це значення, а не код: `EntryQuery` можна зберегти, порівняти,
передати в порт і показати в API. Саме тому тут немає жодних замикань.
"""

from __future__ import annotations

from dataclasses import dataclass

from dndsheet.compendium.domain.entry import Category, CompendiumEntry, search_key
from dndsheet.shared.errors import ValidationError

MAX_LIMIT = 200
DEFAULT_LIMIT = 50


@dataclass(frozen=True, slots=True)
class EntryQuery:
    """Умови відбору записів. Порожній запит — «усе, починаючи з нуля»."""

    category: Category | None = None
    source_id: str | None = None
    q: str | None = None
    level: int | None = None
    school: str | None = None
    feature_type: str | None = None
    item_type: str | None = None
    rarity: str | None = None
    magical: bool | None = None
    subclass_of: str | None = None
    edition: str | None = None
    status: str | None = None
    limit: int = DEFAULT_LIMIT
    offset: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.limit, bool) or not isinstance(self.limit, int):
            raise ValidationError("limit має бути цілим числом")
        if not 1 <= self.limit <= MAX_LIMIT:
            raise ValidationError(f"limit має бути в межах 1..{MAX_LIMIT}")
        if isinstance(self.offset, bool) or not isinstance(self.offset, int):
            raise ValidationError("offset має бути цілим числом")
        if self.offset < 0:
            raise ValidationError("offset не може бути відʼємним")
        if self.level is not None:
            if isinstance(self.level, bool) or not isinstance(self.level, int):
                raise ValidationError("level має бути цілим числом")
            if not 0 <= self.level <= 9:
                raise ValidationError("level закляття має бути в межах 0..9")

    def matches(self, entry: CompendiumEntry) -> bool:
        """Чи проходить запис умови. Кожен фільтр незалежний."""
        if self.category is not None and entry.category is not self.category:
            return False
        if self.source_id is not None and entry.source_id != self.source_id:
            return False
        if self.q and search_key(self.q) not in entry.search_text:
            return False
        if self.level is not None and entry.spell_level != self.level:
            return False
        if self.school is not None and entry.spell_school != self.school.casefold():
            return False
        if self.feature_type is not None and self.feature_type.casefold() not in entry.feature_types:
            return False
        if self.item_type is not None and entry.item_type != self.item_type.casefold():
            return False
        if self.rarity is not None and entry.rarity != self.rarity.casefold():
            return False
        if self.magical is not None and entry.is_magical != self.magical:
            return False
        if self.subclass_of is not None and entry.subclass_of != self.subclass_of.casefold():
            return False
        if self.edition is not None and entry.edition != self.edition:
            return False
        return not (self.status is not None and entry.status != self.status)

    def narrower_for(self, category: Category) -> "EntryQuery":
        """Той самий запит, але з фіксованою категорією (для індексів)."""
        if self.category is category:
            return self
        return EntryQuery(
            category=category,
            source_id=self.source_id,
            q=self.q,
            level=self.level,
            school=self.school,
            feature_type=self.feature_type,
            item_type=self.item_type,
            rarity=self.rarity,
            magical=self.magical,
            subclass_of=self.subclass_of,
            edition=self.edition,
            status=self.status,
            limit=self.limit,
            offset=self.offset,
        )


@dataclass(frozen=True, slots=True)
class Page:
    """Сторінка результатів. `total` — скільки всього підходить під фільтр."""

    items: tuple[CompendiumEntry, ...]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total
