"""HTTP-шар контексту `characters`.

Поки що тут немає збереження персонажів (етап 6) і візарда (етап 3): сервіс
віддає **еталонних** персонажів, порахованих справжніми правилами. Це вже
корисно: видно, що домен рахує правильні числа, і на чому перевіряти фронт.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from dndsheet.characters.api.serializers import computed_sheet
from dndsheet.characters.application.golden import GoldenCase, build_golden_cases
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.infrastructure.compendium_rules import CompendiumRulesSource
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.export.application.registry import RendererRegistry
from dndsheet.export.domain.renderer import RenderOptions, RendererError, RendererUnavailable
from dndsheet.sheets.application.build_document import build_sheet_document

router = APIRouter(prefix="/api/v1/characters", tags=["characters"])


def build_cases(service: CompendiumService) -> tuple[GoldenCase, ...]:
    """Зібрати еталонні листи над справжнім довідником.

    Порожній корпус — не помилка: тоді еталонів немає, а `/golden` чесно
    віддасть порожній список.
    """
    if not service.mechanics_available():
        return ()
    return build_golden_cases(CompendiumRulesSource(service))


def _cases(request: Request) -> tuple[GoldenCase, ...]:
    cases = getattr(request.app.state, "golden_cases", None)
    if cases is None:  # pragma: no cover — так не буває, якщо app зібрано create_app
        raise HTTPException(status_code=503, detail="еталонні персонажі не зібрані")
    return cases


def _registry(request: Request) -> RendererRegistry:
    registry = getattr(request.app.state, "renderers", None)
    if registry is None:  # pragma: no cover
        raise HTTPException(status_code=503, detail="рендери не зібрані")
    return registry


def _find(cases: tuple[GoldenCase, ...], key: str) -> GoldenCase:
    wanted = key.strip().casefold()
    for case in cases:
        if case.key == wanted:
            return case
    raise HTTPException(status_code=404, detail=f"немає еталонного персонажа {key!r}")


def _payload(case: GoldenCase) -> dict:
    computed = DerivedStatsCalculator().compute(case.character)
    return {
        "key": case.key,
        "title_uk": case.title_uk,
        "summary_uk": case.summary_uk,
        "sheet": computed_sheet(case.character, computed),
    }


@router.get("/golden")
def golden(request: Request) -> dict:
    """Еталонні персонажі з повністю обчисленим листом."""
    items = [_payload(case) for case in _cases(request)]
    return {"items": items, "total": len(items)}


@router.get("/golden/{key}")
def golden_case(key: str, request: Request) -> dict:
    return _payload(_find(_cases(request), key))


@router.get("/golden/{key}/export/{render_format}")
def golden_export(key: str, render_format: str, request: Request) -> Response:
    """Експорт еталонного листа тим самим рендером, що й решта."""
    case = _find(_cases(request), key)
    computed = DerivedStatsCalculator().compute(case.character)
    document = build_sheet_document(case.character, computed)
    try:
        renderer = _registry(request).get(render_format)
    except RendererError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        result = renderer.render(document, RenderOptions())
    except RendererUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RendererError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )
