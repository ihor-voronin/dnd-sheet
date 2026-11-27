"""Conformance на справжньому листі: обидва рендери малюють те, що в документі.

Фікстури (`contract/fixtures/*.json`) перевіряють формат. Тут — інше:
документ, зібраний із реального персонажа зі станом, мусить дійти до виходу
без втрат. Якщо розділ з'явився в документі, але не в Markdown чи не в HTML,
це падіння саме тут.

PDF збирається з HTML-шаблону: перевірка HTML — це перевірка змісту PDF.
Сам `%PDF` перевіряється лише там, де є WeasyPrint (на Windows без GTK його
немає, і це чесний skip, а не зелений тест).
"""

from __future__ import annotations

import html as html_module
import io

import pytest
from dndsheet.characters.application.golden import build_golden_cases
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.domain.state import DeathSaves, SheetState
from dndsheet.export.domain.renderer import RenderOptions
from dndsheet.export.infrastructure.markdown_renderer import MarkdownRenderer
from dndsheet.export.infrastructure.pdf_renderer import PdfRenderer
from dndsheet.sheets.application.build_document import build_sheet_document
from dndsheet.sheets.domain.document import SheetDocument
from rules_fixture import FixtureRules


def _character_document(**state) -> SheetDocument:  # noqa: ANN003
    """Варлок 1 зі змінами за столом: 4 хіти, витрачений комірка, нотатка."""
    rules = FixtureRules()
    case = {case.key: case for case in build_golden_cases(rules)}["warlock-1"]
    character = case.character
    character.set_hp(current=4, temporary=2)
    character.set_state(
        SheetState(
            pact_used=1,
            death_saves=DeathSaves(successes=1, failures=0),
            inspiration=True,
            exhaustion=1,
            notes={"appearance": "роги й хвіст", "notes": "шукає сестру"},
            **state,
        )
    )
    character.set_override("armor_class", 15)
    computed = DerivedStatsCalculator().compute(character)
    attacks = [
        {
            "name_en": "dagger",
            "attack_bonus": 4,
            "damage": "1d4+1 piercing",
            "ability": "dex",
            "notes": "finesse, light, thrown (range 20/60)",
            "equipped": False,
        }
    ]
    return build_sheet_document(character, computed, attacks)


@pytest.fixture(scope="module")
def document() -> SheetDocument:
    return _character_document()


def _every_field(document: SheetDocument):
    for page in document.pages:
        for section in page.sections:
            for field_id in section.fields:
                yield section, document.fields[field_id]


def _expected(field) -> list[str]:  # noqa: ANN001 — Field
    """Те саме перетворення, що роблять рендери: інакше тест перевіряє не той текст."""
    value = field.value
    if value is None:
        return ["—"]
    if isinstance(value, bool):
        return ["так" if value else "ні"]
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


# --- Markdown ---------------------------------------------------------------


def test_markdown_contains_the_whole_sheet(document: SheetDocument) -> None:
    text = MarkdownRenderer().render(document).content.decode("utf-8")

    assert document.title.uk in text
    for section, field in _every_field(document):
        assert section.title.uk in text, f"немає розділу {section.id!r}"
        assert field.label.uk in text, f"немає підпису {field.id!r}"
        for expected in _expected(field):
            assert expected in text, f"немає значення {field.id!r}"


def test_markdown_marks_overrides_only(document: SheetDocument) -> None:
    text = MarkdownRenderer().render(document).content.decode("utf-8")
    ac_line = next(line for line in text.splitlines() if "Клас захисту" in line)
    assert "15" in ac_line
    assert "вручну" in ac_line
    skill_line = next(line for line in text.splitlines() if "Скритність" in line)
    assert "вручну" not in skill_line, "обчислене поле не позначається як виправлене"


def test_markdown_can_hide_originals(document: SheetDocument) -> None:
    text = MarkdownRenderer().render(document, RenderOptions(show_originals=False)).content.decode("utf-8")
    assert "Strength" not in text
    assert "Сила" in text


# --- HTML (те, з чого збирається PDF) --------------------------------------


def test_html_contains_the_whole_sheet(document: SheetDocument) -> None:
    markup = PdfRenderer().render_html(document)

    assert document.title.uk in markup
    for section, field in _every_field(document):
        assert section.title.uk in markup, f"немає розділу {section.id!r}"
        assert html_module.escape(field.label.uk) in markup, f"немає підпису {field.id!r}"
        for expected in _expected(field):
            assert html_module.escape(expected) in markup, f"немає значення {field.id!r}"


def test_html_marks_origin(document: SheetDocument) -> None:
    markup = PdfRenderer().render_html(document)
    assert "✎" in markup, "виправлене вручну поле позначене"
    assert "•" in markup, "обчислене поле позначене"


def test_html_has_one_page_block_per_document_page(document: SheetDocument) -> None:
    markup = PdfRenderer().render_html(document)
    assert markup.count('class="page"') == len(document.pages)


# --- PDF --------------------------------------------------------------------


def test_pdf_is_produced_where_weasyprint_exists(document: SheetDocument) -> None:
    pytest.importorskip("weasyprint", reason="WeasyPrint недоступний у цьому середовищі")
    result = PdfRenderer().render(document)

    assert result.content.startswith(b"%PDF")
    assert result.media_type == "application/pdf"

    pypdf = pytest.importorskip("pypdf", reason="pypdf недоступний")
    reader = pypdf.PdfReader(io.BytesIO(result.content))
    assert len(reader.pages) >= len(document.pages)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert document.title.uk in text
    assert "Клас захисту" in text, "кирилиця має витягуватись із PDF (шрифт із ToUnicode)"
    assert "15" in text, "виправлене значення теж має бути в PDF"
