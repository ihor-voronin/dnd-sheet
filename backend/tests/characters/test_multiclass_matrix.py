"""Вимоги мультикласу на всіх парах класів (PHB, p. 163; TCoE, p. 9 — артифіцер).

Для кожної пари «перший клас → новий клас» перевіряється: із мінімально
достатніми характеристиками обох класів рівень доступний, а якщо будь-якої
однієї обовʼязкової характеристики бракує на 1 — ні.
"""

from __future__ import annotations

from itertools import product

import pytest

from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.services.level_up import CLASS_KEYS, LevelUpPlanner
from dndsheet.compendium.infrastructure.mechanics_index import JsonMechanicsRepository
from dndsheet.shared.kernel import Ability, AbilityScore

from helpers import make_character

#: Таблиця PHB: альтернативи «АБО», усередині — «І».
REQUIREMENTS: dict[str, tuple[tuple[Ability, ...], ...]] = {
    "artificer": ((Ability.INT,),),
    "barbarian": ((Ability.STR,),),
    "bard": ((Ability.CHA,),),
    "cleric": ((Ability.WIS,),),
    "druid": ((Ability.WIS,),),
    "fighter": ((Ability.STR,), (Ability.DEX,)),
    "monk": ((Ability.DEX, Ability.WIS),),
    "paladin": ((Ability.STR, Ability.CHA),),
    "ranger": ((Ability.DEX, Ability.WIS),),
    "rogue": ((Ability.DEX,),),
    "sorcerer": ((Ability.CHA,),),
    "warlock": ((Ability.CHA,),),
    "wizard": ((Ability.INT,),),
}


@pytest.fixture(scope="module")
def rules():
    repository = JsonMechanicsRepository()
    if not repository.available():
        pytest.skip("немає індексу механік (content/index/*-mechanics.json)")
    return repository


def _available(rules, first: str, second: str, scores: dict[Ability, int]) -> bool:  # noqa: ANN001
    character = make_character(
        rules,
        abilities={ability: AbilityScore(scores.get(ability, 8)) for ability in Ability},
        classes=[CharacterClass(first, 1, subclass_key=_subclass(first))],
    )
    plan = next(item for item in LevelUpPlanner().plans(character) if item.class_key == second)
    return plan.allowed


def _subclass(class_key: str) -> str | None:
    # Класи з підкласом на 1 рівні (PHB): без нього персонаж невалідний.
    return {"cleric": "life-domain", "sorcerer": "draconic-bloodline", "warlock": "the-fiend"}.get(class_key)


def _minimal(*classes: str) -> dict[Ability, int]:
    """Перша альтернатива кожного класу — по 13, решта 8."""
    scores: dict[Ability, int] = {}
    for class_key in classes:
        for ability in REQUIREMENTS[class_key][0]:
            scores[ability] = 13
    return scores


def test_table_matches_mechanics(rules) -> None:  # noqa: ANN001
    for class_key in CLASS_KEYS:
        definition = rules.class_mechanics(class_key)
        if definition is None:
            continue
        expected = {frozenset(alternative) for alternative in REQUIREMENTS[class_key]}
        actual = {frozenset(alternative) for alternative in definition.multiclass_requirements}
        assert actual == expected, class_key


@pytest.mark.parametrize("first,second", [pair for pair in product(CLASS_KEYS, CLASS_KEYS) if pair[0] != pair[1]])
def test_pair(rules, first: str, second: str) -> None:  # noqa: ANN001
    if rules.class_mechanics(first) is None or rules.class_mechanics(second) is None:
        pytest.skip("клас відсутній в індексі")
    enough = _minimal(first, second)
    assert _available(rules, first, second, enough), f"{first} → {second}: {enough}"
    for class_key in (first, second):
        for ability in REQUIREMENTS[class_key][0]:
            lowered = {**enough, ability: 12}
            # Воїну досить іншої альтернативи — якщо вона вже є, бракувати не буде.
            other_ok = any(
                all(lowered.get(item, 8) >= 13 for item in alternative)
                for alternative in REQUIREMENTS[class_key][1:]
            )
            if other_ok:
                continue
            assert not _available(rules, first, second, lowered), f"{first} → {second}: бракує {ability.value}"
