"""Safe Expression Playground (Milestone 7.10.A18).

Provides a guarded environment for experimenting with expression transforms
before committing them to the ingestion rule set. The module exposes pure
helpers that perform AST linting, timeout-enforced evaluation, and result type
categorisation so they can be unit-tested headlessly. A Qt dialog wrapper
("SafeExpressionPlaygroundDialog") is optionally provided for the GUI when PyQt6
is available.
"""

from __future__ import annotations

import concurrent.futures
import json
import math
import time
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional

from gui.ingestion.rule_schema import TransformSpec
from gui.ingestion.rule_transforms import TransformExecutionError, apply_transform_chain
from gui.ingestion.security_sandbox import SandboxIssue, scan_expression

__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "ALLOWED_EXPR_NAMES",
    "SamplePayload",
    "PlaygroundResult",
    "parse_sample_input",
    "categorize_value",
    "format_preview",
    "build_expr_snippet",
    "evaluate_expression_playground",
    "SafeExpressionPlaygroundDialog",
]

DEFAULT_TIMEOUT_SECONDS = 0.5
ALLOWED_EXPR_NAMES = {"value", "len", "min", "max", "sum"}


@dataclass
class SamplePayload:
    """Parsed representation of the sample value provided by the user."""

    value: Any
    category: str
    preview: str


@dataclass
class PlaygroundResult:
    """Outcome of linting + evaluating a candidate expression."""

    ok: bool
    issues: List[SandboxIssue]
    evaluation_error: Optional[str]
    sample: SamplePayload
    result_value: Any | None
    result_category: Optional[str]
    result_preview: Optional[str]
    duration_ms: Optional[float]
    snippet: Optional[str]


def parse_sample_input(sample_text: str, *, mode: str = "auto") -> SamplePayload:
    """Parse user-provided sample text into a Python value.

    Parameters
    ----------
    sample_text:
        Raw text entered by the user (may be JSON or plain text).
    mode:
        One of "auto", "text", or "json". When "auto" (default), the function
        attempts JSON parsing first and falls back to plain text on failure. When
        "json" is requested explicitly, a ``ValueError`` is raised if parsing
        fails.
    """

    sample_text = sample_text or ""
    mode_normalised = (mode or "auto").strip().lower()
    if mode_normalised not in {"auto", "text", "json"}:
        mode_normalised = "auto"
    if mode_normalised in {"auto", "json"}:
        try:
            value = json.loads(sample_text)
        except Exception:
            if mode_normalised == "json":
                raise ValueError("Invalid JSON sample payload") from None
        else:
            category = f"json-{categorize_value(value)}"
            preview = format_preview(value)
            return SamplePayload(value=value, category=category, preview=preview)
    # Treat as plain text fallback
    return SamplePayload(value=sample_text, category="text", preview=_truncate(sample_text))


def categorize_value(value: Any) -> str:
    """Return a coarse category for the provided value."""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return "number"
        return "number"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return value.__class__.__name__


def format_preview(value: Any, *, limit: int = 240) -> str:
    """Generate a compact textual representation of *value* for UI display."""

    try:
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False, indent=2)
        else:
            rendered = json.dumps(value, ensure_ascii=False)
    except TypeError:
        rendered = repr(value)
    return _truncate(rendered, limit)


def build_expr_snippet(expression: str) -> str:
    """Return a JSON snippet representing an expression transform."""

    payload = {"kind": "expr", "code": expression}
    return json.dumps(payload, ensure_ascii=False)


