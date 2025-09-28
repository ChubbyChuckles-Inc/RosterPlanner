"""Utility helpers and dialog for importing HTML snippets as fixtures (Milestone 7.10.A19)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

__all__ = [
    "FIXTURE_SUBDIR",
    "FixtureImportError",
    "FixtureSaveResult",
    "prepare_fixture_filename",
    "save_html_fixture",
    "HtmlFixtureImportDialog",
]

FIXTURE_SUBDIR = Path("fixtures") / "html_snippets"


class FixtureImportError(RuntimeError):
    """Raised when a fixture cannot be persisted to disk."""


@dataclass(slots=True)
class FixtureSaveResult:
    """Details about a saved snippet."""

    path: Path
    created: bool


_VALID_NAME_RE = re.compile(r"[^a-z0-9\-]+")


def _normalise_slug(name: str) -> str:
    slug = name.strip().lower()
    slug = slug.replace(" ", "-")
    slug = _VALID_NAME_RE.sub("-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or "snippet"


def prepare_fixture_filename(base_dir: Path, name: str, *, ensure_unique: bool = True) -> Path:
    """Return a safe filename for a snippet under the fixtures directory."""

    base_dir = base_dir.resolve()
    target_dir = base_dir / FIXTURE_SUBDIR
    slug = _normalise_slug(name)
    target_dir.mkdir(parents=True, exist_ok=True)
    candidate = target_dir / f"{slug}.html"
    if not ensure_unique or not candidate.exists():
        return candidate
    suffix = 1
    while True:
        numbered = target_dir / f"{slug}-{suffix}.html"
        if not numbered.exists():
            return numbered
        suffix += 1


def save_html_fixture(
    base_dir: Path,
    snippet: str,
    *,
    filename: Optional[str] = None,
    overwrite: bool = False,
) -> FixtureSaveResult:
    """Persist an HTML snippet to the fixtures folder."""

    if not snippet.strip():
        raise FixtureImportError("Snippet is empty")
    target = (
        prepare_fixture_filename(base_dir, filename or "snippet", ensure_unique=not overwrite)
        if filename
        else prepare_fixture_filename(base_dir, "snippet", ensure_unique=not overwrite)
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    created = not target.exists()
    with target.open("w", encoding="utf-8") as fh:
        fh.write(snippet)
        if not snippet.endswith("\n"):
            fh.write("\n")
    return FixtureSaveResult(path=target, created=created)


try:  # pragma: no cover
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMessageBox,
        QPlainTextEdit,
        QVBoxLayout,
    )
except Exception:  # pragma: no cover
    HtmlFixtureImportDialog = None  # type: ignore
else:

    class HtmlFixtureImportDialog(QDialog):  # pragma: no cover - smoke tested via UI flows
        """Simple dialog wrapper for fixture import workflow."""

        def __init__(self, base_dir: Path, initial_snippet: str = "", parent=None) -> None:
            super().__init__(parent)
            self._base_dir = Path(base_dir)
            self.setWindowTitle("Import HTML Fixture")
            self.resize(740, 520)
            layout = QVBoxLayout(self)

            layout.addWidget(QLabel("Provide a name and HTML snippet to capture as a fixture."))

            name_row = QHBoxLayout()
            name_row.addWidget(QLabel("Fixture name:"))
            self.name_edit = QLineEdit()
            self.name_edit.setPlaceholderText("e.g., team-card-table")
            name_row.addWidget(self.name_edit, 1)
            layout.addLayout(name_row)

            self.snippet_edit = QPlainTextEdit()
            self.snippet_edit.setPlaceholderText("<div class='team-card'>...</div>")
            self.snippet_edit.setPlainText(initial_snippet)
            self.snippet_edit.setTabStopDistance(
                4 * self.snippet_edit.fontMetrics().horizontalAdvance(" ")
            )
            layout.addWidget(self.snippet_edit, 1)

            self.info_label = QLabel(
                "Snippets are stored under fixtures/html_snippets relative to the data root."
            )
            layout.addWidget(self.info_label)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(self._on_accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)

        # ------------------------------------------------------------------
        def _on_accept(self) -> None:
            name = self.name_edit.text().strip() or "snippet"
            snippet = self.snippet_edit.toPlainText()
            try:
                result = save_html_fixture(self._base_dir, snippet, filename=name)
            except FixtureImportError as exc:
                QMessageBox.warning(self, "Import Failed", str(exc))
                return
            except Exception as exc:  # pragma: no cover
                QMessageBox.critical(self, "Unexpected Error", str(exc))
                return
            self._last_result = result
            QMessageBox.information(
                self,
                "Fixture Saved",
                f"Saved to {result.path.relative_to(self._base_dir)}",
                QMessageBox.StandardButton.Ok,
            )
            self.accept()

        # ------------------------------------------------------------------
        def last_result(self) -> FixtureSaveResult | None:
            return getattr(self, "_last_result", None)
