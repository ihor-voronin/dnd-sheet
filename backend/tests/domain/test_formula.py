"""Безпечний обчислювач формул: дозволене працює, заборонене — падає."""

from __future__ import annotations

import pytest

from dndsheet.sheets.domain.formula import FormulaError, evaluate, sheet_functions


@pytest.fixture()
def context() -> dict:
    return {"functions": sheet_functions({"str": 16, "dex": 14}, level=3)}


def test_arithmetic() -> None:
    assert evaluate("2 + 3 * 4") == 14
    assert evaluate("(2 + 3) * 4") == 20
    assert evaluate("7 // 2") == 3
    assert evaluate("7 % 4") == 3


def test_standard_functions(context: dict) -> None:
    assert evaluate("mod('dex')", **context) == 2
    assert evaluate("ability_mod('str')", **context) == 3
    assert evaluate("proficiency()", **context) == 2
    assert evaluate("prof() * 3", **context) == 6
    assert evaluate("10 + mod('dex') + proficiency()", **context) == 14


def test_numeric_builtins() -> None:
    assert evaluate("max(1, 5)") == 5
    assert evaluate("min(1, 5)") == 1
    assert evaluate("floor(2.9)") == 2
    assert evaluate("ceil(2.1)") == 3
    assert evaluate("abs(-4)") == 4


def test_variables_and_conditional() -> None:
    assert evaluate("a + b", variables={"a": 1, "b": 2}) == 3
    assert evaluate("10 if 3 > 2 else 0") == 10
    assert evaluate("3 > 2") is True
    assert evaluate("3 > 2 and 1 < 2") is True
    assert evaluate("not 0") is True


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os')",
        "open('x')",
        "().__class__",
        "x.y",
        "[i for i in range(3)]",
        "lambda: 1",
        "1; 2",
        "{'a': 1}",
        "'text'",
        "a.b",
    ],
)
def test_forbidden_expressions(expression: str) -> None:
    with pytest.raises(FormulaError):
        evaluate(expression)


def test_unknown_name_and_function(context: dict) -> None:
    with pytest.raises(FormulaError, match="Невідоме імʼя"):
        evaluate("unknown + 1", **context)
    with pytest.raises(FormulaError, match="Невідома функція"):
        evaluate("rage()", **context)


def test_division_by_zero() -> None:
    with pytest.raises(FormulaError, match="Ділення на нуль"):
        evaluate("1 / 0")


def test_huge_result_is_rejected() -> None:
    with pytest.raises(FormulaError, match="занадто великий"):
        evaluate("10 ** 999")


def test_empty_expression() -> None:
    with pytest.raises(FormulaError):
        evaluate("   ")


def test_non_numeric_variable_is_rejected() -> None:
    with pytest.raises(FormulaError, match="має бути числом"):
        evaluate("a + 1", variables={"a": "text"})


def test_keyword_arguments_are_rejected() -> None:
    with pytest.raises(FormulaError, match="Іменовані аргументи"):
        evaluate("max(a=1)")
