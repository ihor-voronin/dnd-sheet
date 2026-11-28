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

import secrets
from dataclasses import asdict
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from dndsheet.characters.api import classes_uk, subclasses_uk, uk_text
from dndsheet.characters.api.attacks import attacks_for
from dndsheet.characters.api.background_info import enrich_background
from dndsheet.characters.api.class_choices import (
    allowed_names,
    apply_choices,
    class_choices_payload,
    duplicate_picks,
    feat_probe_groups,
    option_levels,
)
from dndsheet.characters.api.features import (
    class_texts_all,
    enrich_features,
    feature_text_for,
    strip_level_line,
    subclass_features,
    subclass_intro,
)
from dndsheet.characters.api.level_up import level_up_payload, report_payload
from dndsheet.characters.api.print_view import build_print_view
from dndsheet.characters.api.school_limits import check_schools
from dndsheet.characters.api.serializers import (
    character_brief,
    computed_sheet,
    draft_payload,
    step_answers,
)
from dndsheet.characters.api.spell_meta import enrich_spells
from dndsheet.characters.api.uk_text import with_english
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
from dndsheet.export.domain.renderer import RendererError, RendererUnavailable, RenderOptions
from dndsheet.identity.api.router import require_user
from dndsheet.shared.errors import ConflictError, DomainError, NotFoundError
from dndsheet.shared.kernel import Ability
from dndsheet.shared.rules import (
    dragon_damage_type,
    feat_ability_options,
    natural_weapon_die,
    natural_weapon_for,
)
from dndsheet.sheets.application.build_document import build_sheet_document

#: Без входу відкриті лише еталонні листи й довідкові тексти класів і підкласів.
_PUBLIC_PREFIXES = (
    "/api/v1/characters/golden",
    "/api/v1/characters/wizard/class-features/",
    "/api/v1/characters/wizard/subclass/",
)


def _guard(request: Request) -> None:
    """Доступ: персонажі й чернетки — лише власнику; чужий id виглядає як відсутній.

    Залежність рівня роутера виконується після вибору маршруту, тож
    `path_params` уже містить `character_id` чи `draft_id`.
    """
    # Без входу (`DNDSHEET_AUTH=off`) гравець один — і все його.
    if request.url.path.startswith(_PUBLIC_PREFIXES) or not request.app.state.auth_enabled:
        return
    user = require_user(request)
    params = request.path_params
    character_id = params.get("character_id")
    if character_id is not None:
        store = request.app.state.characters
        if store.version(character_id) is not None and store.owner(character_id) != user.id:
            raise HTTPException(status_code=404, detail=f"немає персонажа {character_id!r}")
    draft_id = params.get("draft_id")
    if draft_id is not None:
        drafts = request.app.state.drafts
        if drafts.get(draft_id) is not None and drafts.owner(draft_id) != user.id:
            raise HTTPException(status_code=404, detail=f"немає чернетки {draft_id!r}")


router = APIRouter(prefix="/api/v1/characters", tags=["characters"], dependencies=[Depends(_guard)])

#: Скільки персонажів може мати один гравець. Межа рятує базу від скрипта чи
#: асистента, що «створює» в циклі; живому гравцю 50 героїв вистачає з запасом.
CHARACTER_LIMIT = 50


def _own_ids(request: Request) -> tuple[str, ...]:
    """Персонажі того, хто питає; без входу — усі персонажі бази."""
    store = request.app.state.characters
    return store.ids_of(require_user(request).id) if request.app.state.auth_enabled else store.ids()


def _check_limit(request: Request) -> None:
    if len(_own_ids(request)) >= CHARACTER_LIMIT:
        raise HTTPException(
            status_code=409,
            detail=f"у вас уже {CHARACTER_LIMIT} персонажів — це межа; видаліть когось, щоб створити нового",
        )


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


def _background_item_names(payload: dict) -> None:
    """Речі зі спорядження передісторії («insignia of rank») — українською з її ж перекладу.

    У довіднику предметів таких записів немає: це рядки з тексту передісторії, і
    переклад для них уже є в `equipment_rows` (той самий, що бачить візард).
    """
    names: dict[str, str] = {}
    for row in (payload.get("background_details") or {}).get("equipment_rows") or []:
        if row.get("text_uk"):
            names[str(row.get("text", "")).casefold()] = row["text_uk"]
        for choice, choice_uk in zip(row.get("choices") or [], row.get("choices_uk") or []):
            if choice_uk:
                names[str(choice).casefold()] = choice_uk
    for item in payload["inventory"]["items"]:
        uk = names.get(str(item.get("name_en", "")).casefold())
        if uk:
            item["name_uk"] = uk


