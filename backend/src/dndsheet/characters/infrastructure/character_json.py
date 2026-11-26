"""Збереження агрегатів у JSON: один формат на диск і назад.

Тут живе те, що не має бути в домені: як саме `Character` і `Draft`
виглядають у файлі. Домен знає лише свої типи; адаптер `json_store` викликає
ці функції й пише байти. Коли зʼявиться БД (етап 6), зміниться адаптер, а
формат лишиться тим самим контрактом — тому він і версіонований.

Правила відновлення:

* невідомий `schema` — помилка, а не «спробуємо як є»;
* ключ класу/виду/передісторії читається з `RulesSource` у момент
  відновлення, тому числа не дублюються у файлі: правила лишаються єдиним
  джерелом істини;
* усе, що зберігається, — це **стан**, а не похідні: максимум хітів, КЗ, слоти
  не пишуться, бо вони рахуються кожного разу з правил.
"""

from __future__ import annotations

from typing import Any, Mapping

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.class_level import CharacterClass, MulticlassWaiver
from dndsheet.characters.domain.inventory import Inventory, InventoryItem, ItemKind
from dndsheet.characters.domain.ports import RulesSource
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiency,
    ProficiencyKind,
    Proficiencies,
    SourceKind,
)
from dndsheet.characters.domain.spells import KnownSpell
from dndsheet.characters.domain.state import DeathSaves, SheetState
from dndsheet.characters.domain.vitals import HitPointState
from dndsheet.characters.domain.wizard import AbilityMethod, Draft
from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import Ability, AbilityScore, Money

CHARACTER_SCHEMA = "character/2"
#: `character/1` писав `hp.current: 0` і для «повних хітів»: калькулятор
#: підставляв максимум, тому відрізнити «не задано» від «0 хітів» було нічим.
LEGACY_CHARACTER_SCHEMAS = frozenset({"character/1"})
DRAFT_SCHEMA = "wizard-draft/1"


# ---------------------------------------------------------------------------
# дрібні частини: спільні для персонажа й чернетки
# ---------------------------------------------------------------------------


def abilities_to_record(abilities: Mapping[Ability, AbilityScore]) -> dict[str, int]:
    return {ability.value: score.value for ability, score in abilities.items()}


def ability_spread_from_record(record: Mapping[str, Any] | None) -> dict[Ability, int]:
    """Вільний розподіл бонусів (правила 2022) із файлу."""
    spread: dict[Ability, int] = {}
    for key, value in (record or {}).items():
        try:
            spread[Ability(str(key))] = int(value)
        except (ValueError, TypeError) as exc:
            raise ValidationError(f"невірний розподіл бонусів: {key!r}") from exc
    return spread


def abilities_from_record(record: Mapping[str, Any] | None) -> dict[Ability, AbilityScore]:
    values: dict[Ability, AbilityScore] = {}
    for key, value in (record or {}).items():
        try:
            ability = Ability(str(key))
        except ValueError as exc:
            raise ValidationError(f"невідома характеристика у файлі: {key!r}") from exc
        values[ability] = AbilityScore(int(value))
    return values


def proficiencies_to_record(collected: Proficiencies) -> list[dict[str, Any]]:
    return [
        {
            "kind": item.kind.value,
            "value": item.value,
            "source": {"kind": item.source.kind.value, "key": item.source.key},
        }
        for item in collected.items
    ]


