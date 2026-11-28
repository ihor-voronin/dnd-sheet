"""Каталог сторінок, підписи й факти — без HTTP."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from dndsheet.compendium.domain.entry import Category
from dndsheet.compendium.domain.query import MAX_LIMIT, EntryQuery
from dndsheet.compendium.infrastructure.factory import build_service
from dndsheet.site.application.catalog import KbCatalog, item_group, uk_sort_key
from dndsheet.site.application.facts import background_facts, class_facts, species_facts, spell_facts
from dndsheet.site.application.labels import Labels, units, with_english
from dndsheet.site.domain.publication import Policy
from dndsheet.site.infrastructure.files import load_json, load_terminology

LABELS = Labels(json.loads((Path(__file__).resolve().parent / "kb-labels.fixture.json").read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def entries() -> dict[Category, list]:
    service = build_service()
    out: dict[Category, list] = {}
    for category in (Category.SPELL, Category.FEAT, Category.ITEM, Category.OPTIONAL_FEATURE):
        rows, offset = [], 0
        while True:
            page = service.entries(EntryQuery(category=category, limit=MAX_LIMIT, offset=offset))
            rows += page.items
            offset += MAX_LIMIT
            if not page.has_more:
                break
        out[category] = rows
    if not out[Category.SPELL]:
        pytest.skip("немає корпусу")
    return out


def test_one_page_per_name_with_aliases(entries) -> None:  # noqa: ANN001
    catalog = KbCatalog(labels=LABELS, policy=Policy.FULL, entries=entries)
    fireball = catalog.find("spells", "fireball")
    assert fireball is not None and fireball.name_uk == "Вогняна куля"
    assert fireball.license == "srd", "найвідкритіша ліцензія серед книг з цим закляттям"
    assert [record.slug for record in catalog.records("spells")].count("fireball") == 1
    assert catalog.alias("spells", "abi-dalzim-s-horrid-wilting") == "abi-dalzims-horrid-wilting"
    assert catalog.alias("spells", "fireball") is None
    levels = [group for group, _ in catalog.groups("spells")]
    assert levels == [str(level) for level in range(10)]
    related = catalog.related(fireball)
    assert related and all(record.group == "3" and record.slug != "fireball" for record in related)


def test_policy_reaches_every_record(entries) -> None:  # noqa: ANN001
    summary = KbCatalog(labels=LABELS, policy=Policy.SUMMARY, entries=entries)
    closed = [record for record in summary.records("feats") if record.license == "proprietary"]
    assert closed and all(not record.publication.text and record.publication.index for record in closed)
    assert summary.find("spells", "fireball").publication.text


def test_item_groups_follow_the_inventory_chips() -> None:
    assert item_group("weapon (longbow)") == "Зброя"
    assert item_group("siege weapon") == "Зброя"
    assert item_group("wondrous item") == "Дивовижні предмети"
    assert item_group("ship") == "Верхові тварини й транспорт"
    assert item_group(None) == "Інше"


def test_ukrainian_alphabetical_order() -> None:
    words = ["Ящір", "Їжак", "Гоблін", "Ґанок", "Ірис", "Єнот", "Ельф", "Orc"]
    assert sorted(words, key=uk_sort_key) == ["Гоблін", "Ґанок", "Ельф", "Єнот", "Ірис", "Їжак", "Ящір", "Orc"]


def test_labels_fall_back_to_the_original() -> None:
    empty = Labels()
    assert not empty.loaded
    assert empty.species("hill dwarf") is None
    assert empty.species_label("hill dwarf") == "Hill Dwarf"
    assert empty.ability("str") == "STR" and empty.source(None) == "" and empty.source("xge") == "XGE"
    assert LABELS.species_label("hill dwarf") == "Пагорбовий дворф (Hill Dwarf)"
    assert LABELS.proficiency_text("weapon", "battleaxes") == "бойова сокира"
    assert LABELS.proficiency("armor", "light") == "легка броня"
    assert with_english("Longsword", "Довгий меч") == "Довгий меч (Longsword)"
    assert with_english("Orc", "orc") == "Orc"


def test_units_translate_spell_lines() -> None:
    assert units("1 bonus action") == "1 бонусна дія"
    assert units("Concentration, up to 1 minute") == "концентрація, до 1 хв."
    assert units("Self (15-foot cone)") == "на себе (15-фт конус)"


def test_facts_like_the_wizard_cards() -> None:
    species = species_facts(
        {
            "size": "small",
            "speed": 30,
            "ability_unresolved": True,
            "skill_any": 1,
            "tools_any": 1,
            "languages": ["common"],
        },
        LABELS,
    )
    rows = {fact.label: fact.value for fact in species}
    assert rows["Характеристики"].startswith("розподіляєте самі")
    assert rows["Навички"] == "1 на вибір" and rows["Мови"] == "спільна"
    klass = {
        fact.label: fact.value
        for fact in class_facts({"key": "fighter", "hit_die": 10, "saving_throws": ["str"]}, LABELS)
    }
    assert klass["Броня"] == "без броні" and klass["Чарування"] == "на 1 рівні не чарує"
    background = background_facts({"skill_proficiencies": ["insight"], "money": {"gp": 15}}, LABELS, "Притулок")
    assert [fact.label for fact in background] == ["Навички", "Риса", "Гроші"]
    spell = {
        fact.label: fact
        for fact in spell_facts(
            {"level": 0, "school": "evocation", "duration": "Concentration, up to 1 minute", "concentration": True},
            LABELS,
        )
    }
    assert spell["Рівень"].value == "заговір · втілення"
    assert spell["Тривалість"].term == "concentration"


def test_files_are_optional(tmp_path: Path) -> None:
    assert load_json(tmp_path / "missing.json") == {}
    broken = tmp_path / "broken.json"
    broken.write_text("[1, 2", encoding="utf-8")
    assert load_json(broken) == {}
    terms = load_terminology()
    assert ("Сила", "Strength", "ability") in terms
