"""Серіалізація обчисленого листа для HTTP.

Домен не знає про JSON: тут кожне поле перетворюється явно, щоб контракт
відповіді було видно в одному файлі. Ключі — стабільні (англійські), підписи
українською живе у `sheets.domain.labels`.
"""

from __future__ import annotations

from typing import Any

from dndsheet.characters.application.rows import (
    feature_rows,
    proficiency_rows,
    spell_rows,
)
from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.proficiencies import Proficiencies
from dndsheet.characters.domain.services.derived_stats import ComputedSheet
from dndsheet.characters.domain.services.feature_resources import resources_for
from dndsheet.characters.domain.services.spell_slots import Spellcasting
from dndsheet.characters.domain.wizard import STEP_ORDER, Draft, WizardStep
from dndsheet.shared.kernel import Ability


def computed_sheet(
    character: Character,
    computed: ComputedSheet,
    attacks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
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
        "resources": resources(character, computed),
        "state": {
            "death_saves": {
                "successes": character.state.death_saves.successes,
                "failures": character.state.death_saves.failures,
            },
            "inspiration": character.state.inspiration,
            "exhaustion": character.state.exhaustion,
            "overrides": dict(character.state.overrides),
            "notes": dict(character.state.notes),
        },
        "overridden": sorted(computed.overridden),
        "features": features(character),
        "attacks_per_action": 1
        + sum(1 for row in feature_rows(character) if row.name_en.startswith("Extra Attack")),
        "feature_resources": [
            {
                "key": resource.key,
                "name_en": resource.name_en,
                "class_key": resource.class_key,
                "class_name": resource.class_name,
                "level": resource.level,
                "total": resource.total,
                "used": resource.used,
                "recharge": resource.recharge,
                "action": resource.action,
            }
            for resource in resources_for(character, computed.ability_modifiers)
        ],
        "attacks": attacks or [],
        "spellcasting": spellcasting(computed.spellcasting),
        "spells": spells(character, computed),
        "proficiencies": proficiencies(computed.proficiencies),
        "carrying": {
            "capacity": computed.carrying_capacity,
            "weight": computed.carried_weight,
        },
        "inventory": {
            "money": character.inventory.money.to_dict(),
            "items": [
                {
                    "name_en": item.name_en,
                    "kind": item.kind.value,
                    "quantity": item.quantity,
                    "weight_lb": item.weight_lb,
                    "equipped": item.equipped,
                    "attuned": item.attuned,
                    "entry_id": item.entry_id,
                    "armor_base": item.armor_base,
                    "dex_cap": item.dex_cap,
                    "notes": item.notes,
                    "damage": item.damage,
                }
                for item in character.inventory.items
            ],
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
    waiver_keys = {waiver.class_key for waiver in character.multiclass_waivers}
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
                "requirements_ignored": entry.class_key in waiver_keys,
            }
            for entry, definition in character.class_entries()
        ],
        # Лист має показати, що вимоги мультикласу обійшли, а не мовчати.
        "multiclass_waivers": [
            {"class_key": waiver.class_key, "requirements": list(waiver.requirements)}
            for waiver in character.multiclass_waivers
        ],
        "version": character.version,
    }


def resources(character: Character, computed: ComputedSheet) -> dict[str, Any]:
    """Лічильники: скільки всього й скільки витрачено — для кнопок листа."""
    slots = {
        str(level): {"total": total, "used": character.state.slot_used(level)}
        for level, total in computed.spellcasting.slots.by_level
    }
    pact = computed.spellcasting.slots.pact
    return {
        "slots": slots,
        "pact": (
            {"total": pact.slots, "used": character.state.pact_used} if pact is not None else None
        ),
        "hit_dice": {
            f"d{die}": {"total": total, "used": character.state.hit_die_used(die)}
            for die, total in sorted(computed.hit_dice.items())
        },
    }


def features(character: Character) -> list[dict[str, Any]]:
    """Уміння класів на поточному рівні — назви й рівень, без тексту.

    Збирання рядків — у `characters.application.rows`, щоб експорт і екран
    показували однаковий список.
    """
    return [
        {
            "name_en": row.name_en,
            "level": row.level,
            "class_key": row.class_key,
            "class_name": row.class_name,
            "source": "class",
        }
        for row in feature_rows(character)
    ]


