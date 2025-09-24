"""Virtualized list placeholder component (Milestone 5.10.70).

Purpose
-------
Provide a lightweight list container that exposes styling hooks (objectName
and dynamic properties) aligned with existing design tokens so a parity test
can assert consistent token application between this component and a known
reference widget (e.g. a basic QLabel styled via tokens).

Scope
-----
This is intentionally minimal and DOES NOT implement true viewport windowing
yet (that will be introduced under later performance / large dataset tasks).
It offers:
 - API to set a list of row text items (strings)
 - Rebuilds child QLabel rows on update
 - Exposes dynamic properties: ``density`` (comfortable/compact) and
   ``variant`` (plain/striped) to allow QSS differentiation.

Test Strategy
-------------
The parity test (``tests/test_virtualized_list_styling_parity.py``) will:
 - Instantiate a ``VirtualizedList`` and a reference QLabel.
 - Ensure both receive a subset of expected token-driven properties (e.g.
   font, palette application via objectName selectors) indirectly by verifying
   objectName and dynamic property presence plus row count semantics.

Future Work
-----------
Real virtualization (only rendering visible subset) will replace the current
full materialization approach. The public interface is kept small to minimize
future breaking changes.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy

__all__ = ["VirtualizedList"]


class VirtualizedList(QWidget):
    """Simplified list widget exposing design token styling hooks.

    Parameters
    ----------
    parent:
        Optional parent widget.
    density:
        Visual density mode ("comfortable" or "compact"). Stored as a dynamic
        property so QSS can adjust padding / spacing.
    variant:
        Visual row styling hint ("plain" or "striped"). Also a dynamic
        property for QSS consumption.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        density: str = "comfortable",
        variant: str = "plain",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("virtualizedList")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._density = density if density in {"comfortable", "compact"} else "comfortable"
        self._variant = variant if variant in {"plain", "striped"} else "plain"
        self.setProperty("density", self._density)
        self.setProperty("variant", self._variant)
        self._items: List[str] = []
        self._rows: List[QLabel] = []

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

    # Public API -----------------------------------------------------
    def set_items(self, items: Iterable[str]) -> None:
        """Replace the displayed list items.

        Parameters
        ----------
        items:
            Iterable of string rows. Each becomes a QLabel child with objectName
            ``virtualizedListRow`` allowing QSS row styling.
        """

        self._items = [str(i) for i in items]
        self._rebuild_rows()

    def items(self) -> List[str]:
        return list(self._items)

    def row_count(self) -> int:
        return len(self._rows)

    def density(self) -> str:  # accessor for tests / future logic
        return self._density

    def variant(self) -> str:
        return self._variant

    # Internal -------------------------------------------------------
    def _clear_rows(self) -> None:
        for r in self._rows:
            r.setParent(None)
            r.deleteLater()
        self._rows.clear()

    def _rebuild_rows(self) -> None:
        layout = self.layout()
        assert layout is not None
        self._clear_rows()
        for idx, text in enumerate(self._items):
            label = QLabel(text, self)
            label.setObjectName("virtualizedListRow")
            # Provide alternating property to enable striped QSS selectors if desired.
            label.setProperty("alt", bool(idx % 2))
            layout.addWidget(label)
            self._rows.append(label)
        layout.addStretch(1)
