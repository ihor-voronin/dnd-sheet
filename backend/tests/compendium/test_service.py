"""Сценарії довідника: зведення, класи, класові закляття, пошук."""

from __future__ import annotations

from pathlib import Path

import pytest

from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.domain.entry import Category
from dndsheet.compendium.domain.query import EntryQuery
from dndsheet.compendium.infrastructure.jsonl_corpus import JsonlCompendiumRepository
from dndsheet.compendium.infrastructure.spell_lists import JsonSpellListRepository
from dndsheet.shared.errors import NotFoundError


def test_summary_counts_books_and_titles(service: CompendiumService) -> None:
    summary = service.summary()
    assert summary.entries == 17
    assert dict(summary.categories)[Category.SPELL] == 5
    assert [(book.source_id, book.title, book.entries) for book in summary.books] == [
        ("demo", "Demo Book", 16),
        ("other", "Other Book", 1),
    ]
    assert summary.spell_lists
    assert summary.warnings == ()


def test_summary_without_corpus_says_so(content_dir: Path) -> None:
    service = CompendiumService(
        JsonlCompendiumRepository(directory=content_dir / "nope"),
        JsonSpellListRepository(path=content_dir / "index" / "spell-lists.json"),
    )
    summary = service.summary()
    assert summary.entries == 0
    assert any("корпус не знайдено" in warning for warning in summary.warnings)


def test_classes_report_how_many_subclasses(service: CompendiumService) -> None:
    classes = {summary.entry.name_en: summary.subclasses for summary in service.classes()}
    assert classes == {"Fighter": 2, "Wizard": 0}


def test_subclasses_accept_case_insensitive_class_name(
    service: CompendiumService,
) -> None:
    assert len(service.subclasses("fighter")) == 2
    assert len(service.subclasses("Fighter")) == 2
    assert service.subclasses("rogue") == ()


def test_class_spells_come_from_book_lists(service: CompendiumService) -> None:
    result = service.class_spells("Wizard")
    assert result.source == "spell-lists"
    assert [entry.name_en for entry in result.spells] == [
        "Chill Touch",
        "Burning Hands",
        "Magic Missile",
        "Fireball",
    ]


def test_class_spells_respect_max_level(service: CompendiumService) -> None:
    result = service.class_spells("Wizard", max_level=1)
    assert [entry.name_en for entry in result.spells] == [
        "Chill Touch",
        "Burning Hands",
        "Magic Missile",
    ]


def test_class_spells_skip_names_missing_from_corpus(service: CompendiumService) -> None:
    """«Неіснуюче закляття» є в списку книги, але запису в корпусі немає."""
    result = service.class_spells("Wizard")
    assert all("Неіснуюче" not in entry.name_en for entry in result.spells)


def test_class_spells_prefer_srd_record_for_duplicate_name(
    service: CompendiumService,
) -> None:
    magic_missile = next(
        entry for entry in service.class_spells("Wizard").spells if entry.name_en == "Magic Missile"
    )
    assert magic_missile.id == "demo/spell/magic-missile"
    assert magic_missile.license == "srd"


def test_class_spells_fall_back_to_entry_data(content_dir: Path) -> None:
    service = CompendiumService(
        JsonlCompendiumRepository(directory=content_dir / "compendium"),
        JsonSpellListRepository(path=content_dir / "index" / "missing.json"),
    )
    result = service.class_spells("Wizard")
    assert result.source == "entry-data"
    assert [entry.name_en for entry in result.spells] == ["Burning Hands"]


def test_class_spells_without_any_source_is_honest(
    service: CompendiumService,
) -> None:
    result = service.class_spells("Rogue")
    assert result.source == "none"
    assert result.spells == ()


def test_optional_features_can_be_filtered_by_group(
    service: CompendiumService,
) -> None:
    assert len(service.optional_features()) == 2
    only_maneuvers = service.optional_features("MANEUVER (BATTLE MASTER)")
    assert [entry.name_en for entry in only_maneuvers] == ["Riposte"]


def test_spells_for_class_uses_class_list(service: CompendiumService) -> None:
    page = service.spells(class_name="Wizard")
    assert page.total == 4
    assert page.items[0].name_en == "Chill Touch"


def test_spells_for_unknown_class_is_empty_not_error(
    service: CompendiumService,
) -> None:
    assert service.spells(class_name="Rogue").total == 0


def test_spells_filter_by_level_covers_all_books(
    service: CompendiumService,
) -> None:
    page = service.spells(level=1)
    assert page.total == 3
    assert {entry.source_id for entry in page.items} == {"demo", "other"}


def test_entry_lookup_raises_for_unknown_id(service: CompendiumService) -> None:
    with pytest.raises(NotFoundError):
        service.entry("demo/class/nope")


def test_entries_are_queryable_through_service(service: CompendiumService) -> None:
    page = service.entries(EntryQuery(category=Category.ITEM, limit=10))
    assert page.total == 2