def spells(character: Character, computed: ComputedSheet) -> list[dict[str, Any]]:
    """Усі закляття персонажа: класові (вибір гравця) + надані видом/підкласом."""
    entry_ids = _entry_ids(character)
    return [
        {
            "name_en": row.name_en,
            "level": row.level,
            "class_key": row.class_key,
            "entry_id": entry_ids.get(row.name_en.casefold()),
            "prepared": row.prepared,
            "always_prepared": row.always_prepared,
            "source": row.source,
            # Власне закляття: лист має позначити його, а не вдавати книжкове.
            "custom": row.custom,
            # Текст власного закляття йде як опис; книжковим його допише
            # довідник (див. `spell_meta.enrich_spells`).
            "description": row.description,
        }
        for row in spell_rows(character, computed)
    ]


def _entry_ids(character: Character) -> dict[str, str | None]:
    """`entry_id` за назвою закляття — для переходів у довідник з екрана."""
    return {spell.name_en.casefold(): spell.entry_id for spell in character.spells}


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
                "max_spell_level": item.max_spell_level,
            }
            for item in casting.classes
        ],
    }


def proficiencies(collected: Proficiencies) -> list[dict[str, Any]]:
    return [
        {
            "kind": row.kind.value,
            "value": row.value,
            "source": {"kind": row.source_kind, "key": row.source_key},
        }
        for row in proficiency_rows(collected)
    ]


# ---------------------------------------------------------------------------
# чернетка візарда
# ---------------------------------------------------------------------------


def draft_payload(draft: Draft) -> dict[str, Any]:
    """Стан чернетки: відповіді кроків, їхній статус і що буде далі."""
    statuses = draft.statuses()
    next_step = draft.next_step()
    return {
        "id": draft.id,
        "revision": draft.revision,
        "name": draft.name,
        "answers": {step.value: step_answers(draft, step) for step in STEP_ORDER},
        "steps": [
            {
                "step": status.step.value,
                "complete": status.complete,
                "unlocked": status.unlocked,
                "optional": status.optional,
            }
            for status in statuses
        ],
        "next_step": next_step.value if next_step else None,
        "ready_to_finish": ready_to_finish(draft),
    }


def ready_to_finish(draft: Draft) -> bool:
    try:
        draft.validate_for_finish()
    except Exception:  # noqa: BLE001 — будь-яка причина означає «ще не готово»
        return False
    return True


def step_answers(draft: Draft, step: WizardStep) -> dict[str, Any]:
    """Відповідь кроку в тій самій формі, яку приймає `PUT` цього кроку."""
    if step is WizardStep.SPECIES:
        return {
            "name": draft.name,
            "species_key": draft.species_key,
            "subspecies_key": draft.subspecies_key,
            "ability_choices": [ability.value for ability in draft.ability_choices],
            "ability_spread": {
                ability.value: amount for ability, amount in draft.ability_spread.items()
            },
            "spell_choices": list(draft.spell_choices),
        }
    if step is WizardStep.CLASS:
        return {"class_key": draft.class_key, "subclass_key": draft.subclass_key}
    if step is WizardStep.ABILITIES:
        return {
            "method": draft.ability_method.value if draft.ability_method else None,
            "scores": {ability.value: score for ability, score in draft.ability_scores.items()},
            "rolls": list(draft.roll_set),
        }
    if step is WizardStep.BACKGROUND:
        return {
            "background_key": draft.background_key,
            "alignment": draft.alignment,
            "picks": [
                {
                    "kind": item.kind.value,
                    "value": item.value,
                    "source": {"kind": item.source.kind.value, "key": item.source.key},
                }
                for item in draft.picks
            ],
        }
    if step is WizardStep.EQUIPMENT:
        return {
            "items": [
                {
                    "name_en": item.name_en,
                    "kind": item.kind.value,
                    "quantity": item.quantity,
                    "weight_lb": item.weight_lb,
                    "equipped": item.equipped,
                    "attuned": item.attuned,
                    "entry_id": item.entry_id,
                    "armor_base": item.armor_base,
                    "dex_cap": item.dex_cap,
                }
                for item in draft.items
            ],
            "money": draft.money.to_dict(),
            "submitted": draft.equipment_submitted,
        }
    return {
        "spells": [
            {
                "name_en": spell.name_en,
                "level": spell.level,
                "class_key": spell.class_key,
                "entry_id": spell.entry_id,
                "prepared": spell.prepared,
                "always_prepared": spell.always_prepared,
            }
            for spell in draft.spells
        ]
    }

