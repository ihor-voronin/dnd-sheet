"""Відкриті сторінки для людей і пошуковиків: довідник `/kb/...`, глосарій, посібник, карта сайту.

Сторінки малює сервер (Jinja), без SPA: текст запису є в HTML одразу, сторінка
легка й читається без JavaScript. Каталог (`KbCatalog`) збирається з тих
самих даних, що й візард, при першому зверненні й живе в памʼяті процесу.

Що індексувати, вирішує `site.domain.publication` (ліцензія × політика
`DNDSHEET_KB_PROPRIETARY`); сторінки поза індексом мають `noindex` і в карту
сайту не потрапляють.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Iterable, Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from dndsheet.characters.api import knowledge
from dndsheet.characters.api.router import class_features, subclass_details
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.domain.entry import Category, CompendiumEntry
from dndsheet.compendium.domain.query import MAX_LIMIT, EntryQuery
from dndsheet.shared.errors import DomainError
from dndsheet.site.api import pages, visuals
from dndsheet.site.application.catalog import SECTION_BY_ID, SECTIONS, KbCatalog, Record
from dndsheet.site.application.labels import Labels
from dndsheet.site.domain.publication import Policy
from dndsheet.site.infrastructure.files import load_json, load_terminology
from dndsheet.visuals.application import emblems
from dndsheet.visuals.domain.catalog import CLASS_UK

log = logging.getLogger(__name__)

router = APIRouter(include_in_schema=False)

_HERE = Path(__file__).resolve().parent
_ENV = Environment(
    loader=FileSystemLoader(_HERE / "templates"),
    autoescape=select_autoescape(["html", "jinja"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_CSS = (_HERE / "static" / "site.css").read_text(encoding="utf-8")
_LOCK = threading.Lock()

#: Сторінки довідника змінюються лише з новою версією застосунку.
_CACHE = "public, max-age=3600, stale-while-revalidate=86400"

#: Сторінки поза довідником, що варто знаходити (карта сайту й `llms.txt`).
STATIC_PAGES: tuple[tuple[str, str], ...] = (
    ("/kb/glossary", "Глосарій D&D 5e: терміни українською з поясненнями"),
    ("/guides/create-character", "Як створити персонажа D&D 5e: покроковий посібник"),
)

_CATEGORIES = (
    Category.SPELL,
    Category.FEAT,
    Category.OPTIONAL_FEATURE,
    Category.ITEM,
    Category.SUBCLASS,
    Category.SPECIES,
    Category.CLASS,
    Category.BACKGROUND,
)


def public_base() -> str:
    return os.environ.get("DNDSHEET_PUBLIC_URL", "http://localhost:8000").strip().rstrip("/")


def spa_dist() -> Path:
    return Path(os.environ.get("DNDSHEET_SPA_DIST") or Path(__file__).resolve().parents[5] / "frontend" / "dist")


def _dist(request: Request) -> Path:
    """Тека SPA, з якою зібрано застосунок (`create_app` кладе її в `app.state.spa_dist`)."""
    return Path(getattr(request.app.state, "spa_dist", None) or spa_dist())


def labels_path(request: Request) -> Path:
    """`kb-labels.json` кладе збірка SPA поруч з `index.html` (frontend/scripts/export-kb-labels.mjs)."""
    explicit = os.environ.get("DNDSHEET_KB_LABELS")
    return Path(explicit) if explicit else _dist(request) / "kb-labels.json"


_UNICODE = {
    "cyrillic": "U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116",
    "latin": "U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, "
    "U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD",
}


@lru_cache(maxsize=4)
def _font_faces(assets: str) -> str:
    """Alegreya з тієї самої збірки SPA (`/assets/*`, кеш на рік): сторінки виглядають як застосунок.

    Назви файлів із хешем, тож шукаємо їх у теці; немає збірки — системні шрифти з `site.css`.
    """
    faces = []
    folder = Path(assets)
    for family, prefix in (("Alegreya", "alegreya"), ("Alegreya Sans", "alegreya-sans")):
        for weight in (400, 700):
            for subset, ranges in _UNICODE.items():
                found = sorted(folder.glob(f"{prefix}-{subset}-{weight}-normal-*.woff2"))
                if found:
                    faces.append(
                        f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};"
                        f"font-display:swap;src:url(/assets/{found[0].name}) format('woff2');unicode-range:{ranges}}}"
                    )
    return "\n".join(faces)


# ---------------------------------------------------------------------------
# каталог
# ---------------------------------------------------------------------------


def _all_entries(service: CompendiumService, category: Category) -> list[CompendiumEntry]:
    items: list[CompendiumEntry] = []
    offset = 0
    while True:
        page = service.entries(EntryQuery(category=category, limit=MAX_LIMIT, offset=offset))
        items.extend(page.items)
        if not page.has_more:
            return items
        offset += MAX_LIMIT


def _safe(load: Any, *args: Any) -> list[dict[str, Any]]:
    """Без корпусу дані візарда порожні або падають — сторінки тоді просто порожні."""
    try:
        return list(load(*args)["items"])
    except (DomainError, KeyError, LookupError, ValueError) as exc:  # pragma: no cover — лише без корпусу
        log.warning("довідник: %s", exc)
        return []


def catalog(request: Request) -> KbCatalog:
    state = request.app.state
    built = getattr(state, "kb_catalog", None)
    if built is not None:
        return built
    with _LOCK:
        built = getattr(state, "kb_catalog", None)
        if built is not None:
            return built
        service: CompendiumService = state.compendium
        classes = _safe(knowledge.classes, request)
        class_spells: dict[str, list[str]] = {}
        for item in classes:
            try:
                class_spells[item["key"]] = [spell.name_en for spell in service.class_spells(item["key"]).spells]
            except DomainError:  # pragma: no cover — клас без списку заклять
                continue
        built = KbCatalog(
            labels=Labels(load_json(labels_path(request))),
            policy=Policy.parse(os.environ.get("DNDSHEET_KB_PROPRIETARY")),
            entries={category: _all_entries(service, category) for category in _CATEGORIES},
            species=_safe(knowledge.species, request),
            classes=classes,
            backgrounds=_safe(knowledge.backgrounds, request),
            class_spells=class_spells,
        )
        state.kb_catalog = built
        if not built.labels.loaded:
            log.warning("довідник: немає %s — назви видів і класів будуть англійською", labels_path(request))
        return built


def _books(request: Request) -> dict[str, Mapping[str, Any]]:
    cached = getattr(request.app.state, "kb_books", None)
    if cached is None:
        overview = request.app.state.compendium.books_overview()
        cached = {book["id"]: book for book in overview.get("books", ())}
        request.app.state.kb_books = cached
    return cached


def _source(request: Request, record: Record, labels: Labels) -> dict[str, Any]:
    book = _books(request).get(record.source_id) or _books(request).get(record.source_id.lower())
    if book:
        return {
            "title": book.get("title_uk") or book.get("title"),
            "title_en": book.get("title"),
            "url": book.get("url"),
            "license": record.license,
        }
    return {"title": labels.source(record.source_id), "title_en": None, "url": None, "license": record.license}


# ---------------------------------------------------------------------------
# відповіді
# ---------------------------------------------------------------------------


def _glossary_keys(catalog_: KbCatalog) -> set[str]:
    return set(catalog_.labels.glossary())


def _render(request: Request, template: str, *, status: int = 200, index: bool = True, **context: Any) -> HTMLResponse:
    base = public_base()
    css = f"{_font_faces(str(_dist(request) / 'assets'))}\n{_CSS}"
    # Емблеми сторінки: шаблон кличе `emblem(...)`, а форми лише використаних іконок
    # вставляє `sprite.markup()` у кінці `<body>` — без зайвих запитів.
    sprite = emblems.Sprite()
    html = _ENV.get_template(template).render(
        base=base,
        css=css,
        index=index,
        sections=SECTIONS,
        sprite=sprite,
        emblem=lambda name, css="emblem", size=None: Markup(sprite.use(name, css)),
        record_emblem=visuals.record_emblem,
        **context,
    )
    headers = {"Cache-Control": _CACHE}
    if not index:
        headers["X-Robots-Tag"] = "noindex"
    return HTMLResponse(html, status_code=status, headers=headers)


def _not_found(request: Request) -> HTMLResponse:
    return _render(
        request,
        "not_found.html.jinja",
        status=404,
        index=False,
        path=request.url.path,
        meta_title="Сторінку не знайдено — довідник D&D 5e",
        description="Такої сторінки в довіднику немає.",
        crumbs=[pages.Crumb("Головна", "/"), pages.Crumb("Довідник", "/kb")],
    )


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=301, headers={"Cache-Control": _CACHE})


def _breadcrumbs_ld(base: str, crumbs: Iterable[pages.Crumb]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": index, "name": crumb.name, "item": f"{base}{crumb.path}"}
            for index, crumb in enumerate(crumbs, start=1)
        ],
    }


# ---------------------------------------------------------------------------
# маршрути
# ---------------------------------------------------------------------------


@router.api_route("/kb", methods=["GET", "HEAD"])
def kb_home(request: Request) -> HTMLResponse:
    built = catalog(request)
    crumbs = [pages.Crumb("Головна", "/"), pages.Crumb("Довідник", "/kb")]
    return _render(
        request,
        "kb_home.html.jinja",
        path="/kb",
        meta_title="Довідник D&D 5e українською: закляття, класи, раси, предмети",
        description=(
            "Довідник Dungeons & Dragons 5e (2014) українською: закляття, класи й підкласи, раси, передісторії, "
            "риси й предмети — з повним описом. Безкоштовно, без реєстрації."
        ),
        crumbs=crumbs,
        counts=built.counts(),
        subclass_count=sum(len(built.subclasses(klass.slug)) for klass in built.records("classes")),
        static_pages=STATIC_PAGES,
        jsonld=[_breadcrumbs_ld(public_base(), crumbs)],
    )


@router.api_route("/kb/", methods=["GET", "HEAD"])
def kb_home_slash() -> RedirectResponse:
    return _redirect("/kb")


@router.api_route("/kb/glossary", methods=["GET", "HEAD"])
def glossary(request: Request) -> HTMLResponse:
    built = catalog(request)
    entries = sorted(built.labels.glossary().items(), key=lambda pair: str(pair[1].get("term", "")).casefold())
    terminology = load_terminology()
    crumbs = [pages.Crumb("Головна", "/"), pages.Crumb("Довідник", "/kb"), pages.Crumb("Глосарій", "/kb/glossary")]
    base = public_base()
    defined = {
        "@context": "https://schema.org",
        "@type": "DefinedTermSet",
        "name": "Глосарій D&D 5e українською",
        "url": f"{base}/kb/glossary",
        "inLanguage": "uk",
        "hasDefinedTerm": [
            {
                "@type": "DefinedTerm",
                "name": entry.get("term"),
                "alternateName": entry.get("en"),
                "description": entry.get("what"),
                "url": f"{base}/kb/glossary#{key}",
            }
            for key, entry in entries
        ],
    }
    return _render(
        request,
        "glossary.html.jinja",
        path="/kb/glossary",
        meta_title="Глосарій D&D 5e українською: що означають терміни гри",
        description=(
            "Що таке кість хітів, рятівний кидок, клас захисту, перевага, концентрація й комірки заклять — "
            "терміни D&D 5e українською з поясненнями й англійськими відповідниками."
        ),
        crumbs=crumbs,
        entries=entries,
        terminology=terminology,
        jsonld=[_breadcrumbs_ld(base, crumbs), defined],
    )


@router.api_route("/guides/create-character", methods=["GET", "HEAD"])
def guide_create_character(request: Request) -> HTMLResponse:
    built = catalog(request)
    crumbs = [pages.Crumb("Головна", "/"), pages.Crumb("Як створити персонажа", "/guides/create-character")]
    base = public_base()
    article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": "Як створити персонажа D&D 5e",
        "inLanguage": "uk",
        "url": f"{base}/guides/create-character",
        "about": "Створення персонажа Dungeons & Dragons 5e за правилами 2014",
    }
    starters = {
        "species": [
            built.find("species", slug) for slug in ("human", "elf", "dwarf", "halfling", "tiefling", "dragonborn")
        ],
        "classes": built.records("classes"),
        "backgrounds": [
            built.find("backgrounds", slug) for slug in ("acolyte", "criminal", "folk-hero", "sage", "soldier")
        ],
    }
    return _render(
        request,
        "guide_create_character.html.jinja",
        path="/guides/create-character",
        meta_title="Як створити персонажа D&D 5e: покроково українською",
        description=(
            "Покроковий посібник: як створити персонажа D&D 5e за правилами 2014 — раса, клас, характеристики, "
            "передісторія, спорядження й закляття. І безкоштовний лист, що рахує все сам."
        ),
        crumbs=crumbs,
        starters={key: [record for record in value if record] for key, value in starters.items()},
        glossary_keys=_glossary_keys(built),
        jsonld=[_breadcrumbs_ld(base, crumbs), article],
    )


#: Підписи емблем на сторінці подяк.
_EMBLEM_LABELS = {
    **{f"class-{key}": f"клас: {label}" for key, label in CLASS_UK.items()},
    "school-abjuration": "школа: захисна",
    "school-conjuration": "школа: виклик",
    "school-divination": "школа: віщування",
    "school-enchantment": "школа: чари",
    "school-evocation": "школа: втілення",
    "school-illusion": "школа: ілюзія",
    "school-necromancy": "школа: некромантія",
    "school-transmutation": "школа: перетворення",
    **{f"section-{section.id}": f"розділ: {section.label}" for section in SECTIONS},
    "section-glossary": "розділ: глосарій",
    "section-guide": "посібник",
}


@router.api_route("/kb/credits", methods=["GET", "HEAD"])
def credits_page(request: Request) -> HTMLResponse:
    """Звідки картинки: game-icons.net (CC BY 3.0) з авторами, власні портрети, шрифти."""
    crumbs = [pages.Crumb("Головна", "/"), pages.Crumb("Довідник", "/kb"), pages.Crumb("Подяки", "/kb/credits")]
    return _render(
        request,
        "credits.html.jinja",
        path="/kb/credits",
        meta_title="Подяки й ліцензії зображень — довідник D&D 5e",
        description="Автори емблем game-icons.net (CC BY 3.0), власні портрети персонажів і шрифти сайту.",
        crumbs=crumbs,
        credits=emblems.credits(),
        labels=_EMBLEM_LABELS,
        jsonld=[_breadcrumbs_ld(public_base(), crumbs)],
    )


@router.api_route("/kb/{section}", methods=["GET", "HEAD"])
def kb_section(section: str, request: Request) -> Response:
    if section not in SECTION_BY_ID:
        return _not_found(request)
    built = catalog(request)
    info = SECTION_BY_ID[section]
    crumbs = [pages.Crumb("Головна", "/"), pages.Crumb("Довідник", "/kb"), pages.Crumb(info.label, f"/kb/{section}")]
    groups = built.groups(section)
    return _render(
        request,
        "kb_section.html.jinja",
        path=f"/kb/{section}",
        meta_title=info.heading,
        description=f"{info.intro} Українською, {len(built.records(section))} записів.",
        crumbs=crumbs,
        section=info,
        groups=groups,
        catalog=built,
        total=len(built.records(section)),
        jsonld=[_breadcrumbs_ld(public_base(), crumbs)],
    )


@router.api_route("/kb/{section}/", methods=["GET", "HEAD"])
def kb_section_slash(section: str) -> RedirectResponse:
    return _redirect(f"/kb/{section}")


def _entry_response(request: Request, page: pages.EntryPage, built: KbCatalog) -> HTMLResponse:
    return _render(
        request,
        "entry.html.jinja",
        index=page.indexable,
        path=page.record.path,
        meta_title=page.meta_title,
        description=page.description,
        crumbs=page.crumbs,
        page=page,
        portraits=visuals.entry_portraits(page.record),
        glossary_keys=_glossary_keys(built),
        jsonld=[_breadcrumbs_ld(public_base(), page.crumbs)],
    )


@router.api_route("/kb/{section}/{slug}", methods=["GET", "HEAD"])
def kb_entry(section: str, slug: str, request: Request) -> Response:
    if section not in SECTION_BY_ID:
        return _not_found(request)
    built = catalog(request)
    record = built.find(section, slug)
    if record is None:
        target = built.alias(section, slug) or built.alias(section, slug.lower())
        if target:
            return _redirect(f"/kb/{section}/{target}")
        return _not_found(request)
    source = _source(request, record, built.labels)
    if section == "species":
        page = pages.species_page(record, built, source)
    elif section == "classes":
        page = pages.class_page(record, built, _class_features(request, record.data.get("key", slug)), source)
    elif section == "backgrounds":
        page = pages.background_page(record, built, source)
    else:
        page = pages.compendium_page(record, built, source)
    return _entry_response(request, page, built)


@router.api_route("/kb/classes/{class_slug}/{slug}", methods=["GET", "HEAD"])
def kb_subclass(class_slug: str, slug: str, request: Request) -> Response:
    built = catalog(request)
    record = built.subclass(class_slug, slug)
    if record is None or record.entry is None:
        return _not_found(request)
    try:
        details = subclass_details(record.entry.id, request)
    except HTTPException:  # pragma: no cover — підклас є в класі, але не в довіднику
        details = {}
    page = pages.subclass_page(record, built, details, _source(request, record, built.labels))
    return _entry_response(request, page, built)


def _class_features(request: Request, class_key: str) -> list[dict[str, Any]]:
    try:
        return list(class_features(class_key, request)["features"])
    except HTTPException:  # клас без механік: сторінка без умінь за рівнями
        return []


# ---------------------------------------------------------------------------
# карта сайту й llms.txt
# ---------------------------------------------------------------------------

SITEMAP_PARTS = ("pages", *(section.id for section in SECTIONS))


def _urls(built: KbCatalog, part: str) -> list[str]:
    if part == "pages":
        return ["/", "/kb", *(f"/kb/{section.id}" for section in SECTIONS), *(path for path, _ in STATIC_PAGES)]
    records = list(built.records(part))
    if part == "classes":
        records += [sub for klass in built.records("classes") for sub in built.subclasses(klass.slug)]
    return [record.path for record in records if record.publication.index]


def _xml(body: str) -> Response:
    return Response(
        '<?xml version="1.0" encoding="UTF-8"?>\n' + body,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.api_route("/sitemap.xml", methods=["GET", "HEAD"])
def sitemap_index(request: Request) -> Response:
    """Індекс карт: по одній на розділ — у Search Console видно, який розділ не індексується."""
    base = public_base()
    built = catalog(request)
    parts = [part for part in SITEMAP_PARTS if _urls(built, part)]
    rows = "".join(f"  <sitemap><loc>{escape(base)}/sitemaps/{part}.xml</loc></sitemap>\n" for part in parts)
    return _xml(f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}</sitemapindex>\n')


@router.api_route("/sitemaps/{name}.xml", methods=["GET", "HEAD"])
def sitemap_part(name: str, request: Request) -> Response:
    if name not in SITEMAP_PARTS:
        return PlainTextResponse("not found", status_code=404)
    base = public_base()
    urls = _urls(catalog(request), name)
    rows = "".join(f"  <url><loc>{escape(base + path)}</loc></url>\n" for path in urls)
    return _xml(f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}</urlset>\n')


@lru_cache(maxsize=1)
def _llms_header() -> str:
    return (
        "# Лист персонажа D&D 5e українською\n\n"
        "> Безкоштовний неофіційний фанатський сайт для Dungeons & Dragons 5e (правила 2014): "
        "створення персонажа, лист, що сам рахує числа, друк у PDF і довідник українською.\n\n"
    )


@router.api_route("/llms.txt", methods=["GET", "HEAD"])
def llms_txt(request: Request) -> PlainTextResponse:
    """Короткий опис сайту для ІІ-пошуку (llmstxt.org): що тут є й куди дивитись."""
    base = public_base()
    built = catalog(request)
    counts = built.counts()
    lines = [_llms_header(), "## Довідник\n"]
    lines += [
        f"- [{section.heading}]({base}/kb/{section.id}): {counts.get(section.id, 0)} сторінок" for section in SECTIONS
    ]
    lines += ["", "## Посібники\n"]
    lines += [f"- [{title}]({base}{path})" for path, title in STATIC_PAGES]
    lines += [
        "",
        "## Застосунок\n",
        f"- [Створити персонажа]({base}/#/create): покроковий візард",
        f"- [ІІ-асистент (MCP)]({base}/mcp): підключення до Claude",
        "",
    ]
    return PlainTextResponse("\n".join(lines), headers={"Cache-Control": "public, max-age=3600"})
