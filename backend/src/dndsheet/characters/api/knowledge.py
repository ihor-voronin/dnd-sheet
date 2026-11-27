"""База знань для всіх, без входу: види, класи, передісторії.

Це ті самі дані, що й у кроках візарда (опис, особливості, уміння, переклад),
лише без чернетки: їх збирає `build_options` для порожньої чернетки, яка ніде
не зберігається. Так довідник і візард не розходяться — правка перекладу чи
тексту видна в обох місцях.

Риси, закляття, опційні вміння й предмети читаються із загального довідника
(`/api/v1/compendium/...`): там уже є українські назви й тексти.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from dndsheet.characters.api import subclasses_uk
from dndsheet.characters.api.router import _compendium, _step_cache
from dndsheet.characters.api.wizard_options import build_options
from dndsheet.characters.domain.wizard import Draft, WizardStep

router = APIRouter(prefix="/api/v1/kb", tags=["knowledge"])


def _options(request: Request, step: WizardStep) -> dict[str, Any]:
    draft = Draft(id="knowledge-base", rules=request.app.state.rules)
    return build_options(step, draft, _compendium(request), _step_cache(request, step))


@router.get("/species")
def species(request: Request) -> dict[str, Any]:
    return {"items": _options(request, WizardStep.SPECIES)["species"]}


@router.get("/classes")
def classes(request: Request) -> dict[str, Any]:
    """Класи з усіма підкласами (не лише тими, що обирають на 1 рівні)."""
    service = _compendium(request)
    items = _options(request, WizardStep.CLASS)["classes"]
    for item in items:
        item["subclasses_all"] = sorted(
            (
                {
                    "id": entry.id,
                    "name_en": entry.name_en,
                    "name_uk": subclasses_uk.name_uk(entry.name_en),
                    "source_id": entry.source_id,
                    "level": entry.data.get("level"),
                }
                for entry in service.subclasses(item["key"])
            ),
            key=lambda sub: (sub["name_uk"] or sub["name_en"]).casefold(),
        )
    return {"items": items}


@router.get("/backgrounds")
def backgrounds(request: Request) -> dict[str, Any]:
    items = [item for item in _options(request, WizardStep.BACKGROUND)["backgrounds"] if not item.get("custom")]
    return {"items": items}