def _subclass_names(payload: dict, compendium: CompendiumService) -> None:
    """Назва підкласу з книги й переклад: «Школа втілення (School of Evocation)».

    У персонажа лише ключ («phb-2014/subclass/school-of-evocation»); зробити з
    нього назву на екрані — це «School Of Evocation» англійською.
    """
    for entry in payload["character"]["classes"]:
        key = entry.get("subclass")
        if not key:
            continue
        try:
            name_en = compendium.entry(key).name_en
        except DomainError:
            name_en = " ".join(word.capitalize() for word in key.rsplit("/", 1)[-1].split("-"))
        entry["subclass_name"] = name_en
        entry["subclass_name_uk"] = subclasses_uk.name_uk(name_en)


def _sheet_payload(request: Request, character) -> dict:  # noqa: ANN001 — Character
    """Повний лист: числа, лічильники, атаки й описи вмінь."""
    computed = DerivedStatsCalculator().compute(character)
    payload = computed_sheet(character, computed, _attacks(request, character, computed))
    compendium = _compendium(request)
    _subclass_names(payload, compendium)
    enrich_spells(payload["spells"], compendium, getattr(request.app.state, "spell_cache", {}))
    _elemental_affinity(payload["spells"], character, computed)
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
    _background_item_names(payload)
    payload["class_choices"] = class_choices_payload(character, compendium)
    # Книга виду — лише там, де від неї залежать числа (кігті табаксі: VGM 1d4, MPMM 1d6).
    natural = natural_weapon_for(character.species_key, character.subspecies_key)
    payload["species_source"] = (
        {
            "chosen": character.species_source,
            "default": character.species.source_id if character.species else None,
            "options": [
                {"source": source, "die": natural_weapon_die(natural, source)} for source in character.species_sources
            ],
            "weapon": natural.name_en,
        }
        if natural is not None and natural.die_mpmm and len(character.species_sources) > 1
        else None
    )
    # Варіантна людина й власна лінія: риса на 1 рівні (PHB, p. 31; TCoE, p. 8).
    payload["species_feat"] = (
        {
            "chosen": character.species_feat,
            "ability": (
                character.feat_abilities[character.species_feat].value
                if character.species_feat in character.feat_abilities
                else None
            ),
            "feat_abilities": _feat_ability_map(compendium),
        }
        if character.grants_species_feat
        else None
    )
    return payload


def _elemental_affinity(spells: list[dict[str, Any]], character, computed) -> None:  # noqa: ANN001
    """Стихійна спорідненість (PHB, p. 102): + Харизма до урону заклять типу драконячого предка.

    Тип урону закляття знає лише довідник, тому примітка дописується тут, після збагачення.
    """
    sorcerer = next((entry for entry in character.classes if entry.class_key == "sorcerer"), None)
    ancestor = character.active_class_choices.get("sub:draconic-bloodline:Dragon Ancestor", ())
    damage = dragon_damage_type(ancestor[0]) if ancestor else None
    if sorcerer is None or sorcerer.level < 6 or damage is None:
        return
    bonus = computed.ability_modifiers[Ability.CHA]
    for spell in spells:
        if (spell.get("damage") or {}).get("type") == damage:
            text = f"Стихійна спорідненість (Elemental Affinity): {bonus:+d} до одного кидка урону"
            spell["note"] = "; ".join(filter(None, [spell.get("note"), text]))


def _feat_ability_map(compendium: CompendiumService) -> dict[str, list[str]]:
    """Риси з +1 до характеристики: id → можливі характеристики."""
    return {
        entry.id: [ability.value for ability in options]
        for entry in compendium.feats()
        if (options := feat_ability_options(entry.text_en or ""))
    }


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
    if step in (WizardStep.BACKGROUND, WizardStep.EQUIPMENT):
        return getattr(request.app.state, "background_cache", {})
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
    _check_limit(request)
    try:
        draft = _wizard(request).start()
    except DomainError as exc:
        raise _http_error(exc) from exc
    request.app.state.drafts.set_owner(draft.id, require_user(request).id)
    step = draft.next_step() or WizardStep.SPECIES
    return _step_payload(request, draft, step)