def proficiencies_from_record(records: list[Mapping[str, Any]] | None) -> tuple[Proficiency, ...]:
    items: list[Proficiency] = []
    for record in records or ():
        try:
            kind = ProficiencyKind(str(record["kind"]))
            source = record["source"]
            items.append(
                Proficiency(
                    kind=kind,
                    value=str(record["value"]),
                    source=GrantSource(
                        kind=SourceKind(str(source["kind"])),
                        key=str(source["key"]),
                    ),
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ValidationError(f"невірне володіння у файлі: {record!r}") from exc
    return tuple(items)


def inventory_to_record(inventory: Inventory) -> dict[str, Any]:
    return {
        "money": inventory.money.to_dict(),
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
            for item in inventory.items
        ],
    }


def inventory_from_record(record: Mapping[str, Any] | None) -> Inventory:
    record = record or {}
    items: list[InventoryItem] = []
    for raw in record.get("items") or ():
        try:
            items.append(
                InventoryItem(
                    name_en=str(raw["name_en"]),
                    kind=ItemKind(str(raw.get("kind") or ItemKind.GEAR.value)),
                    quantity=int(raw.get("quantity") or 1),
                    weight_lb=float(raw.get("weight_lb") or 0),
                    equipped=bool(raw.get("equipped")),
                    attuned=bool(raw.get("attuned")),
                    entry_id=raw.get("entry_id") or None,
                    armor_base=raw.get("armor_base"),
                    dex_cap=raw.get("dex_cap"),
                    notes=raw.get("notes") or None,
                    damage=raw.get("damage") or None,
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ValidationError(f"невірний предмет у файлі: {raw!r}") from exc
    money_payload = record.get("money") or {}
    money = Money(
        pp=int(money_payload.get("pp") or 0),
        gp=int(money_payload.get("gp") or 0),
        ep=int(money_payload.get("ep") or 0),
        sp=int(money_payload.get("sp") or 0),
        cp=int(money_payload.get("cp") or 0),
    )
    return Inventory(items=tuple(items), money=money)


def state_to_record(state: SheetState) -> dict[str, Any]:
    return {
        "slots_used": {str(level): count for level, count in state.slots_used.items()},
        "pact_used": state.pact_used,
        "hit_dice_used": {f"d{die}": count for die, count in state.hit_dice_used.items()},
        "feature_used": dict(state.feature_used),
        "death_saves": {
            "successes": state.death_saves.successes,
            "failures": state.death_saves.failures,
        },
        "inspiration": state.inspiration,
        "exhaustion": state.exhaustion,
        "overrides": dict(state.overrides),
        "notes": dict(state.notes),
    }


def state_from_record(record: Mapping[str, Any] | None) -> SheetState:
    payload = record or {}
    saves = payload.get("death_saves") or {}
    slots: dict[int, int] = {}
    for key, value in (payload.get("slots_used") or {}).items():
        try:
            slots[int(key)] = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"невірні витрачені слоти: {key!r}") from exc
    dice: dict[int, int] = {}
    for key, value in (payload.get("hit_dice_used") or {}).items():
        text = str(key).lstrip("dD")
        try:
            dice[int(text)] = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"невірні витрачені хіт-дайси: {key!r}") from exc
    return SheetState(
        slots_used=slots,
        pact_used=int(payload.get("pact_used") or 0),
        hit_dice_used=dice,
        feature_used={
            str(key): int(value)
            for key, value in (payload.get("feature_used") or {}).items()
        },
        death_saves=DeathSaves(
            successes=int(saves.get("successes") or 0),
            failures=int(saves.get("failures") or 0),
        ),
        inspiration=bool(payload.get("inspiration")),
        exhaustion=int(payload.get("exhaustion") or 0),
        overrides={
            str(key): int(value) for key, value in (payload.get("overrides") or {}).items()
        },
        notes={str(key): str(value) for key, value in (payload.get("notes") or {}).items()},
    )


def spells_to_record(spells: tuple[KnownSpell, ...]) -> list[dict[str, Any]]:
    return [
        {
            "name_en": spell.name_en,
            "level": spell.level,
            "class_key": spell.class_key,
            "entry_id": spell.entry_id,
            "prepared": spell.prepared,
            "always_prepared": spell.always_prepared,
            "custom": spell.custom,
            "description": spell.description,
        }
        for spell in spells
    ]


def spells_from_record(records: list[Mapping[str, Any]] | None) -> tuple[KnownSpell, ...]:
    spells: list[KnownSpell] = []
    for record in records or ():
        try:
            spells.append(
                KnownSpell(
                    name_en=str(record["name_en"]),
                    level=int(record["level"]),
                    class_key=str(record["class_key"]),
                    entry_id=record.get("entry_id") or None,
                    prepared=bool(record.get("prepared")),
                    always_prepared=bool(record.get("always_prepared")),
                    custom=bool(record.get("custom")),
                    description=record.get("description") or None,
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ValidationError(f"невірне закляття у файлі: {record!r}") from exc
    return tuple(spells)


# ---------------------------------------------------------------------------
# персонаж
# ---------------------------------------------------------------------------


def multiclass_waivers_from_record(
    records: list[Mapping[str, Any]] | None,
) -> tuple[MulticlassWaiver, ...]:
    """Позначки «взято без вимог». Немає поля — немає й позначок."""
    waivers: list[MulticlassWaiver] = []
    for record in records or ():
        try:
            waivers.append(
                MulticlassWaiver(
                    class_key=str(record["class_key"]),
                    requirements=tuple(str(item) for item in record.get("requirements") or ()),
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ValidationError(f"невірна позначка вимог у файлі: {record!r}") from exc
    return tuple(waivers)


def character_to_record(character: Character) -> dict[str, Any]:
    return {
        "schema": CHARACTER_SCHEMA,
        "id": character.id,
        "name": character.name,
        "version": character.version,
        "abilities": abilities_to_record(character.abilities),
        "ability_bonus_choices": [ability.value for ability in character.ability_bonus_choices],
        "ability_spread": {
            ability.value: amount for ability, amount in character.ability_spread.items()
        },
        "classes": [
            {
                "class_key": entry.class_key,
                "level": entry.level,
                "subclass_key": entry.subclass_key,
            }
            for entry in character.classes
        ],
        # Вимоги мультикласу, які група обійшла: лист показує це явно.
        "multiclass_waivers": [
            {"class_key": waiver.class_key, "requirements": list(waiver.requirements)}
            for waiver in character.multiclass_waivers
        ],
        "species_key": character.species_key,
        "subspecies_key": character.subspecies_key,
        "background_key": character.background_key,
        "alignment": character.alignment,
        "chosen": proficiencies_to_record(character.chosen),
        "inventory": inventory_to_record(character.inventory),
        "spells": spells_to_record(character.spells),
        "spell_choices": list(character.spell_choices),
        "feats": list(character.feats),
        "asi_taken": character.asi_taken,
        "hp": {
            "current": character.hp.current,
            "temporary": character.hp.temporary,
            "rolls": list(character.hp.rolls),
            "bonus": character.hp.bonus,
            "override_max": character.hp.override_max,
        },
        "state": state_to_record(character.state),
    }


def character_from_record(record: Mapping[str, Any], rules: RulesSource) -> Character:
    schema = str(record.get("schema") or "")
    if schema != CHARACTER_SCHEMA and schema not in LEGACY_CHARACTER_SCHEMAS:
        raise ValidationError(
            f"невідома схема персонажа {record.get('schema')!r}, "
            f"очікується {CHARACTER_SCHEMA!r}"
        )
    legacy = schema != CHARACTER_SCHEMA
    hp = record.get("hp") or {}
    return Character(
        id=str(record["id"]),
        name=str(record["name"]),
        abilities=abilities_from_record(record.get("abilities")),
        rules=rules,
        classes=[
            CharacterClass(
                class_key=str(entry["class_key"]),
                level=int(entry.get("level") or 1),
                subclass_key=entry.get("subclass_key"),
            )
            for entry in record.get("classes") or ()
        ],
        ability_bonus_choices=tuple(
            Ability(str(name)) for name in record.get("ability_bonus_choices") or ()
        ),
        ability_spread=ability_spread_from_record(record.get("ability_spread")),
        multiclass_waivers=multiclass_waivers_from_record(record.get("multiclass_waivers")),
        species_key=record.get("species_key") or None,
        subspecies_key=record.get("subspecies_key") or None,
        background_key=record.get("background_key") or None,
        alignment=record.get("alignment") or None,
        chosen=Proficiencies(items=proficiencies_from_record(record.get("chosen"))),
        inventory=inventory_from_record(record.get("inventory")),
        spells=spells_from_record(record.get("spells")),
        spell_choices=tuple(str(item) for item in record.get("spell_choices") or ()),
        feats=tuple(str(item) for item in record.get("feats") or ()),
        asi_taken=int(record.get("asi_taken") or 0),
        hp=HitPointState(
            current=_hp_current(hp, legacy=legacy),
            temporary=int(hp.get("temporary") or 0),
            rolls=tuple(
                None if value is None else int(value) for value in hp.get("rolls") or ()
            ),
            bonus=int(hp.get("bonus") or 0),
            override_max=hp.get("override_max"),
        ),
        state=state_from_record(record.get("state")),
        version=int(record.get("version") or 1),
    )


def _hp_current(hp: Mapping[str, Any], *, legacy: bool) -> int | None:
    """Поточні хіти з файлу; `None` — «гравець їх ще не змінював».

    У `character/1` нуль означав і «не задано», і «нуль»: калькулятор
    підставляв максимум замість нуля, тож справжнього нуля у файлі бути не
    могло. Тому для старої схеми нуль читаємо як «не задано».
    """
    value = hp.get("current")
    if value is None:
        return None
    current = int(value)
    if legacy and current == 0:
        return None
    return current


# ---------------------------------------------------------------------------
# чернетка
# ---------------------------------------------------------------------------


def draft_to_record(draft: Draft) -> dict[str, Any]:
    return {
        "schema": DRAFT_SCHEMA,
        "id": draft.id,
        "revision": draft.revision,
        "name": draft.name,
        "species_key": draft.species_key,
        "subspecies_key": draft.subspecies_key,
        "ability_choices": [ability.value for ability in draft.ability_choices],
        "ability_spread": {
            ability.value: amount for ability, amount in draft.ability_spread.items()
        },
        "class_key": draft.class_key,
        "subclass_key": draft.subclass_key,
        "ability_method": draft.ability_method.value if draft.ability_method else None,
        "ability_scores": {ability.value: score for ability, score in draft.ability_scores.items()},
        "roll_set": list(draft.roll_set),
        "background_key": draft.background_key,
        "alignment": draft.alignment,
        "picks": proficiencies_to_record(Proficiencies(items=draft.picks)),
        "inventory": inventory_to_record(Inventory(items=draft.items, money=draft.money)),
        "equipment_submitted": draft.equipment_submitted,
        "spells": spells_to_record(draft.spells),
        "spell_choices": list(draft.spell_choices),
    }


def draft_from_record(record: Mapping[str, Any], rules: RulesSource) -> Draft:
    if record.get("schema") != DRAFT_SCHEMA:
        raise ValidationError(
            f"невідома схема чернетки {record.get('schema')!r}, очікується {DRAFT_SCHEMA!r}"
        )
    inventory = inventory_from_record(record.get("inventory"))
    method = record.get("ability_method")
    return Draft(
        id=str(record["id"]),
        rules=rules,
        revision=int(record.get("revision") or 0),
        name=str(record.get("name") or ""),
        species_key=record.get("species_key") or None,
        subspecies_key=record.get("subspecies_key") or None,
        ability_choices=tuple(
            Ability(str(name)) for name in record.get("ability_choices") or ()
        ),
        ability_spread=ability_spread_from_record(record.get("ability_spread")),
        class_key=record.get("class_key") or None,
        subclass_key=record.get("subclass_key") or None,
        ability_method=AbilityMethod(str(method)) if method else None,
        ability_scores={
            Ability(str(key)): int(value)
            for key, value in (record.get("ability_scores") or {}).items()
        },
        roll_set=tuple(int(value) for value in record.get("roll_set") or ()),
        background_key=record.get("background_key") or None,
        alignment=record.get("alignment") or None,
        picks=proficiencies_from_record(record.get("picks")),
        items=inventory.items,
        money=inventory.money,
        equipment_submitted=bool(record.get("equipment_submitted")),
        spells=spells_from_record(record.get("spells")),
        spell_choices=tuple(str(item) for item in record.get("spell_choices") or ()),
    )



