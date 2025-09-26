"""Derived Field Composer (Milestone 7.10.37)

Provides a small ChromeDialog-based UI (invoked from the Ingestion Lab) that helps
users define derived fields based on already extracted resource fields. For the
initial milestone we focus on the core logic & validation surface rather than
polishing advanced UX. The dialog ultimately amends the rule editor JSON by
inserting/merging a top-level `derived` mapping of:

    "derived": {
        "new_field": "expression referencing other fields"
    }

Security / Safety:
 - Expressions are parsed with `ast` in `eval` mode and strictly validated.
 - Only a constrained set of Python AST node types is permitted (arithmetic,
   boolean, comparisons, ternary if-expression, and constants / names).
 - Names must correspond to existing extracted field names (table columns or
   list rule fields) discovered from the current RuleSet.
 - No attribute access, calls, comprehensions, lambdas, imports, or indexing of
   arbitrary objects are allowed.

Limitations (Deferred Enhancements):
 - No dependency ordering resolution (user responsibility to avoid referencing
   another derived field in the *same* apply step).
 - No expression preview evaluation yet; this will be added in a later milestone.
 - When the rule document is updated the entire JSON is re-serialized with
   indentation (pretty print) which may reorder keys. Acceptable for milestone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Set, Tuple, List
import ast
import json

from PyQt6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
)

try:  # pragma: no cover - GUI base optional for tests
    from gui.components.chrome_dialog import ChromeDialog
except Exception:  # pragma: no cover
    ChromeDialog = object  # type: ignore[misc]

__all__ = [
    "gather_available_fields",
    "validate_expression",
    "update_ruleset_with_derived",
    "DerivedFieldComposerDialog",
]


# ---------------------------------------------------------------------------
# Pure helpers (unit tested)


def gather_available_fields(rules_mapping: Dict) -> Set[str]:
    """Return set of field names available for derivation.

    Includes table rule column names + list rule field names. Input is the
    parsed JSON/YAML mapping (not the RuleSet instance) to avoid importing
    heavy schema logic here. We assume the structure conforms to rule_schema.
    """

    out: Set[str] = set()
    resources = rules_mapping.get("resources", {}) if isinstance(rules_mapping, dict) else {}
    if not isinstance(resources, dict):  # defensive
        return out
    for _rname, spec in resources.items():
        if not isinstance(spec, dict):
            continue
        kind = spec.get("kind")
        if kind == "table":
            cols = spec.get("columns") or []
            if isinstance(cols, list):
                out.update([c for c in cols if isinstance(c, str)])
        elif kind == "list":
            fields = spec.get("fields") or {}
            if isinstance(fields, dict):
                out.update([n for n in fields.keys() if isinstance(n, str)])
    return out


ALLOWED_AST_NODES: Tuple[type, ...] = (
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


def validate_expression(expr: str, allowed_names: Set[str]) -> Set[str]:
    """Validate an expression and return referenced field names.

    Raises ValueError on invalid syntax, disallowed nodes, or unknown names.
    Empty / whitespace-only expressions are rejected.
    """

    if not expr or not expr.strip():
        raise ValueError("Expression cannot be empty")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:  # pragma: no cover - direct syntax error path
        raise ValueError(f"Invalid syntax: {e.msg}") from e
    referenced: Set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST_NODES):
            raise ValueError(f"Disallowed syntax: {node.__class__.__name__}")
        if isinstance(node, ast.Name):
            if node.id not in allowed_names:
                raise ValueError(f"Unknown field name: {node.id}")
            referenced.add(node.id)
    if not referenced:
        raise ValueError("Expression must reference at least one existing field")
    return referenced


def update_ruleset_with_derived(raw_rules_text: str, derived: Dict[str, str]) -> str:
    """Return updated pretty JSON rule document with merged derived mapping.

    If parsing fails, raises ValueError. Derived mapping keys/values are assumed
    already validated. Existing `derived` mapping (if any) is merged (new keys
    overwrite duplicates). Returns a re-dumped JSON string with indent=2.
    """

    try:
        data = json.loads(raw_rules_text or "{}")
    except Exception as e:  # pragma: no cover
        raise ValueError(f"Cannot parse rules JSON: {e}") from e
    if not isinstance(data, dict):  # pragma: no cover
        raise ValueError("Rules root must be an object/mapping")
    existing = data.get("derived")
    if existing and isinstance(existing, dict):
        merged = dict(existing)
        merged.update(derived)
    else:
        merged = dict(derived)
    data["derived"] = merged
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# Dialog


class DerivedFieldComposerDialog(ChromeDialog):  # type: ignore[misc]
    """Dialog for composing derived fields.

    Workflow:
      1. User sees list of available base fields.
      2. Enters new field name + expression.
      3. Clicks Validate -> expression checked; if valid can Add.
      4. Accumulated derived fields displayed; Accept merges them into rules.
    """

    def __init__(self, rules_text: str, parent=None):  # noqa: D401
        super().__init__(parent, title="Derived Field Composer")
        self.setObjectName("DerivedFieldComposerDialog")
        try:
            self.resize(720, 560)
        except Exception:  # pragma: no cover
            pass
        lay = self.content_layout() if hasattr(self, "content_layout") else QVBoxLayout(self)
        # Parse once to gather available fields
        try:
            mapping = json.loads(rules_text or "{}")
        except Exception:
            mapping = {}
        self._available = sorted(gather_available_fields(mapping))
        lay.addWidget(QLabel("Available Fields:"))
        self.list_fields = QListWidget()
        for name in self._available:
            QListWidgetItem(name, self.list_fields)
        lay.addWidget(self.list_fields, 1)
        form = QVBoxLayout()
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("New Field Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. points_diff_ratio")
        row1.addWidget(self.name_edit, 1)
        form.addLayout(row1)
        self.expr_edit = QPlainTextEdit()
        self.expr_edit.setPlaceholderText("Expression (e.g. points / diff)")
        self.expr_edit.setFixedHeight(70)
        form.addWidget(self.expr_edit)
        buttons = QHBoxLayout()
        self.btn_validate = QPushButton("Validate")
        self.btn_add = QPushButton("Add Field")
        self.btn_add.setEnabled(False)
        buttons.addWidget(self.btn_validate)
        buttons.addWidget(self.btn_add)
        buttons.addStretch(1)
        form.addLayout(buttons)
        self.status_label = QLabel("")
        self.status_label.setObjectName("derivedStatusLabel")
        form.addWidget(self.status_label)
        lay.addLayout(form)
        lay.addWidget(QLabel("Pending Derived Fields:"))
        self.list_pending = QListWidget()
        lay.addWidget(self.list_pending, 1)
        footer = QHBoxLayout()
        self.btn_ok = QPushButton("Apply")
        self.btn_cancel = QPushButton("Cancel")
        footer.addStretch(1)
        footer.addWidget(self.btn_ok)
        footer.addWidget(self.btn_cancel)
        lay.addLayout(footer)
        # Internal store
        self._derived: Dict[str, str] = {}
        # Signals
        try:  # pragma: no cover - best effort in headless
            self.btn_cancel.clicked.connect(self.reject)  # type: ignore[attr-defined]
            self.btn_ok.clicked.connect(self._accept_and_close)  # type: ignore[attr-defined]
            self.btn_validate.clicked.connect(self._on_validate_clicked)  # type: ignore[attr-defined]
            self.btn_add.clicked.connect(self._on_add_clicked)  # type: ignore[attr-defined]
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _on_validate_clicked(self) -> None:  # noqa: D401
        name = (self.name_edit.text() or "").strip()
        expr = (self.expr_edit.toPlainText() or "").strip()
        if not name:
            self._set_status("Name required", error=True)
            return
        if not expr:
            self._set_status("Expression required", error=True)
            return
        if name in self._available or name in self._derived:
            self._set_status("Name already in use", error=True)
            return
        try:
            validate_expression(expr, set(self._available))
        except ValueError as e:
            self._set_status(str(e), error=True)
            self.btn_add.setEnabled(False)
            return
        self._set_status("Valid expression", error=False)
        self.btn_add.setEnabled(True)

    # ------------------------------------------------------------------
    def _on_add_clicked(self) -> None:  # noqa: D401
        name = (self.name_edit.text() or "").strip()
        expr = (self.expr_edit.toPlainText() or "").strip()
        if not name or not expr:
            return
        self._derived[name] = expr
        QListWidgetItem(f"{name}: {expr}", self.list_pending)
        self.name_edit.clear()
        self.expr_edit.clear()
        self.btn_add.setEnabled(False)
        self._set_status("Added", error=False)

    # ------------------------------------------------------------------
    def _accept_and_close(self) -> None:  # noqa: D401
        if not self._derived:
            self._set_status("No derived fields added", error=True)
            return
        try:
            self.accept()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover
            pass

    # ------------------------------------------------------------------
    def derived_fields(self) -> Dict[str, str]:  # noqa: D401 - simple accessor
        return dict(self._derived)

    # ------------------------------------------------------------------
    def _set_status(self, text: str, *, error: bool) -> None:
        color = "#c62828" if error else "#2e7d32"
        self.status_label.setStyleSheet(f"color:{color};font-weight:bold;")
        self.status_label.setText(text)
