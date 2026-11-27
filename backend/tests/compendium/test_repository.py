"""Читання корпусу: індекси, фільтри, впорядкування, помилки на диску."""

from __future__ import annotations

import json
from pathlib import Path

import corpus
import pytest
from dndsheet.compendium.domain.entry import Category
from dndsheet.compendium.domain.query import EntryQuery
from dndsheet.compendium.infrastructure.jsonl_corpus import (
    CorpusError,
    JsonlCompendiumRepository,
    load_corpus,
)


def test_counts_cover_every_category(repository: JsonlCompendiumRepository) -> None:
    counts = dict(repository.counts())
    assert counts[Category.SPELL] == 5
    assert counts[Category.CLASS] == 2
    assert counts[Category.SUBCLASS] == 2
    assert counts[Category.ITEM] == 2
    assert repository.entries_count() == 17


def test_get_by_id(repository: JsonlCompendiumRepository) -> None:
    entry = repository.get("demo/class/fighter")
    assert entry is not None
    assert entry.name_en == "Fighter"
    assert entry.category is Category.CLASS


def test_get_unknown_id_gives_none(repository: JsonlCompendiumRepository) -> None:
    assert repository.get("demo/class/nope") is None


def test_find_by_category(repository: JsonlCompendiumRepository) -> None:
    page = repository.find(EntryQuery(category=Category.SPELL, limit=10))
    assert page.total == 5
    assert {entry.category for entry in page.items} == {Category.SPELL}


def test_find_by_book(repository: JsonlCompendiumRepository) -> None:
    page = repository.find(EntryQuery(source_id="other"))
    assert page.total == 1
    assert page.items[0].id == "other/spell/magic-missile"


def test_search_ignores_case_and_punctuation(repository: JsonlCompendiumRepository) -> None:
    assert repository.find(EntryQuery(q="BAG OF HOLDING")).total == 1
    assert repository.find(EntryQuery(q="bag of")).total == 1
    assert repository.find(EntryQuery(q="crossbow")).total == 0


def test_filter_by_spell_level(repository: JsonlCompendiumRepository) -> None:
    page = repository.find(EntryQuery(category=Category.SPELL, level=1))
    assert page.total == 3
    assert {entry.name_en for entry in page.items} == {"Burning Hands", "Magic Missile"}


def test_filter_by_optional_feature_group(repository: JsonlCompendiumRepository) -> None:
    page = repository.find(EntryQuery(feature_type="Eldritch Invocation"))
    assert page.total == 1
    assert page.items[0].name_en == "Agonizing Blast"


def test_filter_magical_items(repository: JsonlCompendiumRepository) -> None:
    magical = repository.find(EntryQuery(category=Category.ITEM, magical=True))
    assert magical.total == 1
    assert magical.items[0].name_en == "Bag of Holding"
    plain = repository.find(EntryQuery(category=Category.ITEM, magical=False))
    assert plain.total == 1
    assert plain.items[0].name_en == "Longsword"


def test_filter_subclasses_of_class(repository: JsonlCompendiumRepository) -> None:
    page = repository.find(EntryQuery(subclass_of="fighter"))
    assert page.total == 2
    assert repository.find(EntryQuery(subclass_of="wizard")).total == 0


def test_pagination_slices_and_reports_total(repository: JsonlCompendiumRepository) -> None:
    first = repository.find(EntryQuery(category=Category.SPELL, limit=2, offset=0))
    second = repository.find(EntryQuery(category=Category.SPELL, limit=2, offset=2))
    assert first.total == 5 and second.total == 5
    assert len(first.items) == 2 and len(second.items) == 2
    assert first.has_more and second.has_more
    last = repository.find(EntryQuery(category=Category.SPELL, limit=2, offset=4))
    assert len(last.items) == 1 and not last.has_more


def test_entries_are_sorted_by_name(repository: JsonlCompendiumRepository) -> None:
    names = [entry.name_en for entry in repository.find(EntryQuery(limit=50)).items]
    assert names == sorted(names, key=str.casefold)


def test_corpus_of_other_book_is_separate(repository: JsonlCompendiumRepository) -> None:
    assert dict(repository.books()) == {"demo": 16, "other": 1}


# --- битий корпус --------------------------------------------------------


def _book_dir(content_dir: Path) -> Path:
    """Окремий корпус для зіпсованого випадку: `<root>/broken/*.jsonl`."""
    directory = content_dir / "broken_root" / "broken"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def test_broken_json_reports_file_and_line(content_dir: Path) -> None:
    book = _book_dir(content_dir)
    (book / "spell.jsonl").write_text('{"id": "broken/spell/x"}\n', encoding="utf-8")
    with pytest.raises(CorpusError, match=r"broken/spell\.jsonl:1"):
        JsonlCompendiumRepository(directory=book.parent)._ensure_loaded()


def test_incomplete_record_reports_where(content_dir: Path) -> None:
    book = _book_dir(content_dir)
    record = corpus.record("broken", "spell", "x", "X")
    del record["text_en"]
    (book / "spell.jsonl").write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(CorpusError, match="немає обовʼязкового поля text_en"):
        JsonlCompendiumRepository(directory=book.parent)._ensure_loaded()


def test_record_in_wrong_file_is_an_error(content_dir: Path) -> None:
    book = _book_dir(content_dir)
    record = corpus.record("broken", "item", "x", "X")
    (book / "spell.jsonl").write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(CorpusError, match=r"категорія item у файлі spell\.jsonl"):
        JsonlCompendiumRepository(directory=book.parent)._ensure_loaded()


def test_duplicate_id_keeps_first_and_warns(content_dir: Path) -> None:
    book = _book_dir(content_dir)
    first = corpus.record("broken", "spell", "x", "First")
    second = corpus.record("broken", "spell", "x", "Second")
    (book / "spell.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in (first, second)) + "\n",
        encoding="utf-8",
    )
    loaded = load_corpus(book.parent)
    assert [entry.name_en for entry in loaded.entries] == ["First"]
    assert any("повторний id" in warning for warning in loaded.warnings)


def test_unknown_category_file_is_skipped_with_warning(content_dir: Path) -> None:
    book = _book_dir(content_dir)
    (book / "magicitem.jsonl").write_text("{}\n", encoding="utf-8")
    loaded = load_corpus(book.parent)
    assert loaded.entries == ()
    assert any("невідома категорія" in warning for warning in loaded.warnings)


def test_missing_directory_is_an_empty_corpus(content_dir: Path) -> None:
    loaded = load_corpus(content_dir / "nope")
    assert loaded.entries == () and not loaded.warnings
