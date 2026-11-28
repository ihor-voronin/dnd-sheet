"""Емблеми (game-icons.net, CC BY 3.0): дані, ліцензія, спрайт сторінки, файли для SPA."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from dndsheet.visuals.application import emblems


def test_every_emblem_has_a_shape_and_an_author() -> None:
    rows = emblems.credits()
    assert len(rows) == len(emblems.names()) >= 29
    for row in rows:
        assert row["author"] and row["icon"]
        assert row["url"].startswith("https://game-icons.net/1x1/")
    assert {f"class-{key}" for key in emblems.CLASSES} <= set(emblems.names())
    assert {f"school-{key}" for key in emblems.SCHOOLS} <= set(emblems.names())


def test_mappings() -> None:
    assert emblems.class_emblem("Wizard") == "class-wizard"
    assert emblems.class_emblem("blood hunter") is None
    assert emblems.class_emblem(None) is None
    assert emblems.school_emblem("evocation") == "school-evocation"
    assert emblems.school_emblem("chronurgy") is None


def test_sprite_holds_only_used_shapes() -> None:
    sprite = emblems.Sprite()
    assert sprite.markup() == ""
    first = sprite.use("class-bard", "emblem emblem--card")
    assert first == '<svg class="emblem emblem--card" aria-hidden="true"><use href="#e-class-bard"/></svg>'
    sprite.use("class-bard")
    sprite.use("school-illusion")
    assert sprite.use("nope") == "" and sprite.use(None) == ""
    markup = sprite.markup()
    assert markup.count("<symbol") == 2
    assert 'id="e-class-bard"' in markup and 'id="e-school-illusion"' in markup
    ET.fromstring(markup)  # коректний XML


def test_file_for_the_spa() -> None:
    body = emblems.svg_file("class-wizard")
    root = ET.fromstring(body)
    assert root.get("viewBox") == "0 0 512 512"
    assert emblems.svg_file("nope") is None
    assert emblems.url("class-wizard") == f"/assets/emblems/{emblems.VERSION}/class-wizard.svg"
