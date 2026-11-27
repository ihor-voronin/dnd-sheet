"""Документ листа: усе, що є на екрані, мусить бути й у документі.

Тести тут перевіряють не верстку, а **зміст**: чи потрапив стан (хіти, комірки,
виправлення, нотатки) у документ і чи не зник розділ дорогою.
"""

from __future__ import annotations

import jsonschema
import pytest

from dndsheet.characters.application.golden import GoldenCase, build_golden_cases
from dndsheet.characters.domain.inventory import Inventory, InventoryItem, ItemKind
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.domain.state import DeathSaves, SheetState
from dndsheet.characters.domain.vitals import HitPointState
from dndsheet.sheets.application.build_document import build_sheet_document
from dndsheet.sheets.domain.document import SheetDocument
from dndsheet.shared.kernel import Money

from helpers import make_character


def _document(case: GoldenCase) -> SheetDocument:
    computed = DerivedStatsCalculator().compute(case.character)
    return build_sheet_document(case.character, computed)


def _section_ids(document: SheetDocument) -> list[str]:
    return [section.id for page in document.pages for section in page.sections]


def _values(document: SheetDocument, section_id: str) -> dict[str, object]:
    """Значення полів розділу: {id поля: value}."""
    for page in document.pages:
        for section in page.sections:
            if section.id == section_id:
                return {field_id: document.fields[field_id].value for field_id in section.fields}
    raise AssertionError(f"немає розділу {section_id!r}: {_section_ids(document)}")


# ---------------------------------------------------------------------------
# структура
# ---------------------------------------------------------------------------


def test_document_has_every_sheet_area(golden_cases) -> None:
    """Розділи документа повторюють вкладки листа, а не першу сторінку."""
    document = _document(golden_cases["fighter-1"])
    ids = _section_ids(document)
    for expected in ["identity", "abilities", "combat", "saves", "skills", "features", "inventory"]:
        assert expected in ids, f"немає розділу {expected!r}: {ids}"


def test_every_referenced_field_exists_and_is_unique(golden_cases) -> None:
    document = _document(golden_cases["fighter-2-wizard-3"])
    referenced: list[str] = []
    for page in document.pages:
        assert page.sections, "порожня сторінка в документі"
        for section in page.sections:
            assert section.fields, f"порожній розділ {section.id!r}"
            referenced.extend(section.fields)
    assert len(referenced) == len(set(referenced)), "поле згадується у двох розділах"
    for field_id in referenced:
        assert field_id in document.fields
        assert document.fields[field_id].id == field_id


def test_document_matches_the_contract_schema(golden_cases, schema: dict) -> None:
    """Справжній документ проходить ту саму схему, що й фікстури."""
    for key in golden_cases:
        jsonschema.validate(instance=_document(golden_cases[key]).to_contract_dict(), schema=schema)


def test_spell_sections_follow_the_class(golden_cases) -> None:
    warlock = _section_ids(_document(golden_cases["warlock-1"]))
    fighter = _section_ids(_document(golden_cases["fighter-1"]))
    assert "spells" in warlock and "known-spells" in warlock
    assert "spells" not in fighter and "known-spells" not in fighter


def test_no_attacks_section_without_compendium(golden_cases) -> None:
    """Немає даних зброї — немає й порожнього заголовка «Атаки»."""
    ids = _section_ids(_document(golden_cases["fighter-1"]))
    assert "attacks" not in ids


def test_attacks_render_into_the_document(golden_cases) -> None:
    document = build_sheet_document(
        golden_cases["fighter-1"].character,
        DerivedStatsCalculator().compute(golden_cases["fighter-1"].character),
        attacks=[
            {
                "name_en": "longsword",
                "attack_bonus": 5,
                "damage": "1d8+3 slashing",
                "ability": "str",
                "notes": "versatile (1d10)",
                "equipped": False,
            }
        ],
    )
    values = _values(document, "attacks")
    assert values == {"attack.1": "+5 · 1d8+3 slashing"}
    field = document.fields["attack.1"]
    assert field.label.uk == "longsword"
    assert field.hint is not None and field.hint.uk == "Сила · versatile (1d10)"


# ---------------------------------------------------------------------------
# стан листа
# ---------------------------------------------------------------------------


