"""Передісторія для листа: що вона дає і який у неї текст.

У агрегаті є лише ключ, назва й механіки (навички, інструменти, мови, риса).
Текст «звідки це» живе в довіднику: там опис, рядок Equipment і розділ
`#### Feature: Military Rank`. Цей модуль вирізає їх для вкладки
«Передісторія», а вміння беруться з уже зібраних володінь персонажа — тобто
саме ті, які гравець обрав (мова, інструмент), а не «скільки можна обрати».

Результат кешується на застосунку: тексти книг не змінюються.
"""

from __future__ import annotations

import re
from typing import Any

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.proficiencies import ProficiencyKind
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.domain.entry import Category
from dndsheet.compendium.domain.query import EntryQuery
from dndsheet.shared.errors import NotFoundError

#: `#### Feature: Military Rank` — так оформлені риси передісторій.
FEATURE_HEAD = re.compile(r"^#{2,4}\s+Feature:\s*(.+?)\s*$", re.IGNORECASE)
HEADING = re.compile(r"^#{2,4}\s+")
MECHANICAL = ("Skill Proficiencies:", "Tool Proficiencies:", "Languages:", "Equipment:")


def enrich_background(
    payload: dict[str, Any],
    character: Character,
    service: CompendiumService,
    cache: dict[str, Any] | None = None,
) -> None:
    background = character.background
    if background is None:
        payload["background_details"] = None
        return
    store = cache if cache is not None else {}
    key = f"background:{background.name_en.casefold()}"
    if key not in store:
        store[key] = _details(service, character)
    payload["background_details"] = store[key]


def _details(service: CompendiumService, character: Character) -> dict[str, Any]:
    background = character.background
    entry = _entry(service, background.name_en)
    text = entry.text_en or "" if entry is not None else ""
    description, equipment = _split_description(text)
    feature_text = _feature_text(text, background.feature_en)

    items = character.all_proficiencies().items
    mine = [
        item
        for item in items
        if item.source.kind.value == "background" and item.source.key == background.key
    ]

    def values(kind: ProficiencyKind) -> list[str]:
        return sorted({str(item.value) for item in mine if item.kind is kind})

    chosen = [
        item
        for item in character.chosen.items
        if item.source.kind.value == "background" and item.source.key == background.key
    ]

    def remaining(kind: ProficiencyKind, total: int) -> int:
        picked = sum(1 for item in chosen if item.kind is kind)
        return max(0, total - picked)

    return {
        "key": background.key,
        "name_en": background.name_en,
        "source_id": background.source_id,
        "feature_en": background.feature_en,
        "feature_text": feature_text,
        "description": description,
        "equipment": equipment,
        "skills": values(ProficiencyKind.SKILL),
        "tools": values(ProficiencyKind.TOOL),
        "languages": values(ProficiencyKind.LANGUAGE),
        "skill_any": remaining(ProficiencyKind.SKILL, background.skill_any),
        "tools_any": remaining(ProficiencyKind.TOOL, background.tools_any),
        "languages_any": remaining(
            ProficiencyKind.LANGUAGE, background.languages_any_standard
        ),
    }


def _entry(service: CompendiumService, name: str):  # noqa: ANN202
    """Запис довідника за точною назвою (без «базових правил»)."""
    page = service.entries(EntryQuery(category=Category.BACKGROUND, q=name, limit=100))
    wanted = name.strip().casefold()
    matches = [
        entry for entry in page.items if entry.name_en.strip().casefold() == wanted
    ]
    if not matches:
        return None
    matches.sort(key=lambda entry: (entry.source_id == "basic-rules-2014", entry.id))
    return matches[0]


def _split_description(text: str) -> tuple[str, str]:
    """Опис до першого підзаголовка; рядок Equipment — окремо."""
    head = re.split(r"(?m)^#{2,4}\s+", text, maxsplit=1)[0]
    lines: list[str] = []
    equipment = ""
    for line in head.splitlines():
        stripped = line.strip()
        if stripped.startswith(MECHANICAL):
            if stripped.startswith("Equipment:"):
                equipment = stripped.split(":", 1)[1].strip()
            continue
        lines.append(line.rstrip())
    description = "\n".join(lines).strip()
    while "\n\n\n" in description:
        description = description.replace("\n\n\n", "\n\n")
    return description, equipment


def _feature_text(text: str, feature: str | None) -> str:
    if not feature:
        return ""
    lines = text.splitlines()
    wanted = feature.strip().casefold()
    start = None
    for position, line in enumerate(lines):
        match = FEATURE_HEAD.match(line.strip())
        if match and match.group(1).strip().casefold() == wanted:
            start = position + 1
            break
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        if HEADING.match(line.strip()):
            break
        body.append(line.rstrip())
    return "\n".join(body).strip()


__all__ = ["enrich_background"]