@router.get("/wizard/class-features/{class_key}")
def class_features(class_key: str, request: Request) -> dict:
    """Усі вміння класу за рівнями — з текстом і перекладом.

    Окремий запит, а не частина кроку «Клас»: текстів у 13 класів на кілька
    сотень кілобайт, і потрібні вони лише тоді, коли гравець розгорнув
    «Усі вміння класу за рівнями».
    """
    service = _compendium(request)
    cache = getattr(request.app.state, "feature_cache", {})
    try:
        definition = service.class_mechanics(class_key)
    except DomainError as exc:
        raise _http_error(exc) from exc
    texts = class_texts_all(service, definition.key, cache)
    rows: list[dict[str, Any]] = []
    for feature in definition.features:
        row: dict[str, Any] = {"name_en": feature.name_en, "level": feature.level}
        text = feature_text_for(feature.name_en, texts)
        if text:
            row["text"] = text
        # Переклад — той самий шар, що й у главі класу: назва + текст.
        classes_uk.enrich_feature(row)
        # «3rd-level sorcerer feature» у тілі не потрібен: рівень є в заголовку
        # рядка. Прибираємо вже після перекладу, щоб не зламати ключ.
        strip_level_line(row)
        rows.append(row)
    return {"class_key": definition.key, "features": rows}


@router.get("/wizard/subclass/{subclass_key:path}")
def subclass_details(subclass_key: str, request: Request) -> dict:
    """Підклас цілком для вибору: назва, опис-вступ і всі вміння з текстами.

    Вантажиться, коли гравець натиснув на варіант: вбудовувати це в крок
    «Клас» означало б віддавати описи й тексти всіх підкласів класу (у жреця
    їх двадцять) ще до вибору.
    """
    service = _compendium(request)
    cache = getattr(request.app.state, "feature_cache", {})
    try:
        entry = service.entry(subclass_key)
    except DomainError as exc:
        raise _http_error(exc) from exc
    intro = subclass_intro(service, subclass_key, cache)
    return {
        "id": entry.id,
        "name_en": entry.name_en,
        "name_uk": intro.get("name_uk"),
        "description": intro.get("description", ""),
        "description_uk": intro.get("description_uk"),
        "corrupt": bool(intro.get("corrupt")),
        "features": subclass_features(service, subclass_key, cache),
    }


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


def _feat_probe(request: Request, body: dict[str, Any]):  # noqa: ANN202 — Character
    """Пробний персонаж для виборів риси виду: той самий вид, риса й характеристики 10."""
    from dndsheet.characters.domain.character import Character
    from dndsheet.shared.kernel import AbilityScore

    feat = str(body.get("species_feat") or body.get("feat") or "").strip().casefold()
    return Character(
        id="probe",
        name="probe",
        abilities={ability: AbilityScore(10) for ability in Ability},
        rules=request.app.state.rules,
        classes=[],
        species_key=body.get("species_key") or None,
        subspecies_key=body.get("subspecies_key") or None,
        feats=(feat,) if feat else (),
    )


@router.post("/wizard/feat-choices")
def wizard_feat_choices(request: Request, payload: dict[str, Any] = Body(default_factory=dict)) -> dict:
    """Групи виборів риси виду для візарда: `{feat, species_key, subspecies_key, choices}`."""
    body = dict(payload or {})
    compendium = _compendium(request)
    try:
        probe = _feat_probe(request, body)
        choices = body.get("choices") or {}
        if not isinstance(choices, dict):
            raise HTTPException(status_code=422, detail="choices має бути обʼєктом «група: [назви]»")
        apply_choices(probe, compendium, {key: list(values) for key, values in choices.items() if values})
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"groups": feat_probe_groups(probe, compendium)}


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
        choices = body.get("species_feat_choices")
        if parsed is WizardStep.SPECIES and isinstance(choices, dict) and choices:
            # Варіанти рис знає довідник — перевіряємо тут, на пробному персонажі.
            apply_choices(
                _feat_probe(request, body),
                _compendium(request),
                {key: list(values) for key, values in choices.items() if values},
            )
        draft = wizard.apply(draft_id, parsed, body, expected_revision=revision)
    except DomainError as exc:
        raise _http_error(exc) from exc
    return _step_payload(request, draft, parsed)


