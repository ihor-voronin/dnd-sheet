"""Атаки для вкладки «Дії»: профіль зброї береться з довідника.

Домен рахує бонус і урон (`domain/attacks.py`); тут лише пошук даних предмета
за назвою або `entry_id`. Результат кешується на час життя застосунку:
одна й та сама зброя в десяти персонажах не має читатися з диска десять разів.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
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
from dndsheet.shared.rules import NATURAL_WEAPONS, die_size, is_monk_weapon, martial_arts_die

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


_DAMAGE = re.compile(r"^(\d+d\d+)([+-]\d+)?(.*)$")


def attacks_for(
    character: Character,
    computed: ComputedSheet,
    service: CompendiumService,
    cache: dict[str, WeaponProfile | None] | None = None,
) -> list[dict[str, Any]]:
    """Атаки для всіх зброї в інвентарі, з даними довідника, і удари без зброї.

    Власний урон предмета (`item.damage`) важливіший за довідник: гравець міг
    узяти магічний меч, якого немає в корпусі, і вписати урон сам.
    """
    store = cache if cache is not None else {}
    rules = _AttackRules.of(character, computed)
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
        row = _weapon_row(item, profile, character, computed, rules)
        if row is not None:
            attacks.append(row)
    attacks.extend(_unarmed_rows(character, computed, rules))
    attacks.extend(_shillelagh_rows(character, computed, service, store, rules))
    return attacks


@dataclass(frozen=True, slots=True)
class _AttackRules:
    """Що з класів, рис і викликів змінює атаки — зібране один раз на лист."""

    mods: dict[Ability, int]
    martial_arts: str | None
    hexblade: bool
    pact_blade: bool
    invocations: frozenset[str]
    battle_smith: bool
    feats: frozenset[str]

    @classmethod
    def of(cls, character: Character, computed: ComputedSheet) -> "_AttackRules":
        subclasses = {entry.class_key: (entry.subclass_key or "").casefold() for entry in character.classes}
        armor = character.inventory.worn_armor
        shield = character.inventory.worn_shield
        monk = character.class_level("monk")
        pact_boons = {value.casefold() for value in character.active_class_choices.get("warlock:Pact Boon", ())}
        return cls(
            mods=dict(computed.ability_modifiers),
            # Бойові мистецтва — лише без броні й щита (PHB, p. 78).
            martial_arts=martial_arts_die(monk) if armor is None and shield is None else None,
            hexblade=character.class_level("warlock") > 0 and subclasses.get("warlock", "").endswith("hexblade"),
            pact_blade="pact of the blade" in pact_boons,
            invocations=frozenset(name.casefold() for name in character.invocations),
            battle_smith=character.class_level("artificer") >= 3
            and subclasses.get("artificer", "").endswith("battle-smith"),
            feats=frozenset(feat.casefold().rsplit("/", 1)[-1] for feat in character.feats),
        )


#: Луки й арбалети, які Improved Pact Weapon дозволяє зробити зброєю угоди (XGtE, p. 57).
_PACT_RANGED = ("shortbow", "longbow", "light crossbow", "heavy crossbow")
_MAGIC_BONUS = re.compile(r"\+\s*[123]\b")


def _note(view, text: str):  # noqa: ANN001, ANN202 — AttackProfile
    return replace(view, notes=", ".join(filter(None, [view.notes, text])))


def _weapon_row(
    item: InventoryItem,
    profile: WeaponProfile,
    character: Character,
    computed: ComputedSheet,
    rules: _AttackRules,
) -> dict[str, Any] | None:
    mods = rules.mods
    properties = profile.properties.casefold()
    name = profile.name_en.casefold()
    ranged = "ammunition" in properties
    magic = bool(_MAGIC_BONUS.search(item.name_en)) or item.attuned
    proficient = _weapon_proficient(profile, computed)
    alternatives: dict[Ability, int] = {}
    notes: list[str] = []
    min_die: str | None = None

    # Бойові мистецтва: зброя ченця — Спритність і кістка мистецтв (PHB, p. 78).
    if rules.martial_arts and is_monk_weapon(profile.name_en, properties, profile.group):
        alternatives[Ability.DEX] = mods[Ability.DEX]
        min_die = rules.martial_arts
        notes.append(f"Бойові мистецтва (Martial Arts): Спритність, кістка {rules.martial_arts}")
    # Зброя угоди: ближня (або лук/арбалет з Improved Pact Weapon) — володіння (PHB, p. 107).
    improved = "improved pact weapon" in rules.invocations
    pact = rules.pact_blade and (not ranged or (improved and any(bow in name for bow in _PACT_RANGED)))
    if pact and not proficient:
        proficient = True
        notes.append("володіння — як зброєю угоди (Pact Weapon)")
    # Хекс-воїн: Харизма для зброї угоди й обраної одноручної зброї (XGtE, p. 55).
    if rules.hexblade and proficient and (pact or "two-handed" not in properties):
        alternatives[Ability.CHA] = mods[Ability.CHA]
        if not pact:
            notes.append("Хекс-воїн (Hex Warrior): Харизма — для зброї, обраної після тривалого відпочинку")
    # Бойова готовність: Інтелект для магічної зброї (TCoE, p. 18).
    if rules.battle_smith and magic:
        alternatives[Ability.INT] = mods[Ability.INT]
        notes.append("Бойова готовність (Battle Ready): Інтелект для магічної зброї")

    view = attack_profile(
        profile,
        strength_modifier=mods[Ability.STR],
        dexterity_modifier=mods[Ability.DEX],
        proficiency=computed.proficiency_bonus,
        proficient=proficient,
        alternatives=alternatives,
        min_die=min_die,
    )
    if view is None:
        return None
    # Fighting Style: Archery — +2 до атак дальньою зброєю (PHB, p. 72).
    if ranged and character.has_class_choice("archery"):
        view = replace(view, attack_bonus=view.attack_bonus + 2)
    if item.damage:
        view = replace(view, damage=item.damage.strip())
    if item.notes:
        view = replace(view, notes=item.notes.strip())
    for text in notes:
        view = _note(view, text)
    if pact:
        lifedrinker = "lifedrinker" in rules.invocations
        if improved and not magic:
            view = replace(view, attack_bonus=view.attack_bonus + 1, damage=_add_damage(view.damage, 1))
            view = _note(view, "Покращена зброя угоди (Improved Pact Weapon): +1")
        if lifedrinker:
            view = _note(view, f"Пивець життя (Lifedrinker): +{max(1, mods[Ability.CHA])} некротичного урону")
        if "thirsting blade" in rules.invocations:
            view = _note(view, "Спраглий клинок (Thirsting Blade): дві атаки за дію")
        if improved or lifedrinker:
            view = _note(view, "лише якщо це зброя угоди")
    view = _fighting_style(view, properties, character)
    if computed.armor_untrained:
        view = _note(view, "завада: броня без володіння")
    return {
        "name_en": view.name_en,
        "attack_bonus": view.attack_bonus,
        "damage": view.damage,
        "range": _range_label(profile),
        "ability": view.ability.value,
        "notes": view.notes,
        "equipped": item.equipped,
        "kind": "weapon",
    }


def _unarmed_rows(character: Character, computed: ComputedSheet, rules: _AttackRules) -> list[dict[str, Any]]:
    """Удар без зброї й природна зброя виду (кігті, укус, роги).

    Кістка — найбільша з доступних: 1 (PHB, p. 195), бойові мистецтва ченця,
    Tavern Brawler d4, стиль Unarmed Fighting d6, природна зброя виду.
    Спритність — лише з бойовими мистецтвами.
    """
    mods = rules.mods
    dice: list[tuple[str, str]] = []
    if rules.martial_arts:
        dice.append((rules.martial_arts, f"Бойові мистецтва (Martial Arts): {rules.martial_arts}"))
    if "tavern-brawler" in rules.feats:
        dice.append(("1d4", "Корчемний забіяка (Tavern Brawler): 1d4"))
    if character.has_class_choice("unarmed fighting"):
        dice.append(("1d6", "Бій без зброї (Unarmed Fighting): 1d6, 1d8 — якщо руки вільні"))
    alternatives = {Ability.DEX: mods[Ability.DEX]} if rules.martial_arts else {}

    def row(name_en: str, base: str, damage_type: str, ability: Ability, extra: list[str]) -> dict[str, Any]:
        best, label = max([(base, "")] + dice, key=lambda pair: die_size(pair[0]))
        view = attack_profile(
            WeaponProfile(name_en=name_en, damage=f"{base} {damage_type}"),
            strength_modifier=mods[ability],
            dexterity_modifier=mods[Ability.DEX],
            proficiency=computed.proficiency_bonus,
            alternatives=alternatives,
            min_die=best,
        )
        assert view is not None
        if view.ability is Ability.STR:
            view = replace(view, ability=ability)
        view = replace(view, notes="")
        for text in extra + ([label] if label else []):
            view = _note(view, text)
        if rules.martial_arts:
            view = _note(view, "ще один удар бонусною дією після атаки")
        if computed.armor_untrained and view.ability in (Ability.STR, Ability.DEX):
            view = _note(view, "завада: броня без володіння")
        return {
            "name_en": view.name_en,
            "attack_bonus": view.attack_bonus,
            "damage": view.damage,
            "range": "5 feet",
            "ability": view.ability.value,
            "notes": view.notes,
            "equipped": True,
            "kind": "unarmed",
        }

    rows = [row("Unarmed Strike", "1", "bludgeoning", Ability.STR, [])]
    natural = NATURAL_WEAPONS.get(_slug(character.subspecies_key)) or NATURAL_WEAPONS.get(
        _slug(character.species_key)
    )
    if natural is not None:
        species = character.species
        mpmm = species is not None and "MPMM" in (species.source_id or "").upper()
        base = natural.die_mpmm if mpmm and natural.die_mpmm else natural.die
        extra = ["лише у зміненій формі (Shifting)"] if natural.note == "shifted only" else []
        if natural.ability is Ability.CON:
            extra.append("Статура замість Сили; перевага, якщо у вас менше половини хітів")
        rows.append(row(natural.name_en, base, natural.damage_type, natural.ability, extra))
    return rows


def _slug(value: str | None) -> str:
    return (value or "").strip().casefold().rsplit("/", 1)[-1]


def _shillelagh_rows(
    character: Character,
    computed: ComputedSheet,
    service: CompendiumService,
    cache: dict[str, WeaponProfile | None],
    rules: _AttackRules,
) -> list[dict[str, Any]]:
    """Shillelagh: палиця чи бойовий посох — характеристика чарування й d8 (PHB, p. 275)."""
    known = [spell for spell in character.spells if spell.name_en.casefold() == "shillelagh"]
    granted = any(spell.name_en.casefold() == "shillelagh" for spell in computed.granted_spells)
    if not known and not granted:
        return []
    ability = Ability.WIS
    if known and character.has_class(known[0].class_key):
        casting = character.class_definition(known[0].class_key).spellcasting_ability
        if casting is not None:
            ability = casting
    rows = []
    for item in character.inventory.items:
        folded = item.name_en.casefold()
        if item.kind is not ItemKind.WEAPON or "greatclub" in folded:
            continue
        if "club" not in folded and "quarterstaff" not in folded:
            continue
        profile = _profile(item, service, cache)
        if profile is None:
            continue
        view = attack_profile(
            WeaponProfile(name_en=profile.name_en, damage=profile.damage, group=profile.group),
            strength_modifier=rules.mods[ability],
            dexterity_modifier=rules.mods[Ability.DEX],
            proficiency=computed.proficiency_bonus,
            proficient=True,
            min_die="1d8",
        )
        if view is None:
            continue
        rows.append(
            {
                "name_en": f"{profile.name_en} (Shillelagh)",
                "attack_bonus": view.attack_bonus,
                "damage": view.damage,
                "range": "5 feet",
                "ability": ability.value,
                "notes": "Дубинка (Shillelagh): бонусна дія, 1 хвилина; зброя магічна",
                "equipped": item.equipped,
                "kind": "spell",
            }
        )
    return rows


def _add_damage(damage: str, bonus: int) -> str:
    """«1d8+3 slashing» + 2 → «1d8+5 slashing»."""
    match = _DAMAGE.match(damage)
    if not match:
        return damage
    total = int(match.group(2) or 0) + bonus
    sign = f"{total:+d}" if total else ""
    return f"{match.group(1)}{sign}{match.group(3)}"


def _fighting_style(view, properties: str, character: Character):  # noqa: ANN001, ANN202 — AttackProfile
    """Бойові стилі, що міняють рядок атаки (PHB, p. 72; TCoE, p. 41).

    Dueling: +2 урону зброєю ближнього бою в одній руці — сервер не знає, що в
    другій руці, тож додає й пише умову. Great Weapon Fighting, Two-Weapon
    Fighting і Thrown Weapon Fighting — примітки з умовою.
    """
    melee = "ammunition" not in properties
    if melee and "two-handed" not in properties and character.has_class_choice("dueling"):
        view = replace(view, damage=_add_damage(view.damage, 2))
        view = _note(view, "Дуель (Dueling): +2, якщо в другій руці немає зброї")
    if melee and ("two-handed" in properties or "versatile" in properties) and character.has_class_choice(
        "great weapon fighting"
    ):
        view = _note(view, "Бій великою зброєю (Great Weapon Fighting): перекидайте 1 і 2 на кубиках урону")
    if melee and "light" in properties and character.has_class_choice("two-weapon fighting"):
        view = _note(view, "Бій двома зброями (Two-Weapon Fighting): модифікатор і до урону другої атаки")
    if "thrown" in properties and character.has_class_choice("thrown weapon fighting"):
        view = _note(view, "Бій метальною зброєю (Thrown Weapon Fighting): +2 урону, якщо метнути")
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
        same = [candidate for candidate in page.items if candidate.name_en.casefold() == key]
        # Однойменні записи з різних книг: спершу той, де є група зброї (PHB).
        entry = next((candidate for candidate in same if (candidate.data or {}).get("group")), None) or next(
            iter(same), None
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
