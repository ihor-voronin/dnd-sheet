"""Що показати на кроці візарда: вибір із правил і довідника.

Це шар **складання**: сам візард (домен, сценарій) не знає ні про довідник, ні
про те, як виглядає список класів. Тут збирається те, що потрібно екрану:
перелік видів із підрасами, класи з їхніми навичками й підкласами, вартість
point buy, списки заклять класу.

Формат навмисно «плоский»: кожен крок повертає `options` і `answers` у тій
самій формі, яку приймає `PUT` цього кроку. Тому екран лише намальовує те, що
прийшло, і надсилає назад — без окремих перетворень на клієнті.
"""

from __future__ import annotations

from typing import Any

from dndsheet.characters.domain.wizard import (
    POINT_BUY_BUDGET,
    POINT_BUY_COSTS,
    STANDARD_ARRAY,
    Draft,
    WizardStep,
)
from dndsheet.characters.api.species_traits import species_details
from dndsheet.compendium.api.serializers import (
    background_mechanics_full,
    class_mechanics_full,
    entry_brief,
    species_mechanics_full,
)
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.shared.errors import NotFoundError
from dndsheet.shared.rules import requires_subspecies

ALIGNMENTS: tuple[str, ...] = (
    "lawful good",
    "neutral good",
    "chaotic good",
    "lawful neutral",
    "neutral",
    "chaotic neutral",
    "lawful evil",
    "neutral evil",
    "chaotic evil",
)

