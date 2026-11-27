"""Фікстури для тестів документа листа (контекст `sheets`)."""

from __future__ import annotations

import pytest
from dndsheet.characters.application.golden import GoldenCase, build_golden_cases
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from rules_fixture import FixtureRules


@pytest.fixture()
def rules() -> FixtureRules:
    """Мінімальний набір правил: працює без корпусу."""
    return FixtureRules()


@pytest.fixture()
def calculator() -> DerivedStatsCalculator:
    return DerivedStatsCalculator()


@pytest.fixture(scope="module")
def golden_cases() -> dict[str, GoldenCase]:
    return {case.key: case for case in build_golden_cases(FixtureRules())}
