"""Поділитися персонажем: посилання «лише читати», без входу.

Хто має посилання (`/#/s/<токен>`), бачить той самий лист, що й власник, і може
його надрукувати чи завантажити PDF, але змінити нічого не може: тут лише
GET-ендпоінти. Токен — випадковий (`secrets.token_urlsafe`), одне посилання на
персонажа; власник створює нове (старе перестає працювати) або відкликає його.

Невідомий чи відкликаний токен — 404 без пояснень, чий це був лист.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from dndsheet.characters.api.router import (
    _print_renderer,
    _print_view,
    _sheet_payload,
    _wizard,
)
from dndsheet.export.domain.renderer import RenderOptions, RendererError, RendererUnavailable
from dndsheet.shared.errors import DomainError

router = APIRouter(prefix="/api/v1/shared", tags=["sharing"])


def _character(request: Request, token: str):  # noqa: ANN202 — Character
    character_id = request.app.state.shares.character_of(token)
    if character_id is None:
        raise HTTPException(status_code=404, detail="посилання недійсне або його відкликали")
    try:
        return _wizard(request).character(character_id)
    except DomainError as exc:
        raise HTTPException(status_code=404, detail="посилання недійсне або його відкликали") from exc


@router.get("/{token}")
def shared_sheet(token: str, request: Request) -> dict[str, Any]:
    """Лист для перегляду: ті самі дані, що й у власника, але без жодних змін."""
    return {"sheet": _sheet_payload(request, _character(request, token)), "read_only": True}


@router.get("/{token}/version")
def shared_version(token: str, request: Request) -> dict[str, int]:
    """Номер версії: відкрита сторінка оновлюється, коли власник змінює лист."""
    character = _character(request, token)
    return {"version": character.version}


@router.get("/{token}/print", response_class=HTMLResponse)
def shared_print(token: str, request: Request, originals: bool = True, detailed: bool = True) -> HTMLResponse:
    character = _character(request, token)
    html = _print_renderer(request).character_html(
        _print_view(request, character), RenderOptions(show_originals=originals), detailed=detailed
    )
    return HTMLResponse(html)


@router.get("/{token}/export/pdf")
def shared_pdf(token: str, request: Request, originals: bool = True, detailed: bool = True) -> Response:
    character = _character(request, token)
    try:
        result = _print_renderer(request).render_character(
            _print_view(request, character), RenderOptions(show_originals=originals), detailed=detailed
        )
    except RendererUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RendererError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    name = quote(f"{character.name or 'character'}.pdf")
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={"Content-Disposition": f"attachment; filename=\"character-sheet.pdf\"; filename*=UTF-8''{name}"},
    )
