"""HTTP API (FastAPI). Тонкий шар: валідація, композиція, віддача SPA."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles

from dndsheet.characters.api.router import build_cases, router as characters_router
from dndsheet.characters.infrastructure.compendium_rules import CompendiumRulesSource
from dndsheet.compendium.api.router import router as compendium_router
from dndsheet.compendium.infrastructure.factory import build_service
from dndsheet.export.application.registry import RendererRegistry
from dndsheet.export.domain.renderer import RenderOptions, RendererError, RendererUnavailable
from dndsheet.export.infrastructure.markdown_renderer import MarkdownRenderer
from dndsheet.export.infrastructure.pdf_renderer import PdfRenderer
from dndsheet.sheets.application.demo import build_demo_document


def _default_spa_dist() -> Path:
    # backend/src/dndsheet/api/app.py -> repo root
    return Path(__file__).resolve().parents[4] / "frontend" / "dist"


def _build_registry() -> RendererRegistry:
    registry = RendererRegistry()
    registry.register(MarkdownRenderer())
    registry.register(PdfRenderer())
    return registry


def create_app() -> FastAPI:
    app = FastAPI(
        title="dndsheet",
        version="0.1.0",
        description="D&D 5e (2014) character sheet builder, Ukrainian",
    )
    renderers = _build_registry()
    app.state.renderers = renderers

    # Довідник завантажується один раз на застосунок: 3818 записів у памʼяті
    # дешевші за будь-який кеш на диску. Немає корпусу — сервіс порожній,
    # `/summary` чесно про це скаже.
    compendium = build_service()
    app.state.compendium = compendium
    app.state.rules = CompendiumRulesSource(compendium)
    # Еталонні персонажі рахуються на старті: якщо корпусу немає, список
    # порожній, і `/golden` віддає `items: []`, а не 500.
    app.state.golden_cases = build_cases(compendium)

    app.include_router(compendium_router)
    app.include_router(characters_router)

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/renderers", tags=["export"])
    def list_renderers() -> dict[str, list[str]]:
        return {"formats": [fmt.value for fmt in renderers.formats()]}

    @app.get("/api/v1/demo/sheet", tags=["demo"])
    def demo_sheet() -> dict:
        """Демонстраційний SheetDocument (не контент із книг)."""
        return _demo_document(app).to_contract_dict()

    @app.get("/api/v1/demo/export/{render_format}", tags=["demo"])
    def demo_export(render_format: str) -> Response:
        try:
            renderer = renderers.get(render_format)
        except RendererError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        try:
            result = renderer.render(_demo_document(app), RenderOptions())
        except RendererUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except RendererError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return Response(
            content=result.content,
            media_type=result.media_type,
            headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
        )

    dist = Path(os.environ.get("DNDSHEET_SPA_DIST", _default_spa_dist()))
    if dist.is_dir():
        # TODO(етап 3): SPA-fallback на index.html для клієнтських маршрутів.
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="spa")

    return app


def _demo_document(app: FastAPI):
    """Демо-документ; без корпусу — чесна відповідь 503, а не вигадані правила."""
    cases = app.state.golden_cases
    if not cases:
        raise HTTPException(
            status_code=503,
            detail="немає корпусу механік: демо-лист не з чого зібрати",
        )
    return build_demo_document(app.state.rules)
