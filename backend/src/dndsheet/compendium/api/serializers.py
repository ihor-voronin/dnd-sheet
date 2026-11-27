"""Перетворення доменних записів у JSON для API.

Список і один запис віддаються по-різному: у списку текст книги не потрібен
(він важить більше за всі інші поля разом), а в картці запису — потрібен.
Тому `brief` і `full` — різні контракти, і це видно з коду, а не з нагоди.
"""

from __future__ import annotations

from typing import Any

from dndsheet.compendium.domain.entry import CompendiumEntry
from dndsheet.shared.rules import (
    BackgroundMechanics,
    ClassMechanics,
    SpeciesMechanics,
)
from dndsheet.shared.translations import entry_name_uk, entry_text_uk


def entry_brief(entry: CompendiumEntry) -> dict[str, Any]:
    """Запис для списків і вибору: без тексту, але з усіма полями `data`."""
    return {
        "id": entry.id,
        "source_id": entry.source_id,
        "category": entry.category.value,
        "name_en": entry.name_en,
        # Назва з шару перекладу (закляття, риси, вибори класу), якщо в записі її немає.
        "name_uk": entry.name_uk or entry_name_uk(entry.category.value, entry.name_en),
        "display_name": entry.display_name,
        "edition": entry.edition,
        "license": entry.license,
        "page": entry.page,
        "url": entry.url,
        "status": entry.status,
        "translated": entry.is_translated,
        "data": dict(entry.data),
    }


def entry_full(entry: CompendiumEntry) -> dict[str, Any]:
    """Повний запис: додає текст книги й походження."""
    payload = entry_brief(entry)
    payload.update(
        {
            "schema": entry.schema,
            "text_en": entry.text_en,
            "text_uk": entry.text_uk or entry_text_uk(entry.category.value, entry.text_en or ""),
            "fetched_at": entry.fetched_at,
            "notes": list(entry.notes),
        }
    )
    return payload


# ---------------------------------------------------------------------------
# механіки: числа, з яких рахують лист
# ---------------------------------------------------------------------------


def class_mechanics_full(item: ClassMechanics) -> dict[str, Any]:
    """Механіки класу так, як їх чекає візард і обчислювач листа."""
    return {
        "key": item.key,
        "name_en": item.name_en,
        "source_id": item.source_id,
        "hit_die": item.hit_die,
        "saving_throws": [ability.value for ability in sorted(item.saving_throws, key=_order)],
        "skill_choices": [
            {"count": choice.count, "from": [skill.value for skill in choice.options]} for choice in item.skill_choices
        ],
        "skill_any": item.skill_any,
        "skill_limit": item.skill_limit,
        "armor_training": list(item.armor_training),
        "weapon_training": list(item.weapon_training),
        "tool_training": list(item.tool_training),
        "spellcasting": (
            {
                "ability": item.spellcasting_ability.value,
                "progression": item.caster_progression.value if item.caster_progression else None,
                "prepares": item.prepares_spells,
            }
            if item.spellcasting_ability
            else None
        ),
        "cantrips_known": list(item.cantrips_known),
        "spells_known": list(item.spells_known or ()),
        "spell_slots": [list(row) for row in item.spell_slots],
        "pact_slots": [list(row) for row in item.pact_slots],
        "subclass": ({"title": item.subclass_title, "level": item.subclass_level} if item.subclass_title else None),
        "multiclass_requirements": [
            {ability.value: score for ability, score in alternative.items()}
            for alternative in item.multiclass_requirements
        ],
        "multiclass_gained": {
            "armor": list(item.multiclass_armor),
            "weapons": list(item.multiclass_weapons),
            "tools": list(item.multiclass_tools),
        },
        "features": [{"name_en": feature.name_en, "level": feature.level} for feature in item.features],
        "optional_features": {
            name: [{"level": level, "count": count} for level, count in steps]
            for name, steps in item.optional_features.items()
        },
        "subclass_spells": {
            key: {"prepared": list(value.prepared), "expanded": list(value.expanded)}
            for key, value in item.subclass_spells.items()
        },
        "variants": list(item.variants),
    }


def species_mechanics_full(item: SpeciesMechanics) -> dict[str, Any]:
    return {
        "key": item.key,
        "name_en": item.name_en,
        "source_id": item.source_id,
        "subrace_of": item.subrace_of,
        "size": item.size.value,
        "speed": item.speed,
        "ability_bonuses": {bonus.ability.value: bonus.amount for bonus in item.ability_bonuses},
        "ability_choice": (
            {
                "count": item.ability_choice.count,
                "amount": item.ability_choice.amount,
                "from": [ability.value for ability in item.ability_choice.options],
            }
            if item.ability_choice
            else None
        ),
        "skill_proficiencies": sorted(skill.value for skill in item.skill_proficiencies),
        "skill_any": item.skill_any,
        "weapon_proficiencies": list(item.weapon_proficiencies),
        "tool_proficiencies": list(item.tool_proficiencies),
        "tools_any": item.tools_any,
        "languages": list(item.languages),
        "languages_any_standard": item.languages_any_standard,
        "darkvision": item.darkvision,
        "resistances": list(item.resistances),
        "ability_unresolved": item.ability_unresolved,
        "shared_cantrips": list(item.shared_cantrips),
        "cantrip_choice": (
            {
                "from_class": item.cantrip_choice_class,
                "count": item.cantrip_choice_count,
            }
            if item.cantrip_choice_class
            else None
        ),
        "granted_spells": [
            {"name": spell.name_en, "level": spell.spell_level, "min_level": spell.min_level}
            for spell in item.granted_spells
        ],
        "variants": list(item.variants),
    }


def background_mechanics_full(item: BackgroundMechanics) -> dict[str, Any]:
    return {
        "key": item.key,
        "name_en": item.name_en,
        "source_id": item.source_id,
        "skill_proficiencies": sorted(skill.value for skill in item.skill_proficiencies),
        "skill_any": item.skill_any,
        "tool_proficiencies": list(item.tool_proficiencies),
        "tools_any": item.tools_any,
        "languages_any_standard": item.languages_any_standard,
        "feature_en": item.feature_en,
        "variants": list(item.variants),
    }


_ABILITY_ORDER = ("str", "dex", "con", "int", "wis", "cha")


def _order(value: Any) -> int:
    """Порядок характеристик як на листі (STR, DEX, CON, INT, WIS, CHA)."""
    try:
        return _ABILITY_ORDER.index(str(getattr(value, "value", value)))
    except ValueError:
        return len(_ABILITY_ORDER)
