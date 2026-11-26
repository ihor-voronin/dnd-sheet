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
from dndsheet.characters.domain.ports import CharacterRepository
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.domain.services.rest import RestService
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
        if current is not None:
            if not isinstance(current, Mapping):
                raise ValidationError("hp має бути обʼєктом")
            if "current" in current:
                new_current = _int(current["current"], "поточні хіти")
            if "temporary" in current:
                temporary = _int(current["temporary"], "тимчасові хіти")

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
        self.characters.save(character)
        return character

    # ------------------------------------------------------------------
    # відпочинок
    # ------------------------------------------------------------------

    def rest(self, character_id: str, kind: str) -> Character:
        character = self.load(character_id)
        cleaned = (kind or "").strip().casefold()
        if cleaned == "long":
            self.rest_service.long_rest(character)
        elif cleaned == "short":
            self.rest_service.short_rest(character)
        else:
            raise ValidationError(f"невідомий відпочинок {kind!r} (short або long)")
        self.characters.save(character)
        return character

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