def build_options(
    step: WizardStep,
    draft: Draft,
    service: CompendiumService,
    cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if step is WizardStep.SPECIES:
        return _species_options(draft, service, cache)
    if step is WizardStep.CLASS:
        return _class_options(draft, service)
    if step is WizardStep.ABILITIES:
        return _abilities_options(draft)
    if step is WizardStep.BACKGROUND:
        return _background_options(draft, service)
    if step is WizardStep.EQUIPMENT:
        return _equipment_options(draft, service)
    return _spells_options(draft, service)


# ---------------------------------------------------------------------------


def _species_options(
    draft: Draft,
    service: CompendiumService,
    cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Види з числами й **особливостями з книги**.

    Текст умінь («Hare-Trigger», «Rabbit Hop») живе тільки в довіднику, тому
    він приходить сюди ж: інакше екран показував Harengon як «без бонусів» і
    гравець не бачив, що вид дає.
    """
    store = cache if cache is not None else {}
    species: list[dict[str, Any]] = []
    choice_classes: set[str] = set()
    for item in service.species_list():
        payload = _species_entry(item, service, store)
        payload["subspecies"] = [
            _species_entry(child, service, store, parent=item.name_en)
            for child in service.subspecies_of(item.name_en)
        ]
        for candidate in (payload, *payload["subspecies"]):
            if candidate.get("cantrip_choice"):
                choice_classes.add(candidate["cantrip_choice"]["from_class"])
        species.append(payload)
    # Заговори для вибору («один заговір візарда» у високого ельфа) — зі
    # списку того класу, який названий у правилі виду.
    class_cantrips: dict[str, list[dict[str, Any]]] = {}
    for class_key in sorted(choice_classes):
        try:
            spells = service.class_spells(class_key, max_level=0)
        except NotFoundError:
            continue
        class_cantrips[class_key] = [entry_brief(entry) for entry in spells.spells]
    return {
        "species": species,
        "class_cantrips": class_cantrips,
        "hint": (
            "Підраса успадковує числа батьківського виду: «Hill Dwarf» уже "
            "несе +2 CON і +1 WIS."
        ),
    }


def _species_entry(
    item,  # noqa: ANN001 — SpeciesMechanics
    service: CompendiumService,
    cache: dict[str, Any],
    *,
    parent: str | None = None,
) -> dict[str, Any]:
    """Числа виду + текст книги: опис і особливості."""
    payload = species_mechanics_full(item)
    details = species_details(service, item.name_en, parent_name_en=parent, cache=cache)
    payload["traits"] = (details or {}).get("traits") or []
    payload["description"] = (details or {}).get("description") or ""
    payload["text_lang"] = (details or {}).get("lang")
    payload["text_from"] = (
        (details or {}).get("from_parent") or (details or {}).get("from_rule")
        if details
        else None
    )
    # Підраса обовʼязкова лише там, де вона визначає числа (PHB: дворф, ельф,
    # гном, піврослик; EEPC: genasi; ERLW: shifter; EGtW: aasimar; gith).
    payload["subspecies_required"] = requires_subspecies(item.key)
    return payload


def _class_options(draft: Draft, service: CompendiumService) -> dict[str, Any]:
    classes: list[dict[str, Any]] = []
    for definition in service.class_definitions():
        payload = class_mechanics_full(definition)
        payload["skill_options"] = [skill.value for skill in definition.skill_options()]
        payload["cantrips_at_level_1"] = definition.cantrips_at(1)
        payload["spells_known_at_level_1"] = definition.spells_known_at(1)
        subclass_entries: list[dict[str, Any]] = []
        if definition.subclass_level == 1:
            for entry in service.subclasses(definition.name_en):
                brief = entry_brief(entry)
                grants = definition.subclass_spells_for(entry.id)
                brief["grants"] = (
                    {"prepared": list(grants.prepared), "expanded": list(grants.expanded)}
                    if grants is not None
                    else {"prepared": [], "expanded": []}
                )
                subclass_entries.append(brief)
        payload["subclass"] = (
            {
                "title": definition.subclass_title,
                "level": definition.subclass_level,
                "options": subclass_entries,
            }
            if definition.subclass_title
            else None
        )
        classes.append(payload)
    return {
        "classes": classes,
        "hint": "Підклас на 1 рівні обирають лише ті класи, де він там і зʼявляється.",
    }


def _abilities_options(draft: Draft) -> dict[str, Any]:
    return {
        "methods": ["standard_array", "point_buy", "rolls", "manual"],
        "standard_array": list(STANDARD_ARRAY),
        "point_buy": {
            "budget": POINT_BUY_BUDGET,
            "costs": {str(score): cost for score, cost in sorted(POINT_BUY_COSTS.items())},
            "min": min(POINT_BUY_COSTS),
            "max": max(POINT_BUY_COSTS),
        },
        "species_bonuses": {
            ability.value: draft.ability_bonuses.get(ability, 0)
            for ability in draft.ability_bonuses
        },
        "hint": (
            "Оцінки тут — базові. Бонуси виду додаються на листі й показуються "
            "окремо, щоб було видно, звідки взялося число."
        ),
    }


def _background_options(draft: Draft, service: CompendiumService) -> dict[str, Any]:
    options: dict[str, Any] = {
        "backgrounds": [
            background_mechanics_full(item) for item in service.backgrounds()
        ],
        "alignments": list(ALIGNMENTS),
        "class_skills": None,
        "species_skills": None,
    }
    if draft.class_key:
        definition = draft.class_definition
        options["class_skills"] = {
            "key": definition.key,
            "limit": definition.skill_limit,
            "options": [skill.value for skill in definition.skill_options()],
            "any": definition.skill_any > 0,
        }
    species = draft.species
    if species is not None:
        options["species_skills"] = {
            "key": species.key,
            "fixed": sorted(skill.value for skill in species.skill_proficiencies),
            "any": species.skill_any,
            "languages_any": species.languages_any_standard,
            "tools_any": species.tools_any,
        }
    return options


def _equipment_options(draft: Draft, service: CompendiumService) -> dict[str, Any]:
    options: dict[str, Any] = {
        "items_url": "/api/v1/compendium/items",
        "hint": (
            "Спорядження не обовʼязкове: можна пропустити й додати предмети вже "
            "на листі. Пошук предметів — у довіднику."
        ),
    }
    if draft.class_key:
        definition = draft.class_definition
        options["class"] = {
            "key": definition.key,
            "armor_training": list(definition.armor_training),
            "weapon_training": list(definition.weapon_training),
        }
    return options


def _spells_options(draft: Draft, service: CompendiumService) -> dict[str, Any]:
    if not draft.class_key:
        return {"casting": None}
    definition = draft.class_definition
    if not definition.casts_spells:
        return {
            "casting": None,
            "hint": f"{definition.name_en} на 1 рівні не чарує — крок можна пропустити.",
        }
    spells = service.class_spells(definition.key, max_level=1)
    cantrips = [entry_brief(entry) for entry in spells.spells if entry.data.get("level") == 0]
    leveled = [entry_brief(entry) for entry in spells.spells if entry.data.get("level") == 1]
    reserved = _granted_for_draft(draft)
    expanded = _expanded_for_draft(draft, service)
    known_ids = {entry["id"] for entry in leveled}
    for entry in expanded:
        if entry["id"] not in known_ids:
            leveled.append(entry)
            known_ids.add(entry["id"])
    ability = draft.class_definition.spellcasting_ability
    prepared_limit = None
    if definition.prepares_spells and ability is not None:
        prepared_limit = max(1, draft.ability_modifier(ability) + 1)
    return {
        "casting": {
            "class_key": definition.key,
            "name_en": definition.name_en,
            "ability": ability.value if ability else None,
            "prepares": definition.prepares_spells,
            "cantrips_limit": definition.cantrips_at(1),
            "spells_known_limit": definition.spells_known_at(1),
            "prepared_limit": prepared_limit,
            "source": spells.source,
        },
        "cantrips": cantrips,
        "spells": leveled,
        "granted": reserved,
        "expanded": [entry["name_en"] for entry in expanded],
        "hint": (
            "Список — зі «Spell Lists» книг. Закляття належить класу, тому "
            "вони й лежать у кроці класу."
        ),
    }


def _granted_for_draft(draft: Draft) -> list[dict[str, Any]]:
    """Що вже дано видом і підкласом — не рахується в лімітах класу."""
    granted: list[dict[str, Any]] = []
    species = draft.species
    if species is not None:
        for name in species.shared_cantrips:
            granted.append({"name_en": name, "level": 0, "source": "species", "prepared": True})
        for spell in species.granted_spells:
            if spell.min_level <= 1:
                granted.append(
                    {
                        "name_en": spell.name_en,
                        "level": spell.spell_level,
                        "source": "species",
                        "prepared": False,
                    }
                )
        for name in draft.spell_choices:
            granted.append({"name_en": name, "level": 0, "source": "species", "prepared": True})
    if draft.class_key:
        definition = draft.class_definition
        spells = definition.subclass_spells_for(draft.subclass_key)
        if spells is not None:
            for name in spells.prepared:
                granted.append(
                    {"name_en": name, "level": 1, "source": "subclass", "prepared": True}
                )
    return granted


def _expanded_for_draft(draft: Draft, service: CompendiumService) -> list[dict[str, Any]]:
    """Розширений список патрона варлока: додаткові закляття на вибір."""
    if not draft.class_key:
        return []
    definition = draft.class_definition
    spells = definition.subclass_spells_for(draft.subclass_key)
    if spells is None or not spells.expanded:
        return []
    entries: list[dict[str, Any]] = []
    for name in spells.expanded:
        page = service.spells(level=1, query=name)
        if not page.items:
            page = service.spells(query=name)
        exact = next(
            (item for item in page.items if item.name_en.casefold() == name.casefold()),
            page.items[0] if page.items else None,
        )
        if exact is not None:
            entries.append(entry_brief(exact))
    return entries
