"""Safe expression evaluation and ``${...}`` template interpolation.

Nexus flows are data, not code.  Expressions are therefore evaluated with a
small, deliberately restricted AST interpreter instead of :func:`eval`.  The
language supports:

* names and dotted access into mappings (``vars.region``, ``steps.load.data``)
* indexing and slicing (``items[0]``, ``matrix[1:3]``)
* literals, lists, tuples, dicts and sets
* arithmetic, comparisons, boolean operators and the conditional expression
* a whitelist of pure helper functions (``len``, ``min``, ``merge``, ...)

Arbitrary attribute access, method calls, comprehensions, lambdas and imports
are rejected.
"""

from __future__ import annotations

import ast
import math
import operator
import random
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from .errors import ExpressionError

_EXPR_START = "${"
_ESCAPED_EXPR_START = "$${"
_STEP_ATTR_RE = re.compile(r"\bsteps\.([A-Za-z_][A-Za-z0-9_]*)")
_STEP_ITEM_RE = re.compile(r"\bsteps\[\s*['\"]([^'\"]+)['\"]\s*\]")


# ---------------------------------------------------------------------------
# Helpers exposed to expressions
# ---------------------------------------------------------------------------


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, Mapping) and isinstance(override, Mapping):
        merged = dict(base)
        for key, value in override.items():
            if key in merged:
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
    return override


def _merge(*values: Any) -> Any:
    result: Any = {}
    for value in values:
        if value is None:
            continue
        if not isinstance(value, Mapping):
            raise ExpressionError(f"merge() expects mappings, got {type(value).__name__}")
        result = _deep_merge(result, value)
    return result


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _contains(haystack: Any, needle: Any) -> bool:
    if haystack is None:
        return False
    try:
        return needle in haystack
    except TypeError:
        return False


def _startswith(value: Any, prefix: Any) -> bool:
    return str(value).startswith(str(prefix))


def _endswith(value: Any, suffix: Any) -> bool:
    return str(value).endswith(str(suffix))


def _join(separator: Any, values: Any) -> str:
    return str(separator).join(str(value) for value in values)


def _split(value: Any, separator: Any = None) -> list[str]:
    return str(value).split(separator)


_ALLOWED_FUNCTIONS: dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "coalesce": _coalesce,
    "contains": _contains,
    "dict": dict,
    "endswith": _endswith,
    "float": float,
    "int": int,
    "join": _join,
    "len": len,
    "list": list,
    "lower": lambda value: str(value).lower(),
    "max": max,
    "merge": _merge,
    "min": min,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "split": _split,
    "startswith": _startswith,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "upper": lambda value: str(value).upper(),
}

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda left, right: left in right,
    ast.NotIn: lambda left, right: left not in right,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
}


# ---------------------------------------------------------------------------
# Template scanning
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Literal:
    value: str


@dataclass(frozen=True)
class _Expression:
    value: str


_TemplatePart = _Literal | _Expression


def _scan_template(template: str) -> list[_TemplatePart]:
    """Split a template into literal and expression parts.

    Braces inside quoted strings and nested dict literals are handled, so
    ``${ {'a': {'b': 1}} }`` is parsed as one expression.
    """

    parts: list[_TemplatePart] = []
    literal: list[str] = []
    index = 0
    length = len(template)

    def flush() -> None:
        if literal:
            parts.append(_Literal("".join(literal)))
            literal.clear()

    while index < length:
        if template.startswith(_ESCAPED_EXPR_START, index):
            literal.append(_EXPR_START)
            index += len(_ESCAPED_EXPR_START)
            continue
        if not template.startswith(_EXPR_START, index):
            literal.append(template[index])
            index += 1
            continue

        flush()
        index += len(_EXPR_START)
        start = index
        depth = 1
        quote: str | None = None
        escaped = False

        while index < length:
            char = template[index]
            if quote is not None:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
                index += 1
                continue

            if char in {"'", '"'}:
                quote = char
                index += 1
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    expression = template[start:index].strip()
                    if not expression:
                        raise ExpressionError("empty expression in template")
                    parts.append(_Expression(expression))
                    index += 1
                    break
            index += 1
        else:
            raise ExpressionError(f"unterminated expression in template: {template!r}")

    flush()
    return parts


def is_template(value: str) -> bool:
    """Return True when *value* contains a ``${...}`` expression."""

    return _EXPR_START in value.replace(_ESCAPED_EXPR_START, "")


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