def evaluate_expression_playground(
    expression: str,
    sample_text: str,
    *,
    sample_mode: str = "auto",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> PlaygroundResult:
    """Lint and evaluate *expression* using the supplied sample input."""

    sample = parse_sample_input(sample_text, mode=sample_mode)
    trimmed = (expression or "").strip()
    issues = scan_expression(trimmed, allowed_names=ALLOWED_EXPR_NAMES)
    if issues:
        return PlaygroundResult(
            ok=False,
            issues=issues,
            evaluation_error=None,
            sample=sample,
            result_value=None,
            result_category=None,
            result_preview=None,
            duration_ms=None,
            snippet=None,
        )
    start = time.perf_counter()
    try:
        value = _evaluate_with_timeout(trimmed, sample.value, timeout=timeout)
    except concurrent.futures.TimeoutError:
        duration = (time.perf_counter() - start) * 1000.0
        return PlaygroundResult(
            ok=False,
            issues=issues,
            evaluation_error="Evaluation timed out",
            sample=sample,
            result_value=None,
            result_category=None,
            result_preview=None,
            duration_ms=duration,
            snippet=None,
        )
    except TransformExecutionError as exc:
        duration = (time.perf_counter() - start) * 1000.0
        return PlaygroundResult(
            ok=False,
            issues=issues,
            evaluation_error=str(exc),
            sample=sample,
            result_value=None,
            result_category=None,
            result_preview=None,
            duration_ms=duration,
            snippet=None,
        )
    except Exception as exc:  # pragma: no cover - defensive
        duration = (time.perf_counter() - start) * 1000.0
        return PlaygroundResult(
            ok=False,
            issues=issues,
            evaluation_error=f"Evaluation failed: {exc}",
            sample=sample,
            result_value=None,
            result_category=None,
            result_preview=None,
            duration_ms=duration,
            snippet=None,
        )
    duration = (time.perf_counter() - start) * 1000.0
    category = categorize_value(value)
    preview = format_preview(value)
    snippet = build_expr_snippet(trimmed)
    return PlaygroundResult(
        ok=True,
        issues=issues,
        evaluation_error=None,
        sample=sample,
        result_value=value,
        result_category=category,
        result_preview=preview,
        duration_ms=duration,
        snippet=snippet,
    )


def _evaluate_with_timeout(expression: str, sample_value: Any, *, timeout: float) -> Any:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_evaluate_expression, expression, sample_value)
        return future.result(timeout=timeout)


def _evaluate_expression(expression: str, value: Any) -> Any:
    spec = TransformSpec(kind="expr", code=expression)
    return apply_transform_chain(value, [spec], allow_expressions=True)


def _truncate(text: str, limit: int = 240) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


# ---------------------------------------------------------------------------
# Optional Qt dialog (guarded for headless unit tests)

