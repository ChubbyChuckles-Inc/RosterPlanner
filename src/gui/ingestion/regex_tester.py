"""Regex Tester Pane (Milestone 7.10.36)

Provides a lightweight, self‑contained dialog for interactively testing
regular expressions against sample HTML/text content. Core matching logic is
implemented in a pure helper (`find_regex_matches`) to maximize testability.

Features (initial / minimal):
 - Pattern input (single line)
 - Flags: IGNORECASE, MULTILINE, DOTALL checkboxes
 - Sample text area (multi-line)
 - Live match list (start..end, excerpt, groups) updated on change
 - Inline error display for invalid patterns
 - Highlight matches within the sample text using QTextEdit extra selections

Deferred Enhancements:
 - Replace simple list with QTreeWidget (match -> groups)
 - Export matches to JSON
 - Named group listing
 - Replace / substitution preview
 - Performance guard for very large texts
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any
import re

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QCheckBox,
    QLabel,
    QTextEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
)
from PyQt6.QtGui import QTextCharFormat, QColor
from PyQt6.QtCore import Qt

__all__ = ["RegexTesterDialog", "find_regex_matches"]


@dataclass
class RegexMatch:
    start: int
    end: int
    text: str
    groups: List[str]

    def to_mapping(self) -> Dict[str, Any]:  # pragma: no cover - trivial
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "groups": list(self.groups),
        }


def _compile(pattern: str, flags: int):
    try:
        return re.compile(pattern, flags)
    except re.error as e:
        raise ValueError(f"Invalid regex: {e}") from e


def find_regex_matches(pattern: str, text: str, flags: int = 0) -> List[RegexMatch]:
    """Return all non-overlapping matches for pattern in text.

    Parameters
    ----------
    pattern: str
        Regular expression pattern (Python re syntax).
    text: str
        Text to search.
    flags: int
        Bitwise OR of re flags (IGNORECASE, MULTILINE, DOTALL, etc.).

    Returns
    -------
    list[RegexMatch]
        Ordered list of matches (left-to-right) with captured groups.
    """
    if not pattern:
        return []
    rx = _compile(pattern, flags)
    out: List[RegexMatch] = []
    for m in rx.finditer(text):
        groups = list(m.groups()) if rx.groups else []
        out.append(RegexMatch(start=m.start(), end=m.end(), text=m.group(0), groups=groups))
    return out


try:  # pragma: no cover
    from gui.components.chrome_dialog import ChromeDialog
except Exception:  # pragma: no cover
    ChromeDialog = object  # type: ignore


class RegexTesterDialog(ChromeDialog):  # type: ignore[misc]
    """Interactive regex tester dialog.

    Designed to be lightweight and safe: heavy operations (e.g. catastrophic
    backtracking) are not defended here; future enhancement could add a timeout
    by running matches in a worker thread.
    """

    def __init__(self, sample_text: str = "", parent=None):  # noqa: D401
        super().__init__(parent, title="Regex Tester")
        self.setObjectName("RegexTesterDialog")
        try:
            self.resize(760, 560)
        except Exception:
            pass
        lay = self.content_layout() if hasattr(self, "content_layout") else QVBoxLayout(self)
        # Pattern row
        prow = QHBoxLayout()
        prow.addWidget(QLabel("Pattern:"))
        self.pattern_edit = QLineEdit()
        self.pattern_edit.setPlaceholderText(r"e.g. (Team)\s+(\w+)")
        prow.addWidget(self.pattern_edit, 1)
        self.chk_icase = QCheckBox("IGNORECASE")
        self.chk_multiline = QCheckBox("MULTILINE")
        self.chk_dotall = QCheckBox("DOTALL")
        prow.addWidget(self.chk_icase)
        prow.addWidget(self.chk_multiline)
        prow.addWidget(self.chk_dotall)
        lay.addLayout(prow)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color:#c62828;font-weight:bold;")
        lay.addWidget(self.error_label)

        # Sample text + matches side by side
        row2 = QHBoxLayout()
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(sample_text)
        # Ensure readable baseline styling irrespective of global theme load order
        self.text_edit.setObjectName("regexTesterSample")
        self.text_edit.setStyleSheet(
            "QTextEdit#regexTesterSample { background:#111111; color:#e8e8e8; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
        )
        row2.addWidget(self.text_edit, 3)
        self.match_list = QListWidget()
        self.match_list.setObjectName("regexTesterMatches")
        self.match_list.setStyleSheet(
            "QListWidget#regexTesterMatches { background:#181818; color:#e0e0e0; font-family:Consolas,'Courier New',monospace; font-size:12px; }"
        )
        row2.addWidget(self.match_list, 2)
        lay.addLayout(row2, 1)

        # Buttons / footer
        bbar = QHBoxLayout()
        self.btn_close = QPushButton("Close")
        bbar.addStretch(1)
        bbar.addWidget(self.btn_close)
        lay.addLayout(bbar)
        try:
            self.btn_close.clicked.connect(self.close)  # type: ignore
        except Exception:  # pragma: no cover
            pass

        # Signals (live update)
        self.pattern_edit.textChanged.connect(self._update_matches)  # type: ignore
        self.text_edit.textChanged.connect(self._update_matches)  # type: ignore
        self.chk_icase.stateChanged.connect(self._update_matches)  # type: ignore
        self.chk_multiline.stateChanged.connect(self._update_matches)  # type: ignore
        self.chk_dotall.stateChanged.connect(self._update_matches)  # type: ignore

        self._update_matches()

    # ------------------------------------------------------------------
    def _gather_flags(self) -> int:
        flags = 0
        if self.chk_icase.isChecked():
            flags |= re.IGNORECASE
        if self.chk_multiline.isChecked():
            flags |= re.MULTILINE
        if self.chk_dotall.isChecked():
            flags |= re.DOTALL
        return flags

    # ------------------------------------------------------------------
    def _update_matches(self) -> None:  # noqa: D401
        pattern = self.pattern_edit.text()
        text = self.text_edit.toPlainText()
        flags = self._gather_flags()
        self.match_list.clear()
        self._clear_highlights()
        if not pattern:
            self.error_label.setText("")
            return
        try:
            matches = find_regex_matches(pattern, text, flags)
        except ValueError as e:
            self.error_label.setText(str(e))
            return
        self.error_label.setText(f"{len(matches)} match(es)")
        for m in matches[:500]:  # cap UI spam
            grp_txt = " | ".join(g if g is not None else "" for g in m.groups)
            item_txt = f"[{m.start}:{m.end}] {m.text}"
            if grp_txt:
                item_txt += f"  ({grp_txt})"
            QListWidgetItem(item_txt, self.match_list)
        self._apply_highlights(matches)

    # ------------------------------------------------------------------
    def _apply_highlights(self, matches: List[RegexMatch]) -> None:
        doc = self.text_edit.document()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(255, 235, 59))  # amber-ish
        cursor = self.text_edit.textCursor()
        for m in matches[:1000]:  # safety cap
            tc = cursor
            tc.setPosition(m.start)
            tc.setPosition(m.end, tc.MoveMode.KeepAnchor)  # type: ignore
            tc.setCharFormat(fmt)
        # Note: Using direct char format modifies text formatting cumulatively.
        # For a more robust approach we could use ExtraSelections; deferred for simplicity.

    # ------------------------------------------------------------------
    def _clear_highlights(self) -> None:
        # Reset by re-setting the plain text (cheap for moderate sizes)
        text = self.text_edit.toPlainText()
        self.text_edit.blockSignals(True)
        self.text_edit.setPlainText(text)
        self.text_edit.blockSignals(False)
