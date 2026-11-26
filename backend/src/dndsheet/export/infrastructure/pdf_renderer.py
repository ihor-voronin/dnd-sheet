"""PDF-рендер через WeasyPrint (HTML + CSS paged media).

WeasyPrint імпортується ліниво: на Windows без GTK його може не бути, і тоді
адаптер кидає RendererUnavailable, а не ламає застосунок на старті.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from dndsheet.export.domain.renderer import (
    RenderFormat,
    RenderOptions,
    RenderResult,
    RendererError,
    RendererUnavailable,
    check_contract,
)
from dndsheet.sheets.domain.document import SheetDocument

DEFAULT_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


class PdfRenderer:
    format = RenderFormat.PDF

    def __init__(self, templates_dir: Path | None = None) -> None:
        self._templates_dir = templates_dir or DEFAULT_TEMPLATES_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(self._templates_dir)),
            autoescape=select_autoescape(["html", "jinja"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, document: SheetDocument, options: RenderOptions | None = None) -> RenderResult:
        check_contract(document)
        opts = options or RenderOptions()

        try:
            from weasyprint import HTML
        except ImportError as exc:
            raise RendererUnavailable(
                "WeasyPrint не встановлено (потрібен extra `pdf` і GTK на Windows)"
            ) from exc

        try:
            template = self._env.get_template(f"{opts.template}.html.jinja")
        except Exception as exc:  # noqa: BLE001 - шаблон може бути відсутній
            raise RendererError(f"Шаблон {opts.template!r} недоступний") from exc

        html = template.render(doc=document, o=opts)
        try:
            pdf_bytes = HTML(string=html, base_url=str(self._templates_dir)).write_pdf()
        except Exception as exc:  # noqa: BLE001 - помилки WeasyPrint різнорідні
            raise RendererError(f"Не вдалося згенерувати PDF: {exc}") from exc

        return RenderResult(
            format=self.format,
            content=pdf_bytes,
            media_type="application/pdf",
            filename="character-sheet.pdf",
        )
