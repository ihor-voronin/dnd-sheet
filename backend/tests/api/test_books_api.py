"""Головна сторінка: книги довідника — що дає кожна, ціна, посилання й обкладинка."""

from __future__ import annotations

from fastapi.testclient import TestClient

from dndsheet.api.app import create_app


def test_books_overview_for_the_home_page() -> None:
    client = TestClient(create_app())
    payload = client.get("/api/v1/compendium/books").json()

    # Дата перевірки цін показується поруч із цінами — без неї ціни не можна показувати.
    assert payload["checked"]
    assert payload["currency"] == "USD"
    # Класи й види — з механік, з яких збирається персонаж (артифіцер теж клас).
    assert payload["totals"]["class"] == 13
    assert payload["totals"]["spell"] > 300

    books = {book["id"]: book for book in payload["books"]}
    phb = books["phb-2014"]
    assert phb["group"] == "core"
    assert phb["url"] == "https://www.dndbeyond.com/sources/dnd/phb-2014"
    assert phb["price"] and phb["cover"].startswith("https://www.dndbeyond.com/avatars/")
    assert phb["counts"]["class"] == 12 and phb["counts"]["spell"] > 300
    # Книга без ціни пояснює чому, а не показує порожнє місце.
    assert books["basic-rules-2014"]["price"] is None and books["basic-rules-2014"]["note"]
    assert payload["other_sources"] > 0
