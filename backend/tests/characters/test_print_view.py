"""Перетворення для друку: тексти правил, одиниці, урон, абетка."""

from __future__ import annotations

from dndsheet.characters.api.print_view import (
    components_short,
    damage_text,
    rule_blocks,
    uk_sort_key,
    units,
    weapon_notes,
)


def test_rule_blocks_split_paragraphs_lists_and_tables() -> None:
    text = "**Захист.** Поки ви носите броню.\n\n- раз\n- два\n\n| Рівень | Урон |\n| --- | --- |\n| 1 | 1d6 |"
    blocks = rule_blocks(text)
    assert blocks[0] == {"kind": "p", "lead": "Захист.", "text": "Поки ви носите броню."}
    assert blocks[1] == {"kind": "ul", "items": ["раз", "два"]}
    assert blocks[2] == {"kind": "table", "header": ["Рівень", "Урон"], "rows": [["1", "1d6"]]}


def test_units_and_components_are_ukrainian() -> None:
    assert units("1 bonus action") == "1 бонусна дія"
    assert units("Concentration, up to 1 minute") == "концентрація, до 1 хв"
    assert units("30/120 feet") == "30/120 фт"
    assert components_short("V, S, M (a pinch of salt)") == "В, С, М"


def test_damage_and_weapon_notes() -> None:
    assert damage_text("1d8+3 slashing") == "1d8+3 рубаний"
    assert weapon_notes("Finesse, light, thrown (range 20/60)") == "Фехтувальна, легка, метальна (дальність 20/60)"


def test_ukrainian_alphabet_order() -> None:
    words = ["Історія", "Акробатика", "Виживання", "Обман"]
    assert sorted(words, key=uk_sort_key) == ["Акробатика", "Виживання", "Історія", "Обман"]


def test_background_items_get_their_translation() -> None:
    """Речі з передісторії («insignia of rank») беруть переклад із рядків її спорядження."""
    from dndsheet.characters.api.router import _background_item_names

    payload = {
        "background_details": {
            "equipment_rows": [
                {"text": "an insignia of rank", "choices": [], "text_uk": "знаки розрізнення"},
                {"text": "bone dice", "choices": ["bone dice", "deck of cards"], "choices_uk": ["кістки з кості", "колода карт"]},
            ]
        },
        "inventory": {"items": [{"name_en": "An insignia of rank"}, {"name_en": "deck of cards"}, {"name_en": "Longsword"}]},
    }
    _background_item_names(payload)
    names = [item.get("name_uk") for item in payload["inventory"]["items"]]
    assert names == ["знаки розрізнення", "колода карт", None]
