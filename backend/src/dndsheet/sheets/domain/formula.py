"""Безпечний обчислювач формул для кастомізованих полів.

`eval` не використовується. Дозволені лише: числа, короткі рядкові константи
(як аргументи на кшталт `mod('dex')`), імена, арифметика з числами, порівняння,
`and/or/not`, тернарний вираз і виклики дозволених функцій.
Заборонено: атрибути, індекси, lambda, генератори, comprehension, зірки аргументів.
"""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Callable, Mapping
from typing import Any

from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import AbilityScore, proficiency_bonus

MAX_DEPTH = 25
MAX_NODES = 200
MAX_ABS_RESULT = 10**12
MAX_STRING_LENGTH = 64

_BIN_OPS: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_CMP_OPS: dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

_SAFE_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "floor": math.floor,
    "ceil": math.ceil,
    "round": round,
    "abs": abs,
    "min": min,
    "max": max,
    "int": int,
}


class FormulaError(ValidationError):
    """Формула невалідна або виконує заборонену операцію."""


def sheet_functions(scores: Mapping[str, int], level: int) -> dict[str, Callable[..., Any]]:
    """Стандартні функції листка: mod('dex'), proficiency(), prof()."""
    modifiers = {str(key): AbilityScore(int(score)).modifier for key, score in scores.items()}

    def mod(name: str) -> int:
        try:
            return modifiers[str(name)]
        except KeyError as exc:
            raise FormulaError(f"Невідома характеристика: {name!r}") from exc

    def prof() -> int:
        return proficiency_bonus(level)

    return {"mod": mod, "ability_mod": mod, "proficiency": prof, "prof": prof}


def evaluate(
    expression: str,
    *,
    variables: Mapping[str, Any] | None = None,
    functions: Mapping[str, Callable[..., Any]] | None = None,
) -> int | float | bool:
    if not expression or not expression.strip():
        raise FormulaError("Порожня формула")

    safe_vars = _numeric_mapping(variables or {}, "змінна")
    safe_funcs = {**_SAFE_FUNCTIONS, **_functions_mapping(functions or {})}

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"Синтаксична помилка у формулі: {expression!r}") from exc

    if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
        raise FormulaError("Формула занадто складна")

    # Фінальний результат має бути числом або bool: рядок назовні не випускаємо.
    return _guard_result(_eval(tree.body, safe_vars, safe_funcs, depth=0))


def _numeric_mapping(mapping: Mapping[str, Any], kind: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in mapping.items():
        if not isinstance(name, str) or not name.isidentifier():
            raise FormulaError(f"Некоректне імʼя {kind}: {name!r}")
        if isinstance(value, bool):
            result[name] = value
        elif isinstance(value, (int, float)):
            result[name] = value
        else:
            raise FormulaError(f"{kind} {name!r} має бути числом")
    return result


def _functions_mapping(mapping: Mapping[str, Callable[..., Any]]) -> dict[str, Callable[..., Any]]:
    result: dict[str, Callable[..., Any]] = {}
    for name, function in mapping.items():
        if not isinstance(name, str) or not name.isidentifier():
            raise FormulaError(f"Некоректне імʼя функції: {name!r}")
        if not callable(function):
            raise FormulaError(f"Функція {name!r} не викликається")
        result[name] = function
    return result


def _eval(node: ast.AST, variables: dict[str, Any], functions: dict[str, Callable[..., Any]], *, depth: int) -> Any:
    if depth > MAX_DEPTH:
        raise FormulaError("Формула занадто глибока")

    if isinstance(node, ast.Constant):
        return _check_constant(node.value)

    if isinstance(node, ast.Name):
        if node.id in variables:
            return variables[node.id]
        raise FormulaError(f"Невідоме імʼя: {node.id}")

    if isinstance(node, ast.BinOp):
        operation = _BIN_OPS.get(type(node.op))
        if operation is None:
            raise FormulaError(f"Заборонена операція: {type(node.op).__name__}")
        left = _eval(node.left, variables, functions, depth=depth + 1)
        right = _eval(node.right, variables, functions, depth=depth + 1)
        if not (_is_number(left) and _is_number(right)):
            raise FormulaError("Арифметичні операції дозволені лише з числами")
        try:
            return _guard_result(operation(left, right))
        except ZeroDivisionError as exc:
            raise FormulaError("Ділення на нуль") from exc

    if isinstance(node, ast.UnaryOp):
        operand = _eval(node.operand, variables, functions, depth=depth + 1)
        if not (_is_number(operand) or isinstance(operand, bool)):
            raise FormulaError("Унарні операції дозволені лише з числами")
        if isinstance(node.op, ast.USub):
            return _guard_result(-operand)
        if isinstance(node.op, ast.UAdd):
            return _guard_result(+operand)
        if isinstance(node.op, ast.Not):
            return not operand
        raise FormulaError(f"Заборонена операція: {type(node.op).__name__}")

    if isinstance(node, ast.Compare):
        left = _eval(node.left, variables, functions, depth=depth + 1)
        for op_node, comparator in zip(node.ops, node.comparators, strict=True):
            operation = _CMP_OPS.get(type(op_node))
            if operation is None:
                raise FormulaError(f"Заборонене порівняння: {type(op_node).__name__}")
            right = _eval(comparator, variables, functions, depth=depth + 1)
            if not operation(left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.BoolOp):
        values = node.values
        if isinstance(node.op, ast.And):
            result: Any = True
            for value in values:
                result = _eval(value, variables, functions, depth=depth + 1)
                if not result:
                    return result
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for value in values:
                result = _eval(value, variables, functions, depth=depth + 1)
                if result:
                    return result
            return result
        raise FormulaError("Заборонена логічна операція")

    if isinstance(node, ast.IfExp):
        condition = _eval(node.test, variables, functions, depth=depth + 1)
        branch = node.body if condition else node.orelse
        return _eval(branch, variables, functions, depth=depth + 1)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise FormulaError("Дозволені лише виклики іменованих функцій")
        if node.keywords:
            raise FormulaError("Іменовані аргументи заборонені")
        function = functions.get(node.func.id)
        if function is None:
            raise FormulaError(f"Невідома функція: {node.func.id}")
        args = [_eval(arg, variables, functions, depth=depth + 1) for arg in node.args]
        try:
            return _guard_result(function(*args))
        except FormulaError:
            raise
        except (TypeError, ValueError) as exc:
            raise FormulaError(f"Помилка у виклику {node.func.id}(): {exc}") from exc

    raise FormulaError(f"Заборонена конструкція: {type(node).__name__}")


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _check_constant(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            raise FormulaError("Рядкова константа задовга")
        return value
    raise FormulaError("Дозволені лише числа, короткі рядки та true/false")


def _guard_result(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        if abs(value) > MAX_ABS_RESULT:
            raise FormulaError("Результат формули занадто великий")
        return value
    raise FormulaError(f"Некоректний результат формули: {type(value).__name__}")
