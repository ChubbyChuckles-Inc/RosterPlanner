"""Runtime execution of field value transform chains (Milestone 7.10.7).

This module complements the declarative schema in ``rule_schema.py`` by
providing a pure-function execution engine that applies a list of
``TransformSpec`` instances to an extracted raw string value, returning
an optionally coerced Python object.

Supported transform kinds (matching ``TransformSpec``):
  trim            -> str.strip()
  collapse_ws     -> collapse internal whitespace to a single space + strip
  to_number       -> parse integer / float with simple comma / dot normalization
  parse_date      -> parse date string using provided strptime formats; returns ISO date 'YYYY-MM-DD'
  expr            -> (OPTIONAL) evaluate a restricted Python expression with variable ``value``
                     ONLY allowed if allow_expressions=True when calling the API.

Safety / Hardening:
 - Expression transforms run with an empty __builtins__ plus a tiny allow list (len, min, max, sum).
 - Code length limited (<= 200 chars) and may not contain forbidden keywords ("import", "exec", "eval", "__").
 - Numeric parsing strips thousands separators (spaces, thin spaces) and normalises comma to decimal point
   if no dot present. Fallback strategy attempts int then float.

The design keeps execution stateless and dependency-free for easy unit testing.

Future extension points (not yet implemented but anticipated by later milestones):
 - Attribute extraction (e.g., @href) as a prior step before transform chain.
 - Regex capture & group referencing transform.
 - Structured error reporting with positions / original values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Iterable, List

from .rule_schema import TransformSpec

__all__ = [
    "TransformExecutionError",
    "apply_transform_chain",
]


class TransformExecutionError(RuntimeError):
    """Raised when a transform cannot be executed safely or fails irrecoverably."""


_FORBIDDEN_EXPR_SNIPPETS = ("import", "exec", "eval", "__", "open", "write", "os.")
_ALLOWED_EXPR_BUILTINS = {"len": len, "min": min, "max": max, "sum": sum}


def _apply_single(value: Any, spec: TransformSpec, allow_expressions: bool) -> Any:
    """Apply a single TransformSpec to the value.

    Parameters
    ----------
    value: Any
        Current pipeline value. ``None`` short-circuits (returned unchanged) except
        that *expr* still runs (so an expression can manufacture a value from None).
    spec: TransformSpec
        The transform descriptor.
    allow_expressions: bool
        Global flag enabling expression execution (already validated at schema parse).
    """
    kind = spec.kind
    if kind == "trim":
        if value is None:
            return None
        return str(value).strip()
    if kind == "collapse_ws":
        if value is None:
            return None
        return re.sub(r"\s+", " ", str(value)).strip()
    if kind == "to_number":
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        # Remove thin spaces / normal spaces used as thousand separators
        text_norm = text.replace("\xa0", " ")
        text_norm = re.sub(r"(?<=\d)[\s_]+(?=\d)", "", text_norm)
        # If there's a comma and no dot treat comma as decimal separator.
        if "," in text_norm and "." not in text_norm:
            text_norm = text_norm.replace(",", ".")
        else:
            # Otherwise drop stray commas (thousands separators)
            text_norm = text_norm.replace(",", "")
        # Attempt int first when no decimal point
        if re.fullmatch(r"[-+]?\d+", text_norm):
            try:
                return int(text_norm)
            except Exception as e:  # pragma: no cover - highly unlikely
                raise TransformExecutionError(f"Failed int parse: {text_norm}") from e
        try:
            return float(text_norm)
        except Exception as e:  # pragma: no cover
            raise TransformExecutionError(f"Failed float parse: {text_norm}") from e
    if kind == "parse_date":
        if value is None:
            return None
        if not spec.formats:
            raise TransformExecutionError("parse_date requires formats at execution time")
        raw = str(value).strip()
        if not raw:
            return None
        last_err: Exception | None = None
        for fmt in spec.formats:
            try:
                dt = datetime.strptime(raw, fmt)
                return dt.date().isoformat()
            except Exception as e:  # pragma: no cover - loops until success or exhaustion
                last_err = e
        raise TransformExecutionError(
            f"parse_date could not parse value '{raw}' with provided formats"
        ) from last_err
    if kind == "expr":
        if not allow_expressions:
            raise TransformExecutionError("Expression execution disabled (allow_expressions=False)")
        code = spec.code or ""
        if len(code) > 200:
            raise TransformExecutionError("Expression too long (limit=200 chars)")
        lowered = code.lower()
        if any(sn in lowered for sn in _FORBIDDEN_EXPR_SNIPPETS):
            raise TransformExecutionError("Expression contains forbidden tokens")
        # Execute in a restricted namespace.
        locals_dict = {"value": value}
        try:
            return eval(
                code, {"__builtins__": _ALLOWED_EXPR_BUILTINS}, locals_dict
            )  # noqa: S307 (intentional sandboxed eval)
        except Exception as e:  # pragma: no cover - expression failure path
            raise TransformExecutionError(f"Expression transform failed: {e}") from e
    raise TransformExecutionError(f"Unsupported transform kind at execution: {kind}")


def apply_transform_chain(
    value: Any, transforms: Iterable[TransformSpec], *, allow_expressions: bool
) -> Any:
    """Apply a sequence of transforms to a value.

    The function is resilient: it stops and raises on the *first* failing
    transform, ensuring errors are explicit for callers (preview panel can
    catch and surface with context). If no transforms are provided, the
    value is returned unchanged.
    """
    current = value
    for spec in transforms:
        current = _apply_single(current, spec, allow_expressions)
    return current
