"""Empty State Component & Registry (Milestone 5.10.9)

Provides a lightweight, token-friendly way to surface consistent empty and error
states across views. Replaces ad-hoc label strings (e.g., 'No history data').

Design Goals:
 - Central registry of templates (id -> title/description/icon)
 - Simple widget (EmptyStateWidget) that renders a template and optional action
 - Non-invasive integration: existing views can swap a plain QLabel for this widget
 - Testable: pure registry logic + visibility toggling in views

Future Extensions:
 - Support multi-action footer
 - Rich illustrations / Lottie placeholder
 - Per-theme icon overrides
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Callable
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import pyqtSignal

try:  # Optional icon usage
    from gui.design.icon_registry import get_icon  # type: ignore
except Exception:  # pragma: no cover - during early bootstrap/tests

    def get_icon(name: str, size: int = 32):  # type: ignore
        return None


__all__ = [
    "EmptyStateTemplate",
    "EmptyStateRegistry",
    "empty_state_registry",
    "get_empty_state_template",
    "EmptyStateWidget",
]


@dataclass
class EmptyStateTemplate:
    """Template definition for a reusable empty/error/info state."""

    key: str
    title: str
    description: str
    icon: Optional[str] = None  # icon registry key
    action_text: Optional[str] = None


class EmptyStateRegistry:
    """Registry holding templates for empty/error states."""

    def __init__(self):
        self._templates: Dict[str, EmptyStateTemplate] = {}
        self._bootstrap_defaults()

    def _bootstrap_defaults(self):
        self.register(
            EmptyStateTemplate(
                key="no_history",
                title="No History Yet",
                description="This player has no recorded performance history.",
                icon="history",
            )
        )
        self.register(
            EmptyStateTemplate(
                key="no_teams",
                title="No Teams Available",
                description="No teams are currently loaded. Run a scrape or ingest data.",
                icon="warning",
            )
        )
        self.register(
            EmptyStateTemplate(
                key="no_division_rows",
                title="No Standings",
                description="Division standings are not available yet.",
                icon="table",
            )
        )
        self.register(
            EmptyStateTemplate(
                key="generic_error",
                title="Something Went Wrong",
                description="An unexpected error occurred while loading this view.",
                icon="error",
                action_text="Retry",
            )
        )
        self.register(
            EmptyStateTemplate(
                key="loading",
                title="Loading...",
                description="Data is being loaded; please wait.",
                icon="spinner",
            )
        )
        self.register(
            EmptyStateTemplate(
                key="no_html_source",
                title="No HTML Loaded",
                description="Select a team or division to view its HTML source.",
                icon="document",
            )
        )

    # CRUD -------------------------------------------------------------
    def register(self, template: EmptyStateTemplate) -> None:
        self._templates[template.key] = template

    def get(self, key: str) -> Optional[EmptyStateTemplate]:
        return self._templates.get(key)

    def all_keys(self):  # pragma: no cover - trivial iteration
        return list(self._templates.keys())


def get_empty_state_template(key: str) -> Optional[EmptyStateTemplate]:
    return empty_state_registry.get(key)


empty_state_registry = EmptyStateRegistry()


class EmptyStateWidget(QWidget):
    """Widget rendering a single EmptyStateTemplate.

    Signals:
        actionRequested: emitted if the optional action button is clicked.
    """

    actionRequested = pyqtSignal(str)

    def __init__(
        self,
        template_key: str,
        parent: Optional[QWidget] = None,
        *_,
        override: Optional[Callable[[EmptyStateTemplate], EmptyStateTemplate]] = None,
    ):
        super().__init__(parent)
        self._template_key = template_key
        self._template = empty_state_registry.get(template_key)
        if self._template is None:
            # Fallback template
            self._template = EmptyStateTemplate(template_key, "Unavailable", "No template found.")
        if override:
            self._template = override(self._template)
        self._build_ui()

    # UI ---------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        # Icon
        if self._template.icon:
            ico = get_icon(self._template.icon, size=32)
            if ico:
                icon_lbl = QLabel()
                icon_lbl.setPixmap(ico.pixmap(32, 32))  # type: ignore
                icon_lbl.setObjectName("emptyStateIcon")
                layout.addWidget(icon_lbl)
        # Title
        self.title_label = QLabel(self._template.title)
        self.title_label.setObjectName("emptyStateTitle")
        layout.addWidget(self.title_label)
        # Description
        self.desc_label = QLabel(self._template.description)
        self.desc_label.setObjectName("emptyStateDesc")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)
        # Action
        self.action_button: QPushButton | None = None
        if self._template.action_text:
            btn = QPushButton(self._template.action_text)
            btn.clicked.connect(lambda: self.actionRequested.emit(self._template_key))  # type: ignore
            btn.setObjectName("emptyStateAction")
            layout.addWidget(btn)
            self.action_button = btn
        layout.addStretch(1)

    # API --------------------------------------------------------------
    def template_key(self) -> str:
        return self._template_key

    def set_template(self, key: str):
        tpl = empty_state_registry.get(key)
        if not tpl:
            return
        self._template_key = key
        self._template = tpl
        self.title_label.setText(tpl.title)
        self.desc_label.setText(tpl.description)
        if self.action_button and not tpl.action_text:
            self.action_button.hide()
        elif not self.action_button and tpl.action_text:
            # Not creating dynamic addition for simplicity; could be extended later.
            pass