class ExpressionEvaluator:
    """Evaluate a single expression against a read-only scope."""

    def __init__(self, scope: Mapping[str, Any]) -> None:
        self.scope = scope

    def evaluate(self, expression: str) -> Any:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ExpressionError(f"invalid expression {expression!r}: {exc.msg}") from exc
        try:
            return self._eval(tree.body)
        except ExpressionError:
            raise
        except Exception as exc:  # pragma: no cover - defensive conversion
            raise ExpressionError(f"failed to evaluate {expression!r}: {exc}") from exc

    # -- AST dispatch -----------------------------------------------------

    def _eval(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return self._lookup(node.id)
        if isinstance(node, ast.Attribute):
            return self._attribute(self._eval(node.value), node.attr)
        if isinstance(node, ast.Subscript):
            return self._subscript(self._eval(node.value), self._eval(node.slice))
        if isinstance(node, ast.Slice):
            return slice(
                self._eval(node.lower) if node.lower else None,
                self._eval(node.upper) if node.upper else None,
                self._eval(node.step) if node.step else None,
            )
        if isinstance(node, ast.List):
            return [self._eval(item) for item in node.elts]
        if isinstance(node, ast.Tuple):
            return tuple(self._eval(item) for item in node.elts)
        if isinstance(node, ast.Set):
            return {self._eval(item) for item in node.elts}
        if isinstance(node, ast.Dict):
            mapping: dict[Any, Any] = {}
            for key, value in zip(node.keys, node.values, strict=True):
                if key is None:
                    raise ExpressionError("** unpacking is not allowed in expressions")
                mapping[self._eval(key)] = self._eval(value)
            return mapping
        if isinstance(node, ast.UnaryOp):
            value = self._eval(node.operand)
            if isinstance(node.op, ast.Not):
                return not value
            if isinstance(node.op, ast.USub):
                return -value
            if isinstance(node.op, ast.UAdd):
                return +value
            if isinstance(node.op, ast.Invert):
                return ~value
            raise ExpressionError("unsupported unary operator")
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                result: Any = True
                for value_node in node.values:
                    result = self._eval(value_node)
                    if not result:
                        return result
                return result
            result = False
            for value_node in node.values:
                result = self._eval(value_node)
                if result:
                    return result
            return result
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left)
            right = self._eval(node.right)
            op = _BIN_OPS.get(type(node.op))
            if op is None:
                raise ExpressionError("unsupported binary operator")
            return op(left, right)
        if isinstance(node, ast.Compare):
            left = self._eval(node.left)
            for op_node, comparator_node in zip(node.ops, node.comparators, strict=True):
                right = self._eval(comparator_node)
                op = _CMP_OPS.get(type(op_node))
                if op is None:
                    raise ExpressionError("unsupported comparison operator")
                if not op(left, right):
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            return self._eval(node.body) if self._eval(node.test) else self._eval(node.orelse)
        if isinstance(node, ast.Call):
            return self._call(node)
        raise ExpressionError(f"unsupported expression element: {type(node).__name__}")

    # -- primitives -------------------------------------------------------

    def _lookup(self, name: str) -> Any:
        if name.startswith("_"):
            raise ExpressionError(f"access to private name '{name}' is not allowed")
        # YAML-style literal spellings are convenient inside ${...} blocks.
        if name in {"true", "false"}:
            return name == "true"
        if name in {"null", "none"}:
            return None
        if name not in self.scope:
            raise ExpressionError(f"unknown name '{name}'")
        return self.scope[name]

    def _attribute(self, value: Any, name: str) -> Any:
        if name.startswith("_"):
            raise ExpressionError(f"access to private attribute '{name}' is not allowed")
        if isinstance(value, Mapping):
            if name in value:
                return value[name]
            raise ExpressionError(f"mapping has no key '{name}'")
        if isinstance(value, BaseModel):
            fields = type(value).model_fields
            if name in fields:
                return getattr(value, name)
            raise ExpressionError(f"{type(value).__name__} has no field '{name}'")
        raise ExpressionError(
            f"cannot access attribute '{name}' on {type(value).__name__}; use a mapping or indexing"
        )

    def _subscript(self, value: Any, key: Any) -> Any:
        if isinstance(value, Mapping):
            try:
                return value[key]
            except KeyError as exc:
                raise ExpressionError(f"key '{key}' not found") from exc
        if isinstance(value, (str, list, tuple)):
            try:
                return value[key]
            except (IndexError, TypeError, KeyError) as exc:
                raise ExpressionError(f"invalid index {key!r}: {exc}") from exc
        raise ExpressionError(f"cannot index {type(value).__name__}")

    def _call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise ExpressionError("only direct calls to whitelisted functions are allowed")
        name = node.func.id
        func = _ALLOWED_FUNCTIONS.get(name)
        if func is None:
            raise ExpressionError(f"function '{name}' is not allowed")
        args = [self._eval(arg) for arg in node.args]
        if any(isinstance(arg, ast.Starred) for arg in node.args):  # pragma: no cover
            raise ExpressionError("starred arguments are not allowed")
        kwargs = {}
        for keyword in node.keywords:
            if keyword.arg is None:
                raise ExpressionError("**kwargs is not allowed")
            kwargs[keyword.arg] = self._eval(keyword.value)
        return func(*args, **kwargs)


