"""Серіалізація обчисленого листа для HTTP.

Домен не знає про JSON: тут кожне поле перетворюється явно, щоб контракт
відповіді було видно в одному файлі. Ключі — стабільні (англійські), підписи
українською живе у `sheets.domain.labels`.
"""

from __future__ import annotations

from typing import Any

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.proficiencies import Proficiencies
from dndsheet.characters.domain.services.derived_stats import ComputedSheet
from dndsheet.characters.domain.services.spell_slots import Spellcasting
from dndsheet.shared.kernel import Ability


def computed_sheet(character: Character, computed: ComputedSheet) -> dict[str, Any]:
    """Повний обчислений лист: усе, що показує екран персонажа."""
    return {
        "character": character_brief(character),
        "abilities": {
            ability.value: {
                "base": computed.abilities[ability].base,
                "bonus": computed.abilities[ability].bonus,
                "total": computed.abilities[ability].total,
                "modifier": computed.abilities[ability].modifier,
            }
            for ability in Ability
        },
        "proficiency_bonus": computed.proficiency_bonus,
        "saving_throws": {
            ability.value: {
                "value": computed.saving_throws[ability],
                "proficient": computed.saving_throw_proficiency[ability],
            }
            for ability in Ability
        },
        "skills": {
            skill: {"value": value, "proficient": computed.skill_proficiency[skill]}
            for skill, value in computed.skills.items()
        },
        "armor_class": {
            "value": computed.armor_class,
            "parts": [{"label": part.label, "value": part.value} for part in computed.armor_class_parts],
        },
        "initiative": computed.initiative,
        "speed": computed.speed,
        "passive_perception": computed.passive_perception,
        "darkvision": computed.darkvision,
        "resistances": list(computed.resistances),
        "hit_points": {
            "maximum": computed.hit_points.maximum,
            "current": computed.hit_points.current,
            "temporary": computed.hit_points.temporary,
            "bloodied": computed.hit_points.is_bloodied,
            "parts": [
                {"label": part.label, "value": part.value} for part in computed.hit_points.parts
            ],
        },
        "hit_dice": {f"d{die}": count for die, count in sorted(computed.hit_dice.items())},
        "spellcasting": spellcasting(computed.spellcasting),
        "proficiencies": proficiencies(computed.proficiencies),
        "carrying": {
            "capacity": computed.carrying_capacity,
            "weight": computed.carried_weight,
        },
        "modifiers": [
            {
                "kind": item.kind.value,
                "value": item.value,
                "key": item.key,
                "note": item.note_en,
                "source": {"kind": item.source.kind.value, "key": item.source.key},
            }
            for item in computed.modifiers.items
        ],
        "feats": list(computed.feats),
        "warnings": list(computed.warnings),
    }


def character_brief(character: Character) -> dict[str, Any]:
    """Шапка листа: хто це, з чого зібраний."""
    species = character.species
    background = character.background
    return {
        "id": character.id,
        "name": character.name,
        "total_level": character.total_level,
        "alignment": character.alignment,
        "species": (
            {
                "key": species.key,
                "name_en": species.name_en,
                "subspecies": character.subspecies_key,
            }
            if species is not None
            else None
        ),
        "background": (
            {"key": background.key, "name_en": background.name_en}
            if background is not None
            else None
        ),
        "classes": [
            {
                "key": entry.class_key,
                "name_en": definition.name_en,
                "level": entry.level,
                "subclass": entry.subclass_key,
                "hit_die": definition.hit_die,
            }
            for entry, definition in character.class_entries()
        ],
        "version": character.version,
    }


def spellcasting(casting: Spellcasting) -> dict[str, Any]:
    slots = {
        "by_level": {str(level): count for level, count in casting.slots.by_level},
        "pact": (
            {"slots": casting.slots.pact.slots, "level": casting.slots.pact.slot_level}
            if casting.slots.pact
            else None
        ),
        "highest_level": casting.slots.highest_level,
    }
    return {
        "caster_level": casting.caster_level,
        "slots": slots,
        "classes": [
            {
                "key": item.class_key,
                "name_en": item.name_en,
                "ability": item.ability.value,
                "level": item.level,
                "save_dc": item.save_dc,
                "attack_bonus": item.attack_bonus,
                "cantrips_limit": item.cantrips_limit,
                "spells_known_limit": item.spells_known_limit,
                "prepared_limit": item.prepared_limit,
                "prepares": item.prepares,
            }
            for item in casting.classes
        ],
    }


def proficiencies(collected: Proficiencies) -> list[dict[str, Any]]:
    return [
        {
            "kind": item.kind.value,
            "value": item.value,
            "source": {"kind": item.source.kind.value, "key": item.source.key},
        }
        for item in collected.items
    ]
