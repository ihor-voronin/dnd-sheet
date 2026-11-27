"""Файлове сховище: агрегат → файл → агрегат без втрат."""

from __future__ import annotations

import json

import pytest
from dndsheet.characters.application.golden import build_golden_cases
from dndsheet.characters.domain.inventory import InventoryItem, ItemKind
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiency,
    ProficiencyKind,
    SourceKind,
)
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.domain.services.spell_slots import SpellSlotService
from dndsheet.characters.domain.wizard import AbilityMethod, Draft
from dndsheet.characters.infrastructure.character_json import (
    character_from_record,
    character_to_record,
    draft_to_record,
)
from dndsheet.characters.infrastructure.json_store import (
    JsonCharacterRepository,
    JsonDraftRepository,
)
from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import Ability, Money


def test_character_roundtrip_keeps_every_field(rules, tmp_data) -> None:
    case = build_golden_cases(rules)[2]  # Воїн 2 / Візард 3 — найповніший з трьох
    repository = JsonCharacterRepository(tmp_data / "characters", rules)
    repository.save(case.character)

    restored = repository.get(case.character.id)
    assert restored is not None
    assert character_to_record(restored) == character_to_record(case.character)


def test_restored_character_computes_the_same_sheet(rules, tmp_data) -> None:
    case = build_golden_cases(rules)[2]
    repository = JsonCharacterRepository(tmp_data / "characters", rules)
    repository.save(case.character)
    restored = repository.get(case.character.id)
    assert restored is not None

    before = DerivedStatsCalculator().compute(case.character)
    after = DerivedStatsCalculator().compute(restored)
    assert (after.armor_class, after.hit_points.maximum) == (
        before.armor_class,
        before.hit_points.maximum,
    )
    assert after.hit_dice == before.hit_dice
    casting_before = SpellSlotService().compute(case.character.class_entries(), {}, after.proficiency_bonus)
    casting_after = SpellSlotService().compute(restored.class_entries(), {}, after.proficiency_bonus)
    assert dict(casting_after.slots.by_level) == dict(casting_before.slots.by_level)


def test_character_list_and_delete(rules, tmp_data) -> None:
    directory = tmp_data / "characters"
    repository = JsonCharacterRepository(directory, rules)
    case = build_golden_cases(rules)[0]
    repository.save(case.character)
    assert repository.ids() == (case.character.id,)
    repository.delete(case.character.id)
    assert repository.ids() == ()
    assert repository.get(case.character.id) is None


def test_draft_roundtrip(rules, tmp_data) -> None:
    draft = Draft(id="drf_1", rules=rules)
    draft.apply_species(name="Тест", species_key="human")
    draft.apply_class(class_key="fighter")
    draft.apply_abilities(
        method=AbilityMethod.STANDARD_ARRAY,
        scores=dict(zip(Ability, (15, 14, 13, 12, 10, 8))),
    )
    draft.apply_background(
        background_key="soldier",
        picks=(
            Proficiency(
                kind=ProficiencyKind.SKILL,
                value="athletics",
                source=GrantSource.of(SourceKind.CLASS, "fighter"),
            ),
            Proficiency(
                kind=ProficiencyKind.SKILL,
                value="perception",
                source=GrantSource.of(SourceKind.CLASS, "fighter"),
            ),
        ),
    )
    draft.apply_equipment(
        items=(
            InventoryItem(
                name_en="chain mail",
                kind=ItemKind.ARMOR,
                armor_base=16,
                dex_cap=0,
                equipped=True,
            ),
        ),
        money=Money(gp=7, sp=3),
    )
    repository = JsonDraftRepository(tmp_data / "drafts", rules)
    repository.save(draft)

    restored = repository.get("drf_1")
    assert restored is not None
    assert draft_to_record(restored) == draft_to_record(draft)


def test_file_is_human_readable_json(rules, tmp_data) -> None:
    case = build_golden_cases(rules)[0]
    repository = JsonCharacterRepository(tmp_data / "characters", rules)
    repository.save(case.character)
    path = tmp_data / "characters" / f"{case.character.id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == "character/2"
    assert payload["name"] == case.character.name
    assert not list(path.parent.glob("*.tmp")), "тимчасовий файл не має лишатися"


def test_id_cannot_escape_directory(rules, tmp_data) -> None:
    repository = JsonCharacterRepository(tmp_data / "characters", rules)
    with pytest.raises(ValidationError, match="ідентифікатор"):
        repository.get("../../etc/passwd")


def test_wrong_schema_is_an_error(rules, tmp_data) -> None:
    directory = tmp_data / "characters"
    directory.mkdir()
    (directory / "x.json").write_text(
        json.dumps({"schema": "character/999", "id": "x", "name": "Хтось"}),
        encoding="utf-8",
    )
    repository = JsonCharacterRepository(directory, rules)
    with pytest.raises(ValidationError, match="схема"):
        repository.get("x")


def test_broken_json_is_an_error(rules, tmp_data) -> None:
    directory = tmp_data / "drafts"
    directory.mkdir()
    (directory / "broken.json").write_text("{не json", encoding="utf-8")
    repository = JsonDraftRepository(directory, rules)
    with pytest.raises(ValidationError, match="невірний JSON"):
        repository.get("broken")


# ---------------------------------------------------------------------------
# міграція character/1 -> character/2
# ---------------------------------------------------------------------------


def _legacy_record(case, current: int) -> dict:  # noqa: ANN001
    record = character_to_record(case.character)
    record["schema"] = "character/1"
    record["hp"] = {**record["hp"], "current": current}
    return record


def test_legacy_zero_hp_means_unset(rules) -> None:
    """У `character/1` нуль не міг означати «нуль хітів» — лист підставляв максимум."""
    case = build_golden_cases(rules)[0]
    restored = character_from_record(_legacy_record(case, 0), rules)
    assert restored.hp.current is None


def test_legacy_real_hp_is_kept(rules) -> None:
    case = build_golden_cases(rules)[0]
    restored = character_from_record(_legacy_record(case, 4), rules)
    assert restored.hp.current == 4


def test_new_schema_keeps_zero_hp(rules) -> None:
    """У `character/2` нуль — це справжній нуль: персонаж непритомний."""
    case = build_golden_cases(rules)[0]
    record = character_to_record(case.character)
    record["hp"] = {**record["hp"], "current": 0}
    restored = character_from_record(record, rules)
    assert restored.hp.current == 0
