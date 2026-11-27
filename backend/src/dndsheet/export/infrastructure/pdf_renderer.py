"""PDF-рендер через WeasyPrint (HTML + CSS paged media).

Два кроки навмисно розділені:

* `render_html` — Jinja-шаблон заповнюється документом. Працює завжди й
  перевіряється тестами: саме тут видно, чи потрапив розділ на сторінку.
* `render` — HTML перетворюється в PDF через WeasyPrint. Він імпортується
  ліниво: на Windows без GTK його може не бути, і тоді адаптер кидає
  `RendererUnavailable`, а не ламає застосунок на старті.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from jinja2 import Environment, FileSystemLoader, select_autoescape

from dndsheet.export.domain.renderer import (
    RendererError,
    RendererUnavailable,
    RenderFormat,
    RenderOptions,
    RenderResult,
    check_contract,
)
from dndsheet.sheets.domain.document import SheetDocument

DEFAULT_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
FONTS_DIR = DEFAULT_TEMPLATES_DIR / "fonts"


@lru_cache(maxsize=1)
def _font_urls() -> dict[str, str]:
    """Шрифти Alegreya (OFL) як data-URI: однаково працює і WeasyPrint, і друк із браузера."""
    return {
        path.name: "data:font/woff2;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
        for path in sorted(FONTS_DIR.glob("*.woff2"))
    }


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

    def available(self) -> bool:
        """Чи є WeasyPrint. Перевіряємо `find_spec`, а не імпорт: імпорт тягне GTK."""
        import importlib.util

        return importlib.util.find_spec("weasyprint") is not None

    def render_html(self, document: SheetDocument, options: RenderOptions | None = None) -> str:
        """HTML листа — проміжний артефакт PDF (і предмет conformance-тестів)."""
        check_contract(document)
        opts = options or RenderOptions()
        try:
            template = self._env.get_template(f"{opts.template}.html.jinja")
        except Exception as exc:  # noqa: BLE001 - шаблон може бути відсутній
            raise RendererError(f"Шаблон {opts.template!r} недоступний") from exc
        return template.render(doc=document, o=opts)

    def render(self, document: SheetDocument, options: RenderOptions | None = None) -> RenderResult:
        html = self.render_html(document, options)
        try:
            from weasyprint import HTML
        except ImportError as exc:
            raise RendererUnavailable("WeasyPrint не встановлено (потрібен extra `pdf` і GTK на Windows)") from exc
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

    # --- лист персонажа для друку -------------------------------------------

    def character_html(
        self, view: Mapping[str, Any], options: RenderOptions | None = None, *, detailed: bool = True
    ) -> str:
        """HTML аркуша з даних `print_view`.

        Спершу аркуш для гри (головна, закляття, спорядження й нотатки), далі —
        додаткові аркуші з повними текстами умінь, особливостей і заклять.
        `detailed=False` лишає лише аркуш для гри.
        """
        opts = options or RenderOptions()
        template = self._env.get_template("character.html.jinja")
        return template.render(v=view, o=opts, font=_font_urls(), detailed=detailed)

    def render_character(
        self,
        view: Mapping[str, Any],
        options: RenderOptions | None = None,
        *,
        detailed: bool = True,
        filename: str = "character-sheet.pdf",
    ) -> RenderResult:
        html = self.character_html(view, options, detailed=detailed)
        try:
            from weasyprint import HTML
        except ImportError as exc:
            raise RendererUnavailable("WeasyPrint не встановлено (потрібен extra `pdf` і GTK на Windows)") from exc
        try:
            pdf_bytes = HTML(string=html, base_url=str(self._templates_dir)).write_pdf()
        except Exception as exc:  # noqa: BLE001 - помилки WeasyPrint різнорідні
            raise RendererError(f"Не вдалося згенерувати PDF: {exc}") from exc
        return RenderResult(format=self.format, content=pdf_bytes, media_type="application/pdf", filename=filename)
