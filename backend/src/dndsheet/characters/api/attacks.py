"""Атаки для вкладки «Дії»: профіль зброї береться з довідника.

Домен рахує бонус і урон (`domain/attacks.py`); тут лише пошук даних предмета
за назвою або `entry_id`. Результат кешується на час життя застосунку:
одна й та сама зброя в десяти персонажах не має читатися з диска десять разів.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from dndsheet.characters.domain.attacks import WeaponProfile, attack_profile
from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.inventory import InventoryItem, ItemKind
from dndsheet.characters.domain.proficiencies import ProficiencyKind
from dndsheet.characters.domain.services.derived_stats import ComputedSheet
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.domain.entry import Category
from dndsheet.compendium.domain.query import EntryQuery
from dndsheet.shared.errors import NotFoundError
from dndsheet.shared.kernel import Ability

#: `Range (20/60)` або `range 20/60` у властивостях зброї.
WEAPON_RANGE = re.compile(r"range\s*\(?\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)


def _range_label(profile: WeaponProfile) -> str:
    """Дистанція зброї з `properties`: 5 ft, досяжність або 20/60 ft."""
    text = profile.properties or ""
    match = WEAPON_RANGE.search(text)
    if match:
        return f"{match.group(1)}/{match.group(2)} feet"
    folded = text.casefold()
    if "reach" in folded:
        return "5 feet (reach)"
    if "ammunition" in folded:
        return "—"
    return "5 feet"


def attacks_for(
    character: Character,
    computed: ComputedSheet,
    service: CompendiumService,
    cache: dict[str, WeaponProfile | None] | None = None,
) -> list[dict[str, Any]]:
    """Атаки для всіх зброї в інвентарі, з даними довідника.

    Власний урон предмета (`item.damage`) важливіший за довідник: гравець міг
    узяти магічний меч, якого немає в корпусі, і вписати урон сам.
    """
    store = cache if cache is not None else {}
    strength = computed.ability_modifiers[Ability.STR]
    dexterity = computed.ability_modifiers[Ability.DEX]
    attacks: list[dict[str, Any]] = []
    for item in character.inventory.items:
        if item.kind is not ItemKind.WEAPON:
            continue
        profile = _profile(item, service, store)
        if profile is None:
            if not item.damage:
                continue
            profile = WeaponProfile(
                name_en=item.name_en,
                damage=item.damage,
                properties=item.notes or "",
            )
        view = attack_profile(
            profile,
            strength_modifier=strength,
            dexterity_modifier=dexterity,
            proficiency=computed.proficiency_bonus,
            proficient=_weapon_proficient(profile, computed),
        )
        if view is None:
            continue
        # Fighting Style: Archery — +2 до атак дальньою зброєю (PHB, p. 72).
        if "ammunition" in profile.properties.casefold() and character.has_class_choice("archery"):
            view = replace(view, attack_bonus=view.attack_bonus + 2)
        if item.damage:
            view = replace(view, damage=item.damage.strip())
        if item.notes:
            view = replace(view, notes=item.notes.strip())
        view = _fighting_style(view, profile.properties.casefold(), character)
        attacks.append(
            {
                "name_en": view.name_en,
                "attack_bonus": view.attack_bonus,
                "damage": view.damage,
                "range": _range_label(profile),
                "ability": view.ability.value,
                "notes": view.notes,
                "equipped": item.equipped,
            }
        )
    return attacks


_DAMAGE = re.compile(r"^(\d+d\d+)([+-]\d+)?(.*)$")


def _fighting_style(view, properties: str, character: Character):  # noqa: ANN001, ANN202 — AttackProfile
    """Бойові стилі, що міняють рядок атаки (PHB, p. 72).

    Dueling: +2 урону зброєю ближнього бою в одній руці — сервер не знає, що в
    другій руці, тож додає й пише умову. Great Weapon Fighting — лише примітка.
    """
    melee = "ammunition" not in properties
    if melee and "two-handed" not in properties and character.has_class_choice("dueling"):
        match = _DAMAGE.match(view.damage)
        if match:
            bonus = int(match.group(2) or 0) + 2
            view = replace(view, damage=f"{match.group(1)}{bonus:+d}{match.group(3)}")
        view = replace(view, notes=", ".join(filter(None, [view.notes, "Дуель (Dueling): +2, якщо в другій руці немає зброї"])))
    if melee and ("two-handed" in properties or "versatile" in properties) and character.has_class_choice(
        "great weapon fighting"
    ):
        view = replace(
            view,
            notes=", ".join(filter(None, [view.notes, "Бій великою зброєю (Great Weapon Fighting): перекидайте 1 і 2 на кубиках урону"])),
        )
    return view


def _singular(value: str) -> str:
    """«longswords» → «longsword», «crossbow, light» → «light crossbow»."""
    text = value.strip().casefold().replace("’", "'")
    if "," in text:
        head, _, tail = text.partition(",")
        text = f"{tail.strip()} {head.strip()}"
    return text[:-1] if text.endswith("s") and not text.endswith("ss") else text


def _weapon_proficient(profile: WeaponProfile, computed: ComputedSheet) -> bool:
    """Чи володіє персонаж цією зброєю: категорією («simple»/«martial») або назвою.

    Власна зброя без групи в довіднику вважається знайомою — інакше вписаний
    гравцем магічний меч раптом втратив би бонус майстерності.
    """
    owned = {
        _singular(item.value)
        for item in computed.proficiencies.items
        if item.kind is ProficiencyKind.WEAPON
    }
    group = profile.group.casefold()
    if not group:
        return True
    if group.startswith("simple") and "simple" in owned:
        return True
    if group.startswith("martial") and "martial" in owned:
        return True
    return _singular(profile.name_en) in owned


def _profile(
    item: InventoryItem,
    service: CompendiumService,
    cache: dict[str, WeaponProfile | None],
) -> WeaponProfile | None:
    key = item.name_en.strip().casefold()
    if key in cache:
        return cache[key]
    entry = None
    if item.entry_id:
        try:
            entry = service.entry(item.entry_id)
        except NotFoundError:
            entry = None
    if entry is None:
        page = service.entries(EntryQuery(category=Category.ITEM, q=item.name_en, limit=10))
        entry = next(
            (candidate for candidate in page.items if candidate.name_en.casefold() == key),
            None,
        )
    profile: WeaponProfile | None = None
    if entry is not None:
        data = dict(entry.data or {})
        damage = data.get("damage")
        if isinstance(damage, str) and damage.strip():
            profile = WeaponProfile(
                name_en=entry.name_en,
                damage=damage.strip(),
                properties=str(data.get("properties") or ""),
                group=str(data.get("group") or ""),
            )
    cache[key] = profile
    return profile