def test_state_is_exported_not_the_rules(rules) -> None:
    """PDF посеред бою показує фактичні хіти, а не максимум."""
    character = make_character(
        rules,
        inventory=Inventory(
            items=(
                InventoryItem(
                    name_en="chain mail",
                    kind=ItemKind.ARMOR,
                    equipped=True,
                    armor_base=16,
                    dex_cap=0,
                ),
            ),
            money=Money(gp=7, sp=3, cp=1),
        ),
        hp=HitPointState(current=4, temporary=2),
    )
    character.set_state(
        SheetState(
            inspiration=True,
            exhaustion=2,
            death_saves=DeathSaves(successes=1, failures=2),
            hit_dice_used={10: 1},
            notes={"appearance": "шрам на щоці", "notes": "боїться води"},
        )
    )
    computed = DerivedStatsCalculator().compute(character)
    document = build_sheet_document(character, computed)

    combat = _values(document, "combat")
    assert combat["hp.current"] == 4
    assert combat["hp.max"] == 10
    assert combat["hp.temp"] == 2
    assert combat["inspiration"] is True
    assert combat["exhaustion"] == 2
    assert combat["death_saves"] == "успіхи 1 / провали 2"
    assert combat["hitdice.left"] == "d10: 0 з 1"

    notes = _values(document, "notes")
    assert notes == {"note.appearance": "шрам на щоці", "note.notes": "боїться води"}
    assert document.fields["note.appearance"].type == "longtext"

    money = _values(document, "money")
    assert money["money.gp"] == 7
    assert money["money.sp"] == 3
    assert money["money.cp"] == 1


def test_zero_hp_is_exported_as_zero(rules) -> None:
    """Непритомний персонаж у PDF — це 0 хітів, а не повні."""
    character = make_character(rules, hp=HitPointState(current=0))
    document = build_sheet_document(character, DerivedStatsCalculator().compute(character))
    assert _values(document, "combat")["hp.current"] == 0


def test_override_changes_origin_not_the_number(rules) -> None:
    character = make_character(rules)
    character.set_override("armor_class", 19)
    character.set_override("skill:stealth", 11)
    document = build_sheet_document(character, DerivedStatsCalculator().compute(character))

    assert document.fields["ac.total"].value == 19
    assert document.fields["ac.total"].origin == "override"
    assert document.fields["skill.stealth"].value == 11
    assert document.fields["skill.stealth"].origin == "override"
    # Невиправлені поля лишаються обчисленими.
    assert document.fields["skill.athletics"].origin == "computed"


def test_spell_slots_show_remaining_and_used(rules) -> None:
    """«2/4» у документі = залишилось / усього; витрачене — у підказці."""
    warlock = build_golden_cases(rules)[1]
    warlock.character.set_state(SheetState(pact_used=1, hit_dice_used={8: 1}))
    document = build_sheet_document(
        warlock.character, DerivedStatsCalculator().compute(warlock.character)
    )
    spells = _values(document, "spells")
    assert spells["spell.pact"] == "0/1"
    assert document.fields["spell.pact"].hint.uk == "витрачено 1"
    known = _values(document, "known-spells")
    # Чотири класові закляття + заговір тифлінга (thaumaturgy) від виду.
    assert len(known) == 5
    assert "заговір" in str(known["spell.1"])
    assert any("від виду" in str(value) for value in known.values())


def test_notes_page_is_absent_when_empty(golden_cases) -> None:
    assert "notes" not in _section_ids(_document(golden_cases["fighter-1"]))


def test_warnings_reach_the_document(rules) -> None:
    character = make_character(rules, hp=HitPointState(current=99))
    document = build_sheet_document(character, DerivedStatsCalculator().compute(character))
    assert _values(document, "warnings")["warnings"] == [
        "поточні хіти (99) більші за максимум (10)"
    ]


def test_unknown_field_type_is_rejected() -> None:
    with pytest.raises(Exception):
        SheetDocument.model_validate(
            {
                "schemaVersion": "1.0",
                "edition": "2014",
                "title": {"uk": "x", "en": "x"},
                "pages": [
                    {
                        "size": "A4",
                        "sections": [{"id": "s", "title": {"uk": "s", "en": "s"}, "fields": ["f"]}],
                    }
                ],
                "fields": {
                    "f": {
                        "id": "f",
                        "type": "unknown",
                        "value": 1,
                        "origin": "input",
                        "label": {"uk": "f", "en": "f"},
                    }
                },
            }
        )
