"""Markdown-рендер: найдешевший адаптер, який доводить, що порт працює.

Потрібен для швидкого перегляду в чаті/редакторі та для conformance-тестів.
Позначає лише **виправлення вручну**: решта чисел порахована сервером, і
писати «обчислено» біля кожного рядка — шум, а не інформація.
"""

from __future__ import annotations

from dndsheet.export.domain.renderer import (
    RenderFormat,
    RenderOptions,
    RenderResult,
    check_contract,
)
from dndsheet.sheets.domain.document import Field, SheetDocument

_OVERRIDE_MARK = " _(вручну)_"
_LEGEND = "_Значення без позначки пораховані сервером за правилами; «вручну» — вписані гравцем._"


class MarkdownRenderer:
    format = RenderFormat.MARKDOWN

    def available(self) -> bool:
        """Залежностей немає — працює завжди."""
        return True

    def render(self, document: SheetDocument, options: RenderOptions | None = None) -> RenderResult:
        check_contract(document)
        opts = options or RenderOptions()

        lines: list[str] = [f"# {self._title(document, opts)}", ""]
        for page in document.pages:
            for section in page.sections:
                lines.append(f"## {section.title.uk}")
                if opts.show_originals and section.title.en != section.title.uk:
                    lines.append(f"_{section.title.en}_")
                lines.append("")
                for field_id in section.fields:
                    field = document.fields[field_id]
                    lines.append(self._field_line(field, opts))
                lines.append("")
        if opts.show_originals:
            lines.append(_LEGEND)

        content = "\n".join(lines).rstrip() + "\n"
        return RenderResult(
            format=self.format,
            content=content.encode("utf-8"),
            media_type="text/markdown; charset=utf-8",
            filename="character-sheet.md",
        )

    @staticmethod
    def _title(document: SheetDocument, opts: RenderOptions) -> str:
        title = document.title.uk
        if opts.show_originals and document.title.en != document.title.uk:
            title = f"{title} ({document.title.en})"
        return title

    @classmethod
    def _field_line(cls, field: Field, opts: RenderOptions) -> str:
        label = field.label.uk
        if opts.show_originals and field.label.en != field.label.uk:
            label = f"{label} ({field.label.en})"
        line = f"- **{label}**: {cls._format_value(field)}"
        if field.hint is not None and opts.show_originals:
            # Текст гравця (власне вміння) буває в кілька абзаців: відступ лишає їх у пункті списку.
            line += " — " + field.hint.uk.strip().replace("\n", "\n  ")
        if field.origin == "override":
            line += _OVERRIDE_MARK
        return line

    @staticmethod
    def _format_value(field: Field) -> str:
        value = field.value
        if value is None:
            return "—"
        if isinstance(value, bool):
            return "так" if value else "ні"
        if isinstance(value, list):
            return ", ".join(str(item) for item in value) or "—"
        return str(value)
