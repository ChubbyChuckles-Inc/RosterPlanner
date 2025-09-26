"""Security sandbox static analyzer (Milestone 7.10.41).

This module performs *static* validation of custom expression transforms
declared in ingestion rule documents as well as derived field expressions.
It does NOT execute any user code. Runtime execution remains guarded in
``rule_transforms`` with length checks and forbidden token filtering.

Goals:
 - Detect disallowed Python syntax constructs early (safer + clearer UX).
 - Provide actionable diagnostics (line/column, category, message).
 - Supply a summarized risk report for the Ingestion Lab UI.

Scope:
 - TransformSpec entries with kind == "expr" (their ``code`` strings).
 - ``derived`` mapping values (string expressions referencing fields).

Allowed syntax (mirrors derived_field_composer.ALLOWED_AST_NODES):
 - Names, constants, arithmetic + boolean operators, comparisons, unary ops,
   ternary if-expressions.

Explicitly disallowed (rejected if encountered):
 - Attribute access, subscripting, function calls, lambdas, comprehensions,
   f-strings, formatted values, assignments, augassign, imports, with, try,
   class/func defs, await/yield, star/unpack nodes.

The analyzer returns a ``SandboxReport`` dataclass with:
 - ok: bool (no errors => True)
 - issues: list of SandboxIssue entries
 - stats: aggregate counts (expressions scanned, distinct categories)

Integration points:
 - The Ingestion Lab panel can invoke ``scan_rules_text`` with the raw rule
   JSON/YAML (currently we expect JSON) to obtain a report and display a
   banner / dialog if issues exist.

Tests live in ``tests/test_security_sandbox.py`` verifying representative
cases (allowed, disallowed call, attribute, comprehension, empty, unknown name).

The implementation deliberately has zero external dependencies for ease of
auditing and unit testing.
"""

from __future__ import annotations

from dataclasses import dataclass
import ast
import json
from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "SandboxIssue",
    "SandboxReport",
    "scan_expression",
    "scan_rules_text",
]


@dataclass
class SandboxIssue:
    """Represents a single security finding in an expression."""

    expr: str
    message: str
    category: str  # e.g., syntax_error, disallowed_node, empty, unknown_name
    lineno: int | None = None
    col: int | None = None
    source: str | None = None  # 'transform' or 'derived'
    field: str | None = None  # optional field / derived name


@dataclass
class SandboxReport:
    """Aggregate result of scanning all expressions in a rule document."""

    ok: bool
    issues: List[SandboxIssue]
    expressions_scanned: int

    def summary(self) -> str:
        if self.ok:
            return f"Security sandbox: OK ({self.expressions_scanned} expressions)"
        cats = {}
        for i in self.issues:
            cats[i.category] = cats.get(i.category, 0) + 1
        cat_part = ", ".join(f"{k}:{v}" for k, v in sorted(cats.items()))
        return (
            f"Security sandbox: {len(self.issues)} issue(s) across {self.expressions_scanned} expressions ["
            + cat_part
            + "]"
        )


# Reuse the allow-list subset from derived_field_composer without importing to
# avoid circular dependencies; keep in sync intentionally (documented here).
_ALLOWED_NODE_TYPES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.UAdd,
    ast.USub,
    ast.And,
    ast.Or,
    ast.NotEq,
    ast.Eq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
)

_DISALLOWED_CATEGORIES = {
    ast.Call: "function_call",
    ast.Attribute: "attribute_access",
    ast.Subscript: "subscript",
    ast.Lambda: "lambda",
    ast.ListComp: "comprehension",
    ast.SetComp: "comprehension",
    ast.DictComp: "comprehension",
    ast.GeneratorExp: "comprehension",
    ast.FormattedValue: "fstring",
    ast.JoinedStr: "fstring",
    ast.Assign: "assignment",
    ast.AugAssign: "assignment",
    ast.Import: "import",
    ast.ImportFrom: "import",
    ast.With: "with",
    ast.Try: "try",
    ast.FunctionDef: "definition",
    ast.AsyncFunctionDef: "definition",
    ast.ClassDef: "definition",
    ast.Await: "await",
    ast.Yield: "yield",
    ast.YieldFrom: "yield",
    ast.Starred: "starred",
}