@router.post("/wizard/{draft_id}/finish")
def finish_draft(draft_id: str, request: Request) -> dict:
    """Зібрати персонажа, зберегти й показати його лист."""
    # Ще раз на фініші: чернетку могли почати, коли місце ще було.
    _check_limit(request)
    try:
        # Навичка з риси виду не має дублювати навичку передісторії чи класу.
        duplicates = duplicate_picks(_wizard(request).load(draft_id).to_character("probe"))
        if duplicates:
            raise HTTPException(
                status_code=422,
                detail="уже є з іншого джерела — змініть вибір риси на кроці виду: " + "; ".join(duplicates),
            )
        character = _wizard(request).finish(draft_id)
    except DomainError as exc:
        raise _http_error(exc) from exc
    request.app.state.characters.set_owner(character.id, require_user(request).id)
    return {"character_id": character.id, "sheet": _sheet_payload(request, character)}


# ---------------------------------------------------------------------------
# збережені персонажі
# ---------------------------------------------------------------------------


def _roster_entry(character, compendium: CompendiumService) -> dict:  # noqa: ANN001 — Character
    """Рядок «Моїх персонажів»: хто це (вид, класи з підкласами, передісторія) і як він зараз.

    Хіти й КЗ рахуються тим самим калькулятором, що й лист, — щоб картка в списку
    не розходилася з листом (поранений герой видно ще до відкриття).
    """
    brief = character_brief(character)
    _subclass_names({"character": brief}, compendium)
    computed = DerivedStatsCalculator().compute(character)
    brief["hit_points"] = {
        "maximum": computed.hit_points.maximum,
        "current": computed.hit_points.current,
        "temporary": computed.hit_points.temporary,
    }
    brief["armor_class"] = computed.armor_class
    return brief


@router.get("")
def saved_characters(request: Request) -> dict:
    store = request.app.state.characters
    user = require_user(request)
    # Без входу — усі персонажі бази (тести й старі записи можуть не мати власника).
    characters = [found for identifier in _own_ids(request) if (found := store.get(identifier)) is not None]
    compendium = _compendium(request)
    items = [_roster_entry(character, compendium) for character in characters]
    # Незавершена чернетка — щоб продовжити створення з іншого пристрою.
    draft_id = request.app.state.drafts.latest_of(user.id)
    return {"items": items, "total": len(items), "limit": CHARACTER_LIMIT, "draft_id": draft_id}


@router.delete("/{character_id}")
def delete_character(character_id: str, request: Request) -> dict:
    """Видалити персонажа назавжди. Посилання «лише читати» на нього перестає працювати.

    Чужий персонаж виглядає як відсутній (`_guard`), тож видалити можна лише свого.
    """
    try:
        request.app.state.shares.revoke(character_id)
        request.app.state.characters.delete(character_id)
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"deleted": character_id}


@router.get("/{character_id}/version")
def character_version(character_id: str, request: Request) -> dict:
    """Лише номер версії: лист опитує його кожні кілька секунд і перечитує себе, коли той змінився."""
    version = request.app.state.characters.version(character_id)
    if version is None:
        raise HTTPException(status_code=404, detail=f"немає персонажа {character_id!r}")
    return {"version": version}


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
    """Часткова зміна стану листа: хіти, комірки, кидки, виправлення, нотатки."""
    body = dict(payload or {})
    version = body.pop("version", None)
    if version is not None and (isinstance(version, bool) or not isinstance(version, int)):
        raise HTTPException(status_code=422, detail="version має бути цілим числом")
    try:
        character = _sheet_service(request).update(character_id, body, expected_version=version)
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
        character = _sheet_service(request).add_item(character_id, item, expected_version=version)
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
        character = _sheet_service(request).update_item(character_id, index, fields, expected_version=version)
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
        character = _sheet_service(request).remove_item(character_id, index, expected_version=version)
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
        if body.get("class_key") and not body.get("custom"):
            check_schools(
                _sheet_service(request).load(character_id), _compendium(request), str(body["class_key"]), [body]
            )
        character = _sheet_service(request).add_spell(character_id, body, expected_version=version)
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
        character = _sheet_service(request).remove_spell(character_id, body, expected_version=version)
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
        character = _sheet_service(request).prepare_spells(character_id, body, expected_version=version)
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"sheet": _sheet_payload(request, character), "version": character.version}


@router.post("/{character_id}/expertise")
def set_expertise(
    character_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    """Експертиза: `{"expertise": ["stealth", "thieves' tools"], "version": N}`."""
    body = dict(payload or {})
    version = _pop_version(body)
    try:
        character = _sheet_service(request).set_expertise(character_id, body, expected_version=version)
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"sheet": _sheet_payload(request, character), "version": character.version}


