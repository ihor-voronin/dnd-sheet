"""Дрібні помічники тестів персонажа."""

from __future__ import annotations

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.shared.kernel import Ability, AbilityScore


def make_character(rules, **overrides) -> Character:  # noqa: ANN001
    """Персонаж-заготовка: Воїн 1, усі характеристики 10, без виду й історії."""
    params: dict = {
        "id": "c-1",
        "name": "Тестовий",
        "abilities": {ability: AbilityScore(10) for ability in Ability},
        "rules": rules,
        "classes": [CharacterClass(class_key="fighter", level=1)],
    }
    params.update(overrides)
    return Character(**params)
