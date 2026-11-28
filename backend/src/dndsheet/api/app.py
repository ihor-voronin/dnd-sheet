"""HTTP API (FastAPI). Тонкий шар: валідація, композиція, віддача SPA."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.auth.routes import build_metadata
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.transport_security import TransportSecuritySettings
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from dndsheet.assistant.server import build_server
from dndsheet.characters.api.attacks import attacks_for
from dndsheet.characters.api.knowledge import router as knowledge_router
from dndsheet.characters.api.router import build_cases
from dndsheet.characters.api.router import router as characters_router
from dndsheet.characters.api.sharing import router as sharing_router
from dndsheet.characters.application.level_up import LevelUpService
from dndsheet.characters.application.sheet import SheetService
from dndsheet.characters.application.wizard import WizardService
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.infrastructure.compendium_rules import (
    CompendiumFeatCatalog,
    CompendiumRulesSource,
    CompendiumSubclassCatalog,
)
from dndsheet.characters.infrastructure.json_store import default_data_dir
from dndsheet.characters.infrastructure.sqlite_store import (
    SqliteCharacterRepository,
    SqliteDraftRepository,
    SqliteShareRepository,
    SqliteStore,
)
from dndsheet.compendium.api.router import router as compendium_router
from dndsheet.compendium.infrastructure.factory import build_service
from dndsheet.export.application.registry import RendererRegistry
from dndsheet.export.domain.renderer import RendererError, RendererUnavailable, RenderOptions
from dndsheet.export.infrastructure.markdown_renderer import MarkdownRenderer
from dndsheet.export.infrastructure.pdf_renderer import PdfRenderer
from dndsheet.identity.api.oauth_provider import SiteOAuthProvider
from dndsheet.identity.api.oauth_router import router as oauth_router
from dndsheet.identity.api.router import LOCAL_USER, auth_enabled
from dndsheet.identity.api.router import router as auth_router
from dndsheet.identity.application.auth import AuthService, LoginResult
from dndsheet.identity.application.oauth import OAuthService
from dndsheet.identity.domain.oauth import SCOPES
from dndsheet.identity.infrastructure.client_metadata import fetch_client_metadata
from dndsheet.identity.infrastructure.sqlite_identity import SqliteIdentityStore
from dndsheet.identity.infrastructure.sqlite_oauth import SqliteOAuthStore
from dndsheet.sheets.application.demo import build_demo_character, build_demo_document
from dndsheet.site.api.router import router as site_router
from dndsheet.visuals.api.router import router as visuals_router


def _default_spa_dist() -> Path:
    # backend/src/dndsheet/api/app.py -> repo root
    return Path(__file__).resolve().parents[4] / "frontend" / "dist"


def _build_registry() -> RendererRegistry:
    registry = RendererRegistry()
    registry.register(MarkdownRenderer())
    registry.register(PdfRenderer())
    return registry


def public_url() -> str:
    """Адреса сайту ззовні: з неї — адреса MCP, видавець токенів і посилання для гравця."""
    return os.environ.get("DNDSHEET_PUBLIC_URL", "http://localhost:8000").strip().rstrip("/")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    # MCP у режимі без стану, але менеджеру сесій SDK потрібна своя група задач.
    server = getattr(app.state, "mcp", None)
    if server is None:  # pragma: no cover — create_app завжди збирає MCP
        yield
        return
    async with server.session_manager.run():
        yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="dndsheet",
        version="0.1.0",
        description="D&D 5e (2014) character sheet builder, Ukrainian",
        lifespan=_lifespan,
    )
    renderers = _build_registry()
    app.state.renderers = renderers

    # Довідник завантажується один раз на застосунок: 3818 записів у памʼяті
    # дешевші за будь-який кеш на диску. Немає корпусу — сервіс порожній,
    # `/summary` чесно про це скаже.
    compendium = build_service()
    app.state.compendium = compendium
    rules = CompendiumRulesSource(compendium)
    app.state.rules = rules
    # Чернетки й персонажі — у базі SQLite `var/dndsheet.sqlite3` з власником;
    # старі файли `var/characters/*.json` переносяться туди один раз і лишаються
    # як резервна копія. Каталог можна перевизначити `DNDSHEET_DATA_DIR`.
    data_dir = default_data_dir()
    database = data_dir / "dndsheet.sqlite3"
    store = SqliteStore(database)
    store.import_json_once(data_dir / "characters", data_dir / "drafts")
    characters = SqliteCharacterRepository(store, rules)
    drafts = SqliteDraftRepository(store, rules)
    app.state.characters = characters
    app.state.drafts = drafts
    app.state.shares = SqliteShareRepository(store)
    _configure_auth(app, database, store)
    app.state.wizard = WizardService(
        drafts=drafts,
        characters=characters,
        rules=rules,
        subclasses=CompendiumSubclassCatalog(compendium),
        feats=CompendiumFeatCatalog(compendium),
    )
    app.state.sheet = SheetService(characters=characters)
    app.state.level_up = LevelUpService(
        characters=characters,
        subclasses=CompendiumSubclassCatalog(compendium),
        feats=CompendiumFeatCatalog(compendium),
    )
    # Кеш профілів зброї: імена не змінюються, тому читаємо довідник раз.
    app.state.attack_cache = {}
    # Кеш коротких даних заклять (час, дистанція, урон) для вкладки «Дії».
    app.state.spell_cache = {}
    # Кеш текстів умінь класів і підкласів для вкладки «Уміння».
    app.state.feature_cache = {}
    # Кеш опису передісторій для однойменної вкладки.
    app.state.background_cache = {}
    # Кеш описів і особливостей видів (тексти книг не змінюються).
    app.state.species_cache = {}
    # Еталонні персонажі рахуються на старті: якщо корпусу немає, список
    # порожній, і `/golden` віддає `items: []`, а не 500.
    app.state.golden_cases = build_cases(compendium)

    app.include_router(auth_router)
    app.include_router(oauth_router)
    app.include_router(compendium_router)
    app.include_router(knowledge_router)
    app.include_router(sharing_router)
    app.include_router(characters_router)
    app.include_router(visuals_router)

    # HEAD too: uptime checks (the README badge via shields.io) send HEAD, not GET.
    @app.api_route("/healthz", methods=["GET", "HEAD"], tags=["ops"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/renderers", tags=["export"])
    def list_renderers() -> dict[str, list[str]]:
        """Зареєстровані формати й ті, що справді працюють у цьому середовищі."""
        return {
            "formats": [fmt.value for fmt in renderers.formats()],
            "available": [fmt.value for fmt in renderers.available()],
        }

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

    # MCP, OAuth і сторінки довідника — до SPA: StaticFiles на «/» забрав би їхні адреси собі.
    dist = Path(os.environ.get("DNDSHEET_SPA_DIST", _default_spa_dist()))
    app.state.spa_dist = dist
    _configure_mcp(app, database, dist / "index.html")
    _configure_crawlers(app)
    app.include_router(site_router)
    _configure_spa_paths(app, dist / "index.html")

    if dist.is_dir():
        # TODO(етап 3): SPA-fallback на index.html для клієнтських маршрутів.
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="spa")

    return app


def _configure_auth(app: FastAPI, database: Path, store: SqliteStore) -> None:
    """Вхід через Telegram (токен і імʼя бота — із середовища) і хто володіє старими персонажами.

    Персонажі, перенесені з файлів, не мають власника. Їх отримує власник
    застосунку: користувач із `DNDSHEET_OWNER_TELEGRAM_ID`, а якщо змінну не
    задано — перший зареєстрований. Без входу (`DNDSHEET_AUTH=off`) усе
    належить локальному гравцю.
    """
    identity = SqliteIdentityStore(database)
    app.state.auth_enabled = auth_enabled()
    app.state.telegram_bot = os.environ.get("DNDSHEET_TELEGRAM_BOT", "").strip().lstrip("@")
    app.state.auth = AuthService(
        users=identity,
        sessions=identity,
        bot_token=os.environ.get("DNDSHEET_TELEGRAM_BOT_TOKEN", "").strip(),
        dev_login_enabled=os.environ.get("DNDSHEET_DEV_LOGIN", "").strip() in {"1", "true", "on", "yes"},
    )
    if not app.state.auth_enabled:
        store.claim_unowned(LOCAL_USER.id)
        return
    owner_raw = os.environ.get("DNDSHEET_OWNER_TELEGRAM_ID", "").strip()

    def on_login(result: LoginResult) -> None:
        if owner_raw:
            if str(result.user.telegram_id) == owner_raw:
                store.claim_unowned(result.user.id)
        elif result.created and identity.count() == 1:
            store.claim_unowned(result.user.id)

    app.state.on_login = on_login


#: Що не для пошуковиків: протокол OAuth, MCP, вхід і чужі листи за посиланням.
_DISALLOW = (
    "/authorize",
    "/token",
    "/register",
    "/revoke",
    "/mcp",
    "/api/v1/auth/",
    "/api/v1/oauth/",
    "/api/v1/shared/",
)


def _configure_crawlers(app: FastAPI) -> None:
    """robots.txt; карта сайту (`/sitemap.xml`) — у `site.api.router`, вона знає всі сторінки довідника.

    Ботів ІІ-пошуку не відганяємо: довідник українською — те, що варто знаходити.
    Решта API відкрита: рендер головної пошуковиком теж читає дані через API.
    """
    base = public_url()
    robots = "\n".join(
        [
            "User-agent: *",
            *(f"Disallow: {path}" for path in _DISALLOW),
            "",
            f"Sitemap: {base}/sitemap.xml",
            "",
        ]
    )

    @app.get("/robots.txt", include_in_schema=False)
    def robots_txt() -> PlainTextResponse:
        return PlainTextResponse(robots, headers={"Cache-Control": "public, max-age=3600"})


#: Сторінки SPA зі справжньою адресою (решта — `#/…`): їх віддає той самий index.html.
SPA_PATHS = ("/bugs",)


def _configure_spa_paths(app: FastAPI, index: Path) -> None:
    """`/bugs` відкривається напряму: сервер віддає SPA, а маршрут SPA читає `location.pathname`."""

    def spa_page() -> Response:
        if not index.is_file():
            raise HTTPException(status_code=404, detail="SPA не зібрано")
        return FileResponse(index, media_type="text/html", headers={"Cache-Control": "no-cache"})

    for path in SPA_PATHS:
        app.add_api_route(path, spa_page, methods=["GET", "HEAD"], include_in_schema=False)


class _BrowserOrMcp:
    """`/mcp` для людей — сторінка SPA про асистента, для клієнтів MCP — сам протокол.

    Браузер просить `text/html`; клієнт MCP — `application/json` чи `text/event-stream`
    і ніколи не HTML. Тож одна адреса й для посилань, і для підключення.
    """

    def __init__(self, mcp_app: ASGIApp, index: Path) -> None:
        self.mcp_app = mcp_app
        self.index = index

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in {"GET", "HEAD"} and self.index.is_file():
            accept = dict(scope.get("headers") or ()).get(b"accept", b"").decode("latin-1")
            if "text/html" in accept:
                page = FileResponse(self.index, media_type="text/html", headers={"Cache-Control": "no-cache"})
                await page(scope, receive, send)
                return
        await self.mcp_app(scope, receive, send)


def _configure_mcp(app: FastAPI, database: Path, index: Path) -> None:
    """MCP на `/mcp` і сайт як сервер авторизації для застосунків (ADR 0005).

    Без входу (`DNDSHEET_AUTH=off`) — MCP без токенів від імені локального гравця.
    """
    base = public_url()
    resource = f"{base}/mcp"
    auth = provider = None
    if app.state.auth_enabled:
        store = SqliteOAuthStore(database)
        service = OAuthService(store=store, issuer=base, resource=resource)
        provider = SiteOAuthProvider(
            service=service,
            store=store,
            consent_url=f"{base}/#/oauth/",
            fetch_metadata=fetch_client_metadata,
        )
        auth = AuthSettings(
            # Рядками, а не AnyHttpUrl(...): так модель зберігає адресу без кінцевої «/».
            issuer_url=base,
            resource_server_url=resource,
            required_scopes=list(SCOPES),
            client_registration_options=ClientRegistrationOptions(
                enabled=True, valid_scopes=list(SCOPES), default_scopes=list(SCOPES)
            ),
            revocation_options=RevocationOptions(enabled=True),
            validate_token_resource=True,
        )
        app.state.oauth = service
        app.state.oauth_provider = provider
        # Метадані сервера авторизації — свої: SDK не оголошує опис застосунку за адресою (CIMD)
        # і публічних клієнтів (`none`), а ми підтримуємо обидва.
        metadata = build_metadata(
            auth.issuer_url, None, auth.client_registration_options, auth.revocation_options
        ).model_copy(
            update={
                "client_id_metadata_document_supported": True,
                "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"],
            }
        )
        document = {**metadata.model_dump(mode="json", exclude_none=True), "issuer": base}

        # Опис ресурсу (RFC 9728) — теж свій: SDK додає до адреси видавця «/», а клієнт MCP
        # порівнює видавця з `issuer` метаданих буквально — і відмовився б.
        protected = {
            "resource": resource,
            "authorization_servers": [base],
            "scopes_supported": list(SCOPES),
            "bearer_methods_supported": ["header"],
            "resource_name": "dnd-sheet",
        }

        @app.get("/.well-known/oauth-authorization-server", include_in_schema=False)
        def authorization_server_metadata() -> JSONResponse:
            return JSONResponse(document, headers={"Access-Control-Allow-Origin": "*"})

        @app.get("/.well-known/oauth-protected-resource/mcp", include_in_schema=False)
        @app.get("/.well-known/oauth-protected-resource", include_in_schema=False)
        def protected_resource_metadata() -> JSONResponse:
            return JSONResponse(protected, headers={"Access-Control-Allow-Origin": "*"})

    # З провайдером SDK сам перевіряє токени через нього (`ProviderTokenVerifier`).
    server = build_server(app, public_url=base, auth=auth, provider=provider)
    host = urlsplit(base).netloc
    mcp_app = server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        host=host,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[host],
            allowed_origins=[base],
        ),
    )
    app.state.mcp = server
    taken = {route.path for route in app.router.routes if isinstance(route, Route)}
    for route in mcp_app.routes:
        path = getattr(route, "path", None)
        if path and path not in taken:
            # Увесь застосунок SDK як кінцева точка: він сам маршрутизує й тримає свої middleware.
            app.router.routes.append(Route(path, endpoint=_BrowserOrMcp(mcp_app, index)))


def _demo_document(app: FastAPI):
    """Демо-документ; без корпусу — чесна відповідь 503, а не вигадані правила."""
    cases = app.state.golden_cases
    if not cases:
        raise HTTPException(
            status_code=503,
            detail="немає корпусу механік: демо-лист не з чого зібрати",
        )
    character = build_demo_character(app.state.rules)
    computed = DerivedStatsCalculator().compute(character)
    attacks = attacks_for(character, computed, app.state.compendium, app.state.attack_cache)
    return build_demo_document(app.state.rules, attacks)