@router.post("/{character_id}/class-choices")
def set_class_choice(
    character_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    """Вибір класу: `{"group": "fighter:Fighting Style", "values": ["Defense"], "version": N}`."""
    body = dict(payload or {})
    version = _pop_version(body)
    group = body.get("group")
    if not isinstance(group, str) or ":" not in group:
        raise HTTPException(status_code=422, detail="group має бути «клас:група»")
    try:
        current = _sheet_service(request).load(character_id)
        character = _sheet_service(request).set_class_choice(
            character_id,
            body,
            allowed=allowed_names(group, _compendium(request), current),
            levels=option_levels(group, _compendium(request), current),
            expected_version=version,
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"невідома група {group!r}") from exc
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"sheet": _sheet_payload(request, character), "version": character.version}


@router.post("/{character_id}/species-source")
def set_species_source(
    character_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    """Книга виду: `{"source": "MPMM", "version": N}`; `null` — книга запису."""
    body = dict(payload or {})
    version = _pop_version(body)
    try:
        character = _sheet_service(request).set_species_source(
            character_id, body.get("source") or None, expected_version=version
        )
    except DomainError as exc:
        raise _http_error(exc) from exc
    return {"sheet": _sheet_payload(request, character), "version": character.version}


@router.post("/{character_id}/species-feat")
def set_species_feat(
    character_id: str,
    request: Request,
    payload: dict[str, Any] = Body(default_factory=dict),
) -> dict:
    """Риса виду: `{"feat_key": "phb-2014/feat/alert", "feat_ability": "dex", "version": N}`."""
    body = dict(payload or {})
    version = _pop_version(body)
    feat_key = str(body.get("feat_key") or "").strip().casefold()
    compendium = _compendium(request)
    entry = next((item for item in compendium.feats() if item.id.casefold() == feat_key), None)
    if entry is None:
        raise HTTPException(status_code=422, detail=f"невідома риса {feat_key!r}")
    options = feat_ability_options(entry.text_en or "")
    raw_ability = body.get("feat_ability")
    ability = None
    if options:
        try:
            ability = Ability(str(raw_ability)) if raw_ability else options[0]
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"невідома характеристика {raw_ability!r}") from exc
        if ability not in options:
            raise HTTPException(status_code=422, detail=f"{entry.name_en}: {ability.value} не підвищується цією рисою")
    try:
        character = _sheet_service(request).set_species_feat(character_id, feat_key, ability, expected_version=version)
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
        current = _sheet_service(request).load(character_id)
        class_key = str(body.get("class_key") or "").casefold()
        check_schools(
            current,
            _compendium(request),
            class_key,
            [item for item in body.get("spells") or [] if isinstance(item, dict)],
            removing=body.get("replace_spell"),
            level=current.class_level(class_key) + 1,
            subclass_key=body.get("subclass_key"),
        )
        character, report = _level_up_service(request).apply(character_id, body, expected_version=version)
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
    """Назви рис за ключем: «Пильний (Alert)», а не id запису."""
    return {
        entry.id.casefold(): with_english(entry.name_en, uk_text.name_uk("feats", entry.name_en))
        for entry in _compendium(request).feats()
    }


def _display_name(name_en: str) -> str:
    """«Warlock» → «Чаклун (Warlock)»: класи, види, передісторії, уміння, закляття."""
    uk = uk_text.name_uk("terms", name_en.strip().casefold()) or next(
        (found for layer in (*_NAME_LAYERS, "backgrounds") if (found := uk_text.name_uk(layer, name_en))),
        None,
    )
    shown = name_en if not name_en.islower() else name_en.replace("-", " ").title()
    return with_english(shown, uk)


#: Шари перекладу, з яких беруться назви полів документа (за хешем назви).
_NAME_LAYERS = ("spells", "classes", "subclasses", "optional-features", "feats")


def _localize_labels(document, character):  # noqa: ANN001, ANN202 — SheetDocument, Character
    """Назви заклять, умінь і предметів документа — українською (англійська лишається в `en`)."""
    by_id = uk_text.read("items")["names"]
    # Переклад предметів — за id запису довідника, тож назва → id береться з інвентаря.
    items = {
        item.name_en.casefold(): by_id[item.entry_id]
        for item in character.inventory.items
        if item.entry_id and item.entry_id in by_id
    }
    fields = {}
    for key, field in document.fields.items():
        label = field.label
        if label is not None and label.uk == label.en:
            uk = next((name for layer in _NAME_LAYERS if (name := uk_text.name_uk(layer, label.en))), None)
            uk = uk or items.get(label.en.casefold())
            if uk:
                field = field.model_copy(update={"label": label.model_copy(update={"uk": uk})})
        fields[key] = field
    return document.model_copy(update={"fields": fields})