# ---------------------------------------------------------------------------
# Public resolver
# ---------------------------------------------------------------------------


class ExpressionResolver:
    """Resolve expressions inside arbitrary YAML/JSON-like values."""

    def __init__(self, scope: Mapping[str, Any]) -> None:
        self.scope = scope

    def resolve(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._resolve_string(value)
        if isinstance(value, Mapping):
            return {key: self.resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.resolve(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.resolve(item) for item in value)
        if isinstance(value, BaseModel):
            return value
        return value

    def evaluate(self, expression: str) -> Any:
        return ExpressionEvaluator(self.scope).evaluate(expression)

    def evaluate_condition(self, value: Any) -> bool:
        """Evaluate a ``when`` value.

        Booleans pass through, template strings are resolved, and bare strings
        are treated as expressions for convenience (``when: steps.x.ok``).
        """

        if value is None:
            return True
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if is_template(value):
                return bool(self._resolve_string(value))
            return bool(self.evaluate(value))
        return bool(value)

    def evaluate_items(self, value: Any) -> list[Any]:
        if isinstance(value, str):
            resolved = self._resolve_string(value) if is_template(value) else self.evaluate(value)
        else:
            resolved = self.resolve(value)
        if resolved is None:
            return []
        if isinstance(resolved, Mapping):
            return list(resolved.values())
        if isinstance(resolved, Iterable) and not isinstance(resolved, (str, bytes)):
            return list(resolved)
        raise ExpressionError(f"foreach items must be a list or mapping, got {type(resolved).__name__}")

    def _resolve_string(self, template: str) -> Any:
        if _ESCAPED_EXPR_START not in template and _EXPR_START not in template:
            return template

        parts = _scan_template(template)
        if len(parts) == 1 and isinstance(parts[0], _Expression):
            return self.evaluate(parts[0].value)

        result: list[str] = []
        for part in parts:
            if isinstance(part, _Literal):
                result.append(part.value)
            else:
                result.append(self._stringify(self.evaluate(part.value)))
        return "".join(result)

    @staticmethod
    def _stringify(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, bool):
            return str(value).lower()
        return str(value)


def resolve_value(value: Any, scope: Mapping[str, Any]) -> Any:
    return ExpressionResolver(scope).resolve(value)


def evaluate_expression(expression: str, scope: Mapping[str, Any]) -> Any:
    return ExpressionEvaluator(scope).evaluate(expression)


# ---------------------------------------------------------------------------
# Static reference extraction (used for implicit DAG edges)
# ---------------------------------------------------------------------------


def _expressions_in_string(value: str, *, bare: bool) -> list[str]:
    if is_template(value):
        return [part.value for part in _scan_template(value) if isinstance(part, _Expression)]
    if bare and value.strip():
        return [value.strip()]
    return []


def extract_step_refs(value: Any, *, bare: bool = False) -> set[str]:
    """Return step ids referenced by expressions in *value*.

    ``bare=False`` only inspects ``${...}`` expressions, which is right for
    ordinary input values.  Pass ``bare=True`` for expression-only fields such
    as ``when`` and ``foreach.items`` where a raw string is also an expression.
    """

    refs: set[str] = set()

    def visit(item: Any, is_bare: bool) -> None:
        if isinstance(item, str):
            for expression in _expressions_in_string(item, bare=is_bare):
                for match in _STEP_ATTR_RE.finditer(expression):
                    refs.add(match.group(1))
                for match in _STEP_ITEM_RE.finditer(expression):
                    refs.add(match.group(1))
        elif isinstance(item, Mapping):
            for child in item.values():
                visit(child, is_bare)
        elif isinstance(item, (list, tuple, set)):
            for child in item:
                visit(child, is_bare)

    visit(value, bare)
    return refs


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


def jitter(base: float, jitter_s: float) -> float:
    if jitter_s <= 0:
        return base
    return base + random.uniform(0.0, jitter_s)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and not math.isnan(value)
