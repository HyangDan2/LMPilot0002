from __future__ import annotations

import ast
import operator
from typing import Callable


class CalculatorError(Exception):
    pass


Number = int | float
BinaryOperator = Callable[[Number, Number], Number]
UnaryOperator = Callable[[Number], Number]

MAX_EXPRESSION_CHARS = 240
MAX_ABS_VALUE = 10**12
MAX_POWER_EXPONENT = 10

BINARY_OPERATORS: dict[type[ast.operator], BinaryOperator] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

UNARY_OPERATORS: dict[type[ast.unaryop], UnaryOperator] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def calculate(expression: str) -> str:
    expression = expression.strip()
    if not expression:
        raise CalculatorError("Calculator expression is empty.")
    if len(expression) > MAX_EXPRESSION_CHARS:
        raise CalculatorError("Calculator expression is too long.")

    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError(f"Invalid calculator expression: {exc.msg}.") from exc

    result = _evaluate_node(parsed.body)
    return _format_number(result)


def _evaluate_node(node: ast.AST) -> Number:
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return _checked_number(node.value)
    if isinstance(node, ast.UnaryOp):
        operator_fn = UNARY_OPERATORS.get(type(node.op))
        if operator_fn is None:
            raise CalculatorError("Unsupported unary operator.")
        return _checked_number(operator_fn(_evaluate_node(node.operand)))
    if isinstance(node, ast.BinOp):
        operator_fn = BINARY_OPERATORS.get(type(node.op))
        if operator_fn is None:
            raise CalculatorError("Unsupported calculator operator.")
        left = _evaluate_node(node.left)
        right = _evaluate_node(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_POWER_EXPONENT:
            raise CalculatorError("Exponent is too large.")
        try:
            return _checked_number(operator_fn(left, right))
        except ZeroDivisionError as exc:
            raise CalculatorError("Division by zero.") from exc
        except OverflowError as exc:
            raise CalculatorError("Calculator result overflowed.") from exc
    raise CalculatorError("Only basic arithmetic expressions are supported.")


def _checked_number(value: Number) -> Number:
    if abs(value) > MAX_ABS_VALUE:
        raise CalculatorError("Calculator result is too large.")
    return value


def _format_number(value: Number) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)
