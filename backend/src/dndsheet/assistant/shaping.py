"""Відповіді API у формі, зручній моделі: коротко, з ключами й українськими назвами.

Повний лист — ~20 КБ із текстами книг; опції кроку візарда — сотні КБ.
Модель не мусить усе це читати: короткий лист містить числа й стан, опції —
структуру й ключі, а довгі тексти обрізано (повний опис — `get_compendium_entry`).
"""

from __future__ import annotations

from typing import Any

#: Поля з прозою книг: у відповіді лишається початок.
TEXT_LIMIT = 200


def _uk(item: dict[str, Any]) -> str:
    return str(item.get("name_uk") or item.get("name_en") or item.get("name") or "")


def compact(value: Any, limit: int = TEXT_LIMIT) -> Any:  # noqa: ANN401 — довільний JSON
    """Та сама структура, але довгі рядки обрізано до `limit` символів."""
    if isinstance(value, dict):
        return {key: compact(item, limit) for key, item in value.items()}
    if isinstance(value, list):
        return [compact(item, limit) for item in value]
    if isinstance(value, str) and len(value) > limit:
        return value[:limit].rstrip() + "…"
    return value


def summary(sheet: dict[str, Any]) -> dict[str, Any]:
    """Короткий лист: усе, що потрібно за столом, без текстів книг."""
    character = sheet.get("character") or {}
    abilities = sheet.get("abilities") or {}
    resources = sheet.get("resources") or {}
    state = sheet.get("state") or {}
    hp = sheet.get("hit_points") or {}
    inventory = sheet.get("inventory") or {}
    spellcasting = sheet.get("spellcasting") or {}
    return {
        "id": character.get("id"),
        "name": character.get("name"),
        "version": character.get("version"),
        "level": character.get("total_level"),
        "species": character.get("species"),
        "background": character.get("background"),
        "classes": [
            {
                "key": entry.get("key"),
                "name": entry.get("name_en"),
                "level": entry.get("level"),
                "subclass": entry.get("subclass_name_uk") or entry.get("subclass_name") or entry.get("subclass"),
            }
            for entry in character.get("classes") or []
        ],
        "abilities": {
            key: {"score": item.get("total"), "modifier": item.get("modifier")} for key, item in abilities.items()
        },
        "proficiency_bonus": sheet.get("proficiency_bonus"),
        "armor_class": (sheet.get("armor_class") or {}).get("value"),
        "initiative": sheet.get("initiative"),
        "speed": sheet.get("speed"),
        "passive_perception": sheet.get("passive_perception"),
        "hit_points": {key: hp.get(key) for key in ("current", "maximum", "temporary")},
        "hit_dice": resources.get("hit_dice"),
        "spell_slots": resources.get("slots"),
        "pact_slots": resources.get("pact"),
        "saving_throws": {
            key: {"value": item.get("value"), "proficient": item.get("proficient")}
            for key, item in (sheet.get("saving_throws") or {}).items()
        },
        "skills": {
            key: {"value": item.get("value"), "expertise": item.get("expertise")}
            for key, item in (sheet.get("skills") or {}).items()
            if item.get("proficient")
        },
        "attacks": [
            {"name": item.get("name_en"), "bonus": item.get("attack_bonus"), "damage": item.get("damage")}
            for item in sheet.get("attacks") or []
        ],
        "spellcasting": [
            {"class": item.get("key"), "save_dc": item.get("save_dc"), "attack_bonus": item.get("attack_bonus")}
            for item in spellcasting.get("classes") or []
        ],
        "spells": [
            {
                "name": item.get("name_en"),
                "name_uk": item.get("name_uk"),
                "level": item.get("level"),
                "class": item.get("class_key"),
                "prepared": item.get("prepared") or item.get("always_prepared"),
            }
            for item in sheet.get("spells") or []
        ],
        "features": [{"name": _uk(item), "level": item.get("level")} for item in sheet.get("features") or []],
        "feature_uses": [
            {
                "key": item.get("key"),
                "name": _uk(item),
                "used": item.get("used"),
                "total": item.get("total"),
                "recharge": item.get("recharge"),
            }
            for item in sheet.get("feature_resources") or []
        ],
        "money": inventory.get("money"),
        "items": [
            {
                "index": index,
                "name": item.get("name_uk") or item.get("name_en"),
                "name_en": item.get("name_en"),
                "quantity": item.get("quantity"),
                "equipped": item.get("equipped"),
                "attuned": item.get("attuned"),
            }
            for index, item in enumerate(inventory.get("items") or [])
        ],
        "state": {key: state.get(key) for key in ("death_saves", "inspiration", "exhaustion")},
        "open_choices": [
            # `group` — ключ для set_class_choice («fighter:Fighting Style»), `name` — для людини.
            {
                "group": item.get("key"),
                "name": item.get("group"),
                "slots": item.get("slots"),
                "chosen": item.get("chosen"),
            }
            for item in sheet.get("class_choices") or []
            if len(item.get("chosen") or []) < (item.get("slots") or 0)
        ],
        "warnings": sheet.get("warnings") or [],
    }
