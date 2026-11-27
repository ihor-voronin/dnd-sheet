"""Сценарій створення персонажа: чернетка → перевірка кроку → персонаж.

Тут немає ні HTTP, ні правил, ні формату файлів: лише порядок дій. Крок
приймає JSON-відповідь кроку, перекладає її в доменні значення, віддає
чернетці, а та перевіряє. Якщо крок не пройшов — виняток і жодного запису:
недописана чернетка не має лишатися на диску.

Створення персонажа — окремий крок сценарію (`finish`): зібрати агрегат,
перевірити його повністю (тут спрацьовує вся валідація `Character`), зберегти
й прибрати чернетку. Персонаж без чернетки — це вже не «недобудоване».
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from uuid import uuid4

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.inventory import InventoryItem, ItemKind
from dndsheet.characters.domain.ports import (
    CharacterRepository,
    DraftRepository,
    RulesSource,
    SubclassCatalog,
)
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiency,
    ProficiencyKind,
    SourceKind,
)
from dndsheet.characters.domain.spells import KnownSpell
from dndsheet.characters.domain.wizard import Draft, WizardStep
from dndsheet.shared.errors import ConflictError, NotFoundError, ValidationError
from dndsheet.shared.ids import CharacterId
from dndsheet.shared.kernel import Ability, Money


def new_draft_id() -> str:
    return f"drf_{uuid4().hex}"


@dataclass(slots=True)
class WizardService:
    """Кроки створення персонажа поверх сховища й правил."""

    drafts: DraftRepository
    characters: CharacterRepository
    rules: RulesSource
    subclasses: SubclassCatalog

    # ------------------------------------------------------------------
    # чернетка
    # ------------------------------------------------------------------

    def start(self) -> Draft:
        draft = Draft(id=new_draft_id(), rules=self.rules)
        self.drafts.save(draft)
        return draft

    def load(self, draft_id: str) -> Draft:
        draft = self.drafts.get(draft_id)
        if draft is None:
            raise NotFoundError(f"немає чернетки {draft_id!r}")
        return draft

    def apply(
        self,
        draft_id: str,
        step: WizardStep | str,
        payload: Mapping[str, Any] | None = None,
        *,
        expected_revision: int | None = None,
    ) -> Draft:
        """Застосувати відповідь кроку й зберегти чернетку."""
        draft = self.load(draft_id)
        if expected_revision is not None and expected_revision != draft.revision:
            raise ConflictError(
                f"чернетку змінено (ревізія {draft.revision}, надіслано {expected_revision})"
            )
        body = payload or {}
        try:
            parsed_step = WizardStep(step)
        except ValueError as exc:
            raise ValidationError(f"невідомий крок {step!r}") from exc
        self._apply_step(draft, parsed_step, body)
        self.drafts.save(draft)
        return draft

    def _apply_step(self, draft: Draft, step: WizardStep, body: Mapping[str, Any]) -> None:
        if step is WizardStep.SPECIES:
            draft.apply_species(
                name=_text(body, "name"),
                species_key=_text(body, "species_key"),
                subspecies_key=_optional_text(body, "subspecies_key"),
                ability_choices=_abilities(body.get("ability_choices")),
                spell_choices=_text_list(body.get("spell_choices")),
                ability_spread=body.get("ability_spread"),
            )
        elif step is WizardStep.CLASS:
            class_key = _text(body, "class_key")
            subclass_key = _optional_text(body, "subclass_key")
            self._check_subclass(class_key, subclass_key)
            draft.apply_class(class_key=class_key, subclass_key=subclass_key)
        elif step is WizardStep.ABILITIES:
            draft.apply_abilities(
                method=_text(body, "method"),
                scores=_score_map(body.get("scores")),
                rolls=_int_list(body.get("rolls")),
            )
        elif step is WizardStep.BACKGROUND:
            draft.apply_background(
                background_key=_text(body, "background_key"),
                picks=_picks(body.get("picks")),
                alignment=_optional_text(body, "alignment"),
            )
        elif step is WizardStep.EQUIPMENT:
            draft.apply_equipment(
                items=_items(body.get("items")),
                money=_money(body.get("money")),
            )
        elif step is WizardStep.SPELLS:
            draft.apply_spells(spells=_spells(body.get("spells")))
        else:  # pragma: no cover - стосується лише розширення переліку
            raise ValidationError(f"крок {step!r} ще не підтримується")

    def _check_subclass(self, class_key: str, subclass_key: str | None) -> None:
        """Ключ підкласу мусить існувати в довіднику — якщо довідник його знає."""
        if not subclass_key:
            return
        known = self.subclasses.subclass_keys(class_key)
        if known is None:
            return
        if subclass_key.strip().casefold() not in {item.casefold() for item in known}:
            raise ValidationError(
                f"невідомий підклас {subclass_key!r} для класу {class_key!r}"
            )

    # ------------------------------------------------------------------
    # створення персонажа
    # ------------------------------------------------------------------

    def finish(self, draft_id: str) -> Character:
        draft = self.load(draft_id)
        character = draft.to_character(CharacterId.new().value)
        self.characters.save(character)
        self.drafts.delete(draft_id)
        return character

    # ------------------------------------------------------------------
    # готові персонажі
    # ------------------------------------------------------------------

    def character(self, character_id: str) -> Character:
        found = self.characters.get(character_id)
        if found is None:
            raise NotFoundError(f"немає персонажа {character_id!r}")
        return found

    def saved_characters(self) -> tuple[Character, ...]:
        found: list[Character] = []
        for identifier in self.characters.ids():
            character = self.characters.get(identifier)
            if character is not None:
                found.append(character)
        return tuple(found)


# ---------------------------------------------------------------------------
# розбір відповіді кроку
# ---------------------------------------------------------------------------


def _text(body: Mapping[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"поле {key!r} обовʼязкове")
    return value.strip()


def _optional_text(body: Mapping[str, Any], key: str) -> str | None:
    value = body.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(f"поле {key!r} має бути рядком")
    return value.strip() or None


def _text_list(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise ValidationError("spell_choices має бути списком назв")
    return tuple(str(value).strip() for value in values if str(value).strip())


def _abilities(values: Any) -> tuple[Ability, ...]:
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise ValidationError("ability_choices має бути списком")
    try:
        return tuple(Ability(str(value).strip().casefold()) for value in values)
    except ValueError as exc:
        raise ValidationError(f"невідома характеристика у виборі: {exc}") from exc


def _score_map(values: Any) -> dict[Ability, int]:
    if not isinstance(values, Mapping):
        raise ValidationError("scores має бути обʼєктом «характеристика: число»")
    result: dict[Ability, int] = {}
    for key, value in values.items():
        try:
            ability = Ability(str(key).strip().casefold())
        except ValueError as exc:
            raise ValidationError(f"невідома характеристика {key!r}") from exc
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(f"{ability.value}: оцінка має бути цілим числом")
        result[ability] = value
    return result


def _int_list(values: Any) -> tuple[int, ...]:
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise ValidationError("кидки мають бути списком чисел")
    result: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(f"кидок {value!r} має бути цілим числом")
        result.append(value)
    return tuple(result)


def _picks(values: Any) -> tuple[Proficiency, ...]:
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise ValidationError("picks має бути списком")
    picks: list[Proficiency] = []
    for record in values:
        if not isinstance(record, Mapping):
            raise ValidationError(f"володіння має бути обʼєктом, отримано {record!r}")
        try:
            kind = ProficiencyKind(str(record["kind"]))
            source = record["source"]
            picks.append(
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
            raise ValidationError(f"невірне володіння: {record!r}") from exc
    return tuple(picks)


def _items(values: Any) -> tuple[InventoryItem, ...]:
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise ValidationError("items має бути списком")
    items: list[InventoryItem] = []
    for record in values:
        if not isinstance(record, Mapping):
            raise ValidationError(f"предмет має бути обʼєктом, отримано {record!r}")
        try:
            items.append(
                InventoryItem(
                    name_en=str(record["name_en"]),
                    kind=ItemKind(str(record.get("kind") or ItemKind.GEAR.value)),
                    quantity=int(record.get("quantity") or 1),
                    weight_lb=float(record.get("weight_lb") or 0),
                    equipped=bool(record.get("equipped")),
                    attuned=bool(record.get("attuned")),
                    entry_id=record.get("entry_id") or None,
                    armor_base=record.get("armor_base"),
                    dex_cap=record.get("dex_cap"),
                    notes=record.get("notes") or None,
                    damage=record.get("damage") or None,
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ValidationError(f"невірний предмет: {record!r}") from exc
    return tuple(items)


def _money(values: Any) -> Money:
    if values is None:
        return Money()
    if not isinstance(values, Mapping):
        raise ValidationError("money має бути обʼєктом «номінал: кількість»")
    allowed = ("pp", "gp", "ep", "sp", "cp")
    unknown = set(values) - set(allowed)
    if unknown:
        raise ValidationError(f"невідомі номінали: {', '.join(sorted(unknown))}")
    numbers: dict[str, int] = {}
    for coin in allowed:
        raw = values.get(coin, 0)
        if raw is None:
            raw = 0
        if isinstance(raw, bool) or not isinstance(raw, (int, float)) or int(raw) != raw:
            raise ValidationError(f"{coin}: кількість має бути цілим числом")
        numbers[coin] = int(raw)
    return Money(**numbers)


def _spells(values: Any) -> tuple[KnownSpell, ...]:
    if values is None:
        return ()
    if not isinstance(values, (list, tuple)):
        raise ValidationError("spells має бути списком")
    spells: list[KnownSpell] = []
    for record in values:
        if not isinstance(record, Mapping):
            raise ValidationError(f"закляття має бути обʼєктом, отримано {record!r}")
        try:
            spells.append(
                KnownSpell(
                    name_en=str(record["name_en"]),
                    level=int(record["level"]),
                    class_key=str(record["class_key"]),
                    entry_id=record.get("entry_id") or None,
                    prepared=bool(record.get("prepared")),
                    always_prepared=bool(record.get("always_prepared")),
                )
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise ValidationError(f"невірне закляття: {record!r}") from exc
    return tuple(spells)

