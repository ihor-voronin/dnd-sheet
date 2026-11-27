"""Розбір сторінки «Spell Lists»: клас, рівень, назви — і що ігнорується."""

from __future__ import annotations

import sys
from pathlib import Path

import corpus
import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ingest.spell_lists import (  # noqa: E402
    _class_from_heading,
    _level_from_heading,
    clean,
    parse_page,
)

PAGE = """
<h2 id="BardSpells"><a href="#BardSpells"></a>Bard Spells</h2>
<h4 id="Cantrips">Cantrips (0 Level)</h4>
<div><p><a href="#BladeWard">Blade Ward</a></p>
<p><a href="#Mockery">Vicious Mockery</a></p></div>
<h4 id="First">1st Level</h4>
<p><a href="#Cure">Cure Wounds</a></p>
<h4 id="Other">Some Other Heading</h4>
<p><a href="#Ignored">Ignored Spell</a></p>
<h2 id="Descriptions"><a href="#Descriptions"></a>Spell Descriptions</h2>
<h4 id="First2">1st Level</h4>
<p><a href="#NotAClass">Not A Class Spell</a></p>
"""


@pytest.fixture()
def page() -> Path:
    path = corpus.BASE / "spells.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PAGE, encoding="utf-8")
    return path


def test_parse_page_reads_classes_and_levels(page: Path) -> None:
    result = parse_page("demo", page)
    assert result.book == "demo"
    assert result.lists == {"Bard": {0: ["Blade Ward", "Vicious Mockery"], 1: ["Cure Wounds"]}}
    assert not result.problems


def test_names_outside_level_sections_are_ignored(page: Path) -> None:
    names = [name for per_level in parse_page("demo", page).lists["Bard"].values() for name in per_level]
    assert "Ignored Spell" not in names


def test_headings_of_non_class_section_are_ignored(page: Path) -> None:
    assert _class_from_heading("Bard Spells") == "Bard"
    assert _class_from_heading("Spell Descriptions") is None


@pytest.mark.parametrize(
    ("heading", "level"),
    [
        ("Cantrips (0 Level)", 0),
        ("1st Level", 1),
        ("2nd Level", 2),
        ("9th Level", 9),
        ("Spell Descriptions", None),
    ],
)
def test_level_from_heading(heading: str, level: int | None) -> None:
    assert _level_from_heading(heading) == level


def test_clean_strips_tags_and_entities() -> None:
    assert clean("<a href='#'>Fire&nbsp;Ball</a>") == "Fire Ball"
