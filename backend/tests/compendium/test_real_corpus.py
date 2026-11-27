"""Довідник на справжньому корпусі.

Ці тести стрибають, якщо корпусу немає (свіжий клон репозиторію його не
містить — тексти книг під копирайтом). Коли корпус є, вони перевіряють, що
домен читає його саме так, як обіцяє контракт: кількості, категорії,
класові списки.
"""

from __future__ import annotations

import pytest
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.domain.entry import Category
from dndsheet.compendium.domain.query import EntryQuery
from dndsheet.compendium.infrastructure.factory import build_service
from dndsheet.compendium.infrastructure.jsonl_corpus import default_content_dir

CONTENT = default_content_dir()

pytestmark = pytest.mark.skipif(not (CONTENT / "compendium").is_dir(), reason="корпусу content/compendium немає")


@pytest.fixture(scope="module")
def service() -> CompendiumService:
    return build_service()


def test_corpus_has_all_sheet_categories(service: CompendiumService) -> None:
    summary = service.summary()
    categories = {category for category, _ in summary.categories}
    expected = {
        Category.CLASS,
        Category.SUBCLASS,
        Category.SPECIES,
        Category.BACKGROUND,
        Category.FEAT,
        Category.OPTIONAL_FEATURE,
        Category.SPELL,
        Category.ITEM,
        Category.RULE,
    }
    assert categories == expected
    assert Category.MONSTER not in categories
    assert summary.entries > 3000


def test_books_have_titles_from_registry(service: CompendiumService) -> None:
    summary = service.summary()
    titles = {book.source_id: book.title for book in summary.books}
    assert titles["phb-2014"].startswith("Player's Handbook")
    assert all(title != source_id for source_id, title in titles.items())


def test_player_handbook_contents(service: CompendiumService) -> None:
    def count(category: Category) -> int:
        return service.entries(EntryQuery(category=category, source_id="phb-2014", limit=200)).total

    assert count(Category.CLASS) == 12
    assert count(Category.SUBCLASS) == 40
    assert count(Category.SPELL) == 361
    assert count(Category.OPTIONAL_FEATURE) == 82


def test_every_class_has_subclasses(service: CompendiumService) -> None:
    classes = service.classes()
    assert len(classes) >= 12
    without = [summary.entry.name_en for summary in classes if summary.subclasses == 0]
    assert not without, f"класи без підкласів: {without}"


def test_wizard_spell_list_is_complete(service: CompendiumService) -> None:
    result = service.class_spells("Wizard")
    assert result.source == "spell-lists"
    assert len(result.spells) >= 200
    cantrips = [entry for entry in result.spells if entry.spell_level == 0]
    assert len(cantrips) == 16
    names = {entry.name_en for entry in result.spells}
    assert {"Fireball", "Shield", "Magic Missile"} <= names


def test_known_spell_resolves_to_phb(service: CompendiumService) -> None:
    entry = service.entry("phb-2014/spell/fireball")
    assert entry.name_en == "Fireball"
    assert entry.spell_level == 3
    assert entry.spell_school == "evocation"
    assert "8d6" in entry.text_en


def test_search_finds_spells_by_partial_name(service: CompendiumService) -> None:
    page = service.entries(EntryQuery(q="fireball", limit=10))
    assert page.total >= 1
    assert any(entry.name_en == "Fireball" for entry in page.items)


def test_corpus_files_load_without_warnings(service: CompendiumService) -> None:
    assert service.summary().warnings == ()
