from __future__ import annotations

import pytest

from nexus.core.errors import ExpressionError
from nexus.core.expr import (
    ExpressionResolver,
    evaluate_expression,
    extract_step_refs,
    resolve_value,
)


def scope() -> dict:
    return {
        "vars": {"x": 10, "flag": True, "name": "nexus", "nested": {"a": 1, "b": 2}},
        "steps": {"load": {"value": 5, "outputs": {"value": 5}, "status": "success"}},
        "env": {"HOME": "/home/test"},
        "config": {"threshold": 0.5},
        "inputs": {"who": "world"},
    }


def test_whole_expression_preserves_type() -> None:
    assert resolve_value("${vars.x}", scope()) == 10
    assert resolve_value("${vars.nested}", scope()) == {"a": 1, "b": 2}
    assert resolve_value("${vars.flag}", scope()) is True


def test_interpolation_stringifies() -> None:
    assert resolve_value("hello ${inputs.who}!", scope()) == "hello world!"
    assert resolve_value("x=${vars.x}", scope()) == "x=10"
    assert resolve_value("flag=${vars.flag}", scope()) == "flag=true"


def test_arithmetic_comparison_and_conditionals() -> None:
    assert evaluate_expression("vars.x * 2 + 1", scope()) == 21
    assert evaluate_expression("vars.x > 5 and vars.flag", scope()) is True
    assert evaluate_expression("'yes' if vars.x > 5 else 'no'", scope()) == "yes"
    assert evaluate_expression("vars.x in [10, 20]", scope()) is True


def test_mapping_access_and_indexing() -> None:
    assert evaluate_expression("vars.nested.a", scope()) == 1
    assert evaluate_expression("vars.nested['b']", scope()) == 2
    assert evaluate_expression("steps.load.value", scope()) == 5
    assert evaluate_expression("env.HOME", scope()) == "/home/test"


def test_helpers_merge_and_coalesce() -> None:
    merged = evaluate_expression("merge(vars.nested, {'b': 9, 'c': 3})", scope())
    assert merged == {"a": 1, "b": 9, "c": 3}
    assert evaluate_expression("coalesce(null, 'fallback')", scope()) == "fallback"
    assert evaluate_expression("startswith('nexus', 'nex')", scope()) is True


def test_yaml_literals() -> None:
    assert evaluate_expression("true", scope()) is True
    assert evaluate_expression("false", scope()) is False
    assert evaluate_expression("null", scope()) is None


def test_escaped_expression() -> None:
    assert resolve_value("$${vars.x}", scope()) == "${vars.x}"


def test_resolve_nested_structures() -> None:
    resolved = ExpressionResolver(scope()).resolve({"a": "${vars.x}", "b": ["${vars.name}", 1]})
    assert resolved == {"a": 10, "b": ["nexus", 1]}


def test_security_rejects_dunder_and_calls() -> None:
    with pytest.raises(ExpressionError):
        evaluate_expression("vars.__class__", scope())
    with pytest.raises(ExpressionError):
        evaluate_expression("__import__('os')", scope())
    with pytest.raises(ExpressionError):
        evaluate_expression("vars.name.upper()", scope())


def test_unknown_name_and_bad_syntax() -> None:
    with pytest.raises(ExpressionError):
        evaluate_expression("vars.missing", scope())
    with pytest.raises(ExpressionError):
        evaluate_expression("vars.x +", scope())
    with pytest.raises(ExpressionError):
        resolve_value("${vars.x", scope())


def test_extract_step_refs() -> None:
    assert extract_step_refs({"x": "${steps.load.value}"}) == {"load"}
    assert extract_step_refs("${steps['a'].x + steps.b.y}") == {"a", "b"}
    assert extract_step_refs("steps.c.ok", bare=True) == {"c"}
    assert extract_step_refs("literal steps.d text") == set()