@router.get("/{character_id}/export/{render_format}")
def character_export(
    character_id: str,
    render_format: str,
    request: Request,
    originals: bool = True,
    detailed: bool = True,
) -> Response:
    """Лист гравця у PDF або Markdown — зі станом, а не з демо-персонажа.

    `originals=false` прибирає англійські підписи (для друку без дрібного
    тексту). Сам документ завжди український: це мова застосунку.
    """
    try:
        character = _wizard(request).character(character_id)
    except DomainError as exc:
        raise _http_error(exc) from exc
    if render_format == "pdf":
        return _character_pdf(request, character, RenderOptions(show_originals=originals), detailed=detailed)
    computed = DerivedStatsCalculator().compute(character)
    document = build_sheet_document(
        character,
        computed,
        _attacks(request, character, computed),
        feat_titles=_feat_titles(request),
        name=_display_name,
    )
    document = _localize_labels(document, character)
    return _render(request, document, render_format, RenderOptions(show_originals=originals))


# ---------------------------------------------------------------------------
# друк: оформлений аркуш (PDF і HTML для друку з браузера)
# ---------------------------------------------------------------------------


def _print_view(request: Request, character) -> dict:  # noqa: ANN001 — Character
    sheet = _sheet_payload(request, character)
    species_key = (sheet["character"].get("species") or {}).get("key") or ""
    mechanics = request.app.state.rules.species_mechanics(species_key) if species_key else None
    return build_print_view(
        sheet,
        compendium=_compendium(request),
        display_name=_display_name,
        species_parent=getattr(mechanics, "subrace_of", None),
        species_cache=getattr(request.app.state, "species_cache", {}),
        feat_titles=_feat_titles(request),
    )


def _print_renderer(request: Request):  # noqa: ANN202 — PdfRenderer
    try:
        renderer = _registry(request).get("pdf")
    except RendererError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not hasattr(renderer, "render_character"):
        raise HTTPException(status_code=503, detail="рендер аркуша не підключений")
    return renderer


def _character_pdf(request: Request, character, options: RenderOptions, *, detailed: bool = True) -> Response:  # noqa: ANN001
    renderer = _print_renderer(request)
    try:
        result = renderer.render_character(_print_view(request, character), options, detailed=detailed)
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


@router.get("/{character_id}/print", response_class=HTMLResponse)
def character_print(
    character_id: str, request: Request, originals: bool = True, detailed: bool = True
) -> HTMLResponse:
    """Той самий аркуш, що й PDF, як сторінка: друк із браузера (Ctrl+P) працює і без WeasyPrint."""
    try:
        character = _wizard(request).character(character_id)
    except DomainError as exc:
        raise _http_error(exc) from exc
    html = _print_renderer(request).character_html(
        _print_view(request, character), RenderOptions(show_originals=originals), detailed=detailed
    )
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# поділитися: посилання «лише читати» (власник створює, замінює, відкликає)
# ---------------------------------------------------------------------------


def _share_payload(token: str | None) -> dict:
    return {"token": token, "path": f"/#/s/{token}" if token else None}


@router.get("/{character_id}/share")
def share_status(character_id: str, request: Request) -> dict:
    _wizard_character(request, character_id)
    return _share_payload(request.app.state.shares.token_of(character_id))


@router.post("/{character_id}/share")
def share_create(character_id: str, request: Request) -> dict:
    """Нове посилання «лише читати»; попереднє (якщо було) перестає працювати."""
    _wizard_character(request, character_id)
    token = secrets.token_urlsafe(16)
    request.app.state.shares.replace(character_id, token)
    return _share_payload(token)


@router.delete("/{character_id}/share")
def share_revoke(character_id: str, request: Request) -> dict:
    _wizard_character(request, character_id)
    request.app.state.shares.revoke(character_id)
    return _share_payload(None)


def _wizard_character(request: Request, character_id: str):  # noqa: ANN202 — Character
    try:
        return _wizard(request).character(character_id)
    except DomainError as exc:
        raise _http_error(exc) from exc
