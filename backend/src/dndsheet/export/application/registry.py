"""Реєстр рендерів: композиційний корінь вирішує, які адаптери доступні."""

from __future__ import annotations

from dndsheet.export.domain.renderer import RenderFormat, RendererError, SheetRenderer


class RendererRegistry:
    def __init__(self) -> None:
        self._renderers: dict[RenderFormat, SheetRenderer] = {}

    def register(self, renderer: SheetRenderer) -> None:
        if renderer.format in self._renderers:
            raise RendererError(f"Рендер {renderer.format} вже зареєстровано")
        self._renderers[renderer.format] = renderer

    def get(self, render_format: RenderFormat | str) -> SheetRenderer:
        try:
            key = RenderFormat(render_format)
        except ValueError as exc:
            raise RendererError(f"Невідомий формат: {render_format!r}") from exc
        try:
            return self._renderers[key]
        except KeyError as exc:
            raise RendererError(f"Формат {key} не зареєстровано") from exc

    def formats(self) -> list[RenderFormat]:
        return sorted(self._renderers, key=lambda fmt: fmt.value)

    def available(self) -> list[RenderFormat]:
        """Лише ті формати, які справді віддадуть файл у цьому середовищі."""
        return sorted(
            (fmt for fmt, renderer in self._renderers.items() if renderer.available()),
            key=lambda fmt: fmt.value,
        )
