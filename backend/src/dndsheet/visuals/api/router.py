"""Портрети: файли SVG і каталог для вибору. Відкрито без входу — це не дані гравця."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from dndsheet.visuals.application import avatars
from dndsheet.visuals.domain import catalog

router = APIRouter(tags=["visuals"])

#: Файл із поточною версією не зміниться ніколи: рік і `immutable`, як у Vite-файлів.
_IMMUTABLE = "public, max-age=31536000, immutable"


@router.get(avatars.PREFIX + "/{version}/{portrait_id}.svg")
def portrait_svg(version: str, portrait_id: str) -> Response:
    body = avatars.svg(portrait_id)
    if body is None:
        raise HTTPException(status_code=404, detail=f"немає портрета {portrait_id!r}")
    # Стара версія в адресі (сторінка з попереднього деплою): віддаємо поточний малюнок,
    # але без довгого кешу — інакше під старою адресою назавжди лишився б новий файл.
    cache = _IMMUTABLE if version == avatars.VERSION else "public, max-age=300"
    return Response(content=body, media_type="image/svg+xml", headers={"Cache-Control": cache})


@router.get("/api/v1/avatars")
def avatar_catalog(response: Response) -> dict:
    """Усі портрети — для вибору з фільтрами. Без адрес: адреса = `base` + id + `.svg`."""
    response.headers["Cache-Control"] = "public, max-age=3600"
    return {
        "version": avatars.VERSION,
        "base": f"{avatars.PREFIX}/{avatars.VERSION}/",
        "groups": [{"key": group.key, "label": group.label} for group in catalog.GROUPS],
        "classes": [{"key": key, "label": catalog.CLASS_UK[key]} for key in catalog.CLASSES],
        "items": [[item.id, item.group, item.gender, item.class_key] for item in catalog.all_portraits()],
        "total": len(catalog.all_portraits()),
    }


@router.get("/api/v1/avatars/recommended")
def recommended_avatars(
    species: str | None = Query(default=None, max_length=120),
    class_key: str | None = Query(default=None, alias="class", max_length=40),
    gender: str | None = Query(default=None, max_length=10),
    limit: int = Query(default=24, ge=1, le=60),
) -> dict:
    """Поради для героя: свій вид і стать, спершу свій клас (20–30 штук)."""
    items = catalog.recommend(species=species, class_key=class_key, gender=gender, limit=limit)
    return {
        "group": catalog.species_group(species),
        "items": [avatars.card(item) for item in items],
    }