def scan_expression(
    expr: str, *, allowed_names: Optional[Iterable[str]] = None
) -> List[SandboxIssue]:
    """Scan a single expression string.

    Parameters
    ----------
    expr: str
        Raw expression text.
    allowed_names: Optional[Iterable[str]]
        If supplied, any Name not present raises an ``unknown_name`` issue.
    """

    issues: List[SandboxIssue] = []
    cleaned = (expr or "").strip()
    if not cleaned:
        issues.append(
            SandboxIssue(
                expr=expr, message="Expression is empty", category="empty", lineno=None, col=None
            )
        )
        return issues
    try:
        tree = ast.parse(cleaned, mode="eval")
    except SyntaxError as e:
        issues.append(
            SandboxIssue(
                expr=expr,
                message=f"Syntax error: {e.msg}",
                category="syntax_error",
                lineno=getattr(e, "lineno", None),
                col=getattr(e, "offset", None),
            )
        )
        return issues
    allowed_set = set(allowed_names or [])
    for node in ast.walk(tree):
        if isinstance(node, tuple(_DISALLOWED_CATEGORIES.keys())):
            issues.append(
                SandboxIssue(
                    expr=expr,
                    message=f"Disallowed syntax: {node.__class__.__name__}",
                    category=_DISALLOWED_CATEGORIES[type(node)],
                    lineno=getattr(node, "lineno", None),
                    col=getattr(node, "col_offset", None),
                )
            )
            # continue scanning to list all problems
        elif not isinstance(node, _ALLOWED_NODE_TYPES):
            issues.append(
                SandboxIssue(
                    expr=expr,
                    message=f"Disallowed node: {node.__class__.__name__}",
                    category="disallowed_node",
                    lineno=getattr(node, "lineno", None),
                    col=getattr(node, "col_offset", None),
                )
            )
        elif isinstance(node, ast.Name) and allowed_names is not None:
            if node.id not in allowed_set:
                issues.append(
                    SandboxIssue(
                        expr=expr,
                        message=f"Unknown name: {node.id}",
                        category="unknown_name",
                        lineno=getattr(node, "lineno", None),
                        col=getattr(node, "col_offset", None),
                    )
                )
    return issues


def _iter_transform_exprs(data: Dict[str, Any]):
    resources = data.get("resources")
    if not isinstance(resources, dict):
        return
    for rname, spec in resources.items():
        if not isinstance(spec, dict):
            continue
        fields = spec.get("fields") or {}
        if isinstance(fields, dict):
            for fname, fmap in fields.items():
                if not isinstance(fmap, dict):
                    continue
                transforms = fmap.get("transforms") or []
                if isinstance(transforms, list):
                    for t in transforms:
                        if (
                            isinstance(t, dict)
                            and t.get("kind") == "expr"
                            and isinstance(t.get("code"), str)
                        ):
                            yield (rname, fname, t.get("code"))


def scan_rules_text(raw: str) -> SandboxReport:
    """Scan a raw rule set JSON string; return SandboxReport.

    The scanner tolerates JSON parsing failures by producing a single
    syntax_error issue rather than raising.
    """

    issues: List[SandboxIssue] = []
    expressions = 0
    try:
        data = json.loads(raw or "{}")
    except Exception as e:  # pragma: no cover
        issues.append(
            SandboxIssue(
                expr="<rules>",
                message=f"Cannot parse JSON: {e}",
                category="syntax_error",
                lineno=None,
                col=None,
                source="rules",
            )
        )
        return SandboxReport(False, issues, expressions)

    # Collect available field names per resource for unknown name checks in derived expressions.
    # For transform expressions we *do not* validate names (they only see 'value').
    base_fields: Dict[str, set] = {}
    resources = data.get("resources")
    if isinstance(resources, dict):
        for rname, spec in resources.items():
            if isinstance(spec, dict):
                fields = spec.get("fields") or {}
                if isinstance(fields, dict):
                    base_fields[rname] = {n for n in fields.keys() if isinstance(n, str)}

    for rname, fname, code in _iter_transform_exprs(data):
        expressions += 1
        expr_issues = scan_expression(code)
        for i in expr_issues:
            i.source = "transform"
            i.field = fname
        issues.extend(expr_issues)

    # Derived expressions
    derived = data.get("derived")
    if isinstance(derived, dict):
        for dname, dexpr in derived.items():
            if not isinstance(dexpr, str):
                continue
            expressions += 1
            # Allowed names are union of *all* base fields and existing derived keys (except current to allow forward refs?)
            allowed = set().union(*base_fields.values()) | set(derived.keys())
            expr_issues = scan_expression(dexpr, allowed_names=allowed)
            for i in expr_issues:
                i.source = "derived"
                i.field = dname
            issues.extend(expr_issues)

    ok = not issues
    return SandboxReport(ok, issues, expressions)
