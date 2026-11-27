"""Фікстури тестів контексту `characters`."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.compendium.infrastructure.mechanics_index import JsonMechanicsRepository
from helpers import make_character  # noqa: F401 — реекспорт для тестів
from rules_fixture import FixtureRules

#: Тека для тимчасових файлів — у репозиторії, а не в системному temp:
#: пісочниця Windows-середовища не завжди дає писати в `%TEMP%`.
TMP_DATA = Path(__file__).resolve().parent / "_tmp_data"


@pytest.fixture()
def tmp_data() -> Path:
    """Порожній каталог під файли сховища (замість `tmp_path`)."""
    shutil.rmtree(TMP_DATA, ignore_errors=True)
    TMP_DATA.mkdir(parents=True)
    try:
        yield TMP_DATA
    finally:
        shutil.rmtree(TMP_DATA, ignore_errors=True)


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
