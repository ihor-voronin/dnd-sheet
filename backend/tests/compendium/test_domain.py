"""Домен довідника: розбір запису, похідні властивості, умови запиту."""

from __future__ import annotations

import pytest

from dndsheet.compendium.domain.entry import (
    Category,
    CompendiumEntry,
    search_key,
)
from dndsheet.compendium.domain.query import EntryQuery, Page
from dndsheet.shared.errors import ValidationError

from corpus import record


def make(category: str, slug: str, name: str, **kwargs) -> CompendiumEntry:
    return CompendiumEntry.from_record(record("demo", category, slug, name, **kwargs))


@pytest.mark.parametrize("value", ["class", "spell", "optionalfeature", "monster"])
def test_category_parses_corpus_values(value: str) -> None:
    assert Category.parse(value).value == value


def test_unknown_category_is_an_error() -> None:
    with pytest.raises(ValidationError, match="невідома категорія"):
        Category.parse("magic-item")


def test_missing_required_field_is_an_error() -> None:
    broken = record("demo", "spell", "x", "X")
    del broken["text_en"]
    with pytest.raises(ValidationError, match="немає обовʼязкового поля text_en"):
        CompendiumEntry.from_record(broken)


def test_id_must_match_category() -> None:
    broken = record("demo", "spell", "x", "X")
    broken["id"] = "demo/item/x"
    with pytest.raises(ValidationError, match="id не збігається з категорією"):
        CompendiumEntry.from_record(broken)


def test_schema_must_be_known() -> None:
    broken = record("demo", "spell", "x", "X")
    broken["schema"] = "compendium-entry/0"
    with pytest.raises(ValidationError, match="схема"):
        CompendiumEntry.from_record(broken)


def test_data_is_read_only() -> None:
    entry = make("spell", "fireball", "Fireball", data={"level": 3})
    with pytest.raises(TypeError):
        entry.data["level"] = 1  # type: ignore[index]


def test_spell_properties() -> None:
    entry = make(
        "spell",
        "fireball",
        "Fireball",
        data={"level": 3, "school": "Evocation", "classes": ["Wizard", "Sorcerer"]},
    )
    assert entry.spell_level == 3
    assert entry.spell_school == "evocation"
    assert entry.spell_classes == ("wizard", "sorcerer")


def test_subclass_properties() -> None:
    entry = make("subclass", "champion", "Champion", data={"class": "Fighter", "level": 3})
    assert entry.subclass_of == "fighter"
    assert entry.subclass_level == 3


def test_optional_feature_groups_are_normalised() -> None:
    entry = make(
        "optionalfeature",
        "riposte",
        "Riposte",
        data={"feature_type": ["Maneuver (Battle Master)"]},
    )
    assert entry.feature_types == ("maneuver (battle master)",)


def test_item_properties() -> None:
    entry = make(
        "item",
        "bag",
        "Bag of Holding",
        data={"item_type": "Wondrous Item", "rarity": "Uncommon", "magical": True},
    )
    assert entry.item_type == "wondrous item"
    assert entry.rarity == "uncommon"
    assert entry.is_magical


def test_display_name_falls_back_to_english() -> None:
    entry = make("species", "elf", "Elf")
    assert entry.display_name == "Elf"
    assert not entry.is_translated

    translated = make(
        "species",
        "elf",
        "Elf",
        name_uk="Ельф",
        text_uk="Текст українською.",
    )
    assert translated.display_name == "Ельф"
    assert translated.is_translated


def test_search_key_ignores_case_and_punctuation() -> None:
    assert search_key("Thieves’ Tools") == "thieves tools"
    assert search_key("Crossbow, Light") == "crossbow light"
    assert search_key("  Bag   of  Holding ") == "bag of holding"


def test_search_text_covers_both_languages() -> None:
    entry = make("species", "elf", "Elf", name_uk="Ельф")
    assert "elf" in entry.search_text
    assert "ельф" in entry.search_text


# --- запит ---------------------------------------------------------------


def test_query_rejects_bad_window() -> None:
    with pytest.raises(ValidationError, match="limit"):
        EntryQuery(limit=0)
    with pytest.raises(ValidationError, match="offset"):
        EntryQuery(offset=-1)


def test_query_rejects_unknown_spell_level() -> None:
    with pytest.raises(ValidationError, match="level"):
        EntryQuery(level=10)


def test_query_matches_filters_independently() -> None:
    spell = make("spell", "fireball", "Fireball", data={"level": 3, "school": "evocation"})
    assert EntryQuery(category=Category.SPELL).matches(spell)
    assert EntryQuery(level=3).matches(spell)
    assert not EntryQuery(level=2).matches(spell)
    assert EntryQuery(q="fireb").matches(spell)
    assert not EntryQuery(q="ice").matches(spell)
    assert EntryQuery(school="EVOCATION").matches(spell)
    assert not EntryQuery(source_id="other").matches(spell)


def test_query_can_be_narrowed_for_index_lookup() -> None:
    query = EntryQuery(source_id="demo", q="dragon", limit=10)
    narrowed = query.narrower_for(Category.ITEM)
    assert narrowed.category is Category.ITEM
    assert narrowed.source_id == "demo"
    assert narrowed.q == "dragon"
    assert query.narrower_for(query.category) is query


def test_page_knows_whether_more_is_left() -> None:
    entry = make("rule", "adventuring", "Adventuring")
    page = Page(items=(entry,), total=3, limit=1, offset=0)
    assert page.has_more
    assert not Page(items=(entry,), total=1, limit=1, offset=0).has_more
