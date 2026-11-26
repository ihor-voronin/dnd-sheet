"""Зміни листа під час гри: лічильники, виправлення, відпочинок.

Застосунок бачить і агрегат, і обчислений лист — тому саме тут перевіряється
те, чого не знає домен: «витрачено не більше, ніж максимум». Домен
відповідає за інваріанти стану (кидки смерті 0..3, хіт-дайси не більше
наявних), застосунок — за числа, які залежать від правил класу.

Кожна зміна пише агрегат на диск і повертає його; невдала — не пише нічого,
бо виняток виникає до `save`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.inventory import InventoryItem, ItemKind
from dndsheet.characters.domain.ports import CharacterRepository
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.domain.services.feature_resources import resources_for
from dndsheet.characters.domain.services.rest import RestReport, RestService
from dndsheet.characters.domain.state import DeathSaves
from dndsheet.shared.errors import ConflictError, NotFoundError, ValidationError


@dataclass(slots=True)
class SheetService:
    """Сценарії листа: змінити стан, відпочити, витратити хіт-дайс."""

    characters: CharacterRepository
    calculator: DerivedStatsCalculator | None = None
    rest_service: RestService | None = None

    def __post_init__(self) -> None:
        if self.calculator is None:
            self.calculator = DerivedStatsCalculator()
        if self.rest_service is None:
            self.rest_service = RestService(self.calculator)

    # ------------------------------------------------------------------
    # читання
    # ------------------------------------------------------------------

    def load(self, character_id: str) -> Character:
        character = self.characters.get(character_id)
        if character is None:
            raise NotFoundError(f"немає персонажа {character_id!r}")
        return character

    # ------------------------------------------------------------------
    # зміна стану
    # ------------------------------------------------------------------

    def update(
        self,
        character_id: str,
        patch: Mapping[str, Any],
        *,
        expected_version: int | None = None,
    ) -> Character:
        character = self.load(character_id)
        if expected_version is not None and expected_version != character.version:
            raise ConflictError(
                f"лист змінено (версія {character.version}, надіслано {expected_version})"
            )
        sheet = self.calculator.compute(character)
        state = character.state
        current = patch.get("hp")
        temporary = None
        new_current = None
        damage = None
        heal = None
        if current is not None:
            if not isinstance(current, Mapping):
                raise ValidationError("hp має бути обʼєктом")
            if "current" in current:
                new_current = _int(current["current"], "поточні хіти")
            if "temporary" in current:
                temporary = _int(current["temporary"], "тимчасові хіти")
            if "damage" in current:
                damage = _int(current["damage"], "шкода")
                if damage < 0:
                    raise ValidationError("шкода не може бути відʼємною")
            if "heal" in current:
                heal = _int(current["heal"], "лікування")
                if heal < 0:
                    raise ValidationError("лікування не може бути відʼємним")
            if damage is not None and heal is not None:
                raise ValidationError("шкода й лікування — це окремі запити")

        if "death_saves" in patch:
            saves = patch["death_saves"] or {}
            if not isinstance(saves, Mapping):
                raise ValidationError("death_saves має бути обʼєктом")
            state = state.with_death_saves(
                DeathSaves(
                    successes=_int(
                        saves.get("successes", state.death_saves.successes), "успіхи"
                    ),
                    failures=_int(
                        saves.get("failures", state.death_saves.failures), "провали"
                    ),
                )
            )
        if "inspiration" in patch:
            state = state.with_inspiration(bool(patch["inspiration"]))
        if "exhaustion" in patch:
            state = state.with_exhaustion(_int(patch["exhaustion"], "втома"))
        if "slots" in patch:
            state = state.with_slots_used(
                self._slots(patch["slots"], sheet.spellcasting.slots.by_level)
            )
        if "pact_used" in patch:
            pact = sheet.spellcasting.slots.pact
            used = _int(patch["pact_used"], "витрачені слоти Pact Magic")
            if pact is None and used:
                raise ValidationError("персонаж не має Pact Magic")
            if pact is not None and used > pact.slots:
                raise ValidationError(
                    f"слотів Pact Magic усього {pact.slots}, витрачено {used}"
                )
            state = state.with_pact_used(used)
        if "hit_dice" in patch:
            state = state.with_hit_dice_used(self._hit_dice(patch["hit_dice"]))
        if "feature_used" in patch:
            values = patch["feature_used"] or {}
            if not isinstance(values, Mapping):
                raise ValidationError("feature_used має бути обʼєктом «ключ: витрачено»")
            limits = {
                resource.key: resource.total
                for resource in resources_for(character, sheet.ability_modifiers)
            }
            used: dict[str, int] = {}
            for key, value in values.items():
                name = str(key).strip()
                if name not in limits:
                    raise ValidationError(f"невідомий класовий ресурс {name!r}")
                count = _int(value, f"витрачено ресурсу {name}")
                if count > limits[name]:
                    raise ValidationError(
                        f"ресурсу {name!r} усього {limits[name]}, витрачено {count}"
                    )
                if count:
                    used[name] = count
            state = state.with_feature_used(used)
        if "overrides" in patch:
            overrides = patch["overrides"] or {}
            if not isinstance(overrides, Mapping):
                raise ValidationError("overrides має бути обʼєктом")
            for key, value in overrides.items():
                if value is None:
                    state = state.without_override(str(key))
                else:
                    state = state.with_override(str(key), _int(value, f"виправлення {key}"))
        if "notes" in patch:
            notes = patch["notes"] or {}
            if not isinstance(notes, Mapping):
                raise ValidationError("notes має бути обʼєктом")
            state = state.with_notes({str(key): str(value) for key, value in notes.items()})

        equip = patch.get("equip")
        if equip is not None:
            if not isinstance(equip, Mapping):
                raise ValidationError("equip має бути обʼєктом")
            name = str(equip.get("name") or "").strip()
            if not name:
                raise ValidationError("equip.name обовʼязковий")
            character.equip_item(name, bool(equip.get("equipped")))

        character.set_state(state)
        if new_current is not None or temporary is not None:
            character.set_hp(current=new_current, temporary=temporary)
        if damage is not None or heal is not None:
            # Хіти могли ще не задавати — тоді це максимум (так само, як на
            # листі). Максимум рахуємо після зміни стану: у тому ж запиті
            # гравець міг змінити й виправлення максимуму.
            fresh = self.calculator.compute(character)
            if character.hp.current is None:
                character.set_hp(current=fresh.hit_points.current)
            if damage is not None:
                character.apply_damage(damage)
            if heal is not None:
                character.heal(heal)
                if (character.hp.current or 0) > fresh.hit_points.maximum:
                    character.set_hp(current=fresh.hit_points.maximum)
        self.characters.save(character)
        return character

    # ------------------------------------------------------------------
    # інвентар
    # ------------------------------------------------------------------

    def add_item(
        self,
        character_id: str,
        payload: Mapping[str, Any],
        *,
        expected_version: int | None = None,
    ) -> Character:
        character = self._load_versioned(character_id, expected_version)
        character.add_item(self._item(payload))
        self.characters.save(character)
        return character

    def update_item(
        self,
        character_id: str,
        index: int,
        payload: Mapping[str, Any],
        *,
        expected_version: int | None = None,
    ) -> Character:
        character = self._load_versioned(character_id, expected_version)
        item = character.inventory.item_at(index)
        character.update_item(index, self._item_fields(payload, item))
        self.characters.save(character)
        return character

    def remove_item(
        self,
        character_id: str,
        index: int,
        *,
        expected_version: int | None = None,
    ) -> Character:
        character = self._load_versioned(character_id, expected_version)
        character.remove_item(index)
        self.characters.save(character)
        return character

    def _load_versioned(self, character_id: str, expected_version: int | None) -> Character:
        character = self.load(character_id)
        if expected_version is not None and expected_version != character.version:
            raise ConflictError(
                f"лист змінено (версія {character.version}, надіслано {expected_version})"
            )
        return character

    @staticmethod
    def _item(payload: Mapping[str, Any]) -> InventoryItem:
        if not isinstance(payload, Mapping):
            raise ValidationError("предмет має бути обʼєктом")
        name = str(payload.get("name_en") or "").strip()
        if not name:
            raise ValidationError("предмет без назви")
        kind = _kind(payload.get("kind"))
        return InventoryItem(
            name_en=name,
            kind=kind,
            quantity=_int(payload.get("quantity", 1), "кількість"),
            weight_lb=_number(payload.get("weight_lb", 0), "вага"),
            equipped=bool(payload.get("equipped", False)),
            attuned=bool(payload.get("attuned", False)),
            entry_id=_optional_str(payload.get("entry_id")),
            armor_base=_optional_int(payload.get("armor_base"), "базовий КЗ"),
            dex_cap=_optional_int(payload.get("dex_cap"), "межа Спритності"),
            notes=_optional_str(payload.get("notes")),
            damage=_optional_str(payload.get("damage")),
        )

    @staticmethod
    def _item_fields(payload: Mapping[str, Any], base: InventoryItem) -> dict[str, Any]:
        """Часткова правка предмета: змінюємо лише надіслані поля."""
        if not isinstance(payload, Mapping):
            raise ValidationError("предмет має бути обʼєктом")
        fields: dict[str, Any] = {}
        if "name_en" in payload:
            name = str(payload.get("name_en") or "").strip()
            if not name:
                raise ValidationError("предмет без назви")
            fields["name_en"] = name
        if "kind" in payload:
            fields["kind"] = _kind(payload.get("kind"))
        if "quantity" in payload:
            fields["quantity"] = _int(payload.get("quantity"), "кількість")
        if "weight_lb" in payload:
            fields["weight_lb"] = _number(payload.get("weight_lb"), "вага")
        if "equipped" in payload:
            fields["equipped"] = bool(payload.get("equipped"))
        if "attuned" in payload:
            fields["attuned"] = bool(payload.get("attuned"))
        if "entry_id" in payload:
            fields["entry_id"] = _optional_str(payload.get("entry_id"))
        if "armor_base" in payload:
            fields["armor_base"] = _optional_int(payload.get("armor_base"), "базовий КЗ")
        if "dex_cap" in payload:
            fields["dex_cap"] = _optional_int(payload.get("dex_cap"), "межа Спритності")
        if "notes" in payload:
            fields["notes"] = _optional_str(payload.get("notes"))
        if "damage" in payload:
            damage = _optional_str(payload.get("damage"))
            target_kind = fields.get("kind", base.kind)
            if damage and target_kind is not ItemKind.WEAPON:
                raise ValidationError("власний урон буває лише у зброї")
            fields["damage"] = damage
        return fields

    # ------------------------------------------------------------------
    # відпочинок
    # ------------------------------------------------------------------

    def rest(self, character_id: str, kind: str) -> tuple[Character, RestReport]:
        character = self.load(character_id)
        cleaned = (kind or "").strip().casefold()
        if cleaned == "long":
            report = self.rest_service.long_rest(character)
        elif cleaned == "short":
            report = self.rest_service.short_rest(character)
        else:
            raise ValidationError(f"невідомий відпочинок {kind!r} (short або long)")
        self.characters.save(character)
        return character, report

    def spend_hit_die(self, character_id: str, die: int, roll: int) -> Character:
        character = self.load(character_id)
        self.rest_service.spend_hit_die(character, int(die), int(roll))
        self.characters.save(character)
        return character

    # ------------------------------------------------------------------
    # розбір вхідних значень
    # ------------------------------------------------------------------

    @staticmethod
    def _slots(values: Any, totals: tuple[tuple[int, int], ...]) -> dict[int, int]:
        if values is None:
            return {}
        if not isinstance(values, Mapping):
            raise ValidationError("slots має бути обʼєктом «рівень: витрачено»")
        limits = dict(totals)
        used: dict[int, int] = {}
        for key, value in values.items():
            try:
                level = int(key)
            except (TypeError, ValueError) as exc:
                raise ValidationError(f"рівень слотів {key!r} має бути числом") from exc
            count = _int(value, f"витрачені слоти {level} рівня")
            if count > limits.get(level, 0):
                raise ValidationError(
                    f"слотів {level} рівня всього {limits.get(level, 0)}, витрачено {count}"
                )
            if count:
                used[level] = count
        return used

    @staticmethod
    def _hit_dice(values: Any) -> dict[int, int]:
        if values is None:
            return {}
        if not isinstance(values, Mapping):
            raise ValidationError("hit_dice має бути обʼєктом «d10: витрачено»")
        used: dict[int, int] = {}
        for key, value in values.items():
            text = str(key).strip().casefold()
            if text.startswith("d"):
                text = text[1:]
            try:
                die = int(text)
            except ValueError as exc:
                raise ValidationError(f"хіт-дайс {key!r} має бути числом") from exc
            count = _int(value, f"витрачені d{die}")
            if count:
                used[die] = count
        return used


def _int(value: Any, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{what}: очікується ціле число")
    return value


def _number(value: Any, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{what}: очікується число")
    if value < 0:
        raise ValidationError(f"{what} не може бути відʼємною")
    return float(value)


def _optional_int(value: Any, what: str) -> int | None:
    if value is None:
        return None
    return _int(value, what)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _kind(value: Any) -> ItemKind:
    if value is None:
        return ItemKind.GEAR
    try:
        return ItemKind(str(value))
    except ValueError as exc:
        kinds = ", ".join(kind.value for kind in ItemKind)
        raise ValidationError(f"невідомий тип предмета {value!r} ({kinds})") from exc
