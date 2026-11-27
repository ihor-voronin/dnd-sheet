"""Спорядження передісторії: рядок `Equipment:` з книги → предмети.

Перевіряється на справжніх рядках PHB: у «Солдата» всередині дужок є кома
(«a dagger, broken blade, or piece of a banner»), і наївний поділ за комами
зламав би предмет на три. Варіанти книги («bone dice or deck of cards»)
лишаються вибором, а «a pouch containing 10 gp» — ще й грошима.
"""

from __future__ import annotations

from dndsheet.characters.api.background_info import parse_equipment

SOLDIER = (
    "An insignia of rank, a trophy taken from a fallen enemy (a dagger, broken "
    "blade, or piece of a banner), a set of bone dice or deck of cards, a set of "
    "common clothes, and a pouch containing 10 gp"
)

ACOLYTE = (
    "A holy symbol (a gift to you when you entered the priesthood), a prayer book "
    "or prayer wheel, 5 sticks of incense, vestments, a set of common clothes, and "
    "a pouch containing 15 gp"
)


def test_soldier_equipment_is_split_into_items() -> None:
    rows, money = parse_equipment(SOLDIER)

    assert [row["text"] for row in rows] == [
        "insignia of rank",
        "trophy taken from a fallen enemy (a dagger, broken blade, or piece of a banner)",
        "bone dice",
        "common clothes",
        "pouch containing 10 gp",
    ]
    assert rows[2]["choices"] == ["bone dice", "deck of cards"]
    assert money == {"gp": 10}


def test_parentheses_commas_do_not_split_items() -> None:
    rows, _ = parse_equipment(ACOLYTE)

    assert any("holy symbol" in row["text"] for row in rows)
    prayer = next(row for row in rows if row["text"] == "prayer book")
    assert prayer["choices"] == ["prayer book", "prayer wheel"]


def test_empty_line_gives_nothing() -> None:
    assert parse_equipment("") == ([], {})
