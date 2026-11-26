"""Атаки для вкладки «Дії»: профіль зброї береться з довідника.

Домен рахує бонус і урон (`domain/attacks.py`); тут лише пошук даних предмета
за назвою або `entry_id`. Результат кешується на час життя застосунку:
одна й та сама зброя в десяти персонажах не має читатися з диска десять разів.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from dndsheet.characters.domain.attacks import WeaponProfile, attack_profile
from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.inventory import InventoryItem, ItemKind
from dndsheet.characters.domain.services.derived_stats import ComputedSheet
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.domain.entry import Category
from dndsheet.compendium.domain.query import EntryQuery
from dndsheet.shared.errors import NotFoundError
from dndsheet.shared.kernel import Ability


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
        )
        if view is None:
            continue
        if item.damage:
            view = replace(view, damage=item.damage.strip())
        if item.notes:
            view = replace(view, notes=item.notes.strip())
        attacks.append(
            {
                "name_en": view.name_en,
                "attack_bonus": view.attack_bonus,
                "damage": view.damage,
                "ability": view.ability.value,
                "notes": view.notes,
                "equipped": item.equipped,
            }
        )
    return attacks


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
            )
    cache[key] = profile
    return profile
