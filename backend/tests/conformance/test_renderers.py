"""Conformance: кожен рендер мусить коректно відпрацювати всі фікстури.

Додаєш новий рендер — додаєш його в цей файл. Без цього він не мержиться.
"""

from __future__ import annotations

import io

import pytest

from dndsheet.export.domain.renderer import RenderOptions, RendererError, check_contract
from dndsheet.export.infrastructure.markdown_renderer import MarkdownRenderer
from dndsheet.export.infrastructure.pdf_renderer import PdfRenderer
from dndsheet.sheets.domain.document import SheetDocument

FIXTURE_NAMES = ["minimal", "full"]


def expected_text(field) -> str:
    """Те саме перетворення, що робить MarkdownRenderer — інакше тест перевіряє не те."""
    value = field.value
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "так" if value else "ні"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


@pytest.fixture(scope="module")
def markdown_renderer() -> MarkdownRenderer:
    return MarkdownRenderer()


@pytest.fixture()
def documents(fixture_documents: dict[str, dict]) -> dict[str, SheetDocument]:
    return {name: SheetDocument.model_validate(fixture_documents[name]) for name in FIXTURE_NAMES}


# --- Markdown ---------------------------------------------------------------


@pytest.mark.parametrize("fixture_name", FIXTURE_NAMES)
def test_markdown_renders_all_sections_and_fields(
    fixture_name: str, documents: dict[str, SheetDocument], markdown_renderer: MarkdownRenderer
) -> None:
    document = documents[fixture_name]
    text = markdown_renderer.render(document).content.decode("utf-8")

    assert document.title.uk in text
    for page in document.pages:
        for section in page.sections:
            assert section.title.uk in text
            for field_id in section.fields:
                field = document.fields[field_id]
                assert field.label.uk in text, f"немає підпису поля {field_id}"
                assert expected_text(field) in text, f"немає значення поля {field_id}"


def test_markdown_shows_english_originals(
    documents: dict[str, SheetDocument], markdown_renderer: MarkdownRenderer
) -> None:
    text = markdown_renderer.render(documents["minimal"]).content.decode("utf-8")
    assert "Strength" in text


def test_markdown_can_hide_originals(
    documents: dict[str, SheetDocument], markdown_renderer: MarkdownRenderer
) -> None:
    text = markdown_renderer.render(
        documents["minimal"], RenderOptions(show_originals=False)
    ).content.decode("utf-8")
    assert "Strength" not in text


def test_markdown_result_metadata(
    documents: dict[str, SheetDocument], markdown_renderer: MarkdownRenderer
) -> None:
    result = markdown_renderer.render(documents["minimal"])
    assert result.media_type.startswith("text/markdown")
    assert result.filename == "character-sheet.md"


# --- PDF --------------------------------------------------------------------


def test_pdf_renders_multi_page_document(documents: dict[str, SheetDocument]) -> None:
    pytest.importorskip("weasyprint", reason="WeasyPrint недоступний у цьому середовищі")
    result = PdfRenderer().render(documents["full"])

    assert result.content.startswith(b"%PDF")
    assert len(result.content) > 1000

    pypdf = pytest.importorskip("pypdf", reason="pypdf недоступний")
    reader = pypdf.PdfReader(io.BytesIO(result.content))
    assert len(reader.pages) >= 2, "документ на 2 сторінки має дати щонайменше 2 сторінки PDF"

    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Сила" in text, "кирилиця має витягуватись із PDF (шрифт із ToUnicode)"


# --- Версія контракту -------------------------------------------------------


def test_major_version_mismatch_is_refused(documents: dict[str, SheetDocument]) -> None:
    document = documents["minimal"].model_copy(update={"schema_version": "2.0"})
    with pytest.raises(RendererError, match="контракт"):
        check_contract(document)

    with pytest.raises(RendererError):
        MarkdownRenderer().render(document)