try:  # pragma: no cover - UI elements validated via smoke tests elsewhere
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QComboBox,
        QHBoxLayout,
        QLabel,
        QPlainTextEdit,
        QPushButton,
        QVBoxLayout,
    )

    try:
        from gui.components.theme_aware import ThemeAwareMixin
    except Exception:  # pragma: no cover

        class ThemeAwareMixin:  # type: ignore
            pass

    try:
        from gui.components.chrome_dialog import ChromeDialog
    except Exception:  # pragma: no cover
        ChromeDialog = object  # type: ignore[misc]

    class SafeExpressionPlaygroundDialog(ChromeDialog, ThemeAwareMixin):  # type: ignore[misc]
        """Interactive dialog wrapping :func:`evaluate_expression_playground`."""

        def __init__(
            self,
            *,
            sample_text: str = "",
            initial_expression: str = "",
            parent=None,
        ) -> None:
            super().__init__(parent, title="Safe Expression Playground")
            self.setObjectName("safeExpressionPlaygroundDialog")
            try:
                self.resize(760, 600)
            except Exception:
                pass
            self._last_result: PlaygroundResult | None = None
            self._accepted_result: PlaygroundResult | None = None
            layout = self.content_layout() if hasattr(self, "content_layout") else QVBoxLayout(self)
            layout.addWidget(QLabel("Experiment with expression transforms in a safe sandbox."))

            expr_label = QLabel("Expression (uses variable 'value'):")
            layout.addWidget(expr_label)
            self.expr_edit = QPlainTextEdit()
            self.expr_edit.setObjectName("exprPlaygroundExpression")
            self.expr_edit.setPlaceholderText("value.strip() if value else ''")
            if initial_expression:
                self.expr_edit.setPlainText(initial_expression)
            layout.addWidget(self.expr_edit)

            sample_row = QHBoxLayout()
            sample_label = QLabel("Sample input:")
            sample_row.addWidget(sample_label)
            self.sample_mode = QComboBox()
            self.sample_mode.addItem("Auto", "auto")
            self.sample_mode.addItem("Text", "text")
            self.sample_mode.addItem("JSON", "json")
            sample_row.addWidget(self.sample_mode, 0)
            sample_row.addStretch(1)
            layout.addLayout(sample_row)
            self.sample_edit = QPlainTextEdit()
            self.sample_edit.setObjectName("exprPlaygroundSample")
            self.sample_edit.setPlaceholderText('"123" or {"value": 10}')
            if sample_text:
                self.sample_edit.setPlainText(sample_text)
            layout.addWidget(self.sample_edit, 1)

            self.sample_summary = QLabel("Sample: text")
            self.sample_summary.setObjectName("exprPlaygroundSampleSummary")
            layout.addWidget(self.sample_summary)

            button_row = QHBoxLayout()
            self.btn_evaluate = QPushButton("Evaluate")
            self.btn_insert = QPushButton("Insert Transform")
            self.btn_insert.setEnabled(False)
            self.btn_close = QPushButton("Close")
            button_row.addWidget(self.btn_evaluate)
            button_row.addWidget(self.btn_insert)
            button_row.addStretch(1)
            button_row.addWidget(self.btn_close)
            layout.addLayout(button_row)

            self.status_label = QLabel("")
            self.status_label.setObjectName("exprPlaygroundStatus")
            layout.addWidget(self.status_label)

            self.result_label = QLabel("")
            self.result_label.setObjectName("exprPlaygroundResultLabel")
            layout.addWidget(self.result_label)

            self.result_view = QPlainTextEdit()
            self.result_view.setObjectName("exprPlaygroundResultView")
            self.result_view.setReadOnly(True)
            self.result_view.setPlaceholderText("Evaluation output will appear here")
            layout.addWidget(self.result_view, 1)

            self.btn_close.clicked.connect(self.reject)  # type: ignore[attr-defined]
            self.btn_evaluate.clicked.connect(self._on_evaluate_clicked)  # type: ignore[attr-defined]
            self.btn_insert.clicked.connect(self._on_insert_clicked)  # type: ignore[attr-defined]

        # ------------------------------------------------------------------
        def _on_evaluate_clicked(self) -> None:
            expression = self.expr_edit.toPlainText()
            sample_text = self.sample_edit.toPlainText()
            mode = self.sample_mode.currentData() or "auto"
            try:
                result = evaluate_expression_playground(
                    expression,
                    sample_text,
                    sample_mode=str(mode),
                )
            except ValueError as exc:
                self._set_status(str(exc), error=True)
                self.sample_summary.setText("Sample: error")
                self.result_label.setText("")
                self.result_view.setPlainText("")
                self.btn_insert.setEnabled(False)
                self._last_result = None
                return
            self._last_result = result
            self.sample_summary.setText(f"Sample: {result.sample.category}")
            if result.sample.preview:
                self.sample_summary.setText(
                    f"Sample: {result.sample.category} → {result.sample.preview}"
                )
            if result.issues:
                issues_text = "\n".join(
                    f"- {issue.category}: {issue.message}" for issue in result.issues[:10]
                )
                if len(result.issues) > 10:
                    issues_text += "\n…"
                self._set_status(issues_text, error=True)
                self.result_label.setText("")
                self.result_view.setPlainText("")
                self.btn_insert.setEnabled(False)
                return
            self._set_status("Sandbox checks passed", error=False)
            if not result.ok:
                err = result.evaluation_error or "Evaluation failed"
                self.result_label.setText(err)
                self.result_view.setPlainText("")
                self.btn_insert.setEnabled(False)
                return
            duration = f"{result.duration_ms:.2f} ms" if result.duration_ms is not None else "n/a"
            self.result_label.setText(f"Result: {result.result_category}  •  Duration: {duration}")
            self.result_view.setPlainText(result.result_preview or "")
            self.btn_insert.setEnabled(True)

        # ------------------------------------------------------------------
        def _on_insert_clicked(self) -> None:
            if not self._last_result or not self._last_result.ok or not self._last_result.snippet:
                return
            self._accepted_result = self._last_result
            self.accept()

        # ------------------------------------------------------------------
        def selected_snippet(self) -> Optional[str]:
            if not self._accepted_result or not self._accepted_result.snippet:
                return None
            meta = self._accepted_result
            duration = f" eval:{meta.duration_ms:.1f}ms" if meta.duration_ms is not None else ""
            comment = f"# expr-playground result:{meta.result_category} sample:{meta.sample.category}{duration}\n"
            return f"\n{comment}{meta.snippet}\n"

        # ------------------------------------------------------------------
        def _set_status(self, text: str, *, error: bool) -> None:
            color = "#c62828" if error else "#2e7d32"
            self.status_label.setStyleSheet(f"color:{color};font-weight:bold;")
            self.status_label.setText(text)

    SafeExpressionPlaygroundDialog.__module__ = __name__

except Exception:  # pragma: no cover

    class SafeExpressionPlaygroundDialog:  # type: ignore[misc]
        """Fallback stub used when PyQt6 is unavailable (e.g., during tests)."""

        def __init__(self, *_, **__):
            raise RuntimeError("Qt widgets unavailable")

        def selected_snippet(self) -> Optional[str]:  # pragma: no cover - stub
            return None
