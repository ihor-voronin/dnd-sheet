"""Фікстури тестів контексту `characters`."""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.compendium.infrastructure.mechanics_index import JsonMechanicsRepository

from helpers import make_character  # noqa: F401 — реекспорт для тестів
from rules_fixture import FixtureRules


@pytest.fixture()
def rules() -> FixtureRules:
    """Мінімальний набір правил: працює без корпусу."""
    return FixtureRules()


@pytest.fixture(params=["fixture", "corpus"])
def any_rules(request):
    """Правила для золотих тестів: і фікстура, і справжній індекс.

    Той самий тест двічі — це навмисно: якщо числа в корпусі розійдуться з
    правилами, тест упаде саме на `corpus`, а не десь у візарді.
    """
    if request.param == "fixture":
        return FixtureRules()
    repository = JsonMechanicsRepository()
    if not repository.available():
        pytest.skip("немає індексу механік (content/index/*-mechanics.json)")
    return repository


@pytest.fixture()
def calculator() -> DerivedStatsCalculator:
    return DerivedStatsCalculator()
