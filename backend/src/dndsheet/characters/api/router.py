"""HTTP-шар контексту `characters`.

Три групи маршрутів:

* `/golden` — еталонні персонажі, пораховані справжніми правилами: на них
  видно, що домен рахує правильно;
* `/wizard` — створення персонажа: чернетка, кроки, фініш. Крок повертає і
  свої `options` (що можна обрати), і `answers` (що вже обрано), щоб екран
  лише малював і надсилав назад;
* `/{character_id}` — збережений персонаж.

Порядок реєстрації важливий: `/wizard` і `/golden` оголошені раніше за
`/{character_id}`, інакше «wizard» читався б як ідентифікатор персонажа.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request, Response

from dndsheet.characters.api.serializers import (
    character_brief,
    computed_sheet,
    draft_payload,
    step_answers,
)
from dndsheet.characters.api.attacks import attacks_for
from dndsheet.characters.api.background_info import enrich_background
from dndsheet.characters.api.features import enrich_features
from dndsheet.characters.api.level_up import level_up_payload, report_payload
from dndsheet.characters.api.spell_meta import enrich_spells
from dndsheet.characters.api.wizard_options import build_options
from dndsheet.characters.application.golden import GoldenCase, build_golden_cases
from dndsheet.characters.application.level_up import LevelUpService
from dndsheet.characters.application.sheet import SheetService
from dndsheet.characters.application.wizard import WizardService
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.domain.wizard import Draft, WizardStep
from dndsheet.characters.infrastructure.compendium_rules import CompendiumRulesSource
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.export.application.registry import RendererRegistry
from dndsheet.export.domain.renderer import RenderOptions, RendererError, RendererUnavailable
from dndsheet.sheets.application.build_document import build_sheet_document
from dndsheet.shared.errors import ConflictError, DomainError, NotFoundError

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


def _attacks(request: Request, character, computed) -> list[dict[str, Any]]:  # noqa: ANN001
    """Атаки з довідника; кеш живе на застосунку (імена зброї не змінюються)."""
    cache = getattr(request.app.state, "attack_cache", {})
    return attacks_for(character, computed, _compendium(request), cache)


def _sheet_payload(request: Request, character) -> dict:  # noqa: ANN001 — Character
    """Повний лист: числа, лічильники, атаки й описи вмінь."""
    computed = DerivedStatsCalculator().compute(character)
    payload = computed_sheet(
        character, computed, _attacks(request, character, computed)
    )
    compendium = _compendium(request)
    enrich_spells(payload["spells"], compendium, getattr(request.app.state, "spell_cache", {}))
    enrich_features(
        payload,
        character,
        compendium,
        getattr(request.app.state, "feature_cache", {}),
    )
    enrich_background(
        payload,
        character,
        compendium,
        getattr(request.app.state, "background_cache", {}),
    )
    return payload


def _render(request: Request, document, render_format: str, options: RenderOptions) -> Response:  # noqa: ANN001
    """Спільний вихід для всіх експортів: формат → байти → вкладення."""
    try:
        renderer = _registry(request).get(render_format)
    except RendererError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        result = renderer.render(document, options)
    except RendererUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RendererError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers={"Content-Disposition": f'attachment; filename="{result.filename}"'},
    )


def _sheet_service(request: Request) -> SheetService:
    service = getattr(request.app.state, "sheet", None)
    if service is None:  # pragma: no cover — так не буває, якщо app зібрано create_app
        raise HTTPException(status_code=503, detail="сервіс листа не підключений")
    return service


def _step_cache(request: Request, step: WizardStep) -> dict[str, Any]:
    """Кеш текстів для кроку: у класу — той самий, що й у листа."""
    if step is WizardStep.CLASS:
        return getattr(request.app.state, "feature_cache", {})
    return getattr(request.app.state, "species_cache", {})


def _level_up_service(request: Request) -> LevelUpService:
    service = getattr(request.app.state, "level_up", None)
    if service is None:  # pragma: no cover — так не буває, якщо app зібрано create_app
        raise HTTPException(status_code=503, detail="підвищення рівня не підключене")
    return service


def _payload(case: GoldenCase, request: Request | None = None) -> dict:
    if request is None:  # pragma: no cover — сумісність для тестів
        computed = DerivedStatsCalculator().compute(case.character)
        sheet = computed_sheet(case.character, computed)
    else:
        sheet = _sheet_payload(request, case.character)
    return {
        "key": case.key,
        "title_uk": case.title_uk,
        "summary_uk": case.summary_uk,
        "sheet": sheet,
    }


@router.get("/golden")
def golden(request: Request) -> dict:
    """Еталонні персонажі з повністю обчисленим листом."""
    items = [_payload(case, request) for case in _cases(request)]
    return {"items": items, "total": len(items)}


@router.get("/golden/{key}")
def golden_case(key: str, request: Request) -> dict:
    return _payload(_find(_cases(request), key), request)


@router.get("/golden/{key}/export/{render_format}")
def golden_export(key: str, render_format: str, request: Request) -> Response:
    """Експорт еталонного листа тим самим рендером, що й решта."""
    case = _find(_cases(request), key)
    computed = DerivedStatsCalculator().compute(case.character)
    document = build_sheet_document(case.character, computed)
    return _render(request, document, render_format, RenderOptions())


# ---------------------------------------------------------------------------
# візард створення персонажа
# ---------------------------------------------------------------------------


def _wizard(request: Request) -> WizardService:
    service = getattr(request.app.state, "wizard", None)
    if service is None:  # pragma: no cover — так не буває, якщо app зібрано create_app
        raise HTTPException(status_code=503, detail="візард не підключений")
    return service


def _compendium(request: Request) -> CompendiumService:
    service = getattr(request.app.state, "compendium", None)
    if service is None:  # pragma: no cover
        raise HTTPException(status_code=503, detail="довідник не підключений")
    return service


def _http_error(exc: DomainError) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


def _parse_step(step: str) -> WizardStep:
    try:
        return WizardStep(step)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"невідомий крок {step!r}") from exc


def _step_payload(request: Request, draft: Draft, step: WizardStep) -> dict[str, Any]:
    statuses = {status.step: status for status in draft.statuses()}
    status = statuses[step]
    return {
        "draft": draft_payload(draft),
        "step": step.value,
        "locked": not status.unlocked,
        "complete": status.complete,
        "answers": step_answers(draft, step),
        "options": build_options(
            step,
            draft,
            _compendium(request),
            _step_cache(request, step),
        ),
        "errors": [],
    }


@router.post("/wizard")
def start_wizard(request: Request) -> dict:
    """Нова чернетка. Повертає перший крок із його вибором."""
    try:
        draft = _wizard(request).start()
    except DomainError as exc:
        raise _http_error(exc) from exc
    step = draft.next_step() or WizardStep.SPECIES
    return _step_payload(request, draft, step)


@router.get("/wizard/{draft_id}")
def read_draft(draft_id: str, request: Request) -> dict:
    """Чернетка без вибору кроку — для шапки й навігації."""
    try:
        draft = _wizard(request).load(draft_id)
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"draft": draft_payload(draft)}


@router.get("/wizard/{draft_id}/steps/{step}")
def read_step(draft_id: str, step: str, request: Request) -> dict:
    parsed = _parse_step(step)
    try:
        draft = _wizard(request).load(draft_id)
    except DomainError as exc:
        raise _http_error(exc) from exc
    return _step_payload(request, draft, parsed)


@router.put("/wizard/{draft_id}/steps/{step}")
def write_step(
    draft_id: str,
    step: str,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    """Записати відповідь кроку. Сервер — єдиний, хто вирішує, чи вона дійсна."""
    parsed = _parse_step(step)
    body = dict(payload or {})
    revision = body.pop("revision", None)
    if revision is not None and (isinstance(revision, bool) or not isinstance(revision, int)):
        raise HTTPException(status_code=422, detail="revision має бути цілим числом")
    wizard = _wizard(request)
    try:
        draft = wizard.load(draft_id)
        statuses = {status.step: status for status in draft.statuses()}
        if not statuses[parsed].unlocked:
            raise HTTPException(
                status_code=422,
                detail="спершу завершіть попередній крок",
            )
        draft = wizard.apply(draft_id, parsed, body, expected_revision=revision)
    except DomainError as exc:
        raise _http_error(exc) from exc
    return _step_payload(request, draft, parsed)


@router.post("/wizard/{draft_id}/finish")
def finish_draft(draft_id: str, request: Request) -> dict:
    """Зібрати персонажа, зберегти й показати його лист."""
    try:
        character = _wizard(request).finish(draft_id)
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"character_id": character.id, "sheet": _sheet_payload(request, character)}


# ---------------------------------------------------------------------------
# збережені персонажі
# ---------------------------------------------------------------------------


@router.get("")
def saved_characters(request: Request) -> dict:
    characters = _wizard(request).saved_characters()
    items = [character_brief(character) for character in characters]
    return {"items": items, "total": len(items)}


@router.get("/{character_id}")
def saved_character(character_id: str, request: Request) -> dict:
    try:
        character = _wizard(request).character(character_id)
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"sheet": _sheet_payload(request, character)}


# ---------------------------------------------------------------------------
# лист під час гри: лічильники, виправлення, відпочинок
# ---------------------------------------------------------------------------


@router.patch("/{character_id}")
def update_character(
    character_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    """Часткова зміна стану листа: хіти, слоти, кидки, виправлення, нотатки."""
    body = dict(payload or {})
    version = body.pop("version", None)
    if version is not None and (isinstance(version, bool) or not isinstance(version, int)):
        raise HTTPException(status_code=422, detail="version має бути цілим числом")
    try:
        character = _sheet_service(request).update(
            character_id, body, expected_version=version
        )
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"sheet": _sheet_payload(request, character), "version": character.version}


@router.post("/{character_id}/items")
def add_inventory_item(
    character_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    """Додати предмет в інвентар (з довідника або власний)."""
    body = dict(payload or {})
    version = _pop_version(body)
    item = body.pop("item", None)
    if not isinstance(item, dict):
        raise HTTPException(status_code=422, detail="item має бути обʼєктом")
    try:
        character = _sheet_service(request).add_item(
            character_id, item, expected_version=version
        )
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"sheet": _sheet_payload(request, character), "version": character.version}


@router.patch("/{character_id}/items/{index}")
def update_inventory_item(
    character_id: str,
    index: int,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    """Змінити предмет за порядком: назва, тип, кількість, урон, броня."""
    body = dict(payload or {})
    version = _pop_version(body)
    fields = body.pop("fields", None)
    if not isinstance(fields, dict):
        raise HTTPException(status_code=422, detail="fields має бути обʼєктом")
    try:
        character = _sheet_service(request).update_item(
            character_id, index, fields, expected_version=version
        )
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"sheet": _sheet_payload(request, character), "version": character.version}


@router.delete("/{character_id}/items/{index}")
def remove_inventory_item(
    character_id: str,
    index: int,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    """Прибрати предмет з інвентаря."""
    body = dict(payload or {})
    version = _pop_version(body)
    try:
        character = _sheet_service(request).remove_item(
            character_id, index, expected_version=version
        )
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"sheet": _sheet_payload(request, character), "version": character.version}


@router.post("/{character_id}/spells")
def add_spell(
    character_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    """Додати закляття поза рівнем: зі списку класу або власне (`custom`)."""
    body = dict(payload or {})
    version = _pop_version(body)
    try:
        character = _sheet_service(request).add_spell(
            character_id, body, expected_version=version
        )
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"sheet": _sheet_payload(request, character), "version": character.version}


@router.delete("/{character_id}/spells")
def remove_spell(
    character_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    """Прибрати закляття з листа (назва + клас)."""
    body = dict(payload or {})
    version = _pop_version(body)
    try:
        character = _sheet_service(request).remove_spell(
            character_id, body, expected_version=version
        )
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"sheet": _sheet_payload(request, character), "version": character.version}


@router.post("/{character_id}/spells/prepare")
def prepare_spells(
    character_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    """Денна підготовка: замінити набір підготовлених заклять класу."""
    body = dict(payload or {})
    version = _pop_version(body)
    try:
        character = _sheet_service(request).prepare_spells(
            character_id, body, expected_version=version
        )
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"sheet": _sheet_payload(request, character), "version": character.version}


def _pop_version(body: dict[str, Any]) -> int | None:
    version = body.pop("version", None)
    if version is not None and (isinstance(version, bool) or not isinstance(version, int)):
        raise HTTPException(status_code=422, detail="version має бути цілим числом")
    return version


@router.post("/{character_id}/rest")
def rest_character(
    character_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    kind = str((payload or {}).get("kind") or "")
    try:
        character, report = _sheet_service(request).rest(character_id, kind)
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {
        "sheet": _sheet_payload(request, character),
        "version": character.version,
        "rest": asdict(report),
    }


@router.post("/{character_id}/hit-dice")
def spend_hit_die(
    character_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    die = (payload or {}).get("die")
    roll = (payload or {}).get("roll")
    for name, value in (("die", die), ("roll", roll)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise HTTPException(status_code=422, detail=f"{name} має бути цілим числом")
    try:
        character = _sheet_service(request).spend_hit_die(character_id, die, roll)
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"sheet": _sheet_payload(request, character), "version": character.version}


# ---------------------------------------------------------------------------
# підвищення рівня
# ---------------------------------------------------------------------------


@router.get("/{character_id}/level-up")
def level_up_preview(character_id: str, request: Request) -> dict:
    """Що дасть наступний рівень — у кожному наявному класі й у кожному новому."""
    try:
        character, _ = _level_up_service(request).preview(character_id)
    except DomainError as exc:
        raise _http_error(exc) from exc
    return level_up_payload(
        character,
        _level_up_service(request),
        _compendium(request),
        getattr(request.app.state, "feature_cache", {}),
    )


@router.post("/{character_id}/level-up")
def level_up(
    character_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    """Узяти рівень: клас, хіти, підклас, характеристики, закляття."""
    body = dict(payload or {})
    version = _pop_version(body)
    try:
        character, report = _level_up_service(request).apply(
            character_id, body, expected_version=version
        )
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {
        "sheet": _sheet_payload(request, character),
        "version": character.version,
        "level_up": report_payload(report),
    }


# ---------------------------------------------------------------------------
# експорт листа
# ---------------------------------------------------------------------------


def _feat_titles(request: Request) -> dict[str, str]:
    """Назви рис за ключем: у документі показуємо текст, а не id запису."""
    return {
        entry.id.casefold(): entry.name_en
        for entry in _compendium(request).feats()
    }


@router.get("/{character_id}/export/{render_format}")
def character_export(
    character_id: str,
    render_format: str,
    request: Request,
    originals: bool = True,
) -> Response:
    """Лист гравця у PDF або Markdown — зі станом, а не з демо-персонажа.

    `originals=false` прибирає англійські підписи (для друку без дрібного
    тексту). Сам документ завжди український: це мова застосунку.
    """
    try:
        character = _wizard(request).character(character_id)
    except DomainError as exc:
        raise _http_error(exc) from exc
    computed = DerivedStatsCalculator().compute(character)
    document = build_sheet_document(
        character,
        computed,
        _attacks(request, character, computed),
        feat_titles=_feat_titles(request),
    )
    return _render(request, document, render_format, RenderOptions(show_originals=originals))
