"""HTTP-шар підвищення рівня: план і застосування.

План — це відповідь на питання «що я отримаю, якщо візьму рівень?», і його
збирає **не домен**, а цей шар: тут є довідник, а отже — підкласи, їхні
вміння й списки заклять. Домен рахує лише числа (хіти, комірки, ліміти).

Екран підвищення вміє те саме, що аркуш D&D Beyond: обрати клас (наявний або
новий — мультиклас), кинути кість хітів або взяти середнє, обрати підклас на
його рівні, покращити характеристики чи взяти рису, додати закляття.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from dndsheet.characters.api import classes_uk, subclasses_uk
from dndsheet.characters.api.features import (
    class_texts_all,
    feature_text_for,
    strip_level_line,
    subclass_features,
    subclass_intro,
)
from dndsheet.characters.application.level_up import LevelUpService
from dndsheet.characters.domain.proficiencies import ProficiencyKind
from dndsheet.characters.domain.services.feature_resources import name_of
from dndsheet.characters.domain.services.level_up import LevelPlan
from dndsheet.compendium.api.serializers import entry_brief
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.shared.kernel import Skill
from dndsheet.shared.rules import MULTICLASS_SKILLS, MUSICAL_INSTRUMENTS, feat_ability_options


def level_up_payload(
    character,  # noqa: ANN001 — Character
    service: LevelUpService,
    compendium: CompendiumService,
    cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """План наступного рівня для кожного класу."""
    plans = service.planner.plans(character)
    return {
        "character_id": character.id,
        "name": character.name,
        "version": character.version,
        "total_level": character.total_level,
        "max_level": 20,
        "can_level_up": bool(plans),
        # Риси з +1 до характеристики: id → можливі характеристики (Actor → cha).
        "feat_abilities": {
            entry.id: [ability.value for ability in options]
            for entry in compendium.feats()
            if (options := feat_ability_options(entry.text_en or ""))
        },
        "plans": [
            {
                **plan_payload(
                    plan,
                    compendium,
                    cache,
                    current_subclass=_current_subclass(character, plan.class_key),
                ),
                "skill_options": _multiclass_skills(character, plan),
                # Бард при мультикласі: один музичний інструмент (PHB, p. 164).
                "tool_options": list(MUSICAL_INSTRUMENTS) if plan.is_new_class and plan.class_key == "bard" else [],
            }
            for plan in plans
        ],
    }


def _multiclass_skills(character, plan: LevelPlan) -> list[str]:  # noqa: ANN001
    """Навички, з яких новий клас дає одну (бард — будь-яка; PHB, p. 164)."""
    if not plan.is_new_class or plan.class_key not in MULTICLASS_SKILLS:
        return []
    definition = character.class_definition(plan.class_key)
    pool = tuple(Skill) if definition.skill_any else definition.skill_options()
    owned = character.all_proficiencies()
    return [skill.value for skill in pool if not owned.has(ProficiencyKind.SKILL, skill.value)]


def plan_payload(
    plan: LevelPlan,
    compendium: CompendiumService,
    cache: dict[str, Any] | None = None,
    *,
    current_subclass: str | None = None,
) -> dict[str, Any]:
    """Один план: числа домену + вибір із довідника."""
    # Тексти вмінь класу — щоб екран показав не лише назву, а й що саме дає
    # рівень (і українською, якщо переклад уже є).
    # Тексти вмінь — з *усіх* книг класу (PHB + TCoE): опційні вміння
    # («Magical Guidance», «Primal Knowledge») є лише в TCoE, і без цього
    # екран підвищення рівня показував би «тексту немає».
    class_texts = class_texts_all(compendium, plan.class_key, cache)
    return {
        "class_key": plan.class_key,
        "class_name": plan.class_name,
        "is_new_class": plan.is_new_class,
        "current_level": plan.current_level,
        "new_level": plan.new_level,
        "total_level_before": plan.total_level_before,
        "total_level_after": plan.total_level_after,
        "hit_die": plan.hit_die,
        "constitution_modifier": plan.constitution_modifier,
        "hp": {"average": plan.hp_average, "best_roll": plan.hp_best_roll},
        "features": [_feature_payload(feature, class_texts) for feature in plan.features],
        "subclass": _subclass_payload(plan, compendium, cache, current=current_subclass),
        "subclass_features": _subclass_features_payload(compendium, cache, current_subclass, plan.new_level),
        "asi": {
            "slots": plan.asi_slots,
            "taken": plan.asi_taken,
            "pending": plan.asi_pending,
        },
        "proficiency_bonus": {
            "before": plan.proficiency_bonus_before,
            "after": plan.proficiency_bonus_after,
        },
        "limits": {
            "cantrips": {"before": plan.cantrips_before, "after": plan.cantrips_after},
            "spells_known": {
                "before": plan.spells_known_before,
                "after": plan.spells_known_after,
            },
            "prepared": {"before": plan.prepared_before, "after": plan.prepared_after},
        },
        "slots": [asdict(row) for row in plan.slots],
        "pact": {
            "before": list(plan.pact_before) if plan.pact_before else None,
            "after": list(plan.pact_after) if plan.pact_after else None,
        },
        "caster_level": {"before": plan.caster_level_before, "after": plan.caster_level_after},
        "max_spell_level": plan.max_spell_level,
        "resources_added": [
            {
                "key": key,
                "name_en": name_of(key) or key,
                **(
                    {"name_uk": uk_name}
                    # Ресурс підкласу (Удача Темного) — у шарі перекладу підкласів.
                    if (
                        uk_name := classes_uk.name_uk(name_of(key) or key)
                        or subclasses_uk.name_uk(name_of(key) or key)
                    )
                    else {}
                ),
            }
            for key in plan.resources_after
            if key not in plan.resources_before
        ],
        "allowed": plan.allowed,
        "blocked_reason": plan.blocked_reason,
        "requirements": list(plan.requirements),
    }


def _feature_payload(feature: Any, texts: dict[str, str]) -> dict[str, Any]:  # noqa: ANN401
    """Нове вміння класу: назва, рівень і текст правила.

    `text` — оригінал книги (для звірки), `text_uk` — переклад, якщо він є.
    """
    row: dict[str, Any] = {"name_en": feature.name_en, "level": feature.level}
    text = feature_text_for(feature.name_en, texts)
    if text:
        row["text"] = text
    classes_uk.enrich_feature(row)
    strip_level_line(row)
    if "name_uk" not in row and (uk_name := classes_uk.name_uk(feature.name_en)):
        row["name_uk"] = uk_name
    return row


def _subclass_payload(
    plan: LevelPlan,
    compendium: CompendiumService,
    cache: dict[str, Any] | None,
    *,
    current: str | None,
) -> dict[str, Any] | None:
    if plan.subclass_level is None:
        return None
    options: list[dict[str, Any]] = []
    if plan.subclass_required:
        definition = compendium.class_mechanics(plan.class_key)
        for entry in compendium.subclasses(definition.name_en):
            # Лише те, що потрібно для вибору: повний запис довідника тут
            # роздував би відповідь у десять разів (у жреця 20 доменів).
            brief = entry_brief(entry)
            items = subclass_features(compendium, entry.id, cache)
            intro = subclass_intro(compendium, entry.id, cache)
            options.append(
                {
                    "id": brief["id"],
                    "name_en": brief["name_en"],
                    # Назва підкласу — з шару перекладу (за назвою, а не за
                    # хвостом id, як у TERMS на фронтенді).
                    "name_uk": subclasses_uk.name_uk(brief["name_en"]) or brief["name_uk"],
                    "source_id": brief["source_id"],
                    # Вступ до глави: «що це за спеціалізація».
                    "description": intro.get("description", ""),
                    "description_uk": intro.get("description_uk"),
                    # Усі вміння підкласу з рівнями: гравець має бачити, що
                    # обрана спеціалізація дасть не лише сьогодні, а й далі.
                    "features": [
                        {
                            "name_en": item["name_en"],
                            "level": item["level"],
                            "new": item["level"] == plan.new_level,
                            **({"name_uk": item["name_uk"]} if item.get("name_uk") else {}),
                            # Текст даємо лише для рівня, який обирають зараз:
                            # уся історія підкласу — це вже зайві кілобайти.
                            **(
                                {"text": item["description"]}
                                if item["level"] == plan.new_level and item.get("description")
                                else {}
                            ),
                            **(
                                {"text_uk": item["text_uk"]}
                                if item["level"] == plan.new_level and item.get("text_uk")
                                else {}
                            ),
                        }
                        for item in items
                    ],
                }
            )
    return {
        "title": plan.subclass_title,
        "level": plan.subclass_level,
        "required": plan.subclass_required,
        "current": current,
        "options": options,
    }


def _subclass_features_payload(
    compendium: CompendiumService,
    cache: dict[str, Any] | None,
    subclass_key: str | None,
    level: int,
) -> list[dict[str, Any]]:
    """Що підклас дає саме на новому рівні.

    Записи вже з перекладом (`name_uk`/`text_uk`): їх готує `subclass_features`.
    """
    if not subclass_key:
        return []
    return [item for item in subclass_features(compendium, subclass_key, cache) if item["level"] == level]


def _current_subclass(character, class_key: str) -> str | None:  # noqa: ANN001
    for entry in character.classes:
        if entry.class_key == class_key:
            return entry.subclass_key
    return None


def report_payload(report) -> dict[str, Any]:  # noqa: ANN001 — LevelUpReport
    return asdict(report)


__all__ = ["level_up_payload", "plan_payload", "report_payload"]
