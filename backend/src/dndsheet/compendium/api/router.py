"""HTTP-шар довідника: тонка обгортка над `CompendiumService`.

Ніяких правил тут немає: параметри валідуються, помилки перекладаються в
HTTP-коди, відповідь серіалізується. Усе, що можна перевірити тестом без
HTTP, перевіряється на рівні сервісу.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from dndsheet.compendium.api.serializers import (
    background_mechanics_full,
    class_mechanics_full,
    entry_brief,
    entry_full,
    species_mechanics_full,
)
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.domain.entry import Category
from dndsheet.compendium.domain.query import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    EntryQuery,
    Page,
)
from dndsheet.shared.errors import NotFoundError, ValidationError

router = APIRouter(prefix="/api/v1/compendium", tags=["compendium"])


def get_service(request: Request) -> CompendiumService:
    service = getattr(request.app.state, "compendium", None)
    if service is None:  # pragma: no cover — так не буває, якщо app зібрано create_app
        raise HTTPException(status_code=503, detail="довідник не завантажено")
    return service


Service = Annotated[CompendiumService, Depends(get_service)]


@router.get("/summary")
def summary(service: Service) -> dict:
    """Зведення: скільки записів, по яких категоріях і книгах."""
    report = service.summary()
    return {
        "entries": report.entries,
        "categories": [
            {"category": category.value, "entries": count}
            for category, count in report.categories
        ],
        "books": [
            {"source_id": book.source_id, "title": book.title, "entries": book.entries}
            for book in report.books
        ],
        "spell_lists": report.spell_lists,
        "mechanics": report.mechanics,
        "warnings": list(report.warnings),
    }


@router.get("/mechanics")
def mechanics_summary(service: Service) -> dict:
    """Зведення механік: скільки класів, видів і передісторій є з числами."""
    classes = service.class_definitions()
    species = service.species_list()
    backgrounds = service.backgrounds()
    return {
        "available": service.mechanics_available(),
        "classes": len(classes),
        "species": len(species),
        "subspecies": len(
            [item for name in species for item in service.subspecies_of(name.key)]
        ),
        "backgrounds": len(backgrounds),
        "warnings": list(service.mechanics_warnings()),
    }


@router.get("/classes/mechanics")
def class_mechanics_list(service: Service) -> dict:
    """Усі класи з механіками — для екрана вибору класу."""
    items = [class_mechanics_full(item) for item in service.class_definitions()]
    return {"items": items, "total": len(items)}


@router.get("/classes/{class_name}/mechanics")
def class_mechanics(class_name: str, service: Service) -> dict:
    """Механіки одного класу: хіт-дайс, володіння, слоти, риси за рівнями."""
    try:
        return class_mechanics_full(service.class_mechanics(class_name))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/species")
def species(service: Service) -> dict:
    """Базові види з механіками (підраси — окремим запитом)."""
    items = [species_mechanics_full(item) for item in service.species_list()]
    return {"items": items, "total": len(items)}


@router.get("/species/{species_name}/subspecies")
def subspecies(species_name: str, service: Service) -> dict:
    items = [species_mechanics_full(item) for item in service.subspecies_of(species_name)]
    return {"items": items, "total": len(items)}


@router.get("/species/{species_name}/mechanics")
def species_mechanics(species_name: str, service: Service) -> dict:
    try:
        return species_mechanics_full(service.species_mechanics(species_name))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/backgrounds")
def backgrounds(service: Service) -> dict:
    items = [background_mechanics_full(item) for item in service.backgrounds()]
    return {"items": items, "total": len(items)}


@router.get("/backgrounds/{background_name}/mechanics")
def background_mechanics(background_name: str, service: Service) -> dict:
    try:
        return background_mechanics_full(service.background_mechanics(background_name))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/entries")
def entries(
    service: Service,
    category: Category | None = None,
    source_id: str | None = None,
    q: str | None = None,
    level: Annotated[int | None, Query(ge=0, le=9)] = None,
    school: str | None = None,
    feature_type: str | None = None,
    item_type: str | None = None,
    rarity: str | None = None,
    magical: bool | None = None,
    subclass_of: str | None = None,
    edition: str | None = None,
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """Записи довідника з фільтрами. Текст книги — лише в картці запису."""
    query = _query(
        category=category,
        source_id=source_id,
        q=q,
        level=level,
        school=school,
        feature_type=feature_type,
        item_type=item_type,
        rarity=rarity,
        magical=magical,
        subclass_of=subclass_of,
        edition=edition,
        status=status,
        limit=limit,
        offset=offset,
    )
    return _page(service.entries(query))


@router.get("/entries/{entry_id:path}")
def entry(entry_id: str, service: Service) -> dict:
    try:
        return entry_full(service.entry(entry_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/classes")
def classes(service: Service) -> dict:
    items = [
        {
            **entry_brief(summary.entry),
            "subclasses": summary.subclasses,
        }
        for summary in service.classes()
    ]
    return {"items": items, "total": len(items)}


@router.get("/classes/{class_name}/subclasses")
def subclasses(class_name: str, service: Service) -> dict:
    items = [entry_brief(subclass) for subclass in service.subclasses(class_name)]
    return {"items": items, "total": len(items)}


@router.get("/classes/{class_name}/spells")
def class_spells(
    class_name: str,
    service: Service,
    max_level: Annotated[int, Query(ge=0, le=9)] = 9,
) -> dict:
    result = service.class_spells(class_name, max_level=max_level)
    items = [entry_brief(spell) for spell in result.spells]
    return {
        "class_name": result.class_name,
        "source": result.source,
        "items": items,
        "total": len(items),
    }


@router.get("/spells")
def spells(
    service: Service,
    level: Annotated[int | None, Query(ge=0, le=9)] = None,
    school: str | None = None,
    class_name: str | None = None,
    q: str | None = None,
) -> dict:
    page = service.spells(level=level, school=school, class_name=class_name, query=q)
    return _page(page)


@router.get("/optional-features")
def optional_features(service: Service, feature_type: str | None = None) -> dict:
    items = [entry_brief(entry) for entry in service.optional_features(feature_type)]
    return {"items": items, "total": len(items)}


@router.get("/items")
def items(
    service: Service,
    item_type: str | None = None,
    rarity: str | None = None,
    magical: bool | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    query = _query(
        category=Category.ITEM,
        item_type=item_type,
        rarity=rarity,
        magical=magical,
        q=q,
        limit=limit,
        offset=offset,
    )
    return _page(service.entries(query))


def _query(**kwargs: object) -> EntryQuery:
    try:
        return EntryQuery(**kwargs)  # type: ignore[arg-type]
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _page(page: Page) -> dict:
    return {
        "items": [entry_brief(entry) for entry in page.items],
        "total": page.total,
        "limit": page.limit,
        "offset": page.offset,
        "has_more": page.has_more,
    }
