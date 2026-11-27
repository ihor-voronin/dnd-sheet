"""Порт рендера: усе, що перетворює SheetDocument у байти, реалізує його.

Кожен адаптер (PDF, Markdown, пізніше PNG/VTT) зобовʼязаний пройти
conformance-тести на `contract/fixtures/*.json`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from dndsheet.sheets.domain.document import SheetDocument

CONTRACT_MAJOR = 1


class RenderFormat(StrEnum):
    PDF = "pdf"
    MARKDOWN = "markdown"


class RendererError(Exception):
    """Рендер не вдався з відомої причини."""


class RendererUnavailable(RendererError):
    """Адаптер не може працювати в цьому середовищі (немає залежності)."""


@dataclass(frozen=True, slots=True)
class RenderOptions:
    """Опції рендера.

    `lang` тут немає навмисно: документ уже зібраний українською (це мова
    застосунку), а англійські оригінали лежать у `LocalizedText` для тултіпа.
    Рендер не перекладає — він малює. `show_originals` показує англійський
    підпис поряд з українським, щоб число можна було звірити з книгою.
    """

    show_originals: bool = True
    template: str = "sheet"


@dataclass(frozen=True, slots=True)
class RenderResult:
    format: RenderFormat
    content: bytes
    media_type: str
    filename: str


@runtime_checkable
class SheetRenderer(Protocol):
    format: RenderFormat

    def available(self) -> bool:
        """Чи може адаптер працювати в цьому середовищі (чи є залежності).

        Різниця з «зареєстрований» принципова: PDF без WeasyPrint
        зареєстрований, але віддасть 503, тож UI не має пропонувати кнопку.
        """
        ...

    def render(self, document: SheetDocument, options: RenderOptions | None = None) -> RenderResult: ...


def check_contract(document: SheetDocument) -> None:
    """Major-невідповідність контракту — привід відмовитись рендерити."""
    try:
        major = int(document.schema_version.split(".", 1)[0])
    except (AttributeError, ValueError) as exc:
        raise RendererError(f"Некоректна версія контракту: {document.schema_version!r}") from exc
    if major != CONTRACT_MAJOR:
        raise RendererError(f"Рендер підтримує контракт {CONTRACT_MAJOR}.x, отримано {document.schema_version}")
