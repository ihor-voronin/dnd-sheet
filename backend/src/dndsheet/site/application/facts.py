"""Рядки «назва — значення» для сторінок довідника.

Ті самі числа, що на картках візарда (`speciesFacts`, `classFacts`,
`backgroundFacts` у `frontend/src/features/wizard/steps.tsx`): довідник і
створення персонажа мають казати одне. `term` — ключ глосарію, з нього
сторінка робить посилання на пояснення терміна.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from dndsheet.site.application.labels import Labels, units


@dataclass(frozen=True, slots=True)
class Fact:
    label: str
    value: str
    term: str | None = None


def _modifier(value: int) -> str:
    return f"+{value}" if value >= 0 else f"−{abs(value)}"


def _with_any(fixed: str, count: int) -> str:
    if not count:
        return fixed
    return f"{fixed + ' + ' if fixed else ''}{count} на вибір"


def species_facts(item: Mapping[str, Any], labels: Labels) -> list[Fact]:
    speed = int(item.get("speed") or 0)
    if item.get("ability_unresolved"):
        bonuses = "розподіляєте самі (+2 і +1 або +1, +1, +1)"
    else:
        parts = [
            f"{_modifier(int(amount))} {labels.ability_short(code)}"
            for code, amount in (item.get("ability_bonuses") or {}).items()
            if amount
        ]
        bonuses = ", ".join(parts) or "без бонусів"
    facts = [
        Fact("Розмір", labels.size(str(item.get("size") or "")), "size"),
        Fact("Швидкість", f"{speed} фт (≈ {round(speed * 0.3)} м)", "speed"),
        Fact("Характеристики", bonuses, "ability"),
    ]
    if item.get("darkvision"):
        facts.append(Fact("Темний зір", f"{item['darkvision']} фт", "darkvision"))
    skills = ", ".join(labels.skill(skill) for skill in item.get("skill_proficiencies") or ())
    if skills or item.get("skill_any"):
        facts.append(Fact("Навички", _with_any(skills, int(item.get("skill_any") or 0)), "skill"))
    weapons = item.get("weapon_proficiencies") or ()
    if weapons:
        facts.append(Fact("Зброя", ", ".join(labels.proficiency_text("weapon", weapon) for weapon in weapons)))
    tools = ", ".join(labels.term(tool) or tool for tool in item.get("tool_proficiencies") or ())
    if tools or item.get("tools_any"):
        facts.append(Fact("Інструменти", _with_any(tools, int(item.get("tools_any") or 0))))
    languages = ", ".join(labels.language(language) for language in item.get("languages") or ())
    if languages or item.get("languages_any_standard"):
        facts.append(Fact("Мови", _with_any(languages, int(item.get("languages_any_standard") or 0)), "language"))
    resistances = item.get("resistances") or ()
    if resistances:
        facts.append(Fact("Опір", ", ".join(labels.damage(damage) for damage in resistances), "resistance"))
    return facts


def background_facts(item: Mapping[str, Any], labels: Labels, feature: str | None) -> list[Fact]:
    facts: list[Fact] = []
    skills = ", ".join(labels.skill(skill) for skill in item.get("skill_proficiencies") or ())
    if skills or item.get("skill_any"):
        facts.append(Fact("Навички", _with_any(skills, int(item.get("skill_any") or 0)), "skill"))
    tools = ", ".join(labels.proficiency("tool", tool) for tool in item.get("tool_proficiencies") or ())
    if tools or item.get("tools_any"):
        facts.append(Fact("Інструменти", _with_any(tools, int(item.get("tools_any") or 0))))
    if item.get("languages_any_standard"):
        facts.append(Fact("Мови", f"{item['languages_any_standard']} на вибір", "language"))
    if feature:
        facts.append(Fact("Риса", feature, "background_feature"))
    gold = (item.get("money") or {}).get("gp") or 0
    if gold:
        facts.append(Fact("Гроші", f"{gold} зм"))
    return facts


def class_facts(item: Mapping[str, Any], labels: Labels) -> list[Fact]:
    facts: list[Fact] = []
    guide = labels.class_guide(str(item.get("key") or ""))
    primary = guide.get("primary") or ()
    if primary:
        facts.append(
            Fact("Основні характеристики", ", ".join(labels.ability(code) for code in primary), "primary_ability")
        )
    if guide.get("role"):
        facts.append(Fact("Роль", str(guide["role"])))
    if guide.get("complexity"):
        facts.append(Fact("Складність", str(guide["complexity"])))
    hit_die = int(item.get("hit_die") or 0)
    facts.append(Fact("Кість хітів", f"d{hit_die} — на 1 рівні {hit_die} + модифікатор Статури хітів", "hit_die"))
    saves = item.get("saving_throws") or ()
    facts.append(Fact("Рятівні кидки", ", ".join(labels.ability(code) for code in saves), "saving_throw"))
    skills = [labels.skill(skill) for skill in item.get("skill_options") or ()]
    limit = int(item.get("skill_limit") or 0)
    if skills or limit:
        text = f"{limit} на вибір {'із: ' + ', '.join(skills) if skills else 'з будь-яких'}"
        if item.get("skill_any"):
            text += f" + {item['skill_any']} з будь-яких"
        facts.append(Fact("Навички", text, "skill"))
    armor = item.get("armor_training") or ()
    facts.append(
        Fact(
            "Броня",
            ", ".join(labels.proficiency("armor", value) for value in armor) if armor else "без броні",
            "proficiency",
        )
    )
    for label, kind, key in (("Зброя", "weapon", "weapon_training"), ("Інструменти", "tool", "tool_training")):
        values = item.get(key) or ()
        if values:
            facts.append(Fact(label, ", ".join(labels.proficiency(kind, value) for value in values)))
    casting = item.get("spellcasting") or None
    if casting:
        start = int(item.get("casts_from_level") or 1)
        mode = "готує закляття" if casting.get("prepares") else "знає закляття"
        text = f"{f'з {start} рівня, ' if start > 1 else ''}від {labels.ability_genitive(str(casting.get('ability')))}, {mode}"
        if item.get("cantrips_at_level_1"):
            text += f"; заговорів на 1 рівні: {item['cantrips_at_level_1']}"
        if item.get("spells_known_at_level_1"):
            text += f"; заклять: {item['spells_known_at_level_1']}"
        facts.append(Fact("Чарування", text, "spellcasting_ability"))
    else:
        facts.append(Fact("Чарування", "на 1 рівні не чарує"))
    return facts


def spell_level_label(level: int, school: str | None, labels: Labels, ritual: bool = False) -> str:
    parts = [f"{level} рівень" if level else "заговір"]
    if school:
        parts.append(labels.school(school))
    if ritual:
        parts.append("ритуал")
    return " · ".join(parts)


def spell_facts(data: Mapping[str, Any], labels: Labels) -> list[Fact]:
    level = data.get("level")
    level = level if isinstance(level, int) and not isinstance(level, bool) else 0
    facts = [
        Fact("Рівень", spell_level_label(level, data.get("school"), labels, bool(data.get("ritual"))), "spell_level")
    ]
    if data.get("casting_time"):
        facts.append(Fact("Час накладання", units(str(data["casting_time"]).split(",")[0].strip())))
    if data.get("range"):
        facts.append(Fact("Дистанція", units(str(data["range"]).strip())))
    if data.get("components"):
        facts.append(Fact("Компоненти", str(data["components"]), "components"))
    if data.get("duration"):
        facts.append(
            Fact(
                "Тривалість",
                units(str(data["duration"]).strip()),
                "concentration" if data.get("concentration") else None,
            )
        )
    return facts
