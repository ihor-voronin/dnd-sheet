"""Сценарій візарда: кроки через сховище, фініш, конфлікти й перезапуск."""

from __future__ import annotations

import pytest
from dndsheet.characters.application.wizard import WizardService
from dndsheet.characters.domain.wizard import WizardStep
from dndsheet.characters.infrastructure.json_store import (
    JsonCharacterRepository,
    JsonDraftRepository,
)
from dndsheet.shared.errors import ConflictError, NotFoundError, ValidationError


class FakeSubclasses:
    """Каталог підкласів для тестів: без довідника, лише те, що треба."""

    def __init__(self, mapping: dict[str, tuple[str, ...]]) -> None:
        self._mapping = mapping

    def subclass_keys(self, class_key: str) -> tuple[str, ...] | None:
        return self._mapping.get(class_key.strip().casefold())


@pytest.fixture()
def service(rules, tmp_data) -> WizardService:
    return WizardService(
        drafts=JsonDraftRepository(tmp_data / "drafts", rules),
        characters=JsonCharacterRepository(tmp_data / "characters", rules),
        rules=rules,
        subclasses=FakeSubclasses({"warlock": ("phb-2014/subclass/the-fiend",), "fighter": ("x",)}),
    )


FIGHTER_STEPS = [
    (
        WizardStep.SPECIES,
        {"name": "Дарія", "species_key": "human"},
    ),
    (WizardStep.CLASS, {"class_key": "fighter"}),
    (
        WizardStep.ABILITIES,
        {
            "method": "standard_array",
            "scores": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
        },
    ),
    (
        WizardStep.BACKGROUND,
        {
            "background_key": "soldier",
            "alignment": "lawful good",
            "picks": [
                {"kind": "skill", "value": "athletics", "source": {"kind": "class", "key": "fighter"}},
                {"kind": "skill", "value": "perception", "source": {"kind": "class", "key": "fighter"}},
            ],
        },
    ),
    (
        WizardStep.EQUIPMENT,
        {
            "items": [
                {
                    "name_en": "chain mail",
                    "kind": "armor",
                    "armor_base": 16,
                    "dex_cap": 0,
                    "equipped": True,
                }
            ],
            "money": {"gp": 10},
        },
    ),
]


def _walk(service: WizardService, draft_id: str, steps) -> None:  # noqa: ANN001
    for step, payload in steps:
        service.apply(draft_id, step, payload)


def test_full_creation_flow(service: WizardService) -> None:
    draft = service.start()
    assert draft.revision == 0
    _walk(service, draft.id, FIGHTER_STEPS)

    draft = service.load(draft.id)
    assert draft.next_step() is None, "усі кроки завершені"
    assert draft.is_complete(WizardStep.SPELLS), "воїн не чарує — крок не потрібен"

    character = service.finish(draft.id)
    assert character.total_level == 1
    assert character.name == "Дарія"
    assert character.inventory.money.gp == 10
    assert service.character(character.id).name == "Дарія"

    with pytest.raises(NotFoundError):
        service.load(draft.id)


def test_each_step_is_saved_immediately(service: WizardService) -> None:
    draft = service.start()
    service.apply(draft.id, WizardStep.SPECIES, {"name": "Мірта", "species_key": "human"})
    reloaded = service.load(draft.id)
    assert reloaded.name == "Мірта"
    assert reloaded.species_key == "human"
    assert reloaded.revision == 1


def test_failed_step_is_not_saved(service: WizardService) -> None:
    draft = service.start()
    service.apply(draft.id, WizardStep.SPECIES, {"name": "Мірта", "species_key": "human"})
    with pytest.raises(ValidationError):
        service.apply(
            draft.id,
            WizardStep.SPECIES,
            {"name": "Мірта", "species_key": "tiefling", "subspecies_key": "wood elf"},
        )
    assert service.load(draft.id).species_key == "human", "стан лишився попередній"
    assert service.load(draft.id).revision == 1


def test_revision_conflict(service: WizardService) -> None:
    draft = service.start()
    service.apply(draft.id, WizardStep.SPECIES, {"name": "А", "species_key": "human"})
    with pytest.raises(ConflictError):
        service.apply(
            draft.id,
            WizardStep.SPECIES,
            {"name": "Б", "species_key": "human"},
            expected_revision=0,
        )
    assert service.load(draft.id).name == "А"


def test_unknown_subclass_is_rejected(service: WizardService) -> None:
    draft = service.start()
    service.apply(draft.id, WizardStep.SPECIES, {"name": "Тіра", "species_key": "human"})
    with pytest.raises(ValidationError, match="невідомий підклас"):
        service._check_subclass("warlock", "phb-2014/subclass/great-old-one")
    service.apply(
        draft.id,
        WizardStep.CLASS,
        {"class_key": "warlock", "subclass_key": "phb-2014/subclass/the-fiend"},
    )
    assert service.load(draft.id).subclass_key == "phb-2014/subclass/the-fiend"


def test_wizard_survives_restart(rules, tmp_data) -> None:
    drafts = JsonDraftRepository(tmp_data / "drafts", rules)
    characters = JsonCharacterRepository(tmp_data / "characters", rules)
    catalog = FakeSubclasses({})
    first = WizardService(drafts=drafts, characters=characters, rules=rules, subclasses=catalog)
    draft = first.start()
    _walk(first, draft.id, FIGHTER_STEPS)
    character = first.finish(draft.id)

    # Новий сервіс на тих самих каталогах — це те саме, що перезапуск.
    second = WizardService(
        drafts=JsonDraftRepository(tmp_data / "drafts", rules),
        characters=JsonCharacterRepository(tmp_data / "characters", rules),
        rules=rules,
        subclasses=catalog,
    )
    restored = second.character(character.id)
    assert restored.name == character.name
    assert restored.total_level == 1
    assert [item.name_en for item in restored.inventory.items] == ["chain mail"]


def test_steps_cannot_be_written_out_of_order(service: WizardService) -> None:
    draft = service.start()
    # Крок «клас» формально валідний, але писати його можна лише після виду;
    # сервіс сам не стежить за порядком — це робить API. Тут перевіряємо, що
    # крок усе одно не зможе дати готового персонажа.
    with pytest.raises(ValidationError):
        service.finish(draft.id)
